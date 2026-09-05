import uuid
import pytest
from django.urls import reverse
from django.core.exceptions import PermissionDenied
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient

from django.utils import timezone
from apps.accounts.models import Role, AuditLog, StudentProfile, AdminSequence
from apps.accounts.services import AccountSecurityService, StudentService
from apps.assessments.models import Assessment, AssessmentSnapshot, TestAttempt, AttemptStatus
from apps.retention.models import LegalHold, LegalHoldStatus, LegalHoldScope, RetentionPolicy, PolicyScope, RetentionRecord, PurgeState

User = get_user_model()


@pytest.fixture
def primary_admin(db):
    """Authoritative Primary Administrator fixture"""
    admin = User.objects.filter(admin_id='EUAD-GAURAV-099').first()
    if not admin:
        admin = User.objects.create_user(
            email='gauravagldeveloper28@gmail.com',
            password='Password123!',
            role=Role.ADMIN,
            admin_id='EUAD-GAURAV-099',
            display_name='Gaurav Agarwal',
            is_staff=True,
            is_superuser=True,
            primary_admin_marker='PRIMARY',
        )
    return admin


@pytest.fixture
def secondary_admin(db):
    """Secondary Administrator fixture"""
    return User.objects.create_user(
        email='secondary.admin@codeguard.local',
        password='Password123!',
        role=Role.ADMIN,
        display_name='Secondary Admin',
        is_staff=True
    )


@pytest.fixture
def student_user(db):
    """Student with profile fixture"""
    user, profile = StudentService.create_student(
        email='test.lifecycle.student@university.edu',
        roll_number='CS2026TEST01'
    )
    return user, profile


@pytest.fixture
def proctor_user(db):
    """Proctor fixture"""
    return User.objects.create_user(
        email='test.proctor@codeguard.local',
        password='Password123!',
        role=Role.PROCTOR,
        display_name='Test Proctor'
    )


# ==============================================================================
# 1. Primary Admin Protection & Authority Tests
# ==============================================================================

@pytest.mark.django_db
class TestPrimaryAdminAuthority:
    def test_primary_admin_identity_rule(self, primary_admin, secondary_admin):
        assert primary_admin.is_primary_admin is True
        assert primary_admin.admin_id == 'EUAD-GAURAV-099'
        assert secondary_admin.is_primary_admin is False
        assert secondary_admin.admin_id.startswith('CG-ADM-')

    def test_primary_admin_model_delete_blocked(self, primary_admin):
        with pytest.raises(PermissionDenied, match="Primary Administrator account is permanently protected"):
            primary_admin.delete()

    def test_primary_admin_api_delete_blocked(self, primary_admin):
        client = APIClient()
        client.force_authenticate(user=primary_admin)
        url = reverse('accounts:admin-administrator-detail', kwargs={'pk': primary_admin.id})
        response = client.delete(url)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "PRIMARY_ADMIN_IMMUTABLE" in str(response.data)

    def test_primary_admin_api_deactivate_blocked(self, primary_admin, secondary_admin):
        client = APIClient()
        client.force_authenticate(user=secondary_admin)
        url = reverse('accounts:admin-administrator-status', kwargs={'pk': primary_admin.id})
        response = client.post(url, {'is_active': False, 'reason': 'Testing deactivation'})
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "PRIMARY_ADMIN_IMMUTABLE" in str(response.data)


# ==============================================================================
# 2. Administrator Lifecycle: Detail, Update, Delete & Permissions
# ==============================================================================

