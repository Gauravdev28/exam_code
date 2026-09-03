import pytest
from unittest.mock import patch
from django.urls import reverse

@pytest.mark.django_db
def test_health_check_endpoint(api_client):
    """Verify health check endpoint returns 200 with operational status."""
    url = reverse('core:health-check')
    response = api_client.get(url)
    
    assert response.status_code == 200
    data = response.json()
    assert data['status'] == 'success'
    assert 'data' in data
    assert 'services' in data['data']
    assert 'database' in data['data']['services']
    assert data['data']['services']['database']['status'] == 'healthy'

@pytest.mark.django_db
def test_health_check_database_failure(api_client):
    """Verify health check endpoint returns 503 when database fails."""
    url = reverse('core:health-check')
    with patch('django.db.connection.cursor', side_effect=Exception("Database connection timeout")):
        response = api_client.get(url)
        
        assert response.status_code == 503
        data = response.json()
        assert data['status'] == 'error'
        assert data['data']['services']['database']['status'] == 'unhealthy'
        assert "Database connection timeout" in data['data']['services']['database']['error']

@pytest.mark.django_db
def test_system_info_endpoint(api_client):
    """Verify public system info endpoint returns API metadata."""
    url = reverse('core:system-info')
    response = api_client.get(url)
    
    assert response.status_code == 200
    data = response.json()
    assert data['status'] == 'success'
    assert data['data']['name'] == 'CODEGUARD API'
    assert 'python' in data['data']['supported_languages']
