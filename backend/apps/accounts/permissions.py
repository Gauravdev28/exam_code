from rest_framework.permissions import BasePermission
from .models import Role

class IsAdmin(BasePermission):
    """
    Allows access only to authenticated users with ADMIN role or staff privileges.
    """
    message = "Administrator privileges required to access this resource."

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user and
            user.is_authenticated and
            user.is_active and
            (user.role == Role.ADMIN or user.is_staff or user.is_superuser)
        )


class IsStudent(BasePermission):
    """
    Allows access only to authenticated users with STUDENT role.
    """
    message = "Student account required to access this resource."

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user and
            user.is_authenticated and
            user.is_active and
            user.role == Role.STUDENT
        )


class IsActiveUser(BasePermission):
    """
    Allows access to any active authenticated user regardless of role.
    """
    message = "Account is inactive or disabled."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_active)


class IsFirstLoginSatisfied(BasePermission):
    """
    Enforces that students have reset their initial temporary password before accessing general platform resources.
    """
    message = "Initial password change is mandatory before accessing assessments or dashboard."
    code = "PASSWORD_CHANGE_REQUIRED"

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated or not user.is_active:
            return False
        if user.role == Role.STUDENT and hasattr(user, 'student_profile'):
            return not user.student_profile.first_login_required
        return True