@pytest.mark.django_db
class TestAdministratorLifecycle:
    def test_get_administrator_detail(self, primary_admin, secondary_admin):
        client = APIClient()
        client.force_authenticate(user=primary_admin)
        url = reverse('accounts:admin-administrator-detail', kwargs={'pk': secondary_admin.id})
        response = client.get(url)
        assert response.status_code == status.HTTP_200_OK
        data = response.data['data']
        assert data['admin_id'] == secondary_admin.admin_id
        assert data['email'] == secondary_admin.email
        assert data['is_primary'] is False

    def test_primary_admin_updates_secondary_admin_details(self, primary_admin, secondary_admin):
        """Administrator identity is immutable; PATCH requests are rejected with 400."""
        client = APIClient()
        client.force_authenticate(user=primary_admin)
        url = reverse('accounts:admin-administrator-detail', kwargs={'pk': secondary_admin.id})

        response = client.patch(url, {
            'display_name': 'Updated Secondary Name',
            'email': 'updated.sec@codeguard.local'
        })
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "ADMIN_IDENTITY_IMMUTABLE" in str(response.data)

    def test_secondary_admin_cannot_update_other_admins(self, secondary_admin):
        """Secondary admin PATCH requests are rejected by identity immutability."""
        other_admin = User.objects.create_user(
            email='other.admin@codeguard.local',
            password='Password123!',
            role=Role.ADMIN
        )
        client = APIClient()
        client.force_authenticate(user=secondary_admin)
        url = reverse('accounts:admin-administrator-detail', kwargs={'pk': other_admin.id})
        response = client.patch(url, {'display_name': 'Hacked Name'})
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "ADMIN_IDENTITY_IMMUTABLE" in str(response.data)

    def test_secondary_admin_cannot_delete_other_admins(self, secondary_admin):
        other_admin = User.objects.create_user(
            email='other.del@codeguard.local',
            password='Password123!',
            role=Role.ADMIN
        )
        client = APIClient()
        client.force_authenticate(user=secondary_admin)
        url = reverse('accounts:admin-administrator-detail', kwargs={'pk': other_admin.id})
        response = client.delete(url)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_primary_admin_deletes_clean_secondary_admin(self, primary_admin, secondary_admin):
        client = APIClient()
        client.force_authenticate(user=primary_admin)
        url = reverse('accounts:admin-administrator-detail', kwargs={'pk': secondary_admin.id})
        admin_id = secondary_admin.admin_id
        admin_email = secondary_admin.email

        response = client.delete(url)
        assert response.status_code == status.HTTP_200_OK
        assert not User.objects.filter(id=secondary_admin.id).exists()

        # Audit history preserved with snapshots!
        log = AuditLog.objects.filter(action='ADMIN_DELETED', target_id=str(secondary_admin.id)).first()
        assert log is not None
        assert log.metadata['target_identity'] == admin_id
        assert log.metadata['target_email'] == admin_email
        assert log.metadata['actor_admin_id'] == 'EUAD-GAURAV-099'

    def test_self_delete_rejected(self, primary_admin, secondary_admin):
        client = APIClient()
        client.force_authenticate(user=secondary_admin)
        url = reverse('accounts:admin-administrator-detail', kwargs={'pk': secondary_admin.id})
        response = client.delete(url)
        assert response.status_code == status.HTTP_403_FORBIDDEN


# ==============================================================================
# 3. Student Lifecycle & Phase 9 Retention Interaction Tests
# ==============================================================================

@pytest.mark.django_db
class TestStudentLifecycleAndRetention:
    def test_delete_clean_student_succeeds(self, primary_admin, student_user):
        user, profile = student_user
        client = APIClient()
        client.force_authenticate(user=primary_admin)
        url = reverse('accounts:admin-student-detail', kwargs={'pk': profile.id})

        euid = profile.euid
        roll = profile.roll_number
        user_id = user.id

        response = client.delete(url)
        assert response.status_code == status.HTTP_200_OK
        assert not User.objects.filter(id=user_id).exists()
        assert not StudentProfile.objects.filter(id=profile.id).exists()

        # Audit log preserved with immutable snapshots
        log = AuditLog.objects.filter(action='STUDENT_DELETED', target_id=str(profile.id)).first()
        assert log is not None
        assert log.metadata['target_identity'] == euid
        assert log.metadata['target_roll_number'] == roll

    def test_delete_student_blocked_when_test_attempt_exists(self, primary_admin, student_user):
        user, profile = student_user

        # Create assessment and test attempt
        now = timezone.now()
        assessment = Assessment.objects.create(
            title="Retention Test Exam",
            description="Retention Test Exam Description",
            created_by=primary_admin,
            duration_minutes=60,
            start_datetime=now,
            end_datetime=now + timezone.timedelta(days=1)
        )
        snapshot = AssessmentSnapshot.objects.create(
            assessment=assessment,
            version_number=1,
            snapshot_data={"title": assessment.title},
            server_evaluation_bundle={}
        )
        TestAttempt.objects.create(
            student=user,
            assessment=assessment,
            assessment_snapshot=snapshot,
            status=AttemptStatus.SUBMITTED,
            randomization_seed="seed123"
        )

        client = APIClient()
        client.force_authenticate(user=primary_admin)
        url = reverse('accounts:admin-student-detail', kwargs={'pk': profile.id})

        response = client.delete(url)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "retained examination records" in str(response.data)
        # Verify account was NOT deleted
        assert User.objects.filter(id=user.id).exists()

    def test_delete_student_blocked_when_legal_hold_exists(self, primary_admin, student_user):
        user, profile = student_user

        # Place legal hold on student
        LegalHold.objects.create(
            title="Academic Misconduct Investigation",
            case_reference="CASE-2026-001",
            reason="Investigating external notes violation",
            scope=LegalHoldScope.STUDENT,
            student=user,
            status=LegalHoldStatus.ACTIVE,
            placed_by=primary_admin
        )

        client = APIClient()
        client.force_authenticate(user=primary_admin)
        url = reverse('accounts:admin-student-detail', kwargs={'pk': profile.id})

        response = client.delete(url)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "active legal hold" in str(response.data)
        assert User.objects.filter(id=user.id).exists()


