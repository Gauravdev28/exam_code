import pytest
from rest_framework import status
from apps.accounts.models import User, StudentProfile, Role, Section, AuditLog
from apps.accounts.services import StudentService, AccountSecurityService, SectionService
from apps.assessments.models import (
    Assessment,
    AssessmentStatus,
    AssessmentAssignment,
    TestAttempt,
    AttemptStatus,
    AssessmentSnapshot,
)
from apps.assessments.services import AssessmentService
from datetime import timedelta
from django.utils import timezone


@pytest.fixture
def primary_admin_user(db):
    user = User.objects.create(
        email="gaurav@codeguard.edu",
        role=Role.ADMIN,
        admin_id="EUAD-GAURAV-099",
        primary_admin_marker="PRIMARY",
        is_active=True,
    )
    user.set_password("AdminPass123!")
    user.save()
    return user


@pytest.fixture
def secondary_admin_user(db):
    user = User.objects.create(
        email="sec_admin@codeguard.edu",
        role=Role.ADMIN,
        admin_id="EUAD-SEC-001",
        is_active=True,
    )
    user.set_password("AdminPass123!")
    user.save()
    return user


@pytest.fixture
def primary_admin_client(api_client, primary_admin_user):
    api_client.force_authenticate(user=primary_admin_user)
    return api_client


@pytest.fixture
def secondary_admin_client(api_client, secondary_admin_user):
    api_client.force_authenticate(user=secondary_admin_user)
    return api_client


@pytest.fixture
def sample_section(db):
    return Section.objects.create(code="CSE-A", name="Computer Science A", is_active=True)


@pytest.fixture
def test_students(db, sample_section):
    s1, _ = StudentService.create_student("stud1@univ.edu", "R001", section=sample_section)
    s2, _ = StudentService.create_student("stud2@univ.edu", "R002", section=sample_section)
    s3, _ = StudentService.create_student("stud3@univ.edu", "R003", section=sample_section)
    return [s1, s2, s3]


@pytest.mark.django_db
class TestBulkStudentDeletionService:
    def test_bulk_delete_students_success(self, test_students, sample_section):
        student_ids = [s.id for s in test_students[:2]]
        result = StudentService.bulk_delete_students(student_ids)

        assert result['total'] == 2
        assert result['success_count'] == 2
        assert result['failure_count'] == 0

        # Verify students deleted from DB
        assert not User.objects.filter(id__in=student_ids).exists()
        assert not StudentProfile.objects.filter(user_id__in=student_ids).exists()

        # Verify remaining student exists
        assert User.objects.filter(id=test_students[2].id).exists()

        # Verify section count reflects deletion
        sections_with_counts = SectionService.get_sections_with_counts()
        sec_data = next(s for s in sections_with_counts if s.id == sample_section.id)
        assert sec_data.student_count == 1

    def test_bulk_delete_student_with_attempt_fails(self, primary_admin_user, test_students):
        student_with_attempt = test_students[0]
        # Create an assessment and attempt
        now = timezone.now()
        assessment = Assessment.objects.create(
            title="Attempt Test",
            duration_minutes=30,
            status=AssessmentStatus.PUBLISHED,
            start_datetime=now,
            end_datetime=now + timedelta(days=1),
            created_by=primary_admin_user,
        )
        snapshot = AssessmentSnapshot.objects.create(
            assessment=assessment,
            version_number=1,
            snapshot_data={"title": assessment.title},
            server_evaluation_bundle={}
        )
        TestAttempt.objects.create(
            student=student_with_attempt,
            assessment=assessment,
            assessment_snapshot=snapshot,
            status=AttemptStatus.SUBMITTED,
            randomization_seed="seed123",
            started_at=now - timedelta(minutes=20),
            submitted_at=now - timedelta(minutes=5),
        )

        all_ids = [s.id for s in test_students]
        result = StudentService.bulk_delete_students(all_ids)

        assert result['total'] == 3
        assert result['success_count'] == 2
        assert result['failure_count'] == 1

        # The student with attempt should fail
        failed_res = next(r for r in result['results'] if r['id'] == str(student_with_attempt.id))
        assert not failed_res['success']
        assert "retained" in failed_res['error'].lower() or "attempt" in failed_res['error'].lower()

        # The other two students should succeed
        assert not User.objects.filter(id=test_students[1].id).exists()
        assert not User.objects.filter(id=test_students[2].id).exists()
        assert User.objects.filter(id=student_with_attempt.id).exists()

    def test_bulk_delete_non_existent_id(self, test_students):
        import uuid
        fake_id = uuid.uuid4()
        ids = [test_students[0].id, fake_id]
        result = StudentService.bulk_delete_students(ids)

        assert result['total'] == 2
        assert result['success_count'] == 1
        assert result['failure_count'] == 1
        failed_res = next(r for r in result['results'] if r['id'] == str(fake_id))
        assert not failed_res['success']
        assert "not found" in failed_res['error'].lower()


