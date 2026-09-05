from django.contrib.auth import login, logout, update_session_auth_hash
from django.utils import timezone
from django.middleware.csrf import get_token
from django.views.decorators.csrf import ensure_csrf_cookie
from django.utils.decorators import method_decorator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

from apps.core.responses import APIResponse
from apps.core.pagination import StandardResultsSetPagination
from .models import User, StudentProfile, Role, AuditLog, Section
from .serializers import (
    LoginSerializer,
    UserSerializer,
    StudentDetailSerializer,
    CreateStudentSerializer,
    UpdateStudentSerializer,
    BulkImportConfirmSerializer,
    ChangePasswordSerializer,
    AdministratorSerializer,
    CreateAdministratorSerializer,
    UpdateAdministratorSerializer,
    ResetPasswordSerializer,
    AuditLogSerializer,
    SectionSerializer,
    CreateSectionSerializer,
    UpdateSectionSerializer,
    BulkAccountDeleteSerializer,
)
from apps.assessments.models import Assessment, AssessmentStatus
from .permissions import IsAdmin, IsStudent, IsActiveUser, IsFirstLoginSatisfied
from .throttling import LoginRateThrottle
from .services import StudentService, ImportService, AuditService, AccountSecurityService, SectionService

# ==============================================================================
# Authentication Views
# ==============================================================================