# ==============================================================================
# 4. Password Reset & Session Revocation Tests
# ==============================================================================

@pytest.mark.django_db
class TestPasswordResetHardening:
    def test_student_password_reset_forces_first_login(self, primary_admin, student_user):
        user, profile = student_user
        # Mark as completed first login
        user.first_login_required = False
        user.save()
        profile.first_login_required = False
        profile.save()

        client = APIClient()
        client.force_authenticate(user=primary_admin)
        url = reverse('accounts:admin-student-reset-password', kwargs={'pk': profile.id})

        response = client.post(url, {
            'reason': 'Student requested temporary password reset via department coordinator'
        })
        assert response.status_code == status.HTTP_200_OK
        data = response.data['data']
        temp_pwd = data['temporary_password']
        assert len(temp_pwd) >= 12

        # User and profile must now have first_login_required = True
        user.refresh_from_db()
        profile.refresh_from_db()
        assert user.first_login_required is True
        assert profile.first_login_required is True

        # Audit log verification: no plaintext password leaked
        log = AuditLog.objects.filter(action='PASSWORD_RESET', target_id=str(profile.id)).order_by('-created_at').first()
        assert log is not None
        assert temp_pwd not in str(log.metadata)
        assert log.metadata['reason'] == 'Student requested temporary password reset via department coordinator'

    def test_admin_password_reset_requires_reason(self, primary_admin, secondary_admin):
        client = APIClient()
        client.force_authenticate(user=primary_admin)
        url = reverse('accounts:admin-administrator-reset-password', kwargs={'pk': secondary_admin.id})

        # Empty reason should be rejected
        response = client.post(url, {'reason': '   '})
        assert response.status_code == status.HTTP_400_BAD_REQUEST


# ==============================================================================
# 5. Audit Immutability & Multi-Parameter Search Tests
# ==============================================================================

@pytest.mark.django_db
class TestAuditSystemHardening:
    def test_audit_logs_are_append_only(self, primary_admin):
        log = AuditLog.objects.create(
            actor=primary_admin,
            action="TEST_ACTION",
            metadata={"test": "data"}
        )

        with pytest.raises(PermissionDenied, match="immutable"):
            log.action = "MUTATED_ACTION"
            log.save()

        with pytest.raises(PermissionDenied, match="append-only"):
            log.delete()

    def test_audit_log_search_and_role_filtering(self, primary_admin, secondary_admin):
        # Create distinct audit logs
        AuditLog.objects.create(
            actor=primary_admin,
            action="ADMIN_CREATED",
            target_type="User",
            target_id=str(secondary_admin.id),
            metadata={
                "actor_name": "Gaurav Agarwal",
                "actor_admin_id": "EUAD-GAURAV-099",
                "target_identity": secondary_admin.admin_id,
                "target_email": secondary_admin.email,
                "target_role": "ADMIN",
                "reason": "Onboarding new proctoring director",
                "result": "SUCCESS"
            }
        )
        AuditLog.objects.create(
            actor=primary_admin,
            action="STUDENT_CREATED",
            target_type="StudentProfile",
            target_id=str(uuid.uuid4()),
            metadata={
                "actor_name": "Gaurav Agarwal",
                "target_identity": "CG-ROLL999",
                "target_email": "student999@domain.com",
                "target_role": "STUDENT",
                "reason": "Batch student registration",
                "result": "SUCCESS"
            }
        )

        client = APIClient()
        client.force_authenticate(user=primary_admin)
        url = reverse('accounts:admin-security-audit-logs')

        # Filter by role = ADMIN
        res_admin = client.get(url, {'role': 'ADMIN'})
        assert res_admin.status_code == status.HTTP_200_OK
        logs_admin = res_admin.data['data']['logs']
        assert any(l['action'] == 'ADMIN_CREATED' for l in logs_admin)

        # Free-text search by reason keyword
        res_search = client.get(url, {'search': 'proctoring director'})
        assert res_search.status_code == status.HTTP_200_OK
        assert len(res_search.data['data']['logs']) >= 1
        assert res_search.data['data']['logs'][0]['target_identity'] == secondary_admin.admin_id

    def test_unauthorized_proctor_and_student_blocked_from_audit(self, proctor_user, student_user):
        user, _ = student_user
        client = APIClient()
        url = reverse('accounts:admin-security-audit-logs')

        # Student blocked
        client.force_authenticate(user=user)
        res_student = client.get(url)
        assert res_student.status_code == status.HTTP_403_FORBIDDEN

        # Proctor blocked
        client.force_authenticate(user=proctor_user)
        res_proctor = client.get(url)
        assert res_proctor.status_code == status.HTTP_403_FORBIDDEN
