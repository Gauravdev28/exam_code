from datetime import timedelta
from django.conf import settings
from django.core import signing
from django.core.exceptions import ValidationError
from django.db.models import Sum
from django.utils import timezone

from apps.assessments.models import TestAttempt
from apps.retention.models import (
    RetentionTombstone,
    RetentionRecord,
    PurgeState,
    LegalHold,
    LegalHoldStatus,
    FileCleanupQueue,
    FileCleanupStatus,
    RetentionPolicy,
    PurgeJobRun,
    PurgeTriggerType,
    PurgeJobStatus,
)
from .scrubbing import AuthoritativeScrubbingService


class RetentionMetricsService:
    @classmethod
    def get_retention_metrics(cls):
        """
        Calculates authoritative storage and lifecycle metrics.
        Clearly distinguishes confirmed physical bytes reclaimed from logical row counts.
        """
        now = timezone.now()
        in_7_days = now + timedelta(days=7)

        # Physical filesystem metrics
        tombstone_aggs = RetentionTombstone.objects.aggregate(
            total_bytes=Sum('confirmed_bytes_reclaimed')
        )
        confirmed_bytes = tombstone_aggs['total_bytes'] or 0

        pending_queue_aggs = FileCleanupQueue.objects.filter(
            status=FileCleanupStatus.PENDING
        ).aggregate(
            pending_bytes=Sum('file_bytes')
        )
        pending_cleanup_bytes = pending_queue_aggs['pending_bytes'] or 0

        return {
            'confirmed_bytes_reclaimed': confirmed_bytes,
            'confirmed_mb_reclaimed': round(confirmed_bytes / (1024 * 1024), 2),
            'total_tombstones_count': RetentionTombstone.objects.count(),
            'active_legal_holds_count': LegalHold.objects.filter(status=LegalHoldStatus.ACTIVE).count(),
            'upcoming_purges_7d_count': RetentionRecord.objects.filter(
                purge_state__in=[PurgeState.SCHEDULED, PurgeState.DEFERRED_EXPORT],
                detailed_data_expires_at__lte=in_7_days,
                detailed_data_expires_at__gt=now
            ).count(),
            'due_today_count': RetentionRecord.objects.filter(
                purge_state__in=[PurgeState.SCHEDULED, PurgeState.DEFERRED_EXPORT],
                detailed_data_expires_at__lte=now
            ).count(),
            'deferred_holds_count': RetentionRecord.objects.filter(purge_state=PurgeState.DEFERRED_HOLD).count(),
            'deferred_exports_count': RetentionRecord.objects.filter(purge_state=PurgeState.DEFERRED_EXPORT).count(),
            'pending_file_cleanups_count': FileCleanupQueue.objects.filter(status=FileCleanupStatus.PENDING).count(),
            'pending_file_cleanup_bytes': pending_cleanup_bytes,
            'active_policies_count': RetentionPolicy.objects.filter(is_active=True).count(),
        }

    @classmethod
    def generate_purge_preview(cls, assessment_id=None):
        """
        Generates a dry-run purge preview and issues a signed 5-minute preview token.
        Does not mutate any state.
        """
        now = timezone.now()
        qs = RetentionRecord.objects.filter(
            detailed_data_expires_at__lte=now,
            purge_state__in=[PurgeState.SCHEDULED, PurgeState.DEFERRED_HOLD, PurgeState.DEFERRED_EXPORT]
        ).select_related('attempt', 'attempt__student', 'attempt__assessment')

        if assessment_id:
            qs = qs.filter(attempt__assessment_id=assessment_id)

        candidates = []
        eligible_ids = []

        for rec in qs:
            attempt = rec.attempt
            eligible = AuthoritativeScrubbingService.is_eligible_for_purge(attempt, now=now)
            if eligible:
                eligible_ids.append(str(attempt.id))

            candidates.append({
                'attempt_id': str(attempt.id),
                'assessment_id': str(attempt.assessment_id),
                'assessment_title': attempt.assessment.title,
                'student_id': str(attempt.student_id),
                'student_euid': getattr(attempt.student, 'euid', ''),
                'detailed_data_expires_at': rec.detailed_data_expires_at.isoformat(),
                'current_purge_state': rec.purge_state,
                'is_eligible': eligible,
            })

        # Generate signed 5-minute preview token
        token_payload = {
            'eligible_ids': eligible_ids,
            'generated_at': now.isoformat(),
            'assessment_id': str(assessment_id) if assessment_id else None,
        }
        preview_token = signing.dumps(token_payload, salt='purge_preview_v1')

        return {
            'preview_token': preview_token,
            'total_candidates': len(candidates),
            'eligible_count': len(eligible_ids),
            'candidates': candidates,
            'valid_for_seconds': 300,
        }

    @classmethod
    def validate_and_execute_preview_purge(cls, preview_token, operator_user=None, process_filesystem_sync=True):
        """
        Re-validates eligibility under row locks and executes manual purge for previewed attempts.
        Rejects stale or tampered tokens.
        """
        try:
            payload = signing.loads(preview_token, salt='purge_preview_v1', max_age=300)
        except signing.SignatureExpired:
            raise ValidationError("Purge preview token has expired (5-minute validity limit). Please generate a new preview.")
        except signing.BadSignature:
            raise ValidationError("Invalid or tampered purge preview token.")

        eligible_ids = payload.get('eligible_ids', [])
        if not eligible_ids:
            return {'purged_count': 0, 'deferred_count': 0, 'skipped_count': 0}

        run = PurgeJobRun.objects.create(
            trigger_type=PurgeTriggerType.MANUAL_ADMIN,
            status=PurgeJobStatus.RUNNING,
            operator_user=operator_user,
            attempts_evaluated_count=len(eligible_ids)
        )

        purged_count = 0
        deferred_hold_count = 0
        deferred_export_count = 0

        for attempt_id in eligible_ids:
            res = AuthoritativeScrubbingService.execute_purge_for_attempt(
                attempt_id,
                operator_user=operator_user,
                process_filesystem_sync=process_filesystem_sync
            )
            if res.get('purged'):
                purged_count += 1
            elif res.get('status') == 'DEFERRED_HOLD':
                deferred_hold_count += 1
            elif res.get('status') == 'DEFERRED_EXPORT':
                deferred_export_count += 1

        run.status = PurgeJobStatus.COMPLETED
        run.completed_at = timezone.now()
        run.attempts_purged_count = purged_count
        run.attempts_deferred_hold_count = deferred_hold_count
        run.attempts_deferred_export_count = deferred_export_count
        run.save()

        return {
            'job_run_id': str(run.id),
            'evaluated_count': len(eligible_ids),
            'purged_count': purged_count,
            'deferred_hold_count': deferred_hold_count,
            'deferred_export_count': deferred_export_count,
        }
