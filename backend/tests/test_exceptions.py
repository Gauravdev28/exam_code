import pytest
from rest_framework.exceptions import ValidationError, AuthenticationFailed, PermissionDenied, NotFound
from apps.core.exceptions import custom_exception_handler

def test_custom_exception_handler_validation_error():
    """Verify validation error formatting in standard error envelope."""
    exc = ValidationError({"email": ["Enter a valid email address."]})
    response = custom_exception_handler(exc, context={})
    
    assert response.status_code == 400
    assert response.data["status"] == "error"
    assert response.data["error"]["code"] == "VALIDATION_ERROR"
    assert "email" in response.data["error"]["details"]

def test_custom_exception_handler_permission_denied():
    """Verify permission denied error formatting."""
    exc = PermissionDenied("Admin access required.")
    response = custom_exception_handler(exc, context={})
    
    assert response.status_code == 403
    assert response.data["status"] == "error"
    assert response.data["error"]["code"] == "PERMISSION_DENIED"
    assert response.data["error"]["message"] == "Admin access required."

def test_custom_exception_handler_not_found():
    """Verify 404 not found error formatting."""
    exc = NotFound("Question not found.")
    response = custom_exception_handler(exc, context={})
    
    assert response.status_code == 404
    assert response.data["status"] == "error"
    assert response.data["error"]["code"] == "NOT_FOUND"
