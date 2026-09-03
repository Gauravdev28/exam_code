import logging
from celery import shared_task
from apps.evaluator.services import CodeSubmissionService

logger = logging.getLogger('codeguard.evaluator')


@shared_task(
    bind=True,
    max_retries=3,
    acks_late=True,
    name='apps.evaluator.tasks.evaluate_code_submission_task'
)
def evaluate_code_submission_task(self, submission_id: str):
    """
    Asynchronous Celery execution task evaluating a CodeSubmission.
    Implements exponential backoff retries for transient infrastructure failures only.
    """
    logger.info(f"Starting code evaluation task for submission {submission_id}")
    try:
        submission = CodeSubmissionService.evaluate_submission(submission_id)
        if submission:
            logger.info(f"Evaluation task completed for submission {submission_id}: {submission.verdict}")
        return {"submission_id": submission_id, "status": "COMPLETED"}
    except Exception as exc:
        logger.error(f"Transient error evaluating submission {submission_id}: {exc}", exc_info=True)
        # Exponential backoff for infrastructure failures
        countdown = 2 ** self.request.retries * 2
        raise self.retry(exc=exc, countdown=countdown)
