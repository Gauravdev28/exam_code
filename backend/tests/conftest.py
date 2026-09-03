import pytest
from rest_framework.test import APIClient
from django.core.cache import cache

@pytest.fixture(autouse=True)
def clear_cache_between_tests():
    """Clears Django cache before and after every test to ensure isolated rate limits."""
    cache.clear()
    yield
    cache.clear()

@pytest.fixture
def api_client():
    return APIClient()
