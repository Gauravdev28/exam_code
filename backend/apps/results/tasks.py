import os
import logging
from celery import shared_task
from django.utils import timezone
from .models import ReportJob, ReportStatus
from .services import ResultFinalizationService, ReportService

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=5,
    name='apps.results.tasks.finalize_assessment_result_task'
)
def finalize_assessment_result_task(self, attempt_id: str):
    """
    Asynchronously projects authoritative assessment scoring into immutable AssessmentResult.
    """
    try:
        result = ResultFinalizationService.finalize_attempt(attempt_id=attempt_id)
        logger.info(f"Successfully finalized result {result.id} for attempt {attempt_id}")
        return str(result.id)
    except Exception as exc:
        logger.error(f"Error finalizing result for attempt {attempt_id}: {exc}", exc_info=True)
        raise self.retry(exc=exc)


@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=10,
    name='apps.results.tasks.generate_report_job_task'
)
def generate_report_job_task(self, job_id: str):
    """
    Asynchronously generates export report document (PDF, XLSX, CSV).
    """
    try:
        job = ReportService.generate_report(job_id=job_id)
        logger.info(f"Successfully generated report {job.id} ({job.format})")
        return str(job.id)
    except Exception as exc:
        logger.error(f"Error generating report {job_id}: {exc}", exc_info=True)
        raise self.retry(exc=exc)


@shared_task(name='apps.results.tasks.cleanup_expired_reports_task')
def cleanup_expired_reports_task():
    """
    Daily maintenance task purging report files past their 7-day TTL.
    """
    now = timezone.now()
    expired_jobs = ReportJob.objects.filter(
        expires_at__lt=now,
        status=ReportStatus.COMPLETED
    )
    count = 0
    for job in expired_jobs:
        if job.file_path and os.path.exists(job.file_path):
            try:
                os.remove(job.file_path)
            except OSError:
                pass
        job.status = ReportStatus.EXPIRED
        job.save(update_fields=['status', 'updated_at'])
        count += 1
    logger.info(f"Purged {count} expired report artifacts.")
    return count
