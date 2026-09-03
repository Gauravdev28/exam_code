import logging
from datetime import timedelta
from typing import Optional, List, Dict, Any, Tuple
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import PermissionDenied, ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError as DRFValidationError, NotFound

from apps.accounts.models import User, Role
from apps.accounts.services import AuditService
from apps.assessments.models import Assessment, TestAttempt, AttemptStatus
from apps.assessments.services import AttemptTimerService
from apps.proctoring.models import ProctoringSession, RiskBand
from apps.invigilation.models import (
    ProctorAssignment,
    ProctorIntervention,
    InterventionType,
    ProctorDutySession,
    ProctorChatMessage,
)

logger = logging.getLogger(__name__)

DEFAULT_MAX_CUMULATIVE_PAUSE_SECONDS = 900  # 15 minutes


class ProctorRosterService:
    """
    Manages proctor cohort assignments and object-level authorization links.
    """
    @classmethod
    def assign_proctor(
        cls,
        assessment_id: str,
        proctor_user: User,
        assigned_by_user: Optional[User] = None,
        max_candidates: int = 30,
        notes: str = ''
    ) -> ProctorAssignment:
        assessment = Assessment.objects.filter(id=assessment_id).first()
        if not assessment:
            raise NotFound("Assessment not found.")

        if proctor_user.role not in ['PROCTOR', Role.ADMIN] and not proctor_user.is_staff:
            raise DRFValidationError({"proctor": "User must have PROCTOR or ADMIN role to be assigned."})

        assignment, created = ProctorAssignment.objects.update_or_create(
            assessment=assessment,
            proctor=proctor_user,
            defaults={
                'is_active': True,
                'assigned_by': assigned_by_user,
                'max_candidates': max_candidates,
                'notes': notes
            }
        )
        return assignment

    @classmethod
    def unassign_proctor(cls, assessment_id: str, proctor_user: User) -> bool:
        assignment = ProctorAssignment.objects.filter(assessment_id=assessment_id, proctor=proctor_user).first()
        if assignment:
            assignment.is_active = False
            assignment.save(update_fields=['is_active', 'updated_at'])
            return True
        return False

    @classmethod
    def is_proctor_assigned(cls, proctor_user: User, assessment_id: str) -> bool:
        if proctor_user.role == Role.ADMIN or proctor_user.is_staff or proctor_user.is_superuser:
            return True
        return ProctorAssignment.objects.filter(
            assessment_id=assessment_id,
            proctor=proctor_user,
            is_active=True
        ).exists()


