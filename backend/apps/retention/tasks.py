import logging
from celery import shared_task
from django.conf import settings
from django.utils import timezone

from apps.retention.models import (
    RetentionRecord,
    PurgeState,
    PurgeJobRun,
    PurgeTriggerType,
    PurgeJobStatus,
)
from apps.retention.services import (
    AuthoritativeScrubbingService,
    FilesystemCleanupWorker,
    DsarExportService,
)

logger = logging.getLogger('codeguard.retention')


@shared_task(
    bind=True,
    name='apps.retention.tasks.retention_scheduled_daily_purge'
)
def retention_scheduled_daily_purge(self):
    """
    Scheduled beat task (02:00 UTC daily).
    Scans for expired attempts, executes authoritative DB scrubs in chunks of CHUNK_SIZE,
    and sweeps the 90-day proctoring operational window.
    """
    now = timezone.now()
    chunk_size = getattr(settings, 'RETENTION_CHUNK_SIZE', 100)

    run = PurgeJobRun.objects.create(
        trigger_type=PurgeTriggerType.SCHEDULED_DAILY,
        status=PurgeJobStatus.RUNNING
    )

    try:
        # Select candidates
        candidate_ids = list(
            RetentionRecord.objects.filter(
                detailed_data_expires_at__lte=now,
                purge_state__in=[PurgeState.SCHEDULED, PurgeState.DEFERRED_EXPORT]
            ).values_list('attempt_id', flat=True)[:chunk_size]
        )

        run.attempts_evaluated_count = len(candidate_ids)
        purged_count = 0
        deferred_hold_count = 0
        deferred_export_count = 0

        for attempt_id in candidate_ids:
            res = AuthoritativeScrubbingService.execute_purge_for_attempt(attempt_id)
            if res.get('purged'):
                purged_count += 1
            elif res.get('status') == 'DEFERRED_HOLD':
                deferred_hold_count += 1
            elif res.get('status') == 'DEFERRED_EXPORT':
                deferred_export_count += 1

        # Sweep 90-day proctoring risk operational window
        AuthoritativeScrubbingService.sweep_proctoring_operational_window()

        run.status = PurgeJobStatus.COMPLETED
        run.completed_at = timezone.now()
        run.attempts_purged_count = purged_count
        run.attempts_deferred_hold_count = deferred_hold_count
        run.attempts_deferred_export_count = deferred_export_count
        run.save()

        logger.info(
            f"Scheduled daily purge completed: {purged_count} purged, "
            f"{deferred_hold_count} deferred (hold), {deferred_export_count} deferred (export)."
        )
        return str(run.id)
    except Exception as exc:
        logger.exception(f"Daily purge task failed: {exc}")
        run.status = PurgeJobStatus.FAILED
        run.completed_at = timezone.now()
        run.error_summary = str(exc)
        run.save()
        raise


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=10,
    name='apps.retention.tasks.process_file_cleanup_queue'
)
def process_file_cleanup_queue(self, attempt_id: str):
    """
    Asynchronous task for physical filesystem deletion of unlinked evidence files.
    Idempotent and retryable.
    """
    try:
        result = FilesystemCleanupWorker.process_attempt_cleanups(attempt_id)
        logger.info(f"File cleanup for attempt {attempt_id}: {result}")
        return result
    except Exception as exc:
        logger.error(f"Error processing file cleanups for attempt {attempt_id}: {exc}", exc_info=True)
        raise self.retry(exc=exc)


@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=15,
    name='apps.retention.tasks.generate_student_dsar_archive'
)
def generate_student_dsar_archive(self, job_id: str):
    """
    Asynchronously materializes allowlisted snapshot and encrypts with AES-256-GCM.
    """
    try:
        DsarExportService.acquire_snapshot(job_id)
        DsarExportService.generate_and_encrypt_archive(job_id)
        logger.info(f"DSAR archive generation completed for job {job_id}")
        return job_id
    except Exception as exc:
        logger.error(f"DSAR archive generation failed for job {job_id}: {exc}", exc_info=True)
        raise self.retry(exc=exc)


@shared_task(
    name='apps.retention.tasks.cleanup_expired_dsar_archives'
)
def cleanup_expired_dsar_archives():
    """
    Daily scheduled beat task unlinking DSAR archives older than 7 days.
    """
    count = DsarExportService.cleanup_expired_archives()
    logger.info(f"Unlinked {count} expired DSAR archives.")
    return count


@shared_task(
    name='apps.retention.tasks.recover_stale_dsar_export_jobs'
)
def recover_stale_dsar_export_jobs():
    """
    Periodic beat task (every 5m) recovering abandoned SNAPSHOT_PENDING exports whose 15m lease expired.
    """
    count = DsarExportService.recover_stale_jobs()
    if count > 0:
        logger.info(f"Recovered {count} stale DSAR export jobs.")
    return count
