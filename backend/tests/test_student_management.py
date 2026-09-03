import io
import csv
import openpyxl
import pytest
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from rest_framework.exceptions import ValidationError as DRFValidationError

from apps.accounts.models import Role, StudentProfile, AuditLog
from apps.accounts.services import StudentService, EUIDService, ImportService

User = get_user_model()

@pytest.fixture
def admin_user(db):
    return User.objects.create_superuser(
        email="admin@codeguard.local",
        password="AdminSecurePass123!",
        role=Role.ADMIN
    )

@pytest.fixture
def student_one(db):
    user, profile = StudentService.create_student(
        email="student1@university.edu",
        roll_number="BETN1AI25001"
    )
    return user, profile

@pytest.fixture
def student_two(db):
    user, profile = StudentService.create_student(
        email="student2@university.edu",
        roll_number="BETN1AI25002"
    )
    return user, profile


# ==============================================================================
# 1. Student Creation & EUID Tests
# ==============================================================================

@pytest.mark.django_db
def test_admin_can_create_student(api_client, admin_user):
    """1. Admin can create a student with automated EUID and initial password generation."""
    api_client.force_authenticate(user=admin_user)
    url = reverse('accounts:admin-student-list')
    payload = {
        "email": "newstudent@university.edu",
        "roll_number": "BETN1AI25099"
    }
    response = api_client.post(url, payload, format='json')

    assert response.status_code == 201
    data = response.json()
    assert data['status'] == 'success'
    assert data['data']['email'] == "newstudent@university.edu"
    assert data['data']['roll_number'] == "BETN1AI25099"
    assert data['data']['euid'] == "CG-BETN1AI25099"
    assert data['data']['first_login_required'] is True

    # Verify student user in DB
    user = User.objects.get(email="newstudent@university.edu")
    assert user.role == Role.STUDENT
    assert user.check_password("BETN1AI25099") is True
    assert "password" not in str(data)


@pytest.mark.django_db
def test_student_cannot_create_another_student(api_client, student_one):
    """2. Students cannot access student creation endpoint (403 Forbidden)."""
    user, _ = student_one
    api_client.force_authenticate(user=user)
    url = reverse('accounts:admin-student-list')
    response = api_client.post(url, {"email": "bad@uni.edu", "roll_number": "BAD123"}, format='json')
    assert response.status_code == 403


@pytest.mark.django_db
def test_unauthenticated_cannot_create_student(api_client):
    """3. Unauthenticated requests to student creation are rejected with 401."""
    url = reverse('accounts:admin-student-list')
    response = api_client.post(url, {"email": "bad@uni.edu", "roll_number": "BAD123"}, format='json')
    assert response.status_code == 401


@pytest.mark.django_db
def test_duplicate_email_rejected(api_client, admin_user, student_one):
    """4. Duplicate student email is rejected."""
    api_client.force_authenticate(user=admin_user)
    url = reverse('accounts:admin-student-list')
    response = api_client.post(url, {
        "email": "student1@university.edu",
        "roll_number": "DIFFERENT_ROLL"
    }, format='json')

    assert response.status_code == 400
    data = response.json()
    assert data['status'] == 'error'


@pytest.mark.django_db
def test_duplicate_roll_number_rejected(api_client, admin_user, student_one):
    """5. Duplicate student roll number is rejected."""
    api_client.force_authenticate(user=admin_user)
    url = reverse('accounts:admin-student-list')
    response = api_client.post(url, {
        "email": "different_email@university.edu",
        "roll_number": "BETN1AI25001"
    }, format='json')

    assert response.status_code == 400
    data = response.json()
    assert data['status'] == 'error'


@pytest.mark.django_db
def test_euid_generation_and_normalization():
    """7. EUID normalization and deterministic format."""
    assert EUIDService.normalize_roll_number(" betn1-ai 25_001 ") == "BETN1-AI25_001"
    assert EUIDService.generate_euid("BETN1AI25001") == "CG-BETN1AI25001"


