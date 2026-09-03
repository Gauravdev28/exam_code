from rest_framework.permissions import BasePermission
from apps.accounts.models import Role
from apps.invigilation.models import ProctorAssignment
from apps.assessments.models import Assessment, TestAttempt


class IsProctorOrAdmin(BasePermission):
    """
    Grants access strictly to users possessing PROCTOR or ADMIN roles.
    Generic Django is_staff=True does NOT grant invigilation authority.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        user_role = getattr(request.user, 'role', None)
        # ADMIN (or superuser) retains global administrative access
        if user_role == Role.ADMIN or request.user.is_superuser:
            return True
        # Explicit PROCTOR role is required for proctor endpoints
        if user_role == 'PROCTOR':
            return True
        return False


class HasAssignedAssessmentAccess(BasePermission):
    """
    Enforces object-level authorization ensuring a proctor can only access assessments
    they are explicitly assigned to via an active ProctorAssignment.
    Admins retain universal visibility.
    Generic staff without ADMIN/PROCTOR are denied.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        user_role = getattr(request.user, 'role', None)
        if user_role == Role.ADMIN or request.user.is_superuser:
            return True
        if user_role != 'PROCTOR':
            return False

        assessment_id = view.kwargs.get('assessment_id') or view.kwargs.get('pk')
        if not assessment_id:
            return False

        return ProctorAssignment.objects.filter(
            proctor=request.user,
            assessment_id=assessment_id,
            is_active=True
        ).exists()


class HasAttemptInvigilationAccess(BasePermission):
    """
    Enforces that a proctor can only intervene in attempts belonging to assessments
    they are actively assigned to.
    A proctor assigned to Assessment A must not control an attempt belonging to Assessment B.
    Admins retain universal intervention authority.
    Generic staff without ADMIN/PROCTOR are denied.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        user_role = getattr(request.user, 'role', None)
        if user_role == Role.ADMIN or request.user.is_superuser:
            return True
        if user_role != 'PROCTOR':
            return False

        attempt_id = view.kwargs.get('attempt_id') or view.kwargs.get('pk')
        if not attempt_id:
            return False

        attempt = TestAttempt.objects.filter(id=attempt_id).values('assessment_id').first()
        if not attempt:
            return False

        return ProctorAssignment.objects.filter(
            proctor=request.user,
            assessment_id=attempt['assessment_id'],
            is_active=True
        ).exists()
