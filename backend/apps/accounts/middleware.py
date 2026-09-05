import logging
from django.utils import timezone
from django.contrib.auth import logout as auth_logout
from django.http import JsonResponse
from apps.accounts.session_policy import SessionActivityPolicy
from apps.accounts.services import AuditService

logger = logging.getLogger(__name__)


class SessionIdleTimeoutMiddleware:
    """
    Server-authoritative middleware enforcing the centralized session inactivity policy.
    Runs after AuthenticationMiddleware.
    """
    EXEMPT_PREFIXES = (
        '/static/',
        '/media/',
        '/api/v1/auth/login/',
        '/api/v1/auth/csrf/',
        '/api/v1/health/',
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path_info

        # Skip non-relevant and unauthenticated public endpoints
        if any(path.startswith(prefix) for prefix in self.EXEMPT_PREFIXES):
            return self.get_response(request)

        user = getattr(request, 'user', None)
        if user and user.is_authenticated and user.is_active:
            status = SessionActivityPolicy.get_session_status(request)

            if status.get("is_expired"):
                logger.info("Session expired due to inactivity for user %s (%s)", user.id, user.email)
                
                # Write audit event before flushing session
                try:
                    AuditService.log(
                        action="SESSION_IDLE_EXPIRED",
                        actor=user,
                        target_type="User",
                        target_id=str(user.id),
                        metadata={
                            "role": user.role,
                            "email": user.email,
                            "idle_timeout_seconds": status.get("idle_timeout_seconds")
                        },
                        request=request
                    )
                except Exception as audit_err:
                    logger.warning("Failed to log SESSION_IDLE_EXPIRED audit: %s", audit_err)

                auth_logout(request)
                request.session.flush()

                if path.startswith('/api/'):
                    return JsonResponse(
                        {
                            "status": "error",
                            "error": {
                                "code": "SESSION_EXPIRED",
                                "message": "Your session expired due to inactivity. Please sign in again.",
                                "details": None
                            }
                        },
                        status=401
                    )

            elif path != '/api/v1/auth/session/status/':
                # Update last_activity on actual user requests (excluding passive polling of status endpoint)
                request.session['last_activity'] = timezone.now().timestamp()

        return self.get_response(request)