@pytest.mark.django_db
def test_euid_collision_is_rejected_without_suffix(student_one):
    """Correction 1: EUID collision is strictly rejected and never generates indexed suffixes like -1 or -2."""
    with pytest.raises(DRFValidationError) as excinfo:
        EUIDService.validate_unique_euid("BETN1AI25001")
    
    assert "euid" in excinfo.value.detail or "roll_number" in excinfo.value.detail


@pytest.mark.django_db
def test_euid_collision_regression_no_suffix_and_no_duplicate_creation(student_one):
    """
    Final Verification: Verify that when an existing student has EUID 'CG-BETN1AI25001':
    1. EUIDService.validate_unique_euid directly rejects the duplicate.
    2. No '-1', '-2', or other suffix is generated.
    3. StudentService.create_student rejects the operation and does not create an unintended second student profile.
    """
    _, existing_profile = student_one
    initial_count = StudentProfile.objects.count()
    assert existing_profile.euid == "CG-BETN1AI25001"

    # Direct EUIDService collision check
    with pytest.raises(DRFValidationError):
        EUIDService.validate_unique_euid("BETN1AI25001")

    # Verify no indexed suffix exists in database
    assert not StudentProfile.objects.filter(euid__startswith="CG-BETN1AI25001-").exists()

    # Attempt to create another student with colliding roll number/EUID but different email
    with pytest.raises(DRFValidationError):
        StudentService.create_student(
            email="collision_attempt@university.edu",
            roll_number="BETN1AI25001"
        )

    # Verify total student count is unchanged and no partial user was created
    assert StudentProfile.objects.count() == initial_count
    assert not User.objects.filter(email="collision_attempt@university.edu").exists()
    assert not StudentProfile.objects.filter(euid="CG-BETN1AI25001-1").exists()


@pytest.mark.django_db
def test_euid_database_unique_constraint_enforced(student_one):
    """
    Database Integrity: Direct ORM insertion attempting duplicate EUID is rejected by database UNIQUE constraint.
    """
    _, existing_profile = student_one
    new_user = User.objects.create_user(
        email="db_direct_attempt@university.edu",
        password="SomePassword123!"
    )
    with pytest.raises(Exception):
        StudentProfile.objects.create(
            user=new_user,
            roll_number="DIFFERENT_ROLL_NUM",
            euid=existing_profile.euid  # Reusing existing EUID directly
        )


# ==============================================================================
# 2. Dual Authentication & First Login Password Change Tests
# ==============================================================================

@pytest.mark.django_db
def test_student_login_with_email(api_client, student_one):
    """10. Student can authenticate using Email + Password."""
    user, profile = student_one
    url = reverse('accounts:login')
    response = api_client.post(url, {
        "identifier": "student1@university.edu",
        "password": "BETN1AI25001"
    }, format='json')

    assert response.status_code == 200
    data = response.json()
    assert data['status'] == 'success'
    assert data['data']['user']['email'] == "student1@university.edu"
    assert data['data']['user']['first_login_required'] is True


@pytest.mark.django_db
def test_student_login_with_euid(api_client, student_one):
    """11. Student can authenticate using EUID + Password."""
    user, profile = student_one
    url = reverse('accounts:login')
    response = api_client.post(url, {
        "identifier": "CG-BETN1AI25001",
        "password": "BETN1AI25001"
    }, format='json')

    assert response.status_code == 200
    data = response.json()
    assert data['status'] == 'success'
    assert data['data']['user']['email'] == "student1@university.edu"


@pytest.mark.django_db
def test_roll_number_cannot_be_used_for_login(api_client, student_one):
    """Correction 2: Roll Number must NOT be accepted as a login identifier (must fail with 401)."""
    user, profile = student_one
    url = reverse('accounts:login')
    
    # Attempt login using raw roll number (which does not start with CG- and has no @)
    response = api_client.post(url, {
        "identifier": "BETN1AI25001",
        "password": "BETN1AI25001"
    }, format='json')

    assert response.status_code == 401
    data = response.json()
    assert data['status'] == 'error'
    assert data['error']['code'] == 'INVALID_CREDENTIALS'


