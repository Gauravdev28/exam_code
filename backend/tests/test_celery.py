import pytest
from apps.core.tasks import ping_celery

def test_celery_task_direct_execution():
    """Verify Celery task executes and returns expected payload directly."""
    result = ping_celery(message="direct_test")
    assert result == "pong: direct_test"

def test_celery_task_delay_dispatch():
    """Verify Celery task can be dispatched via .delay() and completes successfully."""
    async_result = ping_celery.delay(message="smoke_test")
    assert async_result.successful()
    assert async_result.get(timeout=5) == "pong: smoke_test"
