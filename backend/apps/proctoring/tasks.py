import base64
import logging
from celery import shared_task
from django.utils import timezone
from apps.proctoring.models import ProctoringSession, EventSource, EventSeverity
from apps.proctoring.services import (
    ProctoringAIService,
    ProctoringRiskService,
    ProctoringSessionService,
)

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=2, default_retry_delay=5)
def process_proctoring_frame_task(self, session_id: str, raw_bytes_b64: str, sequence_number: int = 0):
    """
    Asynchronous Celery Task for computer vision frame analysis.
    Executes out-of-band and never blocks Monaco editor typing, autosave, or code execution.
    """
    try:
        session = ProctoringSession.objects.filter(id=session_id).first()
        if not session or session.status not in ['ACTIVE', 'DEGRADED']:
            return {"status": "SKIPPED", "reason": "Session not active"}

        raw_bytes = base64.b64decode(raw_bytes_b64)
        signals = ProctoringAIService.analyze_frame_data(session, raw_bytes, sequence_number)

        for sig in signals:
            event_type = sig['event_type']
            if event_type == 'AI_INFERENCE_FAILURE':
                ProctoringSessionService.degrade_session(session, reason="AI Inference Failure")
            else:
                ProctoringRiskService.record_event(
                    session=session,
                    event_type=event_type,
                    source=EventSource.AI,
                    severity=sig.get('severity', EventSeverity.LOW),
                    confidence=sig.get('confidence', 1.0),
                    started_at=timezone.now(),
                    metadata=sig.get('metadata', {}),
                    evidence=sig.get('evidence')
                )

        return {"status": "SUCCESS", "signals_count": len(signals)}

    except Exception as exc:
        logger.error(f"Error processing frame for session {session_id}: {exc}", exc_info=True)
        try:
            session = ProctoringSession.objects.filter(id=session_id).first()
            if session:
                ProctoringSessionService.degrade_session(session, reason=f"Worker Error: {str(exc)}")
        except Exception:
            pass
        return {"status": "ERROR", "error": str(exc)}


@shared_task(bind=True, max_retries=2, default_retry_delay=5)
def process_proctoring_audio_task(self, session_id: str, raw_bytes_b64: str, client_rms_db: float = 0.0):
    """
    Asynchronous Celery Task for acoustic Voice Activity Detection (VAD).
    """
    try:
        session = ProctoringSession.objects.filter(id=session_id).first()
        if not session or session.status not in ['ACTIVE', 'DEGRADED']:
            return {"status": "SKIPPED", "reason": "Session not active"}

        raw_bytes = base64.b64decode(raw_bytes_b64)
        vad_result = ProctoringAIService.analyze_audio_data(session, raw_bytes, client_rms_db)

        if vad_result.get('is_speech'):
            ProctoringRiskService.record_event(
                session=session,
                event_type='AUDIO_ACTIVITY',
                source=EventSource.AI,
                severity=EventSeverity.MEDIUM,
                confidence=vad_result.get('confidence', 0.85),
                started_at=timezone.now(),
                metadata={'client_rms_db': client_rms_db, 'vad_speech': True},
                evidence=vad_result.get('evidence')
            )

        return {"status": "SUCCESS", "speech_detected": vad_result.get('is_speech', False)}

    except Exception as exc:
        logger.error(f"Error processing audio for session {session_id}: {exc}", exc_info=True)
        return {"status": "ERROR", "error": str(exc)}
