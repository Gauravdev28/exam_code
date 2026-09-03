from celery import shared_task

@shared_task(name='apps.core.tasks.ping_celery')
def ping_celery(message: str = "ping") -> str:
    """
    Foundational smoke test task verifying Celery task registration,
    broker queueing, worker execution, and result serialization.
    """
    return f"pong: {message}"