@method_decorator(ensure_csrf_cookie, name='dispatch')
class CSRFTokenView(APIView):
    """
    CSRF Initialization Endpoint (GET /api/v1/auth/csrf/)
    Safe for unauthenticated clients. Sets the csrftoken cookie and returns JSON token.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        return APIResponse(
            data={"csrf_token": get_token(request)},
            message="CSRF token initialized."
        )


@method_decorator(ensure_csrf_cookie, name='dispatch')
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
        user.first_login_required = False
        user.save(update_fields=['password', 'first_login_required', 'updated_at'])

        # If student, clear first_login_required on student profile as well
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
            target_id=str(user.id),
            metadata={
                "actor_name": user.display_name,
                "target_identity": getattr(user, 'admin_id', None) or (getattr(user, 'student_profile', None).euid if hasattr(user, 'student_profile') else ""),
                "target_email": user.email,
                "reason": "User self-service password change",
                "result": "SUCCESS"
            },
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
        queryset = StudentProfile.objects.select_related('user', 'section').all()

        # Search filter (email, roll_number, euid)
        search = request.query_params.get('search', '').strip()
        if search:
            queryset = queryset.filter(
                Q(roll_number__icontains=search) |
                Q(euid__icontains=search) |
                Q(user__email__icontains=search)
            )

        # Section filter (by ID, code, or 'unassigned')
        section_param = request.query_params.get('section', '').strip()
        if section_param:
            if section_param.lower() in ('unassigned', 'none', 'null'):
                queryset = queryset.filter(section__isnull=True)
            else:
                queryset = queryset.filter(
                    Q(section__id__iexact=section_param) |
                    Q(section__code__iexact=section_param)
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

        section_id = serializer.validated_data.get('section_id')
        sec_obj = None
        if section_id:
            sec_obj = get_object_or_404(Section, id=section_id)

        user, profile = StudentService.create_student(
            email=serializer.validated_data['email'],
            roll_number=serializer.validated_data['roll_number'],
            section=sec_obj,
            actor=request.user,
            request=request
        )

        return APIResponse(
            data=StudentDetailSerializer(profile).data,
            message=f"Student account {profile.roll_number} created successfully.",
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
            StudentProfile.objects.select_related('user', 'section'),
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

        email = serializer.validated_data.get('email')
        update_section = 'section_id' in serializer.validated_data
        sec_obj = None
        if update_section:
            section_id = serializer.validated_data.get('section_id')
            if section_id:
                sec_obj = get_object_or_404(Section, id=section_id)

        updated_profile = StudentService.update_student(
            student_profile=profile,
            email=email,
            section=sec_obj,
            update_section=update_section,
            actor=request.user,
            request=request
        )

        return APIResponse(
            data=StudentDetailSerializer(updated_profile).data,
            message="Student details updated successfully."
        )

    def delete(self, request, pk):
        profile = self._get_student(pk)
        roll = profile.roll_number
        euid = profile.euid
        StudentService.delete_student(profile, actor=request.user, request=request)
        return APIResponse(
            message=f"Student account {roll} ({euid}) successfully deleted.",
            status_code=status.HTTP_200_OK
        )


# ==============================================================================
# Administrator Section Management Views
# ==============================================================================

class AdminSectionListView(APIView):
    """
    List and Create Academic Sections.
    GET /api/v1/admin/sections/
    POST /api/v1/admin/sections/
    """
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        active_only = request.query_params.get('active_only', '').lower() in ('true', '1')
        sections = SectionService.get_sections_with_counts(active_only=active_only)
        search = request.query_params.get('search', '').strip()
        if search:
            sections = sections.filter(Q(code__icontains=search) | Q(name__icontains=search))
        serializer = SectionSerializer(sections, many=True)
        return APIResponse(data=serializer.data)

    def post(self, request):
        serializer = CreateSectionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        section = SectionService.create_section(
            code=serializer.validated_data['code'],
            name=serializer.validated_data['name'],
            is_active=serializer.validated_data.get('is_active', True),
            actor=request.user,
            request=request
        )
        section_with_count = SectionService.get_sections_with_counts().filter(id=section.id).first()
        return APIResponse(
            data=SectionSerializer(section_with_count or section).data,
            message=f"Section '{section.code}' created successfully.",
            status_code=status.HTTP_201_CREATED
        )


class AdminSectionDetailView(APIView):
    """
    Retrieve, Update, and Safe-Delete Academic Section.
    GET /api/v1/admin/sections/<uuid:pk>/
    PATCH /api/v1/admin/sections/<uuid:pk>/
    DELETE /api/v1/admin/sections/<uuid:pk>/
    """
    permission_classes = [IsAuthenticated, IsAdmin]

    def _get_section(self, pk):
        section = SectionService.get_sections_with_counts().filter(id=pk).first()
        if not section:
            section = get_object_or_404(Section, id=pk)
        return section

    def get(self, request, pk):
        section = self._get_section(pk)
        return APIResponse(data=SectionSerializer(section).data)

    def patch(self, request, pk):
        section = get_object_or_404(Section, id=pk)
        serializer = UpdateSectionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        updated_section = SectionService.update_section(
            section=section,
            name=serializer.validated_data.get('name'),
            is_active=serializer.validated_data.get('is_active'),
            actor=request.user,
            request=request
        )
        section_with_count = SectionService.get_sections_with_counts().filter(id=updated_section.id).first()
        return APIResponse(
            data=SectionSerializer(section_with_count or updated_section).data,
            message=f"Section '{updated_section.code}' updated successfully."
        )

    def delete(self, request, pk):
        section = get_object_or_404(Section, id=pk)
        code = section.code
        SectionService.delete_or_deactivate_section(section=section, actor=request.user, request=request)
        return APIResponse(
            message=f"Section '{code}' successfully deleted.",
            status_code=status.HTTP_200_OK
        )


class AdminStudentStatusView(APIView):
    """
    Admin Enable/Disable Student (POST /api/v1/admin/students/<id>/disable/ or /enable/)
    """
    permission_classes = [IsAuthenticated, IsAdmin, IsActiveUser]

    def post(self, request, pk, action=None):
        profile = get_object_or_404(
            StudentProfile.objects.select_related('user'),
            Q(id=pk) | Q(user__id=pk)
        )

        is_active = (action == 'enable')
        reason = request.data.get('reason', '').strip()
        StudentService.set_student_status(
            student_profile=profile,
            is_active=is_active,
            actor=request.user,
            reason=reason,
            request=request
        )

        status_text = "enabled" if is_active else "disabled"
        return APIResponse(
            data=StudentDetailSerializer(profile).data,
            message=f"Student account successfully {status_text}."
        )


class AdminStudentResetPasswordView(APIView):
    """
    Administrative Student Password Reset (POST /api/v1/admin/students/<uuid:pk>/reset-password/)
    Generates a cryptographically secure temporary password, invalidates current sessions,
    forces first_login_required on next login, creates an immutable audit event,
    and returns the temporary password once.
    """
    permission_classes = [IsAuthenticated, IsAdmin, IsActiveUser]

    def post(self, request, pk):
        profile = get_object_or_404(
            StudentProfile.objects.select_related('user'),
            Q(id=pk) | Q(user__id=pk)
        )
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        reason = serializer.validated_data['reason']
        temporary_password = serializer.validated_data.get('temporary_password')
        temp_password = AccountSecurityService.reset_student_password(
            student_profile=profile,
            temporary_password=temporary_password,
            reason=reason,
            actor=request.user,
            request=request
        )

        return APIResponse(
            data={
                "temporary_password": temp_password,
                "student": {
                    "id": str(profile.id),
                    "user_id": str(profile.user.id),
                    "email": profile.user.email,
                    "euid": profile.euid,
                    "roll_number": profile.roll_number
                }
            },
            message="Student password successfully reset. Share this temporary credential securely with the student. It will only be displayed once."
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


# ==============================================================================
# Administrator Management & Operational Dashboard Views
# ==============================================================================

class AdminDashboardOverviewView(APIView):
    """
    Consolidated Operational Overview Endpoint for Admin Dashboard (GET /api/v1/admin/overview/)
    Returns genuine platform counts, upcoming/recent assessments, and recent administrative activity.
    Guarded strictly by IsAdmin.
    """
    permission_classes = [IsAuthenticated, IsAdmin, IsActiveUser]

    def get(self, request):
        # 1. Operational Counts
        now = timezone.now()
        published_assessments = Assessment.objects.filter(status=AssessmentStatus.PUBLISHED)
        active_count = published_assessments.filter(start_datetime__lte=now, end_datetime__gte=now).count()
        upcoming_count = published_assessments.filter(start_datetime__gt=now).count()
        completed_count = Assessment.objects.filter(
            Q(status=AssessmentStatus.ARCHIVED) | Q(status=AssessmentStatus.PUBLISHED, end_datetime__lt=now)
        ).count()
        total_students = User.objects.filter(role=Role.STUDENT, is_active=True).count()

        # 2. Recent Assessments (up to 5)
        recent_assessments_qs = Assessment.objects.all().order_by('-created_at')[:5]
        recent_assessments = [
            {
                "id": str(a.id),
                "title": a.title,
                "status": a.status,
                "start_datetime": a.start_datetime.isoformat() if a.start_datetime else None,
                "end_datetime": a.end_datetime.isoformat() if a.end_datetime else None,
                "duration_minutes": a.duration_minutes,
                "candidates_count": getattr(a, 'assignments', None).count() if hasattr(a, 'assignments') else 0,
            }
            for a in recent_assessments_qs
        ]

        # 3. Upcoming Assessments (up to 4)
        upcoming_assessments_qs = published_assessments.filter(
            start_datetime__gt=now
        ).order_by('start_datetime')[:4]
        upcoming_assessments = [
            {
                "id": str(a.id),
                "title": a.title,
                "status": a.status,
                "start_datetime": a.start_datetime.isoformat() if a.start_datetime else None,
                "duration_minutes": a.duration_minutes,
            }
            for a in upcoming_assessments_qs
        ]

        # 4. Recent Operational Activity (from immutable AuditLog)
        audit_qs = AuditLog.objects.select_related('actor').exclude(
            action__in=['CSRF_INIT', 'LOGIN_RATE_LIMIT']
        ).order_by('-created_at')[:8]

        recent_activity = []
        for log in audit_qs:
            actor_name = log.actor.display_name if log.actor else "System"
            recent_activity.append({
                "id": str(log.id),
                "action": log.action,
                "actor_name": actor_name,
                "target_type": log.target_type or "",
                "target_id": log.target_id or "",
                "timestamp": log.created_at.isoformat(),
                "metadata": log.metadata or {},
            })

        return APIResponse(
            data={
                "metrics": {
                    "active_assessments": active_count,
                    "upcoming_assessments": upcoming_count,
                    "completed_assessments": completed_count,
                    "total_students": total_students,
                },
                "recent_assessments": recent_assessments,
                "upcoming_assessments": upcoming_assessments,
                "recent_activity": recent_activity,
            },
            message="Operational overview loaded successfully."
        )


class AdministratorListView(APIView):
    """
    Administrator Management Collection View (GET/POST /api/v1/admin/administrators/)
    Lists authorized administrators and creates new administrator accounts with server-assigned Admin IDs.
    Guarded strictly by IsAdmin.
    """
    permission_classes = [IsAuthenticated, IsAdmin, IsActiveUser]

    def get(self, request):
        admins = User.objects.filter(role=Role.ADMIN).order_by('created_at', 'id')
        serializer = AdministratorSerializer(admins, many=True)
        return APIResponse(
            data={"administrators": serializer.data, "count": admins.count()},
            message="Administrator accounts retrieved successfully."
        )

    def post(self, request):
        serializer = CreateAdministratorSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email']
        password = serializer.validated_data['password']
        display_name = serializer.validated_data.get('display_name', '').strip()
        is_active = serializer.validated_data['is_active']

        with transaction.atomic():
            admin_user = User.objects.create_user(
                email=email,
                password=password,
                role=Role.ADMIN,
                display_name=display_name or email.split('@')[0].replace('.', ' ').title(),
                is_active=is_active,
                is_staff=True,
                first_login_required=True,
            )

            AuditService.log(
                action="ADMIN_CREATED",
                actor=request.user,
                target_type="User",
                target_id=str(admin_user.id),
                metadata={
                    "actor_name": request.user.display_name,
                    "actor_admin_id": request.user.admin_id,
                    "target_identity": admin_user.admin_id,
                    "target_email": admin_user.email,
                    "target_role": Role.ADMIN,
                    "reason": "Administrator account creation",
                    "result": "SUCCESS"
                },
                request=request
            )

        return APIResponse(
            data=AdministratorSerializer(admin_user).data,
            message=f"Administrator account {admin_user.email} created successfully.",
            status_code=status.HTTP_201_CREATED
        )


class AdministratorDetailView(APIView):
    """
    Administrator Single Account Detail & Mutation View (GET / PATCH / DELETE /api/v1/admin/administrators/<uuid:pk>/)
    - GET: Retrieves administrator details.
    - PATCH: Updates administrator profile (Display Name, Email). Strictly forbids changing Admin ID, Role, or password hash.
    - DELETE: Deletes secondary administrator account. Primary Admin and self cannot be deleted.
    Guarded strictly by IsAdmin and IsActiveUser. Mutating actions strictly require Primary Admin authority.
    """
    permission_classes = [IsAuthenticated, IsAdmin, IsActiveUser]

    def get(self, request, pk):
        target_admin = get_object_or_404(User, pk=pk, role=Role.ADMIN)
        return APIResponse(
            data=AdministratorSerializer(target_admin).data,
            message="Administrator details retrieved."
        )

    def patch(self, request, pk):
        return APIResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            message="Administrator identity and account details are immutable. Editing is prohibited.",
            error={
                "code": "ADMIN_IDENTITY_IMMUTABLE",
                "message": "Administrator email, Admin ID, UUID, display name, and identity fields cannot be modified."
            }
        )

    def put(self, request, pk):
        return self.patch(request, pk)

    def delete(self, request, pk):
        target_admin = get_object_or_404(User, pk=pk, role=Role.ADMIN)

        if not getattr(request.user, 'is_primary_admin', False):
            return APIResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                message="Only the Primary Administrator can delete administrator accounts.",
                error={"code": "FORBIDDEN", "message": "Permission denied."}
            )

        if target_admin.is_primary_admin:
            return APIResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                message="The Primary Administrator account cannot be deleted.",
                error={"code": "PRIMARY_ADMIN_IMMUTABLE", "message": "The Primary Administrator account is permanently protected and cannot be deleted."}
            )

        if str(request.user.id) == str(target_admin.id):
            return APIResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                message="Cannot delete your own administrator account.",
                error={"code": "SELF_DELETION_PROHIBITED", "message": "Cannot delete your own administrator account."}
            )

        admin_email = target_admin.email
        admin_id = target_admin.admin_id
        AccountSecurityService.delete_administrator(target_admin=target_admin, actor=request.user, request=request)

        return APIResponse(
            message=f"Administrator account {admin_email} ({admin_id}) deleted successfully.",
            status_code=status.HTTP_200_OK
        )


class AdministratorStatusView(APIView):
    """
    Administrator Status Mutation Endpoint (POST /api/v1/admin/administrators/<uuid:pk>/status/)
    Enables/disables an administrator account. Rejects self-deactivation, primary admin deactivation,
    and deactivation of the last active administrator.
    """
    permission_classes = [IsAuthenticated, IsAdmin, IsActiveUser]

    def post(self, request, pk):
        target_admin = get_object_or_404(User, pk=pk, role=Role.ADMIN)

        if str(target_admin.id) == str(request.user.id):
            return APIResponse(
                message="Cannot deactivate your own administrator account.",
                status_code=status.HTTP_400_BAD_REQUEST,
                error={"code": "SELF_DEACTIVATION_PROHIBITED", "message": "Self-deactivation is rejected."}
            )

        if target_admin.is_primary_admin:
            return APIResponse(
                message="Cannot deactivate the Primary Administrator account.",
                status_code=status.HTTP_400_BAD_REQUEST,
                error={"code": "PRIMARY_ADMIN_IMMUTABLE", "message": "Primary Administrator account cannot be disabled."}
            )

        desired_status = request.data.get('is_active')
        will_deactivate = (desired_status is False) if desired_status is not None else target_admin.is_active
        if will_deactivate:
            active_count = User.objects.filter(role=Role.ADMIN, is_active=True).exclude(id=target_admin.id).count()
            if active_count == 0:
                return APIResponse(
                    message="Cannot deactivate the last active administrator account.",
                    status_code=status.HTTP_400_BAD_REQUEST,
                    error={"code": "LAST_ADMIN_PROTECTED", "message": "At least one active administrator must remain in the system."}
                )

        if desired_status is not None:
            target_admin.is_active = bool(desired_status)
        else:
            target_admin.is_active = not target_admin.is_active
        target_admin.save(update_fields=['is_active', 'updated_at'])

        reason = request.data.get('reason', '').strip()
        if not target_admin.is_active:
            AccountSecurityService.revoke_user_sessions(target_admin.id)

        action = "ADMIN_DISABLED" if not target_admin.is_active else "ADMIN_ENABLED"
        AuditService.log(
            action=action,
            actor=request.user,
            target_type="User",
            target_id=str(target_admin.id),
            metadata={
                "actor_name": request.user.display_name,
                "actor_admin_id": request.user.admin_id,
                "target_identity": target_admin.admin_id,
                "target_email": target_admin.email,
                "target_role": Role.ADMIN,
                "is_active": target_admin.is_active,
                "reason": reason or ("Administrator disabled." if not target_admin.is_active else "Administrator enabled."),
                "result": "SUCCESS"
            },
            request=request
        )

        return APIResponse(
            data=AdministratorSerializer(target_admin).data,
            message=f"Administrator status updated to {'Active' if target_admin.is_active else 'Disabled'}."
        )


class AdministratorResetPasswordView(APIView):
    """
    Administrative Password Reset for another Administrator (POST /api/v1/admin/administrators/<uuid:pk>/reset-password/)
    """
    permission_classes = [IsAuthenticated, IsAdmin, IsActiveUser]

    def post(self, request, pk):
        target_admin = get_object_or_404(User, pk=pk, role=Role.ADMIN)
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        reason = serializer.validated_data['reason']
        temporary_password = serializer.validated_data.get('temporary_password')
        temp_password = AccountSecurityService.reset_admin_password(
            target_admin=target_admin,
            temporary_password=temporary_password,
            reason=reason,
            actor=request.user,
            request=request
        )

        return APIResponse(
            data={
                "temporary_password": temp_password,
                "administrator": {
                    "id": str(target_admin.id),
                    "email": target_admin.email,
                    "admin_id": target_admin.admin_id
                }
            },
            message="Administrator password successfully reset. Provide this temporary credential securely. It will only be displayed once."
        )


class SecurityAuditLogView(APIView):
    """
    Security Audit Trail Endpoint (GET /api/v1/admin/audit-logs/)
    Provides append-only, immutable audit history with multi-parameter filtering.
    Strictly read-only and restricted to authorized Admins.
    """
    permission_classes = [IsAuthenticated, IsAdmin, IsActiveUser]

    def get(self, request):
        logs = AuditLog.objects.select_related('actor').all().order_by('-created_at')

        action = request.query_params.get('action')
        if action and action.upper() != 'ALL':
            logs = logs.filter(action__iexact=action)

        target_type = request.query_params.get('target_type')
        if target_type:
            logs = logs.filter(target_type__iexact=target_type)

        actor_id = request.query_params.get('actor_id')
        if actor_id:
            logs = logs.filter(actor__id=actor_id)

        role = request.query_params.get('role')
        if role and role.upper() != 'ALL':
            logs = logs.filter(Q(actor__role=role.upper()) | Q(metadata__target_role=role.upper()))

        result = request.query_params.get('result')
        if result and result.upper() != 'ALL':
            logs = logs.filter(metadata__result__iexact=result)

        date_from = request.query_params.get('date_from')
        if date_from:
            logs = logs.filter(created_at__gte=date_from)

        date_to = request.query_params.get('date_to')
        if date_to:
            logs = logs.filter(created_at__lte=date_to)

        search_query = request.query_params.get('search') or request.query_params.get('q')
        if search_query:
            sq = search_query.strip()
            logs = logs.filter(
                Q(actor__display_name__icontains=sq) |
                Q(actor__email__icontains=sq) |
                Q(actor__admin_id__icontains=sq) |
                Q(target_id__icontains=sq) |
                Q(metadata__target_identity__icontains=sq) |
                Q(metadata__target_email__icontains=sq) |
                Q(metadata__target_name__icontains=sq) |
                Q(metadata__target_roll_number__icontains=sq) |
                Q(metadata__actor_name__icontains=sq) |
                Q(metadata__actor_admin_id__icontains=sq) |
                Q(metadata__reason__icontains=sq)
            )

        limit = min(max(int(request.query_params.get('limit', 50)), 1), 100)
        offset = max(int(request.query_params.get('offset', 0)), 0)

        total_count = logs.count()
        paged_logs = logs[offset:offset + limit]

        serializer = AuditLogSerializer(paged_logs, many=True)
        return APIResponse(
            data={
                "logs": serializer.data,
                "total": total_count,
                "limit": limit,
                "offset": offset
            },
            message="Security audit logs retrieved successfully."
        )


class SessionStatusView(APIView):
    """
    Session Inactivity Status Endpoint (GET /api/v1/auth/session/status/)
    Returns server-authoritative remaining time, idle timeout, warning state,
    and active student assessment protection status.
    """
    permission_classes = [IsAuthenticated, IsActiveUser]

    def get(self, request):
        from apps.accounts.session_policy import SessionActivityPolicy
        status_data = SessionActivityPolicy.get_session_status(request)
        return APIResponse(
            data=status_data,
            message="Session status retrieved."
        )


class SessionRefreshView(APIView):
    """
    Session Inactivity Refresh Endpoint (POST /api/v1/auth/session/refresh/)
    Refreshes last_activity for a valid active session.
    Cannot revive expired sessions, bypass first-login, or alter assessment timers.
    """
    permission_classes = [IsAuthenticated, IsActiveUser]

    def post(self, request):
        from apps.accounts.session_policy import SessionActivityPolicy
        status_data = SessionActivityPolicy.refresh_session_activity(request)
        if status_data.get("is_expired"):
            return APIResponse(
                data=status_data,
                message="Session has expired and cannot be refreshed. Please sign in again.",
                status_code=status.HTTP_401_UNAUTHORIZED
            )
        return APIResponse(
            data=status_data,
            message="Session activity refreshed successfully."
        )


class AdminStudentBulkDeleteView(APIView):
    """
    Bulk delete student accounts.
    POST /api/v1/admin/students/bulk-delete/
    Body: { "ids": ["<uuid>", ...] }
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsAdmin]

    def post(self, request):
        serializer = BulkAccountDeleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        student_ids = [str(sid) for sid in serializer.validated_data['ids']]

        result = StudentService.bulk_delete_students(
            student_ids=student_ids,
            actor=request.user,
            request=request
        )
        return APIResponse(
            data=result,
            message=f"Processed {result['total']} student deletions: {result['success_count']} succeeded, {result['failure_count']} failed."
        )


class AdminAdministratorBulkDeleteView(APIView):
    """
    Bulk delete secondary administrator accounts.
    POST /api/v1/admin/administrators/bulk-delete/
    Body: { "ids": ["<uuid>", ...] }
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsAdmin]

    def post(self, request):
        if not getattr(request.user, 'is_primary_admin', False):
            return APIResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                message="Only the Primary Administrator can delete administrator accounts.",
                error={"code": "FORBIDDEN", "message": "Permission denied."}
            )

        serializer = BulkAccountDeleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        admin_ids = [str(aid) for aid in serializer.validated_data['ids']]

        result = AccountSecurityService.bulk_delete_administrators(
            admin_ids=admin_ids,
            actor=request.user,
            request=request
        )
        return APIResponse(
            data=result,
            message=f"Processed {result['total']} administrator deletions: {result['success_count']} succeeded, {result['failure_count']} failed."
        )


