import pytest
from django.urls import reverse
from rest_framework import status
from apps.accounts.models import User, Role
from apps.assessments.models import Assessment, AssessmentStatus
from django.utils import timezone
from datetime import timedelta

@pytest.mark.django_db
class TestAdminDashboardOverview:
    def test_admin_overview_metrics_success(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)

        # Create student
        User.objects.create_user(
            email="student.test@institution.edu",
            password="Password@123",
            role=Role.STUDENT,
            is_active=True
        )

        # Create a published assessment in the future (upcoming)
        now = timezone.now()
        Assessment.objects.create(
            title="Algorithms Midterm",
            description="Midterm test",
            status=AssessmentStatus.PUBLISHED,
            start_datetime=now + timedelta(days=2),
            end_datetime=now + timedelta(days=2, hours=2),
            duration_minutes=90,
            total_points=100,
            created_by=admin_user,
        )

        # Create an active assessment
        Assessment.objects.create(
            title="Python Live Exam",
            description="Live exam test",
            status=AssessmentStatus.PUBLISHED,
            start_datetime=now - timedelta(minutes=10),
            end_datetime=now + timedelta(hours=1),
            duration_minutes=60,
            total_points=50,
            created_by=admin_user,
        )

        response = api_client.get(reverse('accounts:admin-dashboard-overview'))
        assert response.status_code == status.HTTP_200_OK
        data = response.data['data']

        assert 'metrics' in data
        assert data['metrics']['active_assessments'] == 1
        assert data['metrics']['upcoming_assessments'] == 1
        assert data['metrics']['total_students'] >= 1
        assert len(data['recent_assessments']) >= 2
        assert len(data['upcoming_assessments']) == 1
        assert 'recent_activity' in data

    def test_admin_overview_forbidden_for_student(self, api_client):
        student = User.objects.create_user(
            email="regular.student@test.edu",
            password="Password@123",
            role=Role.STUDENT
        )
        api_client.force_authenticate(user=student)
        response = api_client.get(reverse('accounts:admin-dashboard-overview'))
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_admin_overview_unauthenticated(self, api_client):
        response = api_client.get(reverse('accounts:admin-dashboard-overview'))
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]


