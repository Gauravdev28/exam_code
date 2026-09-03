import logging
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import (
    APIException,
    AuthenticationFailed,
    NotAuthenticated,
    PermissionDenied as DRFPermissionDenied,
    ValidationError as DRFValidationError,
    NotFound as DRFNotFound,
    MethodNotAllowed as DRFMethodNotAllowed,
    Throttled as DRFThrottled
)
from django.core.exceptions import PermissionDenied as DjangoPermissionDenied, ValidationError as DjangoValidationError
from django.http import Http404

logger = logging.getLogger(__name__)

def custom_exception_handler(exc, context):
    """
    Standardized DRF Exception Handler for CODEGUARD.
    Ensures all error responses conform to the uniform envelope:
    {
        "status": "error",
        "error": {
            "code": "ERROR_CODE",
            "message": "Human readable error description",
            "details": { ... } or [ ... ]
        }
    }
    """
    # First, let DRF's standard handler process the exception
    response = exception_handler(exc, context)

    # Handle Django's standard non-DRF exceptions
    if response is None:
        if isinstance(exc, Http404):
            return Response({
                "status": "error",
                "error": {
                    "code": "NOT_FOUND",
                    "message": "The requested resource was not found.",
                    "details": str(exc) or None
                }
            }, status=status.HTTP_404_NOT_FOUND)

        elif isinstance(exc, DjangoPermissionDenied):
            return Response({
                "status": "error",
                "error": {
                    "code": "PERMISSION_DENIED",
                    "message": str(exc) or "You do not have permission to perform this action.",
                    "details": None
                }
            }, status=status.HTTP_403_FORBIDDEN)

        elif isinstance(exc, DjangoValidationError):
            details = exc.message_dict if hasattr(exc, 'message_dict') else exc.messages
            return Response({
                "status": "error",
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Validation error occurred.",
                    "details": details
                }
            }, status=status.HTTP_400_BAD_REQUEST)

        # Unhandled 500 server errors
        logger.error(f"Unhandled server exception: {exc}", exc_info=True)
        return Response({
            "status": "error",
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected server error occurred. Please contact system administrator.",
                "details": str(exc) if hasattr(exc, '__str__') else None
            }
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # Distinguish Authentication (401) vs Authorization (403)
    if isinstance(exc, (NotAuthenticated, AuthenticationFailed)):
        response.status_code = status.HTTP_401_UNAUTHORIZED
        error_code = getattr(exc, 'default_code', 'AUTHENTICATION_REQUIRED')
        if hasattr(exc, 'detail') and hasattr(exc.detail, 'code') and exc.detail.code:
            error_code = str(exc.detail.code).upper()
        elif hasattr(exc, 'code') and exc.code:
            error_code = str(exc.code).upper()
        else:
            error_code = "AUTHENTICATION_REQUIRED"
    elif isinstance(exc, (DRFPermissionDenied, DjangoPermissionDenied)):
        response.status_code = status.HTTP_403_FORBIDDEN
        error_code = "PERMISSION_DENIED"
    elif isinstance(exc, (DRFValidationError, DjangoValidationError)):
        response.status_code = status.HTTP_400_BAD_REQUEST
        error_code = "VALIDATION_ERROR"
    elif isinstance(exc, (DRFNotFound, Http404)):
        response.status_code = status.HTTP_404_NOT_FOUND
        error_code = "NOT_FOUND"
    elif isinstance(exc, DRFMethodNotAllowed):
        response.status_code = status.HTTP_405_METHOD_NOT_ALLOWED
        error_code = "METHOD_NOT_ALLOWED"
    elif isinstance(exc, DRFThrottled):
        response.status_code = status.HTTP_429_TOO_MANY_REQUESTS
        error_code = "THROTTLED"
    else:
        error_code = "API_ERROR"

    details = response.data
    message = "An error occurred while processing your request."
    if isinstance(details, dict):
        if "detail" in details:
            message = str(details.pop("detail"))
        elif "message" in details:
            message = str(details.pop("message"))
    elif isinstance(details, list) and len(details) > 0:
        message = str(details[0])

    response.data = {
        "status": "error",
        "error": {
            "code": error_code,
            "message": message,
            "details": details if details else None
        }
    }

    return response
