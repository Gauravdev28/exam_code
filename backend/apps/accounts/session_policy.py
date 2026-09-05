import logging
from typing import Dict, Any, Optional
from django.conf import settings
from django.utils import timezone
from apps.accounts.models import Role

logger = logging.getLogger(__name__)


class SessionActivityPolicy:
    """
    Centralized session inactivity and timeout policy for CODEGUARD.
    Enforces server-authoritative idle expiration across Admin, Proctor, and Student accounts,
    while strictly protecting active student assessments (Phase 5 timer authority).
    """
    DEFAULT_IDLE_TIMEOUT_SECONDS = 1800  # 30 minutes
    DEFAULT_WARNING_SECONDS = 120        # 2 minutes warning
    LAST_ACTIVITY_KEY = 'last_activity'

    @classmethod
    def get_idle_timeout_seconds(cls, user=None) -> int:
        return getattr(settings, 'SESSION_IDLE_TIMEOUT_SECONDS', cls.DEFAULT_IDLE_TIMEOUT_SECONDS)

    @classmethod
    def get_warning_seconds(cls) -> int:
        return getattr(settings, 'SESSION_WARNING_SECONDS', cls.DEFAULT_WARNING_SECONDS)

    @classmethod
    def is_in_active_assessment(cls, user) -> bool:
        """
        Determines if a student user currently has an authoritative active attempt in progress.
        """
        if not user or not user.is_authenticated or user.role != Role.STUDENT:
            return False
        try:
            from apps.assessments.models import TestAttempt, AttemptStatus
            return TestAttempt.objects.filter(student=user, status=AttemptStatus.IN_PROGRESS).exists()
        except Exception as e:
            logger.warning("Error checking active assessment for user %s: %s", getattr(user, 'id', None), e)
            return False

    @classmethod
    def get_session_status(cls, request) -> Dict[str, Any]:
        user = getattr(request, 'user', None)
        if not user or not user.is_authenticated or not user.is_active:
            return {
                "authenticated": False,
                "remaining_seconds": 0,
                "idle_timeout_seconds": cls.get_idle_timeout_seconds(),
                "warning_seconds": cls.get_warning_seconds(),
                "in_active_assessment": False,
                "is_expired": True,
            }

        in_assessment = cls.is_in_active_assessment(user)
        timeout_seconds = cls.get_idle_timeout_seconds(user)
        warning_seconds = cls.get_warning_seconds()

        now = timezone.now().timestamp()
        last_activity = request.session.get('last_activity')

        if last_activity is None:
            # First authenticated request; initialize activity timestamp
            request.session['last_activity'] = now
            last_activity = now

        elapsed = max(0.0, now - float(last_activity))

        if in_assessment:
            # In active assessment, reading/thinking time is exempt from session idle timeout
            remaining_seconds = timeout_seconds
            is_warning = False
            is_expired = False
        else:
            remaining_seconds = max(0, int(timeout_seconds - elapsed))
            is_warning = remaining_seconds <= warning_seconds and remaining_seconds > 0
            is_expired = remaining_seconds <= 0

        return {
            "authenticated": True,
            "user_id": str(user.id),
            "role": user.role,
            "remaining_seconds": remaining_seconds,
            "idle_timeout_seconds": timeout_seconds,
            "warning_seconds": warning_seconds,
            "in_active_assessment": in_assessment,
            "idle_timeout_exempt": in_assessment,
            "is_warning": is_warning,
            "is_expired": is_expired,
        }

    @classmethod
    def refresh_session_activity(cls, request) -> Dict[str, Any]:
        """
        Refreshes active session activity.
        Validates that the session is still valid and not expired.
        """
        status = cls.get_session_status(request)
        if not status["authenticated"] or status["is_expired"]:
            return status

        now = timezone.now().timestamp()
        request.session['last_activity'] = now
        request.session.modified = True
        return cls.get_session_status(request)
