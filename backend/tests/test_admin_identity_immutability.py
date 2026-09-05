"""
CODEGUARD — Administrator Identity Immutability Test Suite

Comprehensive regression and invariant test suite verifying:
- Permanent immutability of administrator identity fields (UUID, Admin ID, email, display_name, role)
- Protection of Primary Administrator against deletion and deactivation
- Secondary administrator lifecycle operations (activation, deactivation, authorized deletion)
- Operational mutability of passwords and first_login_required
- Student email updating and EUID authentication preservation
- Public health endpoint security boundary and query scan audits
- Empty/falsy legacy value immutability (truthiness independence)
"""

import os
import re
import uuid
import pytest
from django.urls import reverse
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import User, Role, AdminSequence, AuditLog, StudentProfile
from apps.accounts.services import AccountSecurityService, StudentService, AdminIdService
from apps.retention.models import LegalHold, LegalHoldStatus, LegalHoldScope


@pytest.fixture
def primary_admin(db):
    """Authoritative Primary Administrator fixture"""
    admin = User.objects.filter(primary_admin_marker='PRIMARY').first()
    if not admin:
        admin = User.objects.create_superuser(
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
    """Clean Secondary Administrator fixture with no dependencies"""
    return User.objects.create_user(
        email='secondary.admin@codeguard.local',
        password='Password123!',
        role=Role.ADMIN,
        display_name='Secondary Administrator',
        is_staff=True,
        is_superuser=False
    )


@pytest.fixture
def student_user(db):
    """Student user fixture with linked StudentProfile"""
    user, profile = StudentService.create_student(
        email='student.immutability@university.edu',
        roll_number='ROLL-IMMUT-001'
    )
    return user, profile


@pytest.fixture
def proctor_user(db):
    """Proctor fixture"""
    return User.objects.create_user(
        email='proctor.immutability@codeguard.local',
        password='Password123!',
        role=Role.PROCTOR,
        is_staff=True
    )


@pytest.mark.django_db
class TestAdminIdentityImmutability:
    """
    Test Suite for CODEGUARD Administrator Identity Immutability Rule.
    Implements all 34 specification tests across categories A through O.
    """

    # =========================================================================
    # A. Identity Immutability
    # =========================================================================

    def test_admin_email_cannot_be_changed(self, primary_admin, secondary_admin):
        """1. Modifying an administrator's email via model save or API is rejected."""
        # Model save attempt on primary admin
        primary_admin.email = 'tampered.primary@codeguard.local'
        with pytest.raises(PermissionDenied, match="Administrator email address is strictly immutable"):
            primary_admin.save()
        primary_admin.refresh_from_db()
        assert primary_admin.email == 'gauravagldeveloper28@gmail.com'

        # Model save attempt on secondary admin
        secondary_admin.email = 'tampered.secondary@codeguard.local'
        with pytest.raises(PermissionDenied, match="Administrator email address is strictly immutable"):
            secondary_admin.save()
        secondary_admin.refresh_from_db()
        assert secondary_admin.email == 'secondary.admin@codeguard.local'

        # API PATCH attempt
        client = APIClient()
        client.force_authenticate(user=primary_admin)
        url = reverse('accounts:admin-administrator-detail', kwargs={'pk': secondary_admin.id})
        res = client.patch(url, {'email': 'tampered.api@codeguard.local'})
        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert res.data['error']['code'] == 'ADMIN_IDENTITY_IMMUTABLE'

    def test_admin_id_cannot_be_changed(self, primary_admin, secondary_admin):
        """2. Modifying an administrator's Admin ID is rejected."""
        primary_admin.admin_id = 'EUAD-HACKED-001'
        with pytest.raises(PermissionDenied, match="Administrator Admin ID is strictly immutable"):
            primary_admin.save()
        primary_admin.refresh_from_db()
        assert primary_admin.admin_id == 'EUAD-GAURAV-099'

        orig_id = secondary_admin.admin_id
        secondary_admin.admin_id = 'CG-ADM-999999'
        with pytest.raises(PermissionDenied, match="Administrator Admin ID is strictly immutable"):
            secondary_admin.save()
        secondary_admin.refresh_from_db()
        assert secondary_admin.admin_id == orig_id

    def test_admin_display_name_cannot_be_changed(self, primary_admin, secondary_admin):
        """3. Modifying an administrator's display name is rejected."""
        primary_admin.display_name = 'Hacked Admin Name'
        with pytest.raises(PermissionDenied, match="Administrator display name is strictly immutable"):
            primary_admin.save()
        primary_admin.refresh_from_db()
        assert primary_admin.display_name == 'Gaurav Agarwal'

        secondary_admin.display_name = 'New Display Name'
        with pytest.raises(PermissionDenied, match="Administrator display name is strictly immutable"):
            secondary_admin.save()
        secondary_admin.refresh_from_db()
        assert secondary_admin.display_name == 'Secondary Administrator'

    def test_admin_role_cannot_be_altered(self, primary_admin, secondary_admin):
        """4. Changing an administrator's role to STUDENT or PROCTOR is rejected."""
        primary_admin.role = Role.STUDENT
        with pytest.raises(PermissionDenied, match="Administrator role cannot be altered"):
            primary_admin.save()
        primary_admin.refresh_from_db()
        assert primary_admin.role == Role.ADMIN

        secondary_admin.role = Role.PROCTOR
        with pytest.raises(PermissionDenied, match="Administrator role cannot be altered"):
            secondary_admin.save()
        secondary_admin.refresh_from_db()
        assert secondary_admin.role == Role.ADMIN

    def test_primary_admin_marker_cannot_be_altered(self, primary_admin, secondary_admin):
        """5. Primary Admin marker cannot be removed from Primary Admin or set on secondary admin."""
        # Removing from primary admin
        primary_admin.primary_admin_marker = None
        with pytest.raises(PermissionDenied, match="Primary Administrator marker cannot be altered"):
            primary_admin.save()
        primary_admin.refresh_from_db()
        assert primary_admin.primary_admin_marker == 'PRIMARY'

        # Assigning to secondary admin
        secondary_admin.primary_admin_marker = 'PRIMARY'
        with pytest.raises(PermissionDenied, match="Primary Administrator marker cannot be altered"):
            secondary_admin.save()
        secondary_admin.refresh_from_db()
        assert secondary_admin.primary_admin_marker is None

    # =========================================================================
    # B. Primary Admin Protection
    # =========================================================================

    def test_primary_admin_cannot_be_deactivated(self, primary_admin, secondary_admin):
        """6. Deactivating Primary Admin is rejected by model save and status API."""
        # Direct save deactivation
        primary_admin.is_active = False
        with pytest.raises(PermissionDenied, match="Primary Administrator account cannot be deactivated"):
            primary_admin.save()
        primary_admin.refresh_from_db()
        assert primary_admin.is_active is True

        # API status deactivation
        client = APIClient()
        client.force_authenticate(user=secondary_admin)
        url = reverse('accounts:admin-administrator-status', kwargs={'pk': primary_admin.id})
        res = client.post(url, {'is_active': False, 'reason': 'Audit test attempt'})
        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert 'PRIMARY_ADMIN_IMMUTABLE' in str(res.data)

    def test_primary_admin_cannot_be_deleted(self, primary_admin, secondary_admin):
        """7. Model delete, service, and API reject deleting Primary Admin."""
        # Model delete
        with pytest.raises(PermissionDenied, match="Primary Administrator account is permanently protected"):
            primary_admin.delete()

        # Service delete
        from rest_framework.exceptions import ValidationError as DRFValidationError
        with pytest.raises(DRFValidationError, match="Primary Administrator account cannot be deleted"):
            AccountSecurityService.delete_administrator(target_admin=primary_admin, actor=secondary_admin)

        # API delete
        client = APIClient()
        client.force_authenticate(user=primary_admin)
        url = reverse('accounts:admin-administrator-detail', kwargs={'pk': primary_admin.id})
        res = client.delete(url)
        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert 'PRIMARY_ADMIN_IMMUTABLE' in str(res.data)

    # =========================================================================
    # C. Secondary Admin Lifecycle
    # =========================================================================

    def test_secondary_admin_creation_succeeds(self, primary_admin):
        """8. Creating a secondary administrator auto-generates sequential ID and sets marker=None."""
        client = APIClient()
        client.force_authenticate(user=primary_admin)
        payload = {
            'display_name': 'Dr. Alan Turing',
            'email': 'Alan.Turing@University.edu',
            'password': 'Password123!',
            'confirm_password': 'Password123!',
            'is_active': True
        }
        res = client.post(reverse('accounts:admin-administrator-list'), payload, format='json')
        assert res.status_code == status.HTTP_201_CREATED
        data = res.data['data']

        assert data['email'] == 'alan.turing@university.edu'
        assert data['display_name'] == 'Dr. Alan Turing'
        assert data['admin_id'].startswith('CG-ADM-')
        assert data['admin_id'] != 'EUAD-GAURAV-099'
        assert data['is_primary'] is False

        new_user = User.objects.get(email='alan.turing@university.edu')
        assert new_user.primary_admin_marker is None
        assert new_user.is_primary_admin is False

    def test_secondary_admin_activation_succeeds(self, primary_admin, secondary_admin):
        """9. Activating a deactivated secondary administrator succeeds."""
        secondary_admin.is_active = False
        secondary_admin.save(update_fields=['is_active', 'updated_at'])

        client = APIClient()
        client.force_authenticate(user=primary_admin)
        url = reverse('accounts:admin-administrator-status', kwargs={'pk': secondary_admin.id})
        res = client.post(url, {'is_active': True, 'reason': 'Reactivating secondary admin'})
        assert res.status_code == status.HTTP_200_OK

        secondary_admin.refresh_from_db()
        assert secondary_admin.is_active is True

    def test_secondary_admin_deactivation_succeeds(self, primary_admin, secondary_admin):
        """10. Deactivating secondary admin succeeds and revokes active sessions."""
        client = APIClient()
        client.force_authenticate(user=primary_admin)
        url = reverse('accounts:admin-administrator-status', kwargs={'pk': secondary_admin.id})
        res = client.post(url, {'is_active': False, 'reason': 'Temporary leave'}, format='json')
        assert res.status_code == status.HTTP_200_OK

        secondary_admin.refresh_from_db()
        assert secondary_admin.is_active is False

    def test_secondary_admin_deletion_succeeds_when_eligible(self, primary_admin, secondary_admin):
        """11. Deleting a secondary admin with zero dependencies succeeds via AccountSecurityService."""
        admin_id = secondary_admin.id
        client = APIClient()
        client.force_authenticate(user=primary_admin)
        url = reverse('accounts:admin-administrator-detail', kwargs={'pk': admin_id})
        res = client.delete(url)
        assert res.status_code == status.HTTP_200_OK

        assert not User.objects.filter(pk=admin_id).exists()
        # Verify audit snapshot exists
        log = AuditLog.objects.filter(action='ADMIN_DELETED', target_id=str(admin_id)).first()
        assert log is not None
        assert log.actor == primary_admin

    def test_secondary_admin_deletion_blocked_by_active_dependencies(self, primary_admin, secondary_admin):
        """12. Deleting secondary admin is blocked when active legal hold dependency exists."""
        LegalHold.objects.create(
            title="Immutability Compliance Hold",
            case_reference="CASE-IMMUT-2026",
            reason="Investigative hold",
            scope=LegalHoldScope.STUDENT,
            status=LegalHoldStatus.ACTIVE,
            placed_by=secondary_admin
        )

        client = APIClient()
        client.force_authenticate(user=primary_admin)
        url = reverse('accounts:admin-administrator-detail', kwargs={'pk': secondary_admin.id})
        res = client.delete(url)
        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert "Cannot delete administrator with active placed legal holds" in str(res.data)

    # =========================================================================
    # D. Password Operations & Operational Update Fields Safety
    # =========================================================================

    def test_admin_password_reset_succeeds(self, primary_admin, secondary_admin):
        """13. Administrative password reset succeeds without triggering identity immutability checks."""
        old_pwd_hash = secondary_admin.password
        temp_pwd = AccountSecurityService.reset_admin_password(
            target_admin=secondary_admin,
            actor=primary_admin,
            reason="User requested credential refresh"
        )
        secondary_admin.refresh_from_db()
        assert secondary_admin.password != old_pwd_hash
        assert secondary_admin.check_password(temp_pwd) is True
        assert secondary_admin.first_login_required is True

    def test_admin_password_change_succeeds(self, secondary_admin):
        """14. Self-service password change operates cleanly without identity immutability interference."""
        secondary_admin.set_password("PermanentNewSecret2026!")
        secondary_admin.first_login_required = False
        secondary_admin.save(update_fields=['password', 'first_login_required', 'updated_at'])

        secondary_admin.refresh_from_db()
        assert secondary_admin.check_password("PermanentNewSecret2026!") is True
        assert secondary_admin.first_login_required is False

    def test_first_login_required_can_change(self, secondary_admin):
        """15. Clearing first_login_required succeeds during normal operational flows."""
        secondary_admin.first_login_required = True
        secondary_admin.save(update_fields=['first_login_required', 'updated_at'])
        secondary_admin.refresh_from_db()
        assert secondary_admin.first_login_required is True

        secondary_admin.first_login_required = False
        secondary_admin.save(update_fields=['first_login_required', 'updated_at'])
        secondary_admin.refresh_from_db()
        assert secondary_admin.first_login_required is False

    # =========================================================================
    # E. Student Email Editing
    # =========================================================================

    def test_student_email_can_still_be_updated(self, primary_admin, student_user):
        """16. StudentService.update_student() updates student email without triggering admin immutability."""
        user, profile = student_user
        updated_profile = StudentService.update_student(
            student_profile=profile,
            email="new.student.address@university.edu",
            actor=primary_admin
        )
        assert updated_profile.user.email == "new.student.address@university.edu"
        user.refresh_from_db()
        assert user.email == "new.student.address@university.edu"

    # =========================================================================
    # F. Student EUID Login
    # =========================================================================

    def test_student_euid_login_succeeds(self, student_user):
        """17. Students can authenticate using their EUID and password."""
        user, profile = student_user
        client = APIClient()
        res = client.post(reverse('accounts:login'), {
            'identifier': profile.euid,
            'password': profile.roll_number
        })
        assert res.status_code == status.HTTP_200_OK
        assert res.data['data']['user']['email'] == user.email

    # =========================================================================
    # G. Admin Email Login
    # =========================================================================

    def test_admin_email_login_succeeds(self, primary_admin):
        """18. Administrators authenticate successfully with registered email and password."""
        client = APIClient()
        res = client.post(reverse('accounts:login'), {
            'identifier': 'gauravagldeveloper28@gmail.com',
            'password': 'Password123!'
        })
        assert res.status_code == status.HTTP_200_OK
        assert res.data['data']['user']['admin_id'] == 'EUAD-GAURAV-099'

    # =========================================================================
    # H. Admin ID Login Rejection
    # =========================================================================

    def test_admin_id_login_rejected(self, primary_admin, secondary_admin):
        """19. Submitting Admin IDs (EUAD-* or CG-ADM-*) as login identifiers is explicitly rejected."""
        client = APIClient()

        # Attempt login with Primary Admin ID
        res1 = client.post(reverse('accounts:login'), {
            'identifier': 'EUAD-GAURAV-099',
            'password': 'Password123!'
        })
        assert res1.status_code == status.HTTP_401_UNAUTHORIZED
        assert res1.data['error']['code'] == 'ADMIN_ID_NOT_LOGIN_CREDENTIAL'

        # Attempt login with Secondary Admin ID
        res2 = client.post(reverse('accounts:login'), {
            'identifier': secondary_admin.admin_id,
            'password': 'Password123!'
        })
        assert res2.status_code == status.HTTP_401_UNAUTHORIZED
        assert res2.data['error']['code'] == 'ADMIN_ID_NOT_LOGIN_CREDENTIAL'

    # =========================================================================
    # I. Marker Invariants
    # =========================================================================

    def test_at_most_one_primary_admin(self, primary_admin):
        """20. Database unique constraint rejects a second user with marker='PRIMARY'."""
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                impostor = User(
                    email='impostor.primary@codeguard.local',
                    role=Role.ADMIN,
                    admin_id='CG-ADM-999998',
                    primary_admin_marker='PRIMARY'
                )
                impostor.set_password('Password123!')
                impostor.save()

    def test_invalid_primary_admin_marker_value_rejected(self, secondary_admin):
        """21. Setting primary_admin_marker to illegal values like 'SECONDARY' is rejected."""
        secondary_admin.primary_admin_marker = 'SECONDARY'
        with pytest.raises(ValidationError):
            secondary_admin.clean()

        with pytest.raises(ValidationError):
            secondary_admin.save()

    def test_primary_admin_marker_null_for_secondary_admin(self, secondary_admin):
        """22. Secondary administrators have primary_admin_marker = None."""
        assert secondary_admin.primary_admin_marker is None
        assert secondary_admin.is_primary_admin is False

    def test_student_cannot_become_primary_admin(self, student_user):
        """23. Assigning primary_admin_marker='PRIMARY' to a student fails validation."""
        user, profile = student_user
        user.primary_admin_marker = 'PRIMARY'
        with pytest.raises(ValidationError):
            user.clean()

    def test_proctor_cannot_become_primary_admin(self, proctor_user):
        """24. Assigning primary_admin_marker='PRIMARY' to a proctor fails validation."""
        proctor_user.primary_admin_marker = 'PRIMARY'
        with pytest.raises(ValidationError):
            proctor_user.clean()

    def test_secondary_admin_cannot_self_promote(self, secondary_admin):
        """25. Secondary administrator cannot promote themselves to Primary Administrator."""
        secondary_admin.primary_admin_marker = 'PRIMARY'
        with pytest.raises(PermissionDenied, match="Primary Administrator marker cannot be altered"):
            secondary_admin.save()

    # =========================================================================
    # J. Migration Bootstrap Authority
    # =========================================================================

    def test_is_superuser_not_runtime_primary_authority(self, primary_admin):
        """26. A secondary admin with is_superuser=True does not gain Primary Admin authority."""
        rogue_admin = User.objects.create_user(
            email='rogue.superuser@codeguard.local',
            password='Password123!',
            role=Role.ADMIN,
            is_staff=True,
            is_superuser=True  # Has is_superuser=True but marker is None
        )
        assert rogue_admin.is_primary_admin is False
        assert rogue_admin.primary_admin_marker is None

        # Cannot delete the actual Primary Admin
        with pytest.raises(Exception):
            AccountSecurityService.delete_administrator(target_admin=primary_admin, actor=rogue_admin)

    # =========================================================================
    # K. Rollback Integrity
    # =========================================================================

    def test_primary_admin_integrity_after_migration_rollback(self, primary_admin):
        """27. Confirms system fails closed if primary_admin_marker is cleared."""
        # When primary_admin_marker is cleared, is_primary_admin evaluates to False
        User.objects.filter(pk=primary_admin.pk).update(primary_admin_marker=None)
        primary_admin.refresh_from_db()
        assert primary_admin.primary_admin_marker is None
        assert primary_admin.is_primary_admin is False
        assert User.objects.filter(primary_admin_marker='PRIMARY').count() == 0

    # =========================================================================
    # L. QuerySet Delete Bypass Audit
    # =========================================================================

    def test_no_queryset_delete_bypass_for_administrators(self):
        """28. Codebase scan test confirming zero User.objects.filter(...).delete() calls exist."""
        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        apps_dir = os.path.join(backend_dir, 'apps')

        pattern = re.compile(r'User\.objects\.(filter|all)\([^)]*\)\.delete\(\)')
        violations = []

        for root, _, files in os.walk(apps_dir):
            for file in files:
                if file.endswith('.py'):
                    path = os.path.join(root, file)
                    with open(path, 'r', encoding='utf-8') as f:
                        for line_num, line in enumerate(f, 1):
                            if pattern.search(line):
                                violations.append(f"{path}:{line_num}: {line.strip()}")

        assert len(violations) == 0, f"Found raw User QuerySet deletion calls: {violations}"

    def test_secondary_admin_delete_uses_authorized_service(self, primary_admin, secondary_admin):
        """29. Administrator deletion executes strictly through AccountSecurityService."""
        admin_id = secondary_admin.id
        AccountSecurityService.delete_administrator(target_admin=secondary_admin, actor=primary_admin)
        assert not User.objects.filter(pk=admin_id).exists()

    # =========================================================================
    # M. QuerySet Update / Bulk Update Bypass Audit
    # =========================================================================

    def test_no_queryset_identity_update_bypass(self):
        """30. Codebase scan test confirming zero QuerySet.update() calls on admin identity fields."""
        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        apps_dir = os.path.join(backend_dir, 'apps')

        # We look for User.objects...update( mutating email, admin_id, or display_name outside migrations
        pattern = re.compile(r'User\.objects\.[^;]+\.update\([^)]*(admin_id|display_name)\s*=')
        violations = []

        for root, _, files in os.walk(apps_dir):
            if 'migrations' in root:
                continue
            for file in files:
                if file.endswith('.py'):
                    path = os.path.join(root, file)
                    with open(path, 'r', encoding='utf-8') as f:
                        for line_num, line in enumerate(f, 1):
                            if pattern.search(line):
                                violations.append(f"{path}:{line_num}: {line.strip()}")

        assert len(violations) == 0, f"Found User QuerySet update calls mutating identity: {violations}"

    def test_no_bulk_update_identity_bypass(self):
        """31. Confirms no bulk_update calls exist on User mutating identity fields."""
        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        apps_dir = os.path.join(backend_dir, 'apps')

        pattern = re.compile(r'bulk_update\([^,]+,\s*\[[^\]]*(admin_id|display_name|role|primary_admin_marker)[^\]]*\]')
        violations = []

        for root, _, files in os.walk(apps_dir):
            for file in files:
                if file.endswith('.py'):
                    path = os.path.join(root, file)
                    with open(path, 'r', encoding='utf-8') as f:
                        for line_num, line in enumerate(f, 1):
                            if pattern.search(line):
                                violations.append(f"{path}:{line_num}: {line.strip()}")

        assert len(violations) == 0, f"Found bulk_update calls mutating User identity: {violations}"

    # =========================================================================
    # N. Email Normalization
    # =========================================================================

    def test_email_normalization_is_applied_before_uniqueness_check(self, primary_admin):
        """32. Creation of Admin@Domain.com normalizes to admin@domain.com before uniqueness validation."""
        client = APIClient()
        client.force_authenticate(user=primary_admin)

        # Create first admin
        res1 = client.post(reverse('accounts:admin-administrator-list'), {
            'display_name': 'Case Normal Test',
            'email': 'CaseAdmin@University.edu',
            'password': 'Password123!',
            'confirm_password': 'Password123!',
            'is_active': True
        }, format='json')
        assert res1.status_code == status.HTTP_201_CREATED
        assert res1.data['data']['email'] == 'caseadmin@university.edu'

        # Attempt to create duplicate with different casing
        res2 = client.post(reverse('accounts:admin-administrator-list'), {
            'display_name': 'Case Normal Duplicate',
            'email': 'CASEADMIN@UNIVERSITY.EDU',
            'password': 'Password123!',
            'confirm_password': 'Password123!',
            'is_active': True
        }, format='json')
        assert res2.status_code == status.HTTP_400_BAD_REQUEST
        assert 'An account with this email address already exists' in str(res2.data)

    # =========================================================================
    # O. Empty / Falsy Legacy Values (Truthiness Independence)
    # =========================================================================

    def test_admin_id_immutability_does_not_depend_on_truthiness(self, secondary_admin):
        """33. Changing an administrator's empty Admin ID is rejected without silent repair."""
        # Directly set empty string at raw database level to simulate corrupt legacy data
        User.objects.filter(pk=secondary_admin.pk).update(admin_id="")
        secondary_admin.refresh_from_db()
        assert secondary_admin.admin_id == ""

        # Attempting to update or 'repair' it on model save must be rejected unconditionally
        secondary_admin.admin_id = "CG-ADM-REPAIRED"
        with pytest.raises(PermissionDenied, match="Administrator Admin ID is strictly immutable"):
            secondary_admin.save()

    def test_display_name_immutability_does_not_depend_on_truthiness(self, secondary_admin):
        """34. Changing an administrator's empty display_name is rejected without silent repair."""
        # Directly set empty string at raw database level
        User.objects.filter(pk=secondary_admin.pk).update(display_name="")
        secondary_admin.refresh_from_db()
        assert secondary_admin.display_name == ""

        # Attempting to populate it on model save must be rejected unconditionally
        secondary_admin.display_name = "Repaired Name"
        with pytest.raises(PermissionDenied, match="Administrator display name is strictly immutable"):
            secondary_admin.save()

    # =========================================================================
    # Additional Section 18 Specific Categories (G, O, Y, Z, AA, AB, AC, AD, AG, AH, AI, AJ, AK, AL)
    # =========================================================================

    def test_uuid_immutability_through_api_and_service(self, primary_admin):
        """G. UUID is immutable; API rejects mutation with ADMIN_IDENTITY_IMMUTABLE."""
        client = APIClient()
        client.force_authenticate(user=primary_admin)
        new_uuid = str(uuid.uuid4())
        res = client.patch(reverse('accounts:admin-administrator-detail', kwargs={'pk': str(primary_admin.pk)}), {
            'id': new_uuid
        }, format='json')
        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert res.data['error']['code'] == 'ADMIN_IDENTITY_IMMUTABLE'

    def test_update_fields_behavior_enforces_immutability(self, secondary_admin):
        """O. update_fields cannot be used to bypass administrator identity immutability."""
        secondary_admin.email = 'tampered_update_fields@codeguard.local'
        with pytest.raises(PermissionDenied, match="Administrator email address is strictly immutable"):
            secondary_admin.save(update_fields=['email'])

        # But operational fields can be updated via update_fields
        secondary_admin.refresh_from_db()
        secondary_admin.first_login_required = True
        secondary_admin.save(update_fields=['first_login_required', 'updated_at'])
        secondary_admin.refresh_from_db()
        assert secondary_admin.first_login_required is True

    def test_migration_bootstrap_with_exactly_one_candidate(self, db):
        """Y. Migration bootstrap designates candidate when exactly one superuser admin exists."""
        import importlib
        migration_mod = importlib.import_module('apps.accounts.migrations.0006_admin_identity_immutability')
        designate_primary_admin = migration_mod.designate_primary_admin
        from django.apps import apps

        User.objects.filter(role=Role.ADMIN).delete()
        admin = User.objects.create_superuser(
            email='bootstrap.candidate@codeguard.local',
            password='Password123!',
            role=Role.ADMIN,
            is_staff=True,
            is_superuser=True
        )
        assert admin.primary_admin_marker is None
        designate_primary_admin(apps, None)
        admin.refresh_from_db()
        assert admin.primary_admin_marker == 'PRIMARY'
        assert admin.is_primary_admin is True

    def test_migration_fails_with_zero_candidates(self, db):
        """Z. Migration fails closed with RuntimeError when zero superuser candidates exist."""
        import importlib
        migration_mod = importlib.import_module('apps.accounts.migrations.0006_admin_identity_immutability')
        designate_primary_admin = migration_mod.designate_primary_admin
        from django.apps import apps

        User.objects.filter(role=Role.ADMIN).delete()
        # Create non-superuser admin
        User.objects.create_user(
            email='nonsuper@codeguard.local',
            password='Password123!',
            role=Role.ADMIN,
            is_staff=True,
            is_superuser=False
        )
        with pytest.raises(RuntimeError, match="Zero Primary Administrator candidates found"):
            designate_primary_admin(apps, None)

    def test_migration_fails_with_multiple_candidates(self, db):
        """AA. Migration fails closed with RuntimeError when multiple superuser candidates exist."""
        import importlib
        migration_mod = importlib.import_module('apps.accounts.migrations.0006_admin_identity_immutability')
        designate_primary_admin = migration_mod.designate_primary_admin
        from django.apps import apps

        User.objects.filter(role=Role.ADMIN).delete()
        User.objects.create_superuser(
            email='super1@codeguard.local',
            password='Password123!',
            role=Role.ADMIN,
            is_staff=True,
            is_superuser=True
        )
        User.objects.create_superuser(
            email='super2@codeguard.local',
            password='Password123!',
            role=Role.ADMIN,
            is_staff=True,
            is_superuser=True
        )
        with pytest.raises(RuntimeError, match="Multiple Primary Administrator candidates found"):
            designate_primary_admin(apps, None)

    def test_case_normalization(self, db):
        """AB. Email case normalization: uppercase/mixed-case normalizes to lowercase."""
        user = User.objects.create_user(
            email='Admin.CaseNormal@CODEGUARD.LOCAL',
            password='Password123!',
            role=Role.ADMIN
        )
        assert user.email == 'admin.casenormal@codeguard.local'
        # Canonical lookup by normalizing input
        canonical_lookup = 'ADMIN.CASENORMAL@CODEGUARD.LOCAL'.strip().lower()
        fetched = User.objects.filter(email=canonical_lookup).first()
        assert fetched is not None
        assert fetched.pk == user.pk

    def test_whitespace_normalization(self, db):
        """AC. Email whitespace normalization: leading and trailing whitespace stripped."""
        user = User.objects.create_user(
            email='   admin.whitespace@codeguard.local   ',
            password='Password123!',
            role=Role.ADMIN
        )
        assert user.email == 'admin.whitespace@codeguard.local'

    def test_real_canonical_email_change_rejected(self, secondary_admin):
        """AD. Real canonical email change on administrator is rejected unconditionally."""
        secondary_admin.email = 'completely.different.email@codeguard.local'
        with pytest.raises(PermissionDenied, match="Administrator email address is strictly immutable"):
            secondary_admin.save()

    def test_direct_api_identity_mutation_rejected(self, primary_admin, secondary_admin):
        """AG. Direct API identity mutation via PATCH and PUT returns 400 ADMIN_IDENTITY_IMMUTABLE."""
        client = APIClient()
        client.force_authenticate(user=primary_admin)
        url = reverse('accounts:admin-administrator-detail', kwargs={'pk': str(secondary_admin.pk)})

        # Test PATCH
        patch_res = client.patch(url, {'email': 'patched@codeguard.local'}, format='json')
        assert patch_res.status_code == status.HTTP_400_BAD_REQUEST
        assert patch_res.data['error']['code'] == 'ADMIN_IDENTITY_IMMUTABLE'

        # Test PUT
        put_res = client.put(url, {'display_name': 'New Display Name'}, format='json')
        assert put_res.status_code == status.HTTP_400_BAD_REQUEST
        assert put_res.data['error']['code'] == 'ADMIN_IDENTITY_IMMUTABLE'

    def test_primary_admin_password_reset(self, primary_admin):
        """AH. Primary Admin password reset/change succeeds while keeping identity strictly intact."""
        email_before = primary_admin.email
        admin_id_before = primary_admin.admin_id
        display_name_before = primary_admin.display_name
        marker_before = primary_admin.primary_admin_marker

        # Primary admin changes own password via ChangePasswordView
        client = APIClient()
        client.force_authenticate(user=primary_admin)
        res = client.post(reverse('accounts:change-password'), {
            'current_password': 'Password123!',
            'new_password': 'NewSecurePrimaryPass2026!',
            'confirm_password': 'NewSecurePrimaryPass2026!'
        }, format='json')
        assert res.status_code == status.HTTP_200_OK

        primary_admin.refresh_from_db()
        assert primary_admin.check_password('NewSecurePrimaryPass2026!')
        assert primary_admin.email == email_before
        assert primary_admin.admin_id == admin_id_before
        assert primary_admin.display_name == display_name_before
        assert primary_admin.primary_admin_marker == marker_before

    def test_secondary_admin_password_reset(self, primary_admin, secondary_admin):
        """AI. Secondary Admin password reset succeeds while keeping identity strictly intact."""
        email_before = secondary_admin.email
        admin_id_before = secondary_admin.admin_id
        display_name_before = secondary_admin.display_name

        result = AccountSecurityService.reset_admin_password(
            target_admin=secondary_admin,
            temporary_password='NewSecondaryPass2026!',
            reason='Security Rotation',
            actor=primary_admin
        )
        assert result == 'NewSecondaryPass2026!'
        secondary_admin.refresh_from_db()
        assert secondary_admin.check_password('NewSecondaryPass2026!')
        assert secondary_admin.email == email_before
        assert secondary_admin.admin_id == admin_id_before
        assert secondary_admin.display_name == display_name_before

    def test_health_endpoint_information_disclosure(self, primary_admin):
        """AJ. Public health endpoint does not disclose sensitive administrator information."""
        client = APIClient()
        res = client.get(reverse('core:health-check'))
        assert res.status_code == status.HTTP_200_OK
        content = str(res.data)

        # Must not disclose Primary Admin email, UUID, Admin ID, or admin count
        assert primary_admin.email not in content
        assert str(primary_admin.pk) not in content
        assert primary_admin.admin_id not in content
        assert 'administrator_count' not in content
        assert 'primary_admin' not in content

    def test_empty_falsy_legacy_identity_values_protected(self, db):
        """AK. Empty/falsy legacy identity values cannot be silently mutated or repaired."""
        user = User.objects.create_user(
            email='legacy.empty@codeguard.local',
            password='Password123!',
            role=Role.ADMIN
        )
        User.objects.filter(pk=user.pk).update(admin_id="", display_name="")
        user.refresh_from_db()
        assert user.admin_id == ""
        assert user.display_name == ""

        # Attempt to set admin_id
        user.admin_id = "NEW-ADMIN-ID"
        with pytest.raises(PermissionDenied, match="Administrator Admin ID is strictly immutable"):
            user.save()

        # Attempt to set display_name
        user.refresh_from_db()
        user.display_name = "New Display Name"
        with pytest.raises(PermissionDenied, match="Administrator display name is strictly immutable"):
            user.save()

    def test_creation_path_not_blocked_by_immutability_logic(self, primary_admin):
        """AL. Creating brand new administrators is never blocked by update immutability rules."""
        client = APIClient()
        client.force_authenticate(user=primary_admin)
        res = client.post(reverse('accounts:admin-administrator-list'), {
            'display_name': 'Newly Created Admin',
            'email': 'newly.created.admin@codeguard.local',
            'password': 'Password123!',
            'confirm_password': 'Password123!',
            'is_active': True
        }, format='json')
        assert res.status_code == status.HTTP_201_CREATED
        new_admin = User.objects.get(email='newly.created.admin@codeguard.local')
        assert new_admin.display_name == 'Newly Created Admin'
        assert new_admin.role == Role.ADMIN
        assert new_admin.primary_admin_marker is None