@pytest.mark.django_db
def test_student_login_with_invalid_euid(api_client):
    """12. Invalid EUID fails authentication with 401."""
    url = reverse('accounts:login')
    response = api_client.post(url, {
        "identifier": "CG-NONEXISTENT",
        "password": "SomePassword"
    }, format='json')

    assert response.status_code == 401
    data = response.json()
    assert data['error']['code'] == 'INVALID_CREDENTIALS'


@pytest.mark.django_db
def test_first_login_password_change_clears_flag(api_client, student_one):
    """14 & 15. Password change verifies current password, updates hash, and clears first_login_required."""
    user, profile = student_one
    assert profile.first_login_required is True

    api_client.force_authenticate(user=user)
    url = reverse('accounts:change-password')
    
    # Attempt with wrong current password
    res_fail = api_client.post(url, {
        "current_password": "WrongPassword!",
        "new_password": "NewSecurePassword2026!",
        "confirm_password": "NewSecurePassword2026!"
    }, format='json')
    assert res_fail.status_code == 400

    # Attempt with matching valid new password
    res_success = api_client.post(url, {
        "current_password": "BETN1AI25001",
        "new_password": "NewSecurePassword2026!",
        "confirm_password": "NewSecurePassword2026!"
    }, format='json')
    assert res_success.status_code == 200
    data = res_success.json()
    assert data['data']['first_login_required'] is False

    profile.refresh_from_db()
    assert profile.first_login_required is False
    assert user.check_password("NewSecurePassword2026!") is True


# ==============================================================================
# 3. Student Self Profile & IDOR Protection Tests
# ==============================================================================

@pytest.mark.django_db
def test_student_can_view_own_profile(api_client, student_one):
    """16. Student can retrieve their own profile."""
    user, profile = student_one
    api_client.force_authenticate(user=user)
    url = reverse('accounts:student-profile')
    response = api_client.get(url)

    assert response.status_code == 200
    data = response.json()
    assert data['data']['roll_number'] == "BETN1AI25001"
    assert data['data']['euid'] == "CG-BETN1AI25001"


@pytest.mark.django_db
def test_student_cannot_access_admin_student_endpoints(api_client, student_one, student_two):
    """17 & 39. Student is blocked from accessing admin student endpoints or querying other students."""
    user_one, _ = student_one
    _, profile_two = student_two

    api_client.force_authenticate(user=user_one)
    # Attempting to access admin list
    res_list = api_client.get(reverse('accounts:admin-student-list'))
    assert res_list.status_code == 403

    # Attempting to access student two details
    res_detail = api_client.get(reverse('accounts:admin-student-detail', kwargs={'pk': profile_two.id}))
    assert res_detail.status_code == 403


# ==============================================================================
# 4. Admin Management & Identity Immutability Tests
# ==============================================================================

@pytest.mark.django_db
def test_admin_can_update_email_only(api_client, admin_user, student_one):
    """Correction 3.1: Admin can update student email address."""
    _, profile = student_one
    api_client.force_authenticate(user=admin_user)
    url = reverse('accounts:admin-student-detail', kwargs={'pk': profile.id})
    
    response = api_client.patch(url, {"email": "updated_student@university.edu"}, format='json')
    assert response.status_code == 200
    data = response.json()
    assert data['data']['email'] == "updated_student@university.edu"
    assert data['data']['roll_number'] == "BETN1AI25001"
    assert data['data']['euid'] == "CG-BETN1AI25001"


@pytest.mark.django_db
def test_admin_cannot_modify_roll_number(api_client, admin_user, student_one):
    """Correction 3.2: Admin attempt to modify student roll_number is rejected with 400 ValidationError."""
    _, profile = student_one
    api_client.force_authenticate(user=admin_user)
    url = reverse('accounts:admin-student-detail', kwargs={'pk': profile.id})
    
    response = api_client.patch(url, {
        "email": "student1@university.edu",
        "roll_number": "NEW_ROLL_999"
    }, format='json')

    assert response.status_code == 400
    data = response.json()
    assert "roll_number" in data['error']['details']