@pytest.mark.django_db
class TestBulkStudentDeletionAPI:
    def test_admin_bulk_delete_students(self, primary_admin_client, test_students):
        url = "/api/v1/admin/students/bulk-delete/"
        payload = {"ids": [str(test_students[0].id), str(test_students[1].id)]}
        response = primary_admin_client.post(url, payload, format="json")

        assert response.status_code == status.HTTP_200_OK
        data = response.data.get('data', response.data)
        assert data['success_count'] == 2
        assert data['failure_count'] == 0

        # Verify audit logs created
        assert AuditLog.objects.filter(action="STUDENT_DELETED").count() >= 2

    def test_non_admin_cannot_bulk_delete_students(self, api_client, test_students):
        api_client.force_authenticate(user=test_students[0])
        url = "/api/v1/admin/students/bulk-delete/"
        response = api_client.post(url, {"ids": [str(test_students[1].id)]}, format="json")
        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestBulkAdminDeletionService:
    def test_bulk_delete_secondary_admins_success(self, primary_admin_user):
        admin1 = User.objects.create_user(
            email="adm1@codeguard.edu",
            password="TempPwd123!",
            role=Role.ADMIN,
            display_name="Admin One",
            is_active=True,
        )
        admin2 = User.objects.create_user(
            email="adm2@codeguard.edu",
            password="TempPwd123!",
            role=Role.ADMIN,
            display_name="Admin Two",
            is_active=True,
        )

        admin_ids = [admin1.id, admin2.id]
        result = AccountSecurityService.bulk_delete_administrators(admin_ids, actor=primary_admin_user)

        assert result['total'] == 2
        assert result['success_count'] == 2
        assert result['failure_count'] == 0
        assert not User.objects.filter(id__in=admin_ids).exists()

    def test_primary_admin_is_permanently_protected(self, primary_admin_user):
        admin1 = User.objects.create_user(
            email="adm_sec@codeguard.edu",
            password="TempPwd123!",
            role=Role.ADMIN,
            display_name="Secondary Admin",
            is_active=True,
        )

        result = AccountSecurityService.bulk_delete_administrators(
            [admin1.id, primary_admin_user.id], actor=primary_admin_user
        )

        assert result['total'] == 2
        assert result['success_count'] == 1
        assert result['failure_count'] == 1

        failed = next(r for r in result['results'] if r['id'] == str(primary_admin_user.id))
        assert not failed['success']
        assert "primary administrator" in failed['error'].lower()

        # Primary admin remains intact
        assert User.objects.filter(id=primary_admin_user.id).exists()

    def test_cannot_delete_self_in_bulk(self, primary_admin_user):
        admin1 = User.objects.create_user(
            email="sec1@codeguard.edu",
            password="TempPwd123!",
            role=Role.ADMIN,
            display_name="Secondary 1",
            is_active=True,
        )
        result = AccountSecurityService.bulk_delete_administrators(
            [admin1.id, primary_admin_user.id], actor=primary_admin_user
        )
        failed = next(r for r in result['results'] if r['id'] == str(primary_admin_user.id))
        assert not failed['success']


@pytest.mark.django_db
class TestBulkAdminDeletionAPI:
    def test_primary_admin_can_bulk_delete_secondary_admins(self, primary_admin_client, primary_admin_user):
        admin1 = User.objects.create_user(
            email="test_sub1@codeguard.edu",
            password="TempPwd123!",
            role=Role.ADMIN,
            display_name="Sub 1",
            is_active=True,
        )
        url = "/api/v1/admin/administrators/bulk-delete/"
        response = primary_admin_client.post(url, {"ids": [str(admin1.id)]}, format="json")

        assert response.status_code == status.HTTP_200_OK
        data = response.data.get('data', response.data)
        assert data['success_count'] == 1
        assert not User.objects.filter(id=admin1.id).exists()

    def test_secondary_admin_forbidden_from_bulk_delete(self, secondary_admin_client, primary_admin_user):
        admin1 = User.objects.create_user(
            email="test_sub2@codeguard.edu",
            password="TempPwd123!",
            role=Role.ADMIN,
            display_name="Sub 2",
            is_active=True,
        )
        url = "/api/v1/admin/administrators/bulk-delete/"
        response = secondary_admin_client.post(url, {"ids": [str(admin1.id)]}, format="json")

        assert response.status_code == status.HTTP_403_FORBIDDEN
