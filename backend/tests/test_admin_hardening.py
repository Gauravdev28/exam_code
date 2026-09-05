import pytest
from concurrent.futures import ThreadPoolExecutor
from django.urls import reverse
from django.db import IntegrityError, transaction
from django.contrib.sessions.backends.db import SessionStore
from django.contrib.auth import authenticate
from rest_framework import status
from apps.accounts.models import User, Role, AuditLog, StudentProfile, AdminSequence
from apps.accounts.services import AdminIdService, AccountSecurityService
from django.core.exceptions import PermissionDenied


@pytest.fixture
def primary_admin(db):
    user = User.objects.create_superuser(
        email="gauravagldeveloper28@gmail.com",
        password="Gaurav@123",
        role=Role.ADMIN,
        admin_id="EUAD-GAURAV-099",
        display_name="Gaurav Agarwal",
        primary_admin_marker="PRIMARY"
    )
    return user


@pytest.fixture
def secondary_admin(db):
    user = User.objects.create_user(
        email="secondary.admin@codeguard.local",
        password="AdminPassword2026!",
        role=Role.ADMIN,
        display_name="Secondary Admin",
        is_staff=True,
        is_superuser=False
    )
    return user


@pytest.fixture
def test_student(db):
    user = User.objects.create_user(
        email="student.test@codeguard.local",
        password="StudentPassword123!",
        role=Role.STUDENT,
        display_name="Test Student"
    )
    profile = StudentProfile.objects.create(
        user=user,
        roll_number="CS2026-999",
        euid="STU-2026-9999",
        first_login_required=False
    )
    return user, profile


@pytest.mark.django_db(transaction=True)
class TestAdminIdentityAndSequence:
    def test_primary_admin_exact_identity(self, primary_admin):
        """Primary admin must be EUAD-GAURAV-099 with Gaurav Agarwal."""
        assert primary_admin.admin_id == "EUAD-GAURAV-099"
        assert primary_admin.display_name == "Gaurav Agarwal"
        assert primary_admin.role == Role.ADMIN

    def test_secondary_admin_unique_sequential_id(self, secondary_admin):
        """Secondary admin receives CG-ADM-00000X and CG-ADM-000001 is never generated."""
        assert secondary_admin.admin_id.startswith("CG-ADM-")
        assert secondary_admin.admin_id != "CG-ADM-000001"
        assert secondary_admin.admin_id != "EUAD-GAURAV-099"

    def test_duplicate_admin_id_prevented_by_database_constraint(self, primary_admin):
        """Database constraint unique_admin_id_for_admins strictly rejects duplicates."""
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                dup = User(
                    email="impostor@codeguard.local",
                    role=Role.ADMIN,
                    admin_id="EUAD-GAURAV-099"
                )
                dup.set_password("SomePass@123")
                dup.save()

    def test_cg_adm_000001_never_generated(self):
        """AdminIdService skips CG-ADM-000001 even if sequence starts from 1."""
        import uuid
        seq, _ = AdminSequence.objects.get_or_create(id=uuid.UUID('00000000-0000-0000-0000-000000000001'))
        seq.last_sequence = 0
        seq.save()

        id1 = AdminIdService.generate_next_admin_id()
        assert id1 == "CG-ADM-000002"
        assert id1 != "CG-ADM-000001"

    def test_admin_id_stable_on_email_or_name_change(self, secondary_admin):
        """Admin email, display name, and Admin ID must be strictly immutable after creation."""
        orig_id = secondary_admin.admin_id
        secondary_admin.email = "renamed.admin@codeguard.local"
        with pytest.raises(PermissionDenied, match="Administrator email address is strictly immutable"):
            secondary_admin.save()

        secondary_admin.refresh_from_db()
        assert secondary_admin.admin_id == orig_id
        assert secondary_admin.email == "secondary.admin@codeguard.local"

        secondary_admin.display_name = "Renamed Admin"
        with pytest.raises(PermissionDenied, match="Administrator display name is strictly immutable"):
            secondary_admin.save()

    def test_sequential_admin_id_generation_without_collisions(self):
        """Sequential calls to AdminIdService generate unique sequential IDs without collision."""
        generated = [AdminIdService.generate_next_admin_id() for _ in range(10)]

        assert len(generated) == len(set(generated)), f"Collisions detected: {generated}"
        for aid in generated:
            assert aid.startswith("CG-ADM-")
            assert aid != "CG-ADM-000001"
            assert aid != "EUAD-GAURAV-099"