class LiveInterventionService:
    """
    Transactional execution engine for live human interventions.
    Strictly adheres to global lock hierarchy:
    Assessment -> User -> TestAttempt -> ProctorIntervention
    """

    @classmethod
    def _dispatch_websocket_event(cls, group_name: str, event_data: dict):
        """
        Dispatches async WebSocket broadcast via Django Channels.
        Gracefully handles Redis absence / connection degradation.
        """
        try:
            from asgiref.sync import async_to_sync
            from channels.layers import get_channel_layer
            channel_layer = get_channel_layer()
            if channel_layer:
                async_to_sync(channel_layer.group_send)(
                    group_name,
                    {
                        "type": "proctor_event",
                        "data": event_data
                    }
                )
        except Exception as exc:
            logger.warning(f"WebSocket notification broadcast degraded: {exc}")

    @classmethod
    @transaction.atomic
    def issue_warning(
        cls,
        proctor: User,
        attempt_id: str,
        reason_code: str,
        message: str,
        internal_notes: str = '',
        idempotency_key: str = ''
    ) -> ProctorIntervention:
        if idempotency_key:
            existing = ProctorIntervention.objects.filter(
                request_idempotency_key=idempotency_key
            ).first()
            if existing:
                return existing

        attempt = TestAttempt.objects.select_for_update().filter(id=attempt_id).select_related('student', 'assessment').first()
        if not attempt:
            raise NotFound("Test attempt not found.")

        if attempt.status != AttemptStatus.IN_PROGRESS:
            raise DRFValidationError({"status": f"Cannot issue warning to attempt in status {attempt.status}."})

        intervention = ProctorIntervention.objects.create(
            attempt=attempt,
            proctor=proctor,
            student=attempt.student,
            event_type=InterventionType.WARNING_ISSUED,
            reason_code=reason_code,
            reason_text=message,
            internal_notes=internal_notes,
            request_idempotency_key=idempotency_key,
            metadata={"source": "PROCTOR_CONSOLE"}
        )

        AuditService.log(
            action="PROCTOR_WARNING_ISSUED",
            actor=proctor,
            target_type="TestAttempt",
            target_id=str(attempt.id),
            metadata={
                "intervention_id": str(intervention.id),
                "reason_code": reason_code,
                "warning_message": message
            }
        )

        # Notify student and proctors
        payload = {
            "event": "WARNING_ISSUED",
            "intervention_id": str(intervention.id),
            "attempt_id": str(attempt.id),
            "reason_code": reason_code,
            "message": message,
            "issued_at": intervention.issued_at.isoformat()
        }
        cls._dispatch_websocket_event(f"attempt_{attempt.id}", payload)
        cls._dispatch_websocket_event(f"proctor_assessment_{attempt.assessment_id}", payload)

        return intervention

    @classmethod
    @transaction.atomic
    def acknowledge_warning(
        cls,
        student: User,
        attempt_id: str,
        intervention_id: str
    ) -> ProctorIntervention:
        attempt = TestAttempt.objects.select_for_update().filter(id=attempt_id).select_related('student', 'assessment').first()
        if not attempt:
            raise NotFound("Test attempt not found.")

        if attempt.student != student:
            raise PermissionDenied("You can only acknowledge warnings issued to your own attempt.")

        warning_event = ProctorIntervention.objects.filter(
            id=intervention_id,
            attempt=attempt,
            event_type=InterventionType.WARNING_ISSUED
        ).first()
        if not warning_event:
            raise NotFound("Warning intervention not found.")

        # Idempotent return if already acknowledged
        existing_ack = ProctorIntervention.objects.filter(
            parent_event=warning_event,
            event_type=InterventionType.WARNING_ACKNOWLEDGED
        ).first()
        if existing_ack:
            return existing_ack

        ack_event = ProctorIntervention.objects.create(
            attempt=attempt,
            proctor=None,
            student=student,
            event_type=InterventionType.WARNING_ACKNOWLEDGED,
            parent_event=warning_event,
            reason_code=warning_event.reason_code,
            reason_text="Acknowledged by candidate.",
            metadata={"acknowledged_at": timezone.now().isoformat()}
        )

        AuditService.log(
            action="PROCTOR_WARNING_ACKNOWLEDGED",
            actor=student,
            target_type="TestAttempt",
            target_id=str(attempt.id),
            metadata={"warning_id": str(warning_event.id)}
        )

        payload = {
            "event": "WARNING_ACKNOWLEDGED",
            "warning_id": str(warning_event.id),
            "acknowledged_at": ack_event.issued_at.isoformat(),
            "attempt_id": str(attempt.id)
        }
        cls._dispatch_websocket_event(f"proctor_assessment_{attempt.assessment_id}", payload)

        return ack_event

    @classmethod
    def get_active_pause(cls, attempt: TestAttempt) -> Optional[ProctorIntervention]:
        """
        Returns active PAUSE_STARTED intervention if attempt is currently paused.
        """
        paused_starts = ProctorIntervention.objects.filter(
            attempt=attempt,
            event_type=InterventionType.PAUSE_STARTED
        ).order_by('-issued_at')

        for ps in paused_starts:
            # Check if this start has a corresponding PAUSE_ENDED
            has_ended = ProctorIntervention.objects.filter(
                parent_event=ps,
                event_type=InterventionType.PAUSE_ENDED
            ).exists()
            if not has_ended:
                return ps
        return None

    @classmethod
    def get_cumulative_pause_seconds(cls, attempt: TestAttempt) -> int:
        """
        Sums duration of all completed pauses for the attempt.
        """
        completed_ends = ProctorIntervention.objects.filter(
            attempt=attempt,
            event_type=InterventionType.PAUSE_ENDED
        )
        total_seconds = 0
        for pe in completed_ends:
            dur = pe.metadata.get('pause_duration_seconds')
            if dur is not None:
                total_seconds += int(dur)
            elif pe.parent_event:
                total_seconds += int((pe.issued_at - pe.parent_event.issued_at).total_seconds())
        return total_seconds

    @classmethod
    @transaction.atomic
    def pause_attempt(
        cls,
        proctor: User,
        attempt_id: str,
        reason: str = '',
        internal_notes: str = '',
        idempotency_key: str = '',
        max_pause_seconds: int = DEFAULT_MAX_CUMULATIVE_PAUSE_SECONDS
    ) -> ProctorIntervention:
        if idempotency_key:
            existing = ProctorIntervention.objects.filter(
                request_idempotency_key=idempotency_key
            ).first()
            if existing:
                return existing

        attempt = TestAttempt.objects.select_for_update().filter(id=attempt_id).select_related('student', 'assessment').first()
        if not attempt:
            raise NotFound("Test attempt not found.")

        if attempt.status != AttemptStatus.IN_PROGRESS:
            raise DRFValidationError({"status": f"Cannot pause attempt in status {attempt.status}."})

        now = timezone.now()
        assessment = attempt.assessment

        # Assessment end boundary check: cannot pause if assessment schedule has ended
        if assessment.end_datetime and now >= assessment.end_datetime:
            raise DRFValidationError({"schedule": "Cannot pause attempt: assessment end datetime has passed."})

        # Single active pause check:
        active_pause = cls.get_active_pause(attempt)
        if active_pause:
            # Idempotent return if already paused
            return active_pause

        # Cumulative pause cap check
        used_pause_sec = cls.get_cumulative_pause_seconds(attempt)
        if used_pause_sec >= max_pause_seconds:
            raise DRFValidationError({
                "pause_limit": f"Cumulative pause limit of {max_pause_seconds // 60} minutes has been exhausted."
            })

        intervention = ProctorIntervention.objects.create(
            attempt=attempt,
            proctor=proctor,
            student=attempt.student,
            event_type=InterventionType.PAUSE_STARTED,
            reason_code="PROCTOR_PAUSE",
            reason_text=reason or "Assessment attempt temporarily paused by proctor.",
            internal_notes=internal_notes,
            request_idempotency_key=idempotency_key,
            metadata={
                "cumulative_used_seconds_before": used_pause_sec,
                "max_allowed_seconds": max_pause_seconds
            }
        )

        AuditService.log(
            action="PROCTOR_ATTEMPT_PAUSED",
            actor=proctor,
            target_type="TestAttempt",
            target_id=str(attempt.id),
            metadata={"reason": reason}
        )

        payload = {
            "event": "PAUSE_STARTED",
            "intervention_id": str(intervention.id),
            "attempt_id": str(attempt.id),
            "reason": reason,
            "paused_at": intervention.issued_at.isoformat()
        }
        cls._dispatch_websocket_event(f"attempt_{attempt.id}", payload)
        cls._dispatch_websocket_event(f"proctor_assessment_{attempt.assessment_id}", payload)

        return intervention

    @classmethod
    @transaction.atomic
    def resume_attempt(
        cls,
        proctor: User,
        attempt_id: str,
        reason: str = '',
        internal_notes: str = '',
        idempotency_key: str = ''
    ) -> Optional[ProctorIntervention]:
        if idempotency_key:
            existing = ProctorIntervention.objects.filter(
                request_idempotency_key=idempotency_key
            ).first()
            if existing:
                return existing

        attempt = TestAttempt.objects.select_for_update().filter(id=attempt_id).select_related('student', 'assessment').first()
        if not attempt:
            raise NotFound("Test attempt not found.")

        if attempt.status != AttemptStatus.IN_PROGRESS:
            raise DRFValidationError({"status": f"Cannot resume attempt in status {attempt.status}."})

        active_pause = cls.get_active_pause(attempt)
        if not active_pause:
            # Idempotent: attempt is not paused
            return None

        now = timezone.now()
        pause_duration_seconds = max(1, int((now - active_pause.issued_at).total_seconds()))

        # Extend expires_at by pause duration, strictly capped at assessment.end_datetime
        if attempt.expires_at:
            extended_expiry = attempt.expires_at + timedelta(seconds=pause_duration_seconds)
            if attempt.assessment.end_datetime and extended_expiry > attempt.assessment.end_datetime:
                extended_expiry = attempt.assessment.end_datetime
            attempt.expires_at = extended_expiry
            attempt.save(update_fields=['expires_at', 'updated_at'])

        resume_event = ProctorIntervention.objects.create(
            attempt=attempt,
            proctor=proctor,
            student=attempt.student,
            event_type=InterventionType.PAUSE_ENDED,
            parent_event=active_pause,
            reason_code="PROCTOR_RESUME",
            reason_text=reason or "Assessment attempt resumed by proctor.",
            internal_notes=internal_notes,
            request_idempotency_key=idempotency_key,
            metadata={
                "pause_duration_seconds": pause_duration_seconds,
                "resumed_at": now.isoformat(),
                "new_expires_at": attempt.expires_at.isoformat() if attempt.expires_at else None
            }
        )

        AuditService.log(
            action="PROCTOR_ATTEMPT_RESUMED",
            actor=proctor,
            target_type="TestAttempt",
            target_id=str(attempt.id),
            metadata={
                "pause_duration_seconds": pause_duration_seconds,
                "new_expires_at": attempt.expires_at.isoformat() if attempt.expires_at else None
            }
        )

        remaining_seconds = AttemptTimerService.get_remaining_seconds(attempt)
        payload = {
            "event": "PAUSE_ENDED",
            "intervention_id": str(resume_event.id),
            "attempt_id": str(attempt.id),
            "pause_duration_seconds": pause_duration_seconds,
            "remaining_seconds": remaining_seconds,
            "resumed_at": resume_event.issued_at.isoformat()
        }
        cls._dispatch_websocket_event(f"attempt_{attempt.id}", payload)
        cls._dispatch_websocket_event(f"proctor_assessment_{attempt.assessment_id}", payload)

        return resume_event

    @classmethod
    @transaction.atomic
    def request_room_scan(
        cls,
        proctor: User,
        attempt_id: str,
        reason: str = '',
        internal_notes: str = ''
    ) -> ProctorIntervention:
        attempt = TestAttempt.objects.select_for_update().filter(id=attempt_id).select_related('student', 'assessment').first()
        if not attempt:
            raise NotFound("Test attempt not found.")

        if attempt.status != AttemptStatus.IN_PROGRESS:
            raise DRFValidationError({"status": f"Cannot request room scan for attempt in status {attempt.status}."})

        intervention = ProctorIntervention.objects.create(
            attempt=attempt,
            proctor=proctor,
            student=attempt.student,
            event_type=InterventionType.ROOM_SCAN_REQUESTED,
            reason_code="ROOM_SCAN",
            reason_text=reason or "Please perform a 360-degree room scan using your webcam.",
            internal_notes=internal_notes
        )

        payload = {
            "event": "ROOM_SCAN_REQUESTED",
            "intervention_id": str(intervention.id),
            "attempt_id": str(attempt.id),
            "instructions": intervention.reason_text
        }
        cls._dispatch_websocket_event(f"attempt_{attempt.id}", payload)
        cls._dispatch_websocket_event(f"proctor_assessment_{attempt.assessment_id}", payload)

        return intervention

    @classmethod
    @transaction.atomic
    def complete_room_scan(
        cls,
        student: User,
        attempt_id: str,
        scan_event_id: str
    ) -> ProctorIntervention:
        attempt = TestAttempt.objects.select_for_update().filter(id=attempt_id).select_related('student', 'assessment').first()
        if not attempt:
            raise NotFound("Test attempt not found.")

        if attempt.student != student:
            raise PermissionDenied("You can only complete room scans for your own attempt.")

        scan_event = ProctorIntervention.objects.filter(
            id=scan_event_id,
            attempt=attempt,
            event_type=InterventionType.ROOM_SCAN_REQUESTED
        ).first()
        if not scan_event:
            raise NotFound("Room scan request event not found.")

        completed_event = ProctorIntervention.objects.create(
            attempt=attempt,
            proctor=None,
            student=student,
            event_type=InterventionType.ROOM_SCAN_COMPLETED,
            parent_event=scan_event,
            reason_code="ROOM_SCAN_COMPLETED",
            reason_text="Candidate completed room scan."
        )

        payload = {
            "event": "ROOM_SCAN_COMPLETED",
            "scan_request_id": str(scan_event.id),
            "attempt_id": str(attempt.id)
        }
        cls._dispatch_websocket_event(f"proctor_assessment_{attempt.assessment_id}", payload)

        return completed_event

    @classmethod
    @transaction.atomic
    def terminate_attempt(
        cls,
        proctor: User,
        attempt_id: str,
        reason_code: str,
        formal_justification: str,
        internal_notes: str = '',
        idempotency_key: str = ''
    ) -> Tuple[TestAttempt, ProctorIntervention]:
        if idempotency_key:
            existing = ProctorIntervention.objects.filter(
                request_idempotency_key=idempotency_key
            ).first()
            if existing:
                return existing.attempt, existing

        attempt = TestAttempt.objects.select_for_update().filter(id=attempt_id).select_related('student', 'assessment').first()
        if not attempt:
            raise NotFound("Test attempt not found.")

        # Idempotency check: if already cancelled, return cleanly
        if attempt.status == AttemptStatus.CANCELLED:
            existing_term = ProctorIntervention.objects.filter(
                attempt=attempt,
                event_type=InterventionType.TERMINATION_REQUESTED
            ).first()
            if existing_term:
                return attempt, existing_term

        # Check terminal state conflict
        if attempt.status in [AttemptStatus.SUBMITTED, AttemptStatus.EXPIRED]:
            raise DRFValidationError({
                "status": f"Cannot terminate attempt: already in terminal state {attempt.status}."
            })

        # Record immutable intervention
        intervention = ProctorIntervention.objects.create(
            attempt=attempt,
            proctor=proctor,
            student=attempt.student,
            event_type=InterventionType.TERMINATION_REQUESTED,
            reason_code=reason_code,
            reason_text=formal_justification,
            internal_notes=internal_notes,
            request_idempotency_key=idempotency_key,
            metadata={
                "formal_justification": formal_justification,
                "terminated_at": timezone.now().isoformat()
            }
        )

        # Transition TestAttempt to CANCELLED (Phase 5 terminal authority)
        now = timezone.now()
        attempt.status = AttemptStatus.CANCELLED
        attempt.submitted_at = now
        attempt.save(update_fields=['status', 'submitted_at', 'updated_at'])

        AuditService.log(
            action="ATTEMPT_TERMINATED_BY_PROCTOR",
            actor=proctor,
            target_type="TestAttempt",
            target_id=str(attempt.id),
            metadata={
                "reason_code": reason_code,
                "justification": formal_justification,
                "intervention_id": str(intervention.id)
            }
        )

        # Trigger Phase 8 finalization on transaction commit
        try:
            from apps.results.tasks import finalize_assessment_result_task
            transaction.on_commit(lambda: finalize_assessment_result_task.delay(str(attempt.id)))
        except Exception:
            pass

        # WebSocket broadcast
        payload = {
            "event": "TERMINATION_REQUESTED",
            "intervention_id": str(intervention.id),
            "attempt_id": str(attempt.id),
            "reason_code": reason_code,
            "justification": formal_justification,
            "status": AttemptStatus.CANCELLED,
            "terminated_at": now.isoformat()
        }
        cls._dispatch_websocket_event(f"attempt_{attempt.id}", payload)
        cls._dispatch_websocket_event(f"proctor_assessment_{attempt.assessment_id}", payload)

        return attempt, intervention