@pytest.mark.django_db
class TestAdministratorManagement:
    def test_admin_list_and_identity_formatting(self, api_client, admin_user):
        primary_admin = User.objects.create_user(
            email="gauravagldeveloper28@gmail.com",
            password="Password@123",
            role=Role.ADMIN
        )
        api_client.force_authenticate(user=primary_admin)

        response = api_client.get(reverse('accounts:admin-administrator-list'))
        assert response.status_code == status.HTTP_200_OK
        data = response.data['data']
        assert 'administrators' in data
        assert len(data['administrators']) >= 2

        primary_in_list = next((a for a in data['administrators'] if a['email'] == "gauravagldeveloper28@gmail.com"), None)
        assert primary_in_list is not None
        assert primary_in_list['admin_id'] == "EUAD-GAURAV-099"
        assert primary_in_list['role'] == Role.ADMIN
        assert primary_in_list['display_name'] == "Gaurav Agarwal"

        secondary_in_list = next((a for a in data['administrators'] if a['email'] == admin_user.email), None)
        assert secondary_in_list is not None
        assert secondary_in_list['admin_id'].startswith("CG-ADM-")


    def test_development_admin_exact_admin_id(self, api_client):
        dev_admin = User.objects.create_user(
            email="gauravagldeveloper28@gmail.com",
            password="Password@123",
            role=Role.ADMIN
        )
        assert dev_admin.admin_id == "EUAD-GAURAV-099"
        assert dev_admin.display_name == "Gaurav Agarwal"
        assert dev_admin.first_name == "Gaurav"

        api_client.force_authenticate(user=dev_admin)
        res = api_client.get(reverse('accounts:current-user'))
        assert res.status_code == status.HTTP_200_OK
        assert res.data['data']['admin_id'] == "EUAD-GAURAV-099"
        assert res.data['data']['role'] == "ADMIN"

    def test_create_administrator(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)

        payload = {
            "email": "exam.coordinator@institution.edu",
            "password": "SecurePassword@123",
            "is_active": True,
        }
        response = api_client.post(reverse('accounts:admin-administrator-list'), payload, format='json')
        assert response.status_code == status.HTTP_201_CREATED
        created = response.data['data']

        assert created['email'] == "exam.coordinator@institution.edu"
        assert created['admin_id'].startswith("CG-ADM-")
        assert created['role'] == Role.ADMIN

        # Verify in database
        db_user = User.objects.get(email="exam.coordinator@institution.edu")
        assert db_user.role == Role.ADMIN
        assert db_user.check_password("SecurePassword@123") is True

    def test_create_administrator_duplicate_email(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        payload = {
            "email": admin_user.email,
            "password": "SecurePassword@123",
        }
        response = api_client.post(reverse('accounts:admin-administrator-list'), payload, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_student_cannot_manage_administrators(self, api_client):
        student = User.objects.create_user(
            email="unauth.student@test.edu",
            password="Password@123",
            role=Role.STUDENT
        )
        api_client.force_authenticate(user=student)
        response = api_client.get(reverse('accounts:admin-administrator-list'))
        assert response.status_code == status.HTTP_403_FORBIDDEN

        response = api_client.post(reverse('accounts:admin-administrator-list'), {
            "email": "hacker@test.edu",
            "password": "Password@123",
        }, format='json')
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_toggle_administrator_status(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)

        # Create target admin
        target = User.objects.create_user(
            email="target.admin@test.edu",
            password="Password@123",
            role=Role.ADMIN,
            is_active=True
        )

        url = reverse('accounts:admin-administrator-status', kwargs={'pk': target.id})
        
        # Deactivate
        response = api_client.post(url, {"is_active": False}, format='json')
        assert response.status_code == status.HTTP_200_OK
        target.refresh_from_db()
        assert target.is_active is False

        # Reactivate
        response = api_client.post(url, {"is_active": True}, format='json')
        assert response.status_code == status.HTTP_200_OK
        target.refresh_from_db()
        assert target.is_active is True

    def test_self_deactivation_rejected(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        url = reverse('accounts:admin-administrator-status', kwargs={'pk': admin_user.id})
        response = api_client.post(url, {"is_active": False}, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        admin_user.refresh_from_db()
        assert admin_user.is_active is True

    def test_primary_admin_deactivation_rejected(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        primary = User.objects.create_superuser(
            email="gauravagldeveloper28@gmail.com",
            password="SecureAdminPass123!",
            role=Role.ADMIN
        )
        assert primary.admin_id == "EUAD-GAURAV-099"
        url = reverse('accounts:admin-administrator-status', kwargs={'pk': primary.id})
        response = api_client.post(url, {"is_active": False}, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        primary.refresh_from_db()
        assert primary.is_active is True


@pytest.mark.django_db
class TestAccountSecurityAndAuditTrail:
    """
    Test suite for administrative password resets, account disabling, and immutable audit ledger.
    """

    def test_admin_can_reset_student_password(self, api_client, admin_user):
        from apps.accounts.models import StudentProfile, AuditLog
        from django.core.exceptions import PermissionDenied

        student_user = User.objects.create_user(
            email="reset.student@institution.edu",
            password="OldPassword123!",
            role=Role.STUDENT
        )
        profile = StudentProfile.objects.create(
            user=student_user,
            roll_number="CS2026RESET",
            euid="CG-CS2026RESET",
            first_login_required=False
        )

        api_client.force_authenticate(user=admin_user)
        reset_url = reverse('accounts:admin-student-reset-password', kwargs={'pk': profile.id})

        # 1. Reset without reason fails (validation error)
        res_fail = api_client.post(reset_url, {"reason": ""})
        assert res_fail.status_code == status.HTTP_400_BAD_REQUEST

        # 2. Reset with reason succeeds
        res = api_client.post(reset_url, {"reason": "Student forgot password for midterm."})
        assert res.status_code == status.HTTP_200_OK
        data = res.data['data']
        assert 'temporary_password' in data
        temp_pwd = data['temporary_password']
        assert len(temp_pwd) >= 12

        # 3. Target student updated in DB
        student_user.refresh_from_db()
        profile.refresh_from_db()
        assert student_user.check_password("OldPassword123!") is False
        assert student_user.check_password(temp_pwd) is True
        assert profile.first_login_required is True
        assert student_user.first_login_required is True

        # 4. Audit Log entry created
        audit_log = AuditLog.objects.filter(action="PASSWORD_RESET", target_id=str(profile.id)).first()
        assert audit_log is not None
        assert audit_log.actor == admin_user
        assert audit_log.metadata['reason'] == "Student forgot password for midterm."
        assert audit_log.metadata['target_identity'] == "CG-CS2026RESET"
        assert audit_log.metadata['target_email'] == "reset.student@institution.edu"
        assert audit_log.metadata['result'] == "SUCCESS"

        # 5. Verify NO password or token in audit log or metadata
        audit_str = str(audit_log.metadata)
        assert temp_pwd not in audit_str
        assert "password" not in audit_log.metadata
        assert "token" not in audit_log.metadata

        # 6. Verify audit log immutability
        with pytest.raises(PermissionDenied):
            audit_log.action = "TAMPERED"
            audit_log.save()

        with pytest.raises(PermissionDenied):
            audit_log.delete()

    def test_student_and_proctor_cannot_reset_passwords(self, api_client):
        from apps.accounts.models import StudentProfile

        student = User.objects.create_user(
            email="s1@institution.edu",
            password="Password123!",
            role=Role.STUDENT
        )
        target_student = User.objects.create_user(
            email="s2@institution.edu",
            password="Password123!",
            role=Role.STUDENT
        )
        target_profile = StudentProfile.objects.create(
            user=target_student,
            roll_number="CS2026S2",
            euid="CG-CS2026S2"
        )
        proctor = User.objects.create_user(
            email="proctor.auth@institution.edu",
            password="Password123!",
            role=Role.PROCTOR
        )

        reset_url = reverse('accounts:admin-student-reset-password', kwargs={'pk': target_profile.id})

        # Student cannot reset
        api_client.force_authenticate(user=student)
        res = api_client.post(reset_url, {"reason": "Malicious attempt"})
        assert res.status_code == status.HTTP_403_FORBIDDEN

        # Proctor cannot reset
        api_client.force_authenticate(user=proctor)
        res = api_client.post(reset_url, {"reason": "Malicious attempt"})
        assert res.status_code == status.HTTP_403_FORBIDDEN

    def test_admin_can_reset_another_admin_password(self, api_client, admin_user):
        target_admin = User.objects.create_user(
            email="admin2@institution.edu",
            password="OldAdminPass123!",
            role=Role.ADMIN
        )
        api_client.force_authenticate(user=admin_user)
        reset_url = reverse('accounts:admin-administrator-reset-password', kwargs={'pk': target_admin.id})

        res = api_client.post(reset_url, {"reason": "Administrative recovery"})
        assert res.status_code == status.HTTP_200_OK
        data = res.data['data']
        assert 'temporary_password' in data
        temp_pwd = data['temporary_password']

        target_admin.refresh_from_db()
        assert target_admin.check_password("OldAdminPass123!") is False
        assert target_admin.check_password(temp_pwd) is True
        assert target_admin.first_login_required is True

    def test_disable_and_enable_student_with_reason(self, api_client, admin_user):
        from apps.accounts.models import StudentProfile, AuditLog

        student_user = User.objects.create_user(
            email="suspend.student@institution.edu",
            password="Password123!",
            role=Role.STUDENT,
            is_active=True
        )
        profile = StudentProfile.objects.create(
            user=student_user,
            roll_number="CSSUSPEND",
            euid="CG-CSSUSPEND"
        )

        api_client.force_authenticate(user=admin_user)

        # 1. Disable student
        disable_url = reverse('accounts:admin-student-disable', kwargs={'pk': profile.id})
        res_dis = api_client.post(disable_url, {"reason": "Academic integrity violation investigation."})
        assert res_dis.status_code == status.HTTP_200_OK
        student_user.refresh_from_db()
        assert student_user.is_active is False

        # 2. Disabled student cannot log in
        login_res = api_client.post(reverse('accounts:login'), {
            "identifier": "suspend.student@institution.edu",
            "password": "Password123!"
        })
        assert login_res.status_code == status.HTTP_401_UNAUTHORIZED
        assert login_res.json()['error']['code'] == 'ACCOUNT_DISABLED'

        # 3. Enable student
        enable_url = reverse('accounts:admin-student-enable', kwargs={'pk': profile.id})
        res_en = api_client.post(enable_url, {"reason": "Reinstated after review."})
        assert res_en.status_code == status.HTTP_200_OK
        student_user.refresh_from_db()
        assert student_user.is_active is True

        # 4. Verify Audit Logs
        assert AuditLog.objects.filter(action="STUDENT_DISABLED", target_id=str(profile.id)).exists()
        assert AuditLog.objects.filter(action="STUDENT_ENABLED", target_id=str(profile.id)).exists()

    def test_security_audit_log_endpoint_filtering_and_rbacs(self, api_client, admin_user):
        from apps.accounts.models import AuditLog

        AuditLog.objects.create(
            actor=admin_user,
            action="PASSWORD_RESET",
            target_type="StudentProfile",
            target_id="test-target-1",
            metadata={"reason": "Forgot password", "result": "SUCCESS"}
        )

        api_client.force_authenticate(user=admin_user)
        audit_url = reverse('accounts:admin-security-audit-logs')

        res = api_client.get(audit_url)
        assert res.status_code == status.HTTP_200_OK
        data = res.data['data']
        assert 'logs' in data
        assert data['total'] >= 1

        # Test filtering by action
        res_filt = api_client.get(f"{audit_url}?action=PASSWORD_RESET")
        assert res_filt.status_code == status.HTTP_200_OK
        assert all(log['action'] == "PASSWORD_RESET" for log in res_filt.data['data']['logs'])

        # Test student forbidden
        student = User.objects.create_user(
            email="unauth.student.audit@test.edu",
            password="Password123!",
            role=Role.STUDENT
        )
        api_client.force_authenticate(user=student)
        res_forbidden = api_client.get(audit_url)
        assert res_forbidden.status_code == status.HTTP_403_FORBIDDEN