@pytest.mark.django_db
class TestAuthenticationAndSessions:
    def test_primary_admin_login_succeeds(self, api_client, primary_admin):
        """Primary admin authenticates with email and intended password."""
        res = api_client.post(
            reverse('accounts:login'),
            {"identifier": "gauravagldeveloper28@gmail.com", "password": "Gaurav@123"},
            format='json'
        )
        assert res.status_code == status.HTTP_200_OK
        data = res.data['data']
        assert data['user']['admin_id'] == "EUAD-GAURAV-099"
        assert data['user']['role'] == "ADMIN"

    def test_invalid_password_fails(self, api_client, primary_admin):
        res = api_client.post(
            reverse('accounts:login'),
            {"identifier": "gauravagldeveloper28@gmail.com", "password": "WrongPassword"},
            format='json'
        )
        assert res.status_code == status.HTTP_401_UNAUTHORIZED

    def test_disabled_admin_cannot_login(self, api_client, secondary_admin):
        secondary_admin.is_active = False
        secondary_admin.save()

        res = api_client.post(
            reverse('accounts:login'),
            {"identifier": secondary_admin.email, "password": "AdminPassword2026!"},
            format='json'
        )
        assert res.status_code == status.HTTP_401_UNAUTHORIZED

    def test_session_restoration_via_current_user(self, api_client, primary_admin):
        """GET /auth/me/ restores authenticated user session."""
        api_client.force_authenticate(user=primary_admin)
        res = api_client.get(reverse('accounts:current-user'))
        assert res.status_code == status.HTTP_200_OK
        assert res.data['data']['admin_id'] == "EUAD-GAURAV-099"
        assert res.data['data']['email'] == primary_admin.email