class ProctorTriageQueueService:
    """
    Constructs the real-time prioritized triage queue for an assessment console.
    Sorts attempts deterministically by Phase 7 AI Risk Band:
    CRITICAL > HIGH > MEDIUM > LOW > NORMAL
    """
    BAND_PRIORITY = {
        RiskBand.CRITICAL: 1,
        RiskBand.HIGH: 2,
        RiskBand.MEDIUM: 3,
        RiskBand.LOW: 4,
        RiskBand.NORMAL: 5,
    }

    @classmethod
    def get_triage_roster(cls, assessment_id: str, proctor_user: Optional[User] = None) -> List[Dict[str, Any]]:
        assessment = Assessment.objects.filter(id=assessment_id).first()
        if not assessment:
            raise NotFound("Assessment not found.")

        # Fetch all IN_PROGRESS attempts for this assessment
        attempts = TestAttempt.objects.filter(
            assessment=assessment,
            status=AttemptStatus.IN_PROGRESS
        ).select_related('student', 'student__student_profile')

        # Map proctoring sessions
        sessions = ProctoringSession.objects.filter(
            attempt__in=attempts
        ).select_related('attempt')
        session_map = {s.attempt_id: s for s in sessions}

        now = timezone.now()
        roster_items = []

        for att in attempts:
            sess = session_map.get(att.id)
            risk_band = sess.risk_band if sess else RiskBand.NORMAL
            risk_score = float(sess.risk_score) if sess else 0.0
            events_count = sess.total_events_count if sess else 0

            active_pause = LiveInterventionService.get_active_pause(att)
            is_paused = active_pause is not None
            remaining_seconds = AttemptTimerService.get_remaining_seconds(att)

            student = att.student
            profile = getattr(student, 'student_profile', None)

            roster_items.append({
                "attempt_id": str(att.id),
                "student_id": str(student.id),
                "student_name": getattr(profile, 'full_name', '') if profile and getattr(profile, 'full_name', None) else student.email,
                "student_email": student.email,
                "roll_number": profile.roll_number if profile else '',
                "euid": profile.euid if profile else '',
                "status": att.status,
                "is_paused": is_paused,
                "paused_at": active_pause.issued_at.isoformat() if active_pause else None,
                "risk_band": risk_band,
                "risk_score": risk_score,
                "events_count": events_count,
                "remaining_seconds": remaining_seconds,
                "started_at": att.started_at.isoformat() if att.started_at else None,
                "expires_at": att.expires_at.isoformat() if att.expires_at else None,
                "priority_rank": cls.BAND_PRIORITY.get(risk_band, 99)
            })

        # Order by priority_rank ASC (CRITICAL first), then risk_score DESC
        roster_items.sort(key=lambda x: (x['priority_rank'], -x['risk_score']))
        return roster_items