@pytest.mark.django_db
def test_admin_cannot_modify_euid(api_client, admin_user, student_one):
    """Correction 3.3: Admin attempt to modify student EUID is rejected with 400 ValidationError."""
    _, profile = student_one
    api_client.force_authenticate(user=admin_user)
    url = reverse('accounts:admin-student-detail', kwargs={'pk': profile.id})
    
    response = api_client.patch(url, {
        "email": "student1@university.edu",
        "euid": "CG-MODIFIED"
    }, format='json')

    assert response.status_code == 400
    data = response.json()
    assert "euid" in data['error']['details']


@pytest.mark.django_db
def test_protected_fields_mass_assignment_rejected(api_client, admin_user, student_one):
    """Correction 3.4: Mass-assignment attempts to tamper with role, is_active, or first_login_required are rejected."""
    _, profile = student_one
    api_client.force_authenticate(user=admin_user)
    url = reverse('accounts:admin-student-detail', kwargs={'pk': profile.id})
    
    response = api_client.patch(url, {
        "email": "student1@university.edu",
        "role": "ADMIN",
        "is_active": False,
        "first_login_required": False
    }, format='json')

    assert response.status_code == 400
    data = response.json()
    assert "role" in data['error']['details']


@pytest.mark.django_db
def test_admin_search_and_filter_students(api_client, admin_user, student_one, student_two):
    """21, 22, 23. Admin can list, search, and filter student records."""
    api_client.force_authenticate(user=admin_user)
    url = reverse('accounts:admin-student-list')

    # General list
    res = api_client.get(url)
    assert res.status_code == 200
    data = res.json()
    assert data['data']['count'] == 2

    # Search by roll number
    res_search = api_client.get(url, {'search': 'BETN1AI25001'})
    data_search = res_search.json()
    assert data_search['data']['count'] == 1
    assert data_search['data']['results'][0]['roll_number'] == 'BETN1AI25001'

    # Filter by active status
    res_active = api_client.get(url, {'is_active': 'true'})
    assert res_active.json()['data']['count'] == 2


@pytest.mark.django_db
def test_admin_disable_and_enable_student(api_client, admin_user, student_one):
    """24, 25, 26. Admin can disable and enable student accounts, and disabled accounts cannot log in."""
    user, profile = student_one
    api_client.force_authenticate(user=admin_user)

    # Disable student
    disable_url = reverse('accounts:admin-student-disable', kwargs={'pk': profile.id})
    res_dis = api_client.post(disable_url)
    assert res_dis.status_code == 200
    assert res_dis.json()['data']['is_active'] is False

    user.refresh_from_db()
    assert user.is_active is False

    # Attempt student login while disabled
    api_client.logout()
    login_url = reverse('accounts:login')
    res_login = api_client.post(login_url, {
        "identifier": user.email,
        "password": "BETN1AI25001"
    }, format='json')
    assert res_login.status_code == 401
    assert res_login.json()['error']['code'] == 'ACCOUNT_DISABLED'

    # Re-enable student
    api_client.force_authenticate(user=admin_user)
    enable_url = reverse('accounts:admin-student-enable', kwargs={'pk': profile.id})
    res_en = api_client.post(enable_url)
    assert res_en.status_code == 200
    assert res_en.json()['data']['is_active'] is True


# ==============================================================================
# 5. Bulk CSV / XLSX Import & Duplicate Detection Tests
# ==============================================================================