@pytest.mark.django_db
class TestAdministrativePasswordReset:
    def test_admin_can_reset_student_password_manual(self, api_client, primary_admin, test_student):
        """Admin resets student password with custom temporary password and audit record."""
        student_user, profile = test_student
        api_client.force_authenticate(user=primary_admin)

        reset_url = reverse('accounts:admin-student-reset-password', kwargs={'pk': profile.id})
        payload = {
            "reason": "Student requested recovery before exam.",
            "temporary_password": "TempStudentPass123!",
            "confirm_temporary_password": "TempStudentPass123!"
        }
        res = api_client.post(reset_url, payload, format='json')
        assert res.status_code == status.HTTP_200_OK

        student_user.refresh_from_db()
        profile.refresh_from_db()
        assert student_user.check_password("TempStudentPass123!") is True
        assert student_user.first_login_required is True
        assert profile.first_login_required is True

        # Check Audit Log
        audit = AuditLog.objects.filter(action="PASSWORD_RESET", target_id=str(profile.id)).first()
        assert audit is not None
        assert audit.actor == primary_admin
        assert audit.metadata['reason'] == "Student requested recovery before exam."
        assert 'TempStudentPass123!' not in str(audit.metadata)
        assert 'password' not in audit.metadata

    def test_admin_can_reset_another_admin_password_auto(self, api_client, primary_admin, secondary_admin):
        """Primary admin resets secondary admin password with auto-generated temporary password."""
        api_client.force_authenticate(user=primary_admin)

        reset_url = reverse('accounts:admin-administrator-reset-password', kwargs={'pk': secondary_admin.id})
        payload = {"reason": "Routine administrator rotation."}
        res = api_client.post(reset_url, payload, format='json')
        assert res.status_code == status.HTTP_200_OK
        data = res.data['data']
        assert 'temporary_password' in data
        temp_pwd = data['temporary_password']
        assert len(temp_pwd) >= 12

        secondary_admin.refresh_from_db()
        assert secondary_admin.check_password(temp_pwd) is True
        assert secondary_admin.first_login_required is True

    def test_secondary_admin_cannot_reset_primary_admin(self, api_client, primary_admin, secondary_admin):
        """Secondary admin is strictly prohibited from resetting Primary Admin."""
        api_client.force_authenticate(user=secondary_admin)

        reset_url = reverse('accounts:admin-administrator-reset-password', kwargs={'pk': primary_admin.id})
        payload = {"reason": "Unauthorized attempt."}
        res = api_client.post(reset_url, payload, format='json')
        assert res.status_code in [status.HTTP_400_BAD_REQUEST, status.HTTP_403_FORBIDDEN]

    def test_self_reset_via_admin_management_rejected(self, api_client, primary_admin):
        """Admin cannot reset themselves via the administrative endpoint."""
        api_client.force_authenticate(user=primary_admin)

        reset_url = reverse('accounts:admin-administrator-reset-password', kwargs={'pk': primary_admin.id})
        payload = {"reason": "Self-reset attempt."}
        res = api_client.post(reset_url, payload, format='json')
        assert res.status_code == status.HTTP_400_BAD_REQUEST

    def test_weak_temporary_password_rejected(self, api_client, primary_admin, test_student):
        """Weak temporary passwords violating policy must be rejected."""
        _, profile = test_student
        api_client.force_authenticate(user=primary_admin)

        reset_url = reverse('accounts:admin-student-reset-password', kwargs={'pk': profile.id})
        payload = {
            "reason": "Test weak password",
            "temporary_password": "weak",
            "confirm_temporary_password": "weak"
        }
        res = api_client.post(reset_url, payload, format='json')
        assert res.status_code == status.HTTP_400_BAD_REQUEST

    def test_last_active_admin_deactivation_prohibited(self, api_client, primary_admin):
        """System strictly rejects deactivating the last active administrator."""
        # Ensure only 1 active admin exists
        User.objects.filter(role=Role.ADMIN).exclude(id=primary_admin.id).update(is_active=False)

        api_client.force_authenticate(user=primary_admin)
        status_url = reverse('accounts:admin-administrator-status', kwargs={'pk': primary_admin.id})
        res = api_client.post(status_url, {"is_active": False, "reason": "Deactivate self"}, format='json')
        assert res.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestStudentCredentialsAndOnboardingFlow:
    def test_manual_student_creation_credential_rule(self, api_client, primary_admin):
        """Admin enrolls student; EUID is CG-{ROLL}, temp password is roll number, first login required."""
        api_client.force_authenticate(user=primary_admin)

        url = reverse('accounts:admin-student-list')
        payload = {
            "email": "betn1.student@institution.edu",
            "roll_number": "BETN1AI25988"
        }
        res = api_client.post(url, payload, format='json')
        assert res.status_code == status.HTTP_201_CREATED
        data = res.data['data']

        assert data['roll_number'] == "BETN1AI25988"
        assert data['euid'] == "CG-BETN1AI25988"

        # Verify in database: password is NOT plaintext roll number, but matches when checked
        user = User.objects.get(email="betn1.student@institution.edu")
        profile = user.student_profile
        assert user.password != "BETN1AI25988"  # Must be hashed
        assert user.check_password("BETN1AI25988") is True
        assert user.first_login_required is True
        assert profile.first_login_required is True

    def test_student_login_by_email_and_temporary_password(self, api_client, primary_admin):
        """Student can authenticate with email and roll-number temporary password."""
        # Create student first
        api_client.force_authenticate(user=primary_admin)
        api_client.post(
            reverse('accounts:admin-student-list'),
            {"email": "gauravagl07.test@gmail.com", "roll_number": "BETN1AI25988"},
            format='json'
        )

        # Student logs in with email + roll number password
        api_client.logout()
        res = api_client.post(
            reverse('accounts:login'),
            {"identifier": "gauravagl07.test@gmail.com", "password": "BETN1AI25988"},
            format='json'
        )
        assert res.status_code == status.HTTP_200_OK
        data = res.data['data']
        assert data['user']['email'] == "gauravagl07.test@gmail.com"
        assert data['user']['first_login_required'] is True

    def test_student_login_by_euid_and_temporary_password(self, api_client, primary_admin):
        """Student can authenticate with EUID and roll-number temporary password."""
        api_client.force_authenticate(user=primary_admin)
        api_client.post(
            reverse('accounts:admin-student-list'),
            {"email": "euid.student@institution.edu", "roll_number": "BETN1AI25999"},
            format='json'
        )

        api_client.logout()
        res = api_client.post(
            reverse('accounts:login'),
            {"identifier": "CG-BETN1AI25999", "password": "BETN1AI25999"},
            format='json'
        )
        assert res.status_code == status.HTTP_200_OK
        data = res.data['data']
        assert data['user']['email'] == "euid.student@institution.edu"
        assert data['user']['first_login_required'] is True

    def test_student_cannot_login_with_roll_number_alone(self, api_client, primary_admin):
        """Roll Number alone is strictly prohibited as a login identifier."""
        api_client.force_authenticate(user=primary_admin)
        api_client.post(
            reverse('accounts:admin-student-list'),
            {"email": "rollonly.student@institution.edu", "roll_number": "BETN1AI25777"},
            format='json'
        )

        api_client.logout()
        res = api_client.post(
            reverse('accounts:login'),
            {"identifier": "BETN1AI25777", "password": "BETN1AI25777"},
            format='json'
        )
        assert res.status_code == status.HTTP_401_UNAUTHORIZED
        assert res.data['error']['code'] == "INVALID_CREDENTIALS"

    def test_first_login_password_change_flow(self, api_client, primary_admin):
        """Complete first-login flow: temporary login -> change password -> old stops, new works."""
        # 1. Admin creates student
        api_client.force_authenticate(user=primary_admin)
        api_client.post(
            reverse('accounts:admin-student-list'),
            {"email": "flow.student@institution.edu", "roll_number": "BETN1AI25666"},
            format='json'
        )

        # 2. Student logs in
        api_client.logout()
        login_res = api_client.post(
            reverse('accounts:login'),
            {"identifier": "flow.student@institution.edu", "password": "BETN1AI25666"},
            format='json'
        )
        assert login_res.status_code == status.HTTP_200_OK
        assert login_res.data['data']['user']['first_login_required'] is True

        # 3. Student changes password
        change_url = reverse('accounts:change-password')
        change_res = api_client.post(
            change_url,
            {
                "current_password": "BETN1AI25666",
                "new_password": "PermanentSecret2026!",
                "confirm_password": "PermanentSecret2026!"
            },
            format='json'
        )
        assert change_res.status_code == status.HTTP_200_OK
        assert change_res.data['data']['first_login_required'] is False

        # 4. Old password BETN1AI25666 no longer works
        api_client.logout()
        fail_res = api_client.post(
            reverse('accounts:login'),
            {"identifier": "flow.student@institution.edu", "password": "BETN1AI25666"},
            format='json'
        )
        assert fail_res.status_code == status.HTTP_401_UNAUTHORIZED

        # 5. New password works
        success_res = api_client.post(
            reverse('accounts:login'),
            {"identifier": "flow.student@institution.edu", "password": "PermanentSecret2026!"},
            format='json'
        )
        assert success_res.status_code == status.HTTP_200_OK
        assert success_res.data['data']['user']['first_login_required'] is False