class ProctorChatService:
    """
    Bilateral chat service between candidate and authorized proctor.
    """
    @classmethod
    @transaction.atomic
    def send_message(
        cls,
        sender: User,
        attempt_id: str,
        message_text: str,
        recipient: Optional[User] = None
    ) -> ProctorChatMessage:
        attempt = TestAttempt.objects.filter(id=attempt_id).select_related('student', 'assessment').first()
        if not attempt:
            raise NotFound("Test attempt not found.")

        if not message_text or not message_text.strip():
            raise DRFValidationError({"message_text": "Message content cannot be empty."})

        # Determine recipient
        if sender == attempt.student:
            # Student sending to proctor
            if recipient and recipient.role not in ['PROCTOR', Role.ADMIN]:
                raise DRFValidationError({"recipient": "Recipient must be a proctor or admin."})
            if not recipient:
                # Target active proctor assignment or first active proctor
                assignment = ProctorAssignment.objects.filter(
                    assessment=attempt.assessment,
                    is_active=True
                ).first()
                if assignment:
                    recipient = assignment.proctor
                else:
                    recipient = attempt.assessment.created_by
        else:
            # Proctor sending to student
            if not ProctorRosterService.is_proctor_assigned(sender, str(attempt.assessment_id)):
                raise PermissionDenied("Only assigned proctors or administrators can participate in invigilation chat.")
            recipient = attempt.student

        msg = ProctorChatMessage.objects.create(
            attempt=attempt,
            sender=sender,
            recipient=recipient,
            message_text=message_text.strip(),
            is_read=False
        )

        # Broadcast via WebSocket
        chat_payload = {
            "event": "CHAT_MESSAGE",
            "message_id": str(msg.id),
            "attempt_id": str(attempt.id),
            "sender_id": str(sender.id),
            "sender_name": sender.email,
            "sender_role": getattr(sender, 'role', 'USER'),
            "recipient_id": str(recipient.id),
            "message_text": msg.message_text,
            "sent_at": msg.sent_at.isoformat()
        }
        LiveInterventionService._dispatch_websocket_event(f"attempt_{attempt.id}", chat_payload)
        LiveInterventionService._dispatch_websocket_event(f"proctor_assessment_{attempt.assessment_id}", chat_payload)

        return msg

    @classmethod
    def get_chat_history(cls, attempt_id: str, user: User) -> List[ProctorChatMessage]:
        attempt = TestAttempt.objects.filter(id=attempt_id).first()
        if not attempt:
            raise NotFound("Test attempt not found.")

        # Authorization: Must be student or assigned proctor/admin
        is_student = (attempt.student_id == user.id)
        is_proctor = ProctorRosterService.is_proctor_assigned(user, attempt.assessment_id)
        if not is_student and not is_proctor:
            raise PermissionDenied("You are not authorized to access this attempt's chat history.")

        messages = ProctorChatMessage.objects.filter(attempt=attempt).select_related('sender', 'recipient').order_by('sent_at')

        # Mark messages received by this user as read
        unread_ids = [m.id for m in messages if m.recipient_id == user.id and not m.is_read]
        if unread_ids:
            ProctorChatMessage.objects.filter(id__in=unread_ids).update(is_read=True)

        return list(messages)
