from datetime import timedelta
from django.utils import timezone
import pytest
from rest_framework.test import APIClient
from rest_framework import status
from apps.accounts.models import User, StudentProfile, Role
from apps.assessments.models import Assessment, AssessmentStatus
from apps.invigilation.models import ProctorAssignment
from apps.invigilation.services import ProctorRosterService
from apps.accounts.serializers import UserSerializer
from rest_framework.exceptions import ValidationError as DRFValidationError


@pytest.fixture
def admin_user(db):
    return User.objects.create_superuser(
        email="admin.sec@codeguard.local",
        password="AdminPassword2026!",
        role=Role.ADMIN
    )


@pytest.fixture
def student_user(db):
    user = User.objects.create_user(
        email="student.sec@codeguard.local",
        password="StudentPassword2026!",
        role=Role.STUDENT
    )
    StudentProfile.objects.create(
        user=user,
        roll_number="SEC001",
        euid="CG-SEC001",
        first_login_required=False
    )
    return user


def make_assessment(admin_user, title="Security Assessment"):
    now = timezone.now()
    return Assessment.objects.create(
        title=title,
        description="Assessment for role security testing",
        status=AssessmentStatus.PUBLISHED,
        start_datetime=now - timedelta(hours=1),
        end_datetime=now + timedelta(hours=2),
        duration_minutes=60,
        created_by=admin_user
    )


