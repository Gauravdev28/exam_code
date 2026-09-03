from rest_framework.permissions import BasePermission
from apps.accounts.models import Role
from apps.invigilation.models import ProctorAssignment
from apps.assessments.models import Assessment, TestAttempt


class IsProctorOrAdmin(BasePermission):
    """
    Grants access strictly to users possessing PROCTOR or ADMIN roles.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        user_role = getattr(request.user, 'role', None)
        return (
            user_role in ['PROCTOR', Role.ADMIN]
            or request.user.is_staff
            or request.user.is_superuser
            or ProctorAssignment.objects.filter(proctor=request.user, is_active=True).exists()
        )


class HasAssignedAssessmentAccess(BasePermission):
    """
    Enforces object-level authorization ensuring a proctor can only access assessments
    they are explicitly assigned to via an active ProctorAssignment.
    Admins retain universal visibility.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if getattr(request.user, 'role', None) == Role.ADMIN or request.user.is_staff or request.user.is_superuser:
            return True

        assessment_id = view.kwargs.get('assessment_id') or view.kwargs.get('pk')
        if not assessment_id:
            return True

        return ProctorAssignment.objects.filter(
            proctor=request.user,
            assessment_id=assessment_id,
            is_active=True
        ).exists()


class HasAttemptInvigilationAccess(BasePermission):
    """
    Enforces that a proctor can only intervene in attempts belonging to assessments
    they are assigned to.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if getattr(request.user, 'role', None) == Role.ADMIN or request.user.is_staff or request.user.is_superuser:
            return True

        attempt_id = view.kwargs.get('attempt_id') or view.kwargs.get('pk')
        if not attempt_id:
            return True

        attempt = TestAttempt.objects.filter(id=attempt_id).values('assessment_id').first()
        if not attempt:
            return False

        return ProctorAssignment.objects.filter(
            proctor=request.user,
            assessment_id=attempt['assessment_id'],
            is_active=True
        ).exists()