@pytest.mark.django_db
class TestBulkStudentImportIntegrity:
    def test_bulk_import_uses_same_roll_number_password_rule(self, api_client, primary_admin):
        """Bulk student import calls StudentService and applies identical password=roll_number rules."""
        from apps.accounts.services import ImportService

        items = [
            {"roll_number": "BULK2026-001", "email": "bulk1@institution.edu"},
            {"roll_number": "BULK2026-002", "email": "bulk2@institution.edu"},
        ]

        result = ImportService.execute_import(items=items, actor=primary_admin, filename="roster.csv")
        assert result['created_count'] == 2
        assert result['failed_count'] == 0

        # Verify bulk student 1
        s1 = User.objects.get(email="bulk1@institution.edu")
        assert s1.check_password("BULK2026-001") is True
        assert s1.first_login_required is True
        assert s1.student_profile.euid == "CG-BULK2026-001"

        # Verify bulk student 2
        s2 = User.objects.get(email="bulk2@institution.edu")
        assert s2.check_password("BULK2026-002") is True
        assert s2.first_login_required is True
        assert s2.student_profile.euid == "CG-BULK2026-002"

    def test_bulk_import_duplicate_rolls_rejected(self, api_client, primary_admin):
        """Duplicate roll numbers in bulk import are caught and reported as failures."""
        from apps.accounts.services import ImportService

        # Pre-create student
        from apps.accounts.services import StudentService
        StudentService.create_student("existing@institution.edu", "DUPEROLL-01")

        items = [
            {"roll_number": "DUPEROLL-01", "email": "another@institution.edu"},
            {"roll_number": "NEWROLL-02", "email": "new@institution.edu"},
        ]

        result = ImportService.execute_import(items=items, actor=primary_admin, filename="roster.csv")
        assert result['created_count'] == 1
        assert result['failed_count'] == 1
        assert result['failed_rows'][0]['roll_number'] == "DUPEROLL-01"


@pytest.mark.django_db
class TestAdminCreationEndpointAndShubham:
    def test_create_admin_shubham_dhakrey_succeeds(self, api_client, primary_admin):
        """Administrator creation for Shubham Dhakrey succeeds with unique Admin ID and no server error."""
        api_client.force_authenticate(user=primary_admin)

        payload = {
            "display_name": "Shubham Dhakrey",
            "email": "shubham.test@gmail.com",
            "password": "Shubham@123",
            "confirm_password": "Shubham@123",
            "is_active": True
        }
        res = api_client.post(reverse('accounts:admin-administrator-list'), payload, format='json')
        assert res.status_code == status.HTTP_201_CREATED
        data = res.data['data']

        assert data['email'] == "shubham.test@gmail.com"
        assert data['display_name'] == "Shubham Dhakrey"
        assert data['admin_id'].startswith("CG-ADM-")
        assert data['admin_id'] != "CG-ADM-000001"
        assert data['admin_id'] != "EUAD-GAURAV-099"

        # Verify login
        api_client.logout()
        login_res = api_client.post(
            reverse('accounts:login'),
            {"identifier": "shubham.test@gmail.com", "password": "Shubham@123"},
            format='json'
        )
        assert login_res.status_code == status.HTTP_200_OK
        assert login_res.data['data']['user']['display_name'] == "Shubham Dhakrey"

