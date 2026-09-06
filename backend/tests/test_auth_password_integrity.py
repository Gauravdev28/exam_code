import json
import pytest
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from rest_framework.test import APIClient

from apps.accounts.models import User, Role, StudentProfile, Section
from apps.accounts.services import StudentService
from apps.assessments.models import Assessment, AssessmentStatus, AssessmentAssignment
from apps.assessments.services import AssessmentService, AssessmentAudienceService
from apps.questions.models import Question, QuestionVersion, QuestionType


@pytest.fixture
def admin_user(db):
    user = User.objects.create_superuser(
        email="integrity_admin@codeguard.test",
        password="AdminSecure2026!",
        display_name="Integrity Admin"
    )
    return user


@pytest.fixture
def student_user(db):
    user = User.objects.create_user(
        email="integrity_student@codeguard.test",
        password="StudentSecure2026!",
        role=Role.STUDENT,
        display_name="Integrity Student"
    )
    StudentProfile.objects.create(
        user=user,
        roll_number="INTEG001",
        euid="CG-INTEG001",
        first_login_required=False
    )
    return user


@pytest.fixture
def academic_section(db):
    return Section.objects.create(
        code="AIML-INTEG",
        name="AI & ML Integrity Section"
    )


@pytest.mark.django_db
class TestPasswordIntegrityRegression:
    """
    Guarantees that User.password is strictly immutable across all domain,
    API, profile, assessment, and assignment operations, changing ONLY during
    explicit password change/reset flows.
    """

    def test_01_admin_login_works(self, api_client, admin_user):
        """1. Admin login works with established password."""
        res = api_client.post(reverse('accounts:login'), {
            "identifier": admin_user.email,
            "password": "AdminSecure2026!"
        })
        assert res.status_code == 200
        assert res.json()['data']['user']['email'] == admin_user.email
        assert res.json()['data']['user']['role'] == Role.ADMIN

    def test_02_student_login_works(self, api_client, student_user):
        """2. Student login works with established password via both Email and EUID."""
        # Login via email
        res_email = api_client.post(reverse('accounts:login'), {
            "identifier": student_user.email,
            "password": "StudentSecure2026!"
        })
        assert res_email.status_code == 200
        assert res_email.json()['data']['user']['email'] == student_user.email

        # Login via EUID
        res_euid = api_client.post(reverse('accounts:login'), {
            "identifier": student_user.student_profile.euid,
            "password": "StudentSecure2026!"
        })
        assert res_euid.status_code == 200
        assert res_euid.json()['data']['user']['email'] == student_user.email

    def test_03_updating_student_profile_does_not_change_password(self, admin_user, student_user, academic_section):
        """3. Updating StudentProfile does not change password."""
        original_student_hash = student_user.password
        original_admin_hash = admin_user.password

        StudentService.update_student(
            student_profile=student_user.student_profile,
            email="integrity_student_updated@codeguard.test",
            section=academic_section,
            update_section=True,
            actor=admin_user
        )

        student_user.refresh_from_db()
        admin_user.refresh_from_db()

        assert student_user.password == original_student_hash
        assert student_user.check_password("StudentSecure2026!")
        assert admin_user.password == original_admin_hash
        assert admin_user.check_password("AdminSecure2026!")

    def test_04_assigning_a_student_does_not_change_password(self, admin_user, student_user):
        """4. Assigning a student does not change password."""
        original_student_hash = student_user.password
        original_admin_hash = admin_user.password

        now = timezone.now()
        assessment = AssessmentService.create_assessment(
            title="Assignment Test Exam",
            description="Testing password immutability during assignment",
            duration_minutes=60,
            start_datetime=now + timedelta(hours=1),
            end_datetime=now + timedelta(hours=3),
            created_by=admin_user
        )

        AssessmentService.assign_students(
            assessment=assessment,
            student_ids=[student_user.id],
            actor=admin_user
        )

        student_user.refresh_from_db()
        admin_user.refresh_from_db()

        assert student_user.password == original_student_hash
        assert student_user.check_password("StudentSecure2026!")
        assert admin_user.password == original_admin_hash
        assert admin_user.check_password("AdminSecure2026!")

    def test_05_updating_assessment_audience_does_not_change_password(self, admin_user, student_user, academic_section):
        """5. Updating assessment audience does not change password."""
        original_student_hash = student_user.password
        original_admin_hash = admin_user.password

        now = timezone.now()
        assessment = AssessmentService.create_assessment(
            title="Audience Test Exam",
            description="Testing audience configuration",
            duration_minutes=45,
            start_datetime=now + timedelta(hours=1),
            end_datetime=now + timedelta(hours=3),
            created_by=admin_user
        )

        AssessmentAudienceService.configure_audience(
            assessment=assessment,
            section_ids=[str(academic_section.id)],
            student_ids=[str(student_user.id)],
            actor=admin_user
        )

        student_user.refresh_from_db()
        admin_user.refresh_from_db()

        assert student_user.password == original_student_hash
        assert student_user.check_password("StudentSecure2026!")
        assert admin_user.password == original_admin_hash
        assert admin_user.check_password("AdminSecure2026!")

    def test_06_saving_an_assessment_draft_does_not_change_password(self, admin_user, student_user):
        """6. Saving an assessment draft does not change password."""
        original_student_hash = student_user.password
        original_admin_hash = admin_user.password

        now = timezone.now()
        assessment = AssessmentService.create_assessment(
            title="Draft Exam",
            description="Initial description",
            duration_minutes=30,
            start_datetime=now + timedelta(hours=1),
            end_datetime=now + timedelta(hours=2),
            created_by=admin_user
        )

        AssessmentService.update_draft_assessment(
            assessment=assessment,
            actor=admin_user,
            title="Draft Exam Renamed",
            description="Updated description",
            target_student_ids=[str(student_user.id)]
        )

        student_user.refresh_from_db()
        admin_user.refresh_from_db()

        assert student_user.password == original_student_hash
        assert student_user.check_password("StudentSecure2026!")
        assert admin_user.password == original_admin_hash
        assert admin_user.check_password("AdminSecure2026!")

    def test_07_publishing_an_assessment_does_not_change_password(self, admin_user, student_user):
        """7. Publishing an assessment does not change password."""
        original_student_hash = student_user.password
        original_admin_hash = admin_user.password

        # Create Question and publish version
        q = Question.objects.create(
            question_type=QuestionType.CODING,
            created_by=admin_user
        )
        from apps.questions.models import VersionStatus
        qv = QuestionVersion.objects.create(
            question=q,
            version_number=1,
            question_type=QuestionType.CODING,
            title="Sample Question v1",
            description="Solve it",
            points=50,
            status=VersionStatus.PUBLISHED,
            created_by=admin_user
        )

        now = timezone.now()
        assessment = AssessmentService.create_assessment(
            title="Publishing Test Exam",
            description="Testing publish password immutability",
            duration_minutes=60,
            total_points=50,
            start_datetime=now + timedelta(hours=1),
            end_datetime=now + timedelta(hours=3),
            created_by=admin_user
        )

        AssessmentService.add_question(
            assessment=assessment,
            question_version=qv,
            actor=admin_user,
            points=50
        )

        AssessmentAudienceService.configure_audience(
            assessment=assessment,
            section_ids=[],
            student_ids=[str(student_user.id)],
            actor=admin_user
        )

        AssessmentService.publish_assessment(
            assessment=assessment,
            actor=admin_user
        )

        student_user.refresh_from_db()
        admin_user.refresh_from_db()

        assert student_user.password == original_student_hash
        assert student_user.check_password("StudentSecure2026!")
        assert admin_user.password == original_admin_hash
        assert admin_user.check_password("AdminSecure2026!")

    def test_08_login_attempt_does_not_change_password(self, api_client, admin_user, student_user):
        """8. Login attempt (successful or failed) does not change password."""
        original_student_hash = student_user.password
        original_admin_hash = admin_user.password

        # Failed login attempt
        api_client.post(reverse('accounts:login'), {
            "identifier": admin_user.email,
            "password": "WrongPassword123!"
        })
        api_client.post(reverse('accounts:login'), {
            "identifier": student_user.email,
            "password": "WrongPassword123!"
        })

        admin_user.refresh_from_db()
        student_user.refresh_from_db()

        assert admin_user.password == original_admin_hash
        assert admin_user.check_password("AdminSecure2026!")
        assert student_user.password == original_student_hash
        assert student_user.check_password("StudentSecure2026!")

        # Successful login attempt
        api_client.post(reverse('accounts:login'), {
            "identifier": admin_user.email,
            "password": "AdminSecure2026!"
        })
        api_client.post(reverse('accounts:login'), {
            "identifier": student_user.email,
            "password": "StudentSecure2026!"
        })

        admin_user.refresh_from_db()
        student_user.refresh_from_db()

        assert admin_user.password == original_admin_hash
        assert admin_user.check_password("AdminSecure2026!")
        assert student_user.password == original_student_hash
        assert student_user.check_password("StudentSecure2026!")

    def test_09_ordinary_user_profile_patch_does_not_change_password(self, api_client, admin_user, student_user):
        """9. Ordinary User/Profile PATCH does not change password."""
        original_student_hash = student_user.password
        original_admin_hash = admin_user.password

        api_client.force_authenticate(user=admin_user)

        res = api_client.patch(
            reverse('accounts:admin-student-detail', kwargs={'pk': student_user.student_profile.id}),
            {"email": "student_patched@codeguard.test"}
        )
        assert res.status_code == 200

        student_user.refresh_from_db()
        admin_user.refresh_from_db()

        assert student_user.password == original_student_hash
        assert student_user.check_password("StudentSecure2026!")
        assert admin_user.password == original_admin_hash
        assert admin_user.check_password("AdminSecure2026!")

    def test_10_explicit_password_change_does_change_password_correctly(self, api_client, student_user):
        """10. Explicit password change DOES change password correctly."""
        original_hash = student_user.password
        assert student_user.check_password("StudentSecure2026!")

        api_client.force_authenticate(user=student_user)

        res = api_client.post(reverse('accounts:change-password'), {
            "current_password": "StudentSecure2026!",
            "new_password": "BrandNewSecret2026!",
            "confirm_password": "BrandNewSecret2026!"
        })
        assert res.status_code == 200

        student_user.refresh_from_db()

        # Hash MUST have changed and new password MUST verify
        assert student_user.password != original_hash
        assert student_user.check_password("BrandNewSecret2026!")
        assert not student_user.check_password("StudentSecure2026!")

    def test_11_password_remains_valid_after_unrelated_user_save(self, admin_user, student_user):
        """11. Password remains valid after unrelated User save."""
        original_student_hash = student_user.password
        original_admin_hash = admin_user.password

        # Full save without update_fields
        student_user.display_name = "Modified Student Name"
        student_user.save()

        admin_user.save()

        student_user.refresh_from_db()
        admin_user.refresh_from_db()

        assert student_user.password == original_student_hash
        assert student_user.check_password("StudentSecure2026!")
        assert admin_user.password == original_admin_hash
        assert admin_user.check_password("AdminSecure2026!")

    def test_12_password_remains_valid_after_student_profile_save(self, student_user, academic_section):
        """12. Password remains valid after StudentProfile save."""
        original_hash = student_user.password

        prof = student_user.student_profile
        prof.section = academic_section
        prof.save()

        student_user.refresh_from_db()

        assert student_user.password == original_hash
        assert student_user.check_password("StudentSecure2026!")

    def test_13_password_remains_valid_after_assessment_operations(self, admin_user, student_user):
        """13. Password remains valid after assessment operations."""
        original_student_hash = student_user.password
        original_admin_hash = admin_user.password

        now = timezone.now()
        assessment = AssessmentService.create_assessment(
            title="Ops Test Exam",
            description="Testing ops",
            duration_minutes=30,
            start_datetime=now + timedelta(hours=1),
            end_datetime=now + timedelta(hours=2),
            created_by=admin_user
        )

        AssessmentService.archive_assessment(assessment=assessment, actor=admin_user)

        student_user.refresh_from_db()
        admin_user.refresh_from_db()

        assert student_user.password == original_student_hash
        assert student_user.check_password("StudentSecure2026!")
        assert admin_user.password == original_admin_hash
        assert admin_user.check_password("AdminSecure2026!")

    def test_14_password_remains_valid_after_assignment_operations(self, admin_user, student_user):
        """14. Password remains valid after assignment operations (assignment & revocation)."""
        original_student_hash = student_user.password
        original_admin_hash = admin_user.password

        now = timezone.now()
        assessment = AssessmentService.create_assessment(
            title="Assignment Ops Exam",
            description="Testing assignment ops",
            duration_minutes=30,
            start_datetime=now + timedelta(hours=1),
            end_datetime=now + timedelta(hours=2),
            created_by=admin_user
        )

        # Assign
        AssessmentService.assign_students(
            assessment=assessment,
            student_ids=[student_user.id],
            actor=admin_user
        )

        # Revoke
        AssessmentService.revoke_assignment(
            assessment=assessment,
            student_id=str(student_user.id),
            actor=admin_user
        )

        student_user.refresh_from_db()
        admin_user.refresh_from_db()

        assert student_user.password == original_student_hash
        assert student_user.check_password("StudentSecure2026!")
        assert admin_user.password == original_admin_hash
        assert admin_user.check_password("AdminSecure2026!")
