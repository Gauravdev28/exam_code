from decimal import Decimal
from django.db import transaction, models
from django.utils import timezone
from django.conf import settings

from apps.accounts.models import User
from apps.assessments.models import Assessment, TestAttempt, AttemptStatus
from apps.results.models import ResultStatus, HistoricalResultSummary
from apps.evaluator.models import CodeSubmission
from apps.proctoring.models import ProctoringEvent, ProctoringEvidence, ProctoringSession
from apps.retention.models import (
    RetentionRecord,
    PurgeState,
    ScrubStatus,
    FileCleanupStatus,
    FileCleanupQueue,
    ExportJob,
    ExportStatus,
)
from .legal_holds import LegalHoldManager


class AuthoritativeScrubbingService:
    @classmethod
    def is_eligible_for_purge(cls, attempt, now=None):
        """
        Pure verification check: tests if an attempt is currently eligible for retention purge.
        """
        now = now or timezone.now()

        # Must be in terminal attempt status
        if attempt.status not in [AttemptStatus.SUBMITTED, AttemptStatus.EXPIRED, AttemptStatus.CANCELLED]:
            return False

        # Must have finalized result
        if not hasattr(attempt, 'result') or attempt.result.status != ResultStatus.FINALIZED:
            return False

        # Must have retention record and deadline elapsed
        retention_record = getattr(attempt, 'retention_record', None)
        if not retention_record:
            return False

        if retention_record.detailed_data_expires_at > now:
            return False

        if retention_record.purge_state in [PurgeState.SCRUBBING_DB, PurgeState.CLEANING_FILES, PurgeState.PURGED]:
            return False

        # Zero active legal holds
        if LegalHoldManager.has_active_hold_for_attempt(attempt):
            return False

        # Zero protected DSAR exports
        active_dsars = ExportJob.objects.filter(
            attempt=attempt,
            status__in=[ExportStatus.SNAPSHOT_PENDING, ExportStatus.SNAPSHOT_ACQUIRED, ExportStatus.GENERATING]
        )
        for dsar in active_dsars:
            if dsar.status in [ExportStatus.SNAPSHOT_ACQUIRED, ExportStatus.GENERATING]:
                return False
            if dsar.status == ExportStatus.SNAPSHOT_PENDING:
                # Protected only if lease is still active
                if dsar.lease_expires_at and dsar.lease_expires_at > now:
                    return False

        return True

    @classmethod
    def execute_purge_for_attempt(cls, attempt_id, operator_user=None, process_filesystem_sync=False, trigger_async_worker=True):
        """
        Executes the authoritative database scrub for an attempt under the strict global lock hierarchy:
        Assessment -> User/Student -> TestAttempt -> RetentionRecord
        """
        with transaction.atomic():
            # 1. First fetch attempt ID and parent keys without lock to know parent pks
            raw_attempt = TestAttempt.objects.filter(id=attempt_id).values('id', 'assessment_id', 'student_id').first()
            if not raw_attempt:
                return {'status': 'NOT_FOUND', 'purged': False}

            # 2. Acquire parent scope owner locks in global order:
            Assessment.objects.select_for_update().get(id=raw_attempt['assessment_id'])
            User.objects.select_for_update().get(id=raw_attempt['student_id'])

            # 3. Acquire attempt and retention record locks (AUTHORITATIVE SERIALIZATION BOUNDARY):
            attempt = TestAttempt.objects.select_for_update(skip_locked=True).filter(id=attempt_id).first()
            if not attempt:
                return {'status': 'LOCKED', 'purged': False}

            retention_record = RetentionRecord.objects.select_for_update().filter(attempt=attempt).first()
            if not retention_record:
                return {'status': 'NO_RETENTION_RECORD', 'purged': False}

            now = timezone.now()

            # Pre-condition checks:
            if attempt.status not in [AttemptStatus.SUBMITTED, AttemptStatus.EXPIRED, AttemptStatus.CANCELLED]:
                return {'status': 'INELIGIBLE_STATUS', 'purged': False}

            if not hasattr(attempt, 'result') or attempt.result.status != ResultStatus.FINALIZED:
                return {'status': 'UNFINALIZED', 'purged': False}

            if retention_record.detailed_data_expires_at > now:
                return {'status': 'TTL_NOT_ELAPSED', 'purged': False}

            if retention_record.purge_state == PurgeState.PURGED:
                return {'status': 'ALREADY_PURGED', 'purged': False}

            # Check active legal holds
            if LegalHoldManager.has_active_hold_for_attempt(attempt):
                retention_record.purge_state = PurgeState.DEFERRED_HOLD
                retention_record.save(update_fields=['purge_state', 'updated_at'])
                return {'status': 'DEFERRED_HOLD', 'purged': False}

            # Check protected DSAR exports
            active_dsars = ExportJob.objects.filter(
                attempt=attempt,
                status__in=[ExportStatus.SNAPSHOT_PENDING, ExportStatus.SNAPSHOT_ACQUIRED, ExportStatus.GENERATING]
            )
            has_protected_dsar = False
            for dsar in active_dsars:
                if dsar.status in [ExportStatus.SNAPSHOT_ACQUIRED, ExportStatus.GENERATING]:
                    has_protected_dsar = True
                    break
                if dsar.status == ExportStatus.SNAPSHOT_PENDING and dsar.lease_expires_at and dsar.lease_expires_at > now:
                    has_protected_dsar = True
                    break

            if has_protected_dsar:
                retention_record.purge_state = PurgeState.DEFERRED_EXPORT
                retention_record.save(update_fields=['purge_state', 'updated_at'])
                return {'status': 'DEFERRED_EXPORT', 'purged': False}

            # 4. Authoritative Database Scrub
            retention_record.purge_state = PurgeState.SCRUBBING_DB
            retention_record.save(update_fields=['purge_state', 'updated_at'])

            answers_deleted = attempt.answers.all().delete()[0]
            submissions_deleted = CodeSubmission.objects.filter(attempt=attempt).delete()[0]
            events_deleted = ProctoringEvent.objects.filter(session__attempt=attempt).delete()[0]

            # Phase 10: Purge invigilation interventions and candidate chat messages (RET-01)
            from apps.invigilation.services import InvigilationRetentionService
            invig_counts = InvigilationRetentionService.purge_invigilation_records_for_attempt(attempt)
            interventions_deleted = invig_counts.get('interventions_purged', 0)
            chat_deleted = invig_counts.get('chat_purged', 0)

            # Collect evidence files to queue into FileCleanupQueue
            evidence_qs = ProctoringEvidence.objects.filter(session__attempt=attempt)
            evidence_count = 0
            for ev in evidence_qs:
                FileCleanupQueue.objects.create(
                    attempt_id=attempt.id,
                    file_path=ev.storage_path,
                    file_bytes=ev.file_size_bytes or 0,
                    status=FileCleanupStatus.PENDING
                )
                evidence_count += 1
            evidence_qs.delete()

            # Update permanent historical ledger
            HistoricalResultSummary.objects.filter(
                student=attempt.student,
                assessment_id=attempt.assessment_id
            ).update(details_purged=True)

            retention_record.purge_state = PurgeState.CLEANING_FILES
            retention_record.database_scrub_status = ScrubStatus.COMPLETED
            retention_record.last_scrubbed_at = now
            retention_record.save(update_fields=['purge_state', 'database_scrub_status', 'last_scrubbed_at', 'updated_at'])

        # Outside DB transaction: trigger filesystem cleanup
        if process_filesystem_sync:
            from .filesystem import FilesystemCleanupWorker
            FilesystemCleanupWorker.process_attempt_cleanups(attempt_id, operator_user=operator_user)
        elif trigger_async_worker:
            try:
                from apps.retention.tasks import process_file_cleanup_queue
                process_file_cleanup_queue.delay(str(attempt_id))
            except Exception:
                # In environments without Celery broker, fallback gracefully
                pass

        return {
            'status': 'SUCCESS',
            'purged': True,
            'answers_deleted': answers_deleted,
            'submissions_deleted': submissions_deleted,
            'events_deleted': events_deleted,
            'evidence_queued': evidence_count,
            'interventions_deleted': interventions_deleted,
            'chat_deleted': chat_deleted,
        }

    @classmethod
    def sweep_proctoring_operational_window(cls, cutoff_date=None):
        """
        Nullifies proctoring risk telemetry after 90 days pursuant to the approved non-scoring lifecycle.
        """
        cutoff = cutoff_date or (timezone.now() - timezone.timedelta(days=90))
        sessions = ProctoringSession.objects.filter(
            attempt__submitted_at__lte=cutoff
        )
        updated_count = 0
        for s in sessions:
            s.risk_score = Decimal('0.00')
            s.save(update_fields=['risk_score', 'updated_at'])
            updated_count += 1
        return updated_count
