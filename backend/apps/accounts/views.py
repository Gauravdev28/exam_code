from django.contrib.auth import login, logout, update_session_auth_hash
from django.middleware.csrf import get_token
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

from apps.core.responses import APIResponse
from apps.core.pagination import StandardResultsSetPagination
from .models import User, StudentProfile, Role
from .serializers import (
    LoginSerializer,
    UserSerializer,
    StudentDetailSerializer,
    CreateStudentSerializer,
    UpdateStudentSerializer,
    BulkImportConfirmSerializer,
    ChangePasswordSerializer,
)
from .permissions import IsAdmin, IsStudent, IsActiveUser, IsFirstLoginSatisfied
from .throttling import LoginRateThrottle
from .services import StudentService, ImportService, AuditService

# ==============================================================================
# Authentication Views
# ==============================================================================

class LoginView(APIView):
    """
    User Login Endpoint (POST /api/v1/auth/login/)
    Validates credentials (Email or EUID + Password), rotates session key,
    and returns sanitized user profile with first_login_required status.
    """
    permission_classes = [AllowAny]
    throttle_classes = [LoginRateThrottle]

    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data['user']
        
        # Establish authenticated session
        login(request, user)
        
        # Cycle session key to prevent session fixation attacks
        if request.session:
            request.session.cycle_key()

        # Ensure CSRF token is refreshed
        csrf_token = get_token(request)

        AuditService.log(
            action="LOGIN_SUCCESS",
            actor=user,
            target_type="User",
            target_id=user.id,
            metadata={"email": user.email, "role": user.role},
            request=request
        )

        return APIResponse(
            data={
                "user": UserSerializer(user).data,
                "csrf_token": csrf_token
            },
            message=f"Welcome back, {user.email}!",
            status_code=status.HTTP_200_OK
        )


