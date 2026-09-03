import hmac
import hashlib
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError

from apps.assessments.models import TestAttempt
from apps.retention.models import (
    RetentionTombstone,
    RetentionRecord,
    PurgeState,
    FileCleanupQueue,
    FileCleanupStatus,
)


class TombstoneService:
    @classmethod
    def mint_tombstone(cls, attempt_id, operator_user=None):
        """
        Mints an immutable, cryptographically sealed RetentionTombstone.
        Requires 100% of physical files to be confirmed unlinked.
        """
        # Idempotent check
        existing = RetentionTombstone.objects.filter(attempt_id=attempt_id).first()
        if existing:
            return existing

        with transaction.atomic():
            attempt = TestAttempt.objects.select_related('student', 'assessment').get(id=attempt_id)
            retention_record = RetentionRecord.objects.select_for_update().get(attempt=attempt)

            # 1. Authoritative DB scrub must be committed before tombstone can be minted
            from apps.retention.models import ScrubStatus
            if retention_record.database_scrub_status != ScrubStatus.COMPLETED:
                raise ValidationError("Cannot mint tombstone before database scrub has committed.")

            # 2. Verify 100% of filesystem cleanups are confirmed. If ANY file is not CONFIRMED, abort!
            unconfirmed_files = FileCleanupQueue.objects.filter(attempt_id=attempt_id).exclude(
                status=FileCleanupStatus.CONFIRMED
            )
            if unconfirmed_files.exists():
                raise ValidationError("Cannot mint tombstone while filesystem cleanups are unconfirmed or failed (100% physical cleanup required).")

            queue_items = FileCleanupQueue.objects.filter(attempt_id=attempt_id)
            confirmed_bytes = sum(q.file_bytes for q in queue_items)
            files_deleted_count = queue_items.count()

            purged_at = timezone.now()

            # Keyed HMAC-SHA256 integrity proof
            proof_payload = f"{attempt.id}:{attempt.student_id}:{attempt.assessment_id}:{purged_at.isoformat()}:{confirmed_bytes}"
            sha256_audit_proof = hmac.new(
                settings.SECRET_KEY.encode('utf-8'),
                proof_payload.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()

            profile = getattr(attempt.student, 'student_profile', None)
            student_euid = getattr(profile, 'euid', None) or getattr(attempt.student, 'euid', None) or str(attempt.student_id)

            tombstone = RetentionTombstone.objects.create(
                attempt_id=attempt.id,
                student_id=attempt.student_id,
                student_euid=student_euid,
                assessment_id=attempt.assessment_id,
                assessment_title_snapshot=attempt.assessment.title,
                purged_at=purged_at,
                purged_by_system=(operator_user is None),
                operator_user=operator_user,
                answers_scrubbed_count=0,
                code_submissions_scrubbed_count=0,
                proctoring_events_scrubbed_count=0,
                evidence_files_deleted_count=files_deleted_count,
                confirmed_bytes_reclaimed=confirmed_bytes,
                sha256_audit_proof=sha256_audit_proof
            )

            # Transition RetentionRecord to completely PURGED
            retention_record.purge_state = PurgeState.PURGED
            retention_record.filesystem_cleanup_status = FileCleanupStatus.CONFIRMED
            retention_record.save(update_fields=['purge_state', 'filesystem_cleanup_status', 'updated_at'])

            # Transient queue cleanup
            queue_items.delete()

            return tombstone