@pytest.mark.django_db
class TestRoleAuthorizationHardening:
    """
    Security verification tests for role preservation, assessment-scoped assignment authorization,
    CSRF token initialization, and session restoration.
    """

    def test_admin_with_proctor_assignment_retains_admin_role(self, admin_user):
        """
        An ADMIN user assigned to an assessment retains their authoritative ADMIN role.
        ProctorAssignment never promotes, alters, or degrades the user's role.
        """
        assessment = make_assessment(admin_user, "Systems Security Exam")

        assignment = ProctorAssignment.objects.create(
            proctor=admin_user,
            assessment=assessment,
            assigned_by=admin_user,
            is_active=True
        )

        assert assignment.proctor.role == Role.ADMIN
        assert admin_user.role == Role.ADMIN

        # Verify serializer exposes authoritative role
        serialized = UserSerializer(admin_user).data
        assert serialized['role'] == Role.ADMIN

    def test_proctor_without_assignment_retains_proctor_role(self):
        """
        A user with PROCTOR identity retains role PROCTOR even when not assigned to any assessment.
        """
        proctor = User.objects.create_user(
            email="proctor.alpha@codeguard.local",
            password="SecurePassword2026!",
            role="PROCTOR"
        )

        assert proctor.role == "PROCTOR"
        serialized = UserSerializer(proctor).data
        assert serialized['role'] == "PROCTOR"

    def test_unassigned_proctor_cannot_access_assessment_invigilation(self, admin_user):
        """
        A PROCTOR user without an active ProctorAssignment for an assessment receives HTTP 403
        when attempting to access assessment-scoped invigilation endpoints.
        """
        assessment = make_assessment(admin_user, "Database Architecture")

        unassigned_proctor = User.objects.create_user(
            email="proctor.unassigned@codeguard.local",
            password="SecurePassword2026!",
            role="PROCTOR"
        )

        client = APIClient()
        client.force_authenticate(user=unassigned_proctor)

        url = f"/api/v1/proctor/assessments/{assessment.id}/live-roster/"
        response = client.get(url)

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_student_cannot_be_assigned_as_proctor(self, admin_user, student_user):
        """
        Attempting to assign a student as a proctor is strictly rejected by ProctorRosterService.
        """
        assessment = make_assessment(admin_user, "Algorithm Design")

        with pytest.raises(DRFValidationError) as excinfo:
            ProctorRosterService.assign_proctor(
                assessment_id=str(assessment.id),
                proctor_user=student_user,
                assigned_by_user=admin_user
            )

        assert "User must have PROCTOR or ADMIN role" in str(excinfo.value)

    def test_student_cannot_access_admin_endpoints(self, student_user):
        """
        Students receive HTTP 403 on administrative endpoints.
        """
        client = APIClient()
        client.force_authenticate(user=student_user)

        response = client.get("/api/v1/admin/students/")
        assert response.status_code == status.HTTP_403_FORBIDDEN

        response = client.get("/api/v1/admin/questions/")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_proctor_cannot_access_admin_student_management(self):
        """
        Proctors cannot access admin-only student management endpoints.
        """
        proctor = User.objects.create_user(
            email="proctor.beta@codeguard.local",
            password="SecurePassword2026!",
            role="PROCTOR"
        )

        client = APIClient()
        client.force_authenticate(user=proctor)

        response = client.get("/api/v1/admin/students/")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_csrf_token_endpoint_returns_token_and_sets_cookie(self):
        """
        GET /api/v1/auth/csrf/ is accessible to unauthenticated clients, returns a valid CSRF token,
        and ensures the csrftoken cookie is attached.
        """
        client = APIClient()
        response = client.get("/api/v1/auth/csrf/")

        assert response.status_code == status.HTTP_200_OK
        assert "csrf_token" in response.data.get("data", {})
        assert len(response.data["data"]["csrf_token"]) > 10
        assert "csrftoken" in response.cookies

    def test_login_with_euid_identifier_succeeds(self):
        """
        Students can authenticate using their EUID (e.g. CG-BETN1AI25001) as the login identifier.
        """
        user = User.objects.create_user(
            email="candidate.euid@codeguard.local",
            password="CandidatePass2026!",
            role=Role.STUDENT
        )
        StudentProfile.objects.create(
            user=user,
            roll_number="25001",
            euid="CG-BETN1AI25001",
            first_login_required=False
        )

        client = APIClient()
        response = client.post("/api/v1/auth/login/", {
            "identifier": "CG-BETN1AI25001",
            "password": "CandidatePass2026!"
        })

        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"]["user"]["email"] == "candidate.euid@codeguard.local"
        assert response.data["data"]["user"]["role"] == Role.STUDENT

    def test_first_login_enforcement_blocks_student_until_password_changed(self, admin_user):
        """
        A candidate with first_login_required=True is blocked from assessment APIs
        until POST /api/v1/auth/change-password/ succeeds.
        """
        user = User.objects.create_user(
            email="firstlogin.student@codeguard.local",
            password="TemporaryPassword2026!",
            role=Role.STUDENT
        )
        profile = StudentProfile.objects.create(
            user=user,
            roll_number="99001",
            euid="CG-TEMP99001",
            first_login_required=True
        )

        assessment = make_assessment(admin_user, "Compiler Optimization")

        client = APIClient()
        # Authenticate with temporary password
        login_res = client.post("/api/v1/auth/login/", {
            "identifier": "CG-TEMP99001",
            "password": "TemporaryPassword2026!"
        })
        assert login_res.status_code == status.HTTP_200_OK
        assert login_res.data["data"]["user"]["first_login_required"] is True

        # Attempt to access assessment API -> blocked with 403
        attempt_res = client.post(f"/api/v1/student/assessments/{assessment.id}/start/")
        assert attempt_res.status_code == status.HTTP_403_FORBIDDEN
        assert attempt_res.data["error"]["code"] == "PERMISSION_DENIED"

        # Change password
        change_res = client.post("/api/v1/auth/change-password/", {
            "current_password": "TemporaryPassword2026!",
            "new_password": "NewPermPassword2026!#",
            "confirm_password": "NewPermPassword2026!#"
        })
        assert change_res.status_code == status.HTTP_200_OK

        profile.refresh_from_db()
        assert profile.first_login_required is False

    def test_session_restore_via_me_endpoint(self, admin_user):
        """
        GET /api/v1/auth/me/ returns authenticated user profile and authoritative role.
        """
        client = APIClient()
        client.force_authenticate(user=admin_user)

        response = client.get("/api/v1/auth/me/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"]["email"] == admin_user.email
        assert response.data["data"]["role"] == Role.ADMIN