class LogoutView(APIView):
    """
    User Logout Endpoint (POST /api/v1/auth/logout/)
    Terminates active session and records audit event.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        AuditService.log(
            action="LOGOUT",
            actor=user,
            target_type="User",
            target_id=user.id,
            request=request
        )
        logout(request)
        return APIResponse(
            message="Successfully logged out.",
            status_code=status.HTTP_200_OK
        )


class CurrentUserView(APIView):
    """
    Current User Profile Endpoint (GET /api/v1/auth/me/)
    """
    permission_classes = [IsAuthenticated, IsActiveUser]

    def get(self, request):
        return APIResponse(
            data=UserSerializer(request.user).data,
            message="Current user profile retrieved."
        )


class ChangePasswordView(APIView):
    """
    Password Reset / First-Login Password Change Endpoint (POST /api/v1/auth/change-password/)
    Validates current password, applies Django complexity rules, updates hash, and clears first_login_required.
    """
    permission_classes = [IsAuthenticated, IsActiveUser]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        user = request.user
        new_password = serializer.validated_data['new_password']

        user.set_password(new_password)
        user.save(update_fields=['password', 'updated_at'])

        # If student, clear first_login_required
        if user.role == Role.STUDENT and hasattr(user, 'student_profile'):
            profile = user.student_profile
            profile.first_login_required = False
            profile.save(update_fields=['first_login_required', 'updated_at'])

        # Keep active session authenticated after password change
        update_session_auth_hash(request, user)

        AuditService.log(
            action="PASSWORD_CHANGED",
            actor=user,
            target_type="User",
            target_id=user.id,
            request=request
        )

        return APIResponse(
            data=UserSerializer(user).data,
            message="Password successfully changed.",
            status_code=status.HTTP_200_OK
        )


# ==============================================================================
# Student-Facing Views
# ==============================================================================

class StudentProfileView(APIView):
    """
    Student Self Profile Endpoint (GET /api/v1/student/profile/)
    Strictly scoped to the requesting student to eliminate IDOR vulnerabilities.
    """
    permission_classes = [IsAuthenticated, IsStudent, IsActiveUser]

    def get(self, request):
        if not hasattr(request.user, 'student_profile'):
            return APIResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                message="Student profile not found for this account."
            )
        serializer = StudentDetailSerializer(request.user.student_profile)
        return APIResponse(
            data=serializer.data,
            message="Student profile retrieved."
        )


# ==============================================================================
# Administrator Student Management Views
# ==============================================================================

class AdminStudentListView(APIView):
    """
    Admin Student Listing & Single Student Creation (GET / POST /api/v1/admin/students/)
    """
    permission_classes = [IsAuthenticated, IsAdmin]
    pagination_class = StandardResultsSetPagination

    def get(self, request):
        queryset = StudentProfile.objects.select_related('user').all()

        # Search filter (email, roll_number, euid)
        search = request.query_params.get('search', '').strip()
        if search:
            queryset = queryset.filter(
                Q(roll_number__icontains=search) |
                Q(euid__icontains=search) |
                Q(user__email__icontains=search)
            )

        # Status filter (active / disabled)
        status_filter = request.query_params.get('is_active')
        if status_filter is not None:
            is_active = status_filter.lower() in ('true', '1', 't')
            queryset = queryset.filter(user__is_active=is_active)

        # First login filter
        first_login = request.query_params.get('first_login_required')
        if first_login is not None:
            fl_bool = first_login.lower() in ('true', '1', 't')
            queryset = queryset.filter(first_login_required=fl_bool)

        # Sorting
        ordering = request.query_params.get('ordering', '-created_at')
        if ordering in ['created_at', '-created_at', 'roll_number', '-roll_number', 'euid', '-euid', 'user__email', '-user__email']:
            queryset = queryset.order_by(ordering)
        else:
            queryset = queryset.order_by('-created_at')

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request)
        serializer = StudentDetailSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request):
        serializer = CreateStudentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user, profile = StudentService.create_student(
            email=serializer.validated_data['email'],
            roll_number=serializer.validated_data['roll_number'],
            actor=request.user,
            request=request
        )

        return APIResponse(
            data=StudentDetailSerializer(profile).data,
            message="Student account created successfully.",
            status_code=status.HTTP_201_CREATED
        )


class AdminStudentDetailView(APIView):
    """
    Admin Single Student Retrieval & Update (GET / PATCH /api/v1/admin/students/<id>/)
    """
    permission_classes = [IsAuthenticated, IsAdmin]

    def _get_student(self, pk):
        # Support lookup by either StudentProfile UUID or User UUID
        return get_object_or_404(
            StudentProfile.objects.select_related('user'),
            Q(id=pk) | Q(user__id=pk)
        )

    def get(self, request, pk):
        profile = self._get_student(pk)
        return APIResponse(
            data=StudentDetailSerializer(profile).data,
            message="Student details retrieved."
        )

    def patch(self, request, pk):
        profile = self._get_student(pk)
        serializer = UpdateStudentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        updated_profile = StudentService.update_student(
            student_profile=profile,
            email=serializer.validated_data.get('email'),
            actor=request.user,
            request=request
        )

        return APIResponse(
            data=StudentDetailSerializer(updated_profile).data,
            message="Student details updated successfully."
        )


class AdminStudentStatusView(APIView):
    """
    Admin Enable/Disable Student (POST /api/v1/admin/students/<id>/disable/ or /enable/)
    """
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, pk, action=None):
        profile = get_object_or_404(
            StudentProfile.objects.select_related('user'),
            Q(id=pk) | Q(user__id=pk)
        )

        is_active = (action == 'enable')
        StudentService.set_student_status(
            student_profile=profile,
            is_active=is_active,
            actor=request.user,
            request=request
        )

        status_text = "enabled" if is_active else "disabled"
        return APIResponse(
            data=StudentDetailSerializer(profile).data,
            message=f"Student account successfully {status_text}."
        )


# ==============================================================================
# Bulk CSV / XLSX Import Views
# ==============================================================================

class AdminStudentImportPreviewView(APIView):
    """
    Bulk Import Preview Endpoint (POST /api/v1/admin/students/import/preview/)
    Parses and validates CSV/XLSX file, detects duplicates, and produces preview.
    """
    permission_classes = [IsAuthenticated, IsAdmin]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        uploaded_file = request.FILES.get('file')
        if not uploaded_file:
            return APIResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                message="No file uploaded. Please upload a .csv or .xlsx file."
            )

        rows = ImportService.parse_file(uploaded_file)
        preview_report = ImportService.validate_preview(rows)

        AuditService.log(
            action="STUDENT_IMPORT_STARTED",
            actor=request.user,
            target_type="StudentProfile",
            metadata={
                "filename": uploaded_file.name,
                "total_rows": preview_report["total_rows"],
                "valid_count": preview_report["valid_count"],
                "duplicate_count": preview_report["duplicate_count"],
                "invalid_count": preview_report["invalid_count"],
            },
            request=request
        )

        return APIResponse(
            data=preview_report,
            message="File validated successfully. Review import preview before confirmation."
        )


class AdminStudentImportConfirmView(APIView):
    """
    Bulk Import Confirmation Endpoint (POST /api/v1/admin/students/import/confirm/)
    Atomically creates student accounts for confirmed valid rows.
    """
    permission_classes = [IsAuthenticated, IsAdmin]
    parser_classes = [JSONParser]

    def post(self, request):
        serializer = BulkImportConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        students_data = serializer.validated_data['students']
        filename = serializer.validated_data.get('filename')

        result = ImportService.execute_import(
            items=students_data,
            actor=request.user,
            filename=filename,
            request=request
        )

        return APIResponse(
            data=result,
            message=f"Import completed. Created {result['created_count']} student accounts."
        )


# ==============================================================================
# Verification Smoke Views
# ==============================================================================

class AdminOnlyTestView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        return APIResponse(
            data={"admin_access": True, "email": request.user.email, "role": request.user.role},
            message="Authorized administrative resource."
        )


class StudentOnlyTestView(APIView):
    permission_classes = [IsAuthenticated, IsStudent]

    def get(self, request):
        return APIResponse(
            data={"student_access": True, "email": request.user.email, "role": request.user.role},
            message="Authorized student resource."
        )