@pytest.mark.django_db
def test_bulk_csv_preview_and_confirm_workflow(api_client, admin_user, student_one):
    """27, 29, 30, 31, 32, 35, 36. Full Bulk CSV preview, in-file duplicate detection, DB collision check, and batch confirmation."""
    api_client.force_authenticate(user=admin_user)

    csv_content = (
        "Roll Number,Email\n"
        "BETN1AI25055,valid55@university.edu\n"
        "BETN1AI25066,invalid-email-format\n"
        "BETN1AI25001,collision@university.edu\n"
        "BETN1AI25088,dup1@university.edu\n"
        "BETN1AI25088,dup2@university.edu\n"
    )
    csv_file = SimpleUploadedFile("students.csv", csv_content.encode('utf-8'), content_type="text/csv")

    preview_url = reverse('accounts:admin-student-import-preview')
    res_preview = api_client.post(preview_url, {'file': csv_file}, format='multipart')

    assert res_preview.status_code == 200
    p_data = res_preview.json()['data']
    assert p_data['total_rows'] == 5
    assert p_data['valid_count'] == 2  # Row 2 (BETN1AI25055) and Row 5 (first occurrence of BETN1AI25088)
    assert p_data['invalid_count'] == 1  # Row 3 (invalid email)
    assert p_data['duplicate_count'] == 2  # Row 4 (DB collision) and Row 6 (in-file duplicate)

    # Step 2: Confirm import for the valid rows
    confirm_url = reverse('accounts:admin-student-import-confirm')
    confirm_payload = {
        "filename": "students.csv",
        "students": [
            {"roll_number": "BETN1AI25055", "email": "valid55@university.edu"},
            {"roll_number": "BETN1AI25088", "email": "dup1@university.edu"}
        ]
    }
    res_confirm = api_client.post(confirm_url, confirm_payload, format='json')
    assert res_confirm.status_code == 200
    c_data = res_confirm.json()['data']
    assert c_data['created_count'] == 2
    assert c_data['failed_count'] == 0

    # Verify created users exist and have hashed initial passwords
    u55 = User.objects.get(email="valid55@university.edu")
    assert u55.check_password("BETN1AI25055") is True
    assert u55.student_profile.euid == "CG-BETN1AI25055"


@pytest.mark.django_db
def test_bulk_xlsx_preview(api_client, admin_user):
    """28. Bulk XLSX import preview parsing and column detection."""
    api_client.force_authenticate(user=admin_user)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Roll Number", "Email"])
    ws.append(["BETN1AI25077", "excelstudent@university.edu"])

    xlsx_io = io.BytesIO()
    wb.save(xlsx_io)
    xlsx_io.seek(0)

    xlsx_file = SimpleUploadedFile("students.xlsx", xlsx_io.read(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    preview_url = reverse('accounts:admin-student-import-preview')
    res_preview = api_client.post(preview_url, {'file': xlsx_file}, format='multipart')

    assert res_preview.status_code == 200
    data = res_preview.json()['data']
    assert data['total_rows'] == 1
    assert data['valid_count'] == 1
    assert data['rows'][0]['roll_number'] == "BETN1AI25077"


@pytest.mark.django_db
def test_invalid_file_type_rejected(api_client, admin_user):
    """33. Uploading invalid file format is rejected."""
    api_client.force_authenticate(user=admin_user)
    bad_file = SimpleUploadedFile("script.py", b"print('hello')", content_type="text/x-python")
    preview_url = reverse('accounts:admin-student-import-preview')
    response = api_client.post(preview_url, {'file': bad_file}, format='multipart')
    assert response.status_code == 400


# ==============================================================================
# 6. Audit Immutability & Security Tests
# ==============================================================================

@pytest.mark.django_db
def test_audit_log_created_and_immutable(admin_user):
    """42. Audit logs are created on administrative actions and reject updates/deletions."""
    log = AuditLog.objects.create(
        actor=admin_user,
        action="TEST_ACTION",
        target_type="StudentProfile",
        target_id="12345",
        metadata={"key": "value"}
    )
    assert log.id is not None

    # Attempt update
    log.action = "TAMPERED_ACTION"
    with pytest.raises(PermissionDenied):
        log.save()

    # Attempt deletion
    with pytest.raises(PermissionDenied):
        log.delete()
