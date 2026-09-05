import io
import pytest
from django.urls import reverse
from django.db import transaction
from django.core.exceptions import PermissionDenied
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status
from rest_framework.exceptions import ValidationError as DRFValidationError

from apps.accounts.models import User, StudentProfile, Role, Section
from apps.accounts.services import SectionService, StudentService, ImportService
from apps.assessments.models import Assessment, AssessmentStatus, AssessmentAssignment
from apps.assessments.services import AssessmentService, AssessmentAudienceService
from datetime import timedelta
from django.utils import timezone
from apps.questions.models import QuestionType
from apps.questions.services import QuestionService


@pytest.fixture
def admin_client(api_client, admin_user):
    api_client.force_authenticate(user=admin_user)
    return api_client


@pytest.fixture
def sections(db):
    sec_a = Section.objects.create(code="AIML-A", name="AI/ML Section A", is_active=True)
    sec_b = Section.objects.create(code="AIML-B", name="AI/ML Section B", is_active=True)
    sec_c = Section.objects.create(code="CSE-A", name="Computer Science Section A", is_active=True)
    sec_inact = Section.objects.create(code="OLD-SEC", name="Deprecated Section", is_active=False)
    return {
        "AIML-A": sec_a,
        "AIML-B": sec_b,
        "CSE-A": sec_c,
        "INACTIVE": sec_inact,
    }


@pytest.fixture
def cohort_students(db, sections):
    # 2 students in AIML-A
    s1, _ = StudentService.create_student("s1@univ.edu", "AI001", section=sections["AIML-A"])
    s2, _ = StudentService.create_student("s2@univ.edu", "AI002", section=sections["AIML-A"])
    # 2 students in AIML-B
    s3, _ = StudentService.create_student("s3@univ.edu", "AI003", section=sections["AIML-B"])
    s4, _ = StudentService.create_student("s4@univ.edu", "AI004", section=sections["AIML-B"])
    # 2 students in CSE-A
    s5, _ = StudentService.create_student("s5@univ.edu", "CS001", section=sections["CSE-A"])
    s6, _ = StudentService.create_student("s6@univ.edu", "CS002", section=sections["CSE-A"])
    # 1 unassigned student
    s7, _ = StudentService.create_student("s7@univ.edu", "UN001", section=None)

    # Clear first_login_required for API access testing
    for s in [s1, s2, s3, s4, s5, s6, s7]:
        p = s.student_profile
        p.first_login_required = False
        p.save(update_fields=['first_login_required'])

    return {
        "s1": s1, "s2": s2,
        "s3": s3, "s4": s4,
        "s5": s5, "s6": s6,
        "s7": s7,
    }


@pytest.fixture
def draft_assessment(admin_user):
    q, v = QuestionService.create_question(
        question_type=QuestionType.MCQ,
        title="Python Basics",
        description="Which collection is ordered and mutable?",
        points=10,
        type_config={
            "options": [
                {"id": "A", "text": "Set"},
                {"id": "B", "text": "List"},
                {"id": "C", "text": "Tuple"},
                {"id": "D", "text": "Dictionary Keys"}
            ],
            "correct_options": ["B"]
        },
        actor=admin_user
    )
    published_v = QuestionService.publish_version(v, actor=admin_user)

    now = timezone.now()
    assessment = AssessmentService.create_assessment(
        title="Targeting Test Assessment",
        description="Testing section based targeting",
        start_datetime=now,
        end_datetime=now + timedelta(days=1),
        duration_minutes=60,
        total_points=10,
        created_by=admin_user
    )
    AssessmentService.add_question(
        assessment=assessment,
        question_version=published_v,
        actor=admin_user,
        points=10
    )
    return assessment


# ==============================================================================
# 1. Section Model & Service Tests
# ==============================================================================

@pytest.mark.django_db
class TestSectionManagement:
    def test_section_code_normalization(self, admin_user):
        """Codes are trimmed and converted to uppercase."""
        sec = SectionService.create_section(
            code="  aiml-c  ",
            name="AI Section C",
            actor=admin_user
        )
        assert sec.code == "AIML-C"
        assert sec.name == "AI Section C"
        assert sec.is_active is True

    def test_duplicate_section_code_rejected(self, admin_user, sections):
        """Case-insensitive duplicate section code is rejected."""
        with pytest.raises(DRFValidationError) as exc:
            SectionService.create_section(code="aiml-a", name="Duplicate", actor=admin_user)
        assert "already exists" in str(exc.value)

    def test_section_update(self, admin_user, sections):
        """Section name and is_active can be updated."""
        sec = sections["AIML-A"]
        updated = SectionService.update_section(sec, name="Updated AIML A", is_active=False, actor=admin_user)
        assert updated.name == "Updated AIML A"
        assert updated.is_active is False

    def test_section_safe_delete_when_unused(self, admin_user):
        """Unused section can be physically deleted."""
        sec = Section.objects.create(code="EMPTY-SEC", name="Empty")
        sec_id = sec.id
        SectionService.delete_or_deactivate_section(sec, actor=admin_user)
        assert not Section.objects.filter(id=sec_id).exists()

    def test_section_deactivated_when_students_exist(self, admin_user, cohort_students, sections):
        """Section with students cannot be physically deleted; deleting raises DRFValidationError."""
        sec = sections["AIML-A"]
        with pytest.raises(DRFValidationError) as exc:
            SectionService.delete_or_deactivate_section(sec, actor=admin_user)
        assert "Deactivate it instead" in str(exc.value)
        SectionService.update_section(sec, is_active=False, actor=admin_user)
        sec.refresh_from_db()
        assert sec.is_active is False

    def test_section_api_list_and_create(self, admin_client):
        """Admin can list and create sections via API."""
        url = reverse('accounts:admin-section-list')
        res = admin_client.post(url, {"code": "ece-a", "name": "Electronics A"})
        assert res.status_code == status.HTTP_201_CREATED
        assert res.json()['data']['code'] == "ECE-A"

        res_list = admin_client.get(url)
        assert res_list.status_code == status.HTTP_200_OK
        codes = [s['code'] for s in res_list.json()['data']]
        assert "ECE-A" in codes

    def test_section_api_detail_update_delete(self, admin_client, sections):
        """Admin can update and delete/deactivate sections via API."""
        sec = sections["AIML-B"]
        detail_url = reverse('accounts:admin-section-detail', kwargs={'pk': sec.id})

        # Update
        res_patch = admin_client.patch(detail_url, {"name": "AIML Bravo"})
        assert res_patch.status_code == status.HTTP_200_OK
        assert res_patch.json()['data']['name'] == "AIML Bravo"

        # Delete (should delete cleanly if no students)
        empty_sec = Section.objects.create(code="DEL-ME", name="Delete Me")
        del_url = reverse('accounts:admin-section-detail', kwargs={'pk': empty_sec.id})
        res_del = admin_client.delete(del_url)
        assert res_del.status_code == status.HTTP_200_OK
        assert not Section.objects.filter(id=empty_sec.id).exists()


# ==============================================================================
# 2. Student Section Assignment & Filtering Tests
# ==============================================================================

@pytest.mark.django_db
class TestStudentSectionAssignment:
    def test_create_student_with_section(self, admin_user, sections):
        user, profile = StudentService.create_student(
            email="secstudent@univ.edu",
            roll_number="SEC001",
            section=sections["AIML-A"],
            actor=admin_user
        )
        assert profile.section == sections["AIML-A"]

    def test_student_section_change_audit(self, admin_user, cohort_students, sections):
        """Changing student section records STUDENT_SECTION_CHANGED audit log."""
        s1 = cohort_students["s1"]
        profile = s1.student_profile
        StudentService.change_student_section(profile, new_section=sections["CSE-A"], actor=admin_user)
        profile.refresh_from_db()
        assert profile.section == sections["CSE-A"]

    def test_filter_students_by_section(self, admin_client, cohort_students, sections):
        """Admin can filter students by section code, section id, or unassigned."""
        url = reverse('accounts:admin-student-list')

        # Filter by code
        res_a = admin_client.get(f"{url}?section=AIML-A")
        assert res_a.status_code == status.HTTP_200_OK
        data_a = res_a.json()['data']['results']
        assert len(data_a) == 2
        for r in data_a:
            assert r['section']['code'] == "AIML-A"

        # Filter by Unassigned
        res_un = admin_client.get(f"{url}?section=unassigned")
        assert res_un.status_code == status.HTTP_200_OK
        data_un = res_un.json()['data']['results']
        assert any(r['roll_number'] == "UN001" for r in data_un)


# ==============================================================================
# 3. Bulk Import with Section
# ==============================================================================

@pytest.mark.django_db
class TestBulkImportWithSections:
    def test_import_with_valid_section(self, admin_client, sections):
        csv_data = (
            "Roll Number,Email,Section\n"
            "SECIMP01,secimp01@univ.edu,AIML-A\n"
            "SECIMP02,secimp02@univ.edu,AIML-B\n"
        )
        csv_file = SimpleUploadedFile("roster.csv", csv_data.encode('utf-8'), content_type="text/csv")
        res_preview = admin_client.post(
            reverse('accounts:admin-student-import-preview'),
            {'file': csv_file},
            format='multipart'
        )
        assert res_preview.status_code == 200
        p_data = res_preview.json()['data']
        assert p_data['valid_count'] == 2
        assert p_data['invalid_count'] == 0

        # Confirm
        res_confirm = admin_client.post(
            reverse('accounts:admin-student-import-confirm'),
            {
                "filename": "roster.csv",
                "students": [
                    {"roll_number": "SECIMP01", "email": "secimp01@univ.edu", "section": "AIML-A"},
                    {"roll_number": "SECIMP02", "email": "secimp02@univ.edu", "section": "AIML-B"},
                ]
            },
            format='json'
        )
        assert res_confirm.status_code == 200
        p1 = StudentProfile.objects.get(roll_number="SECIMP01")
        assert p1.section.code == "AIML-A"

    def test_import_with_missing_or_invalid_section_rejected(self, admin_client, sections):
        csv_data = (
            "Roll Number,Email,Section\n"
            "BAD01,bad01@univ.edu,\n"
            "BAD02,bad02@univ.edu,NONEXISTENT\n"
            "BAD03,bad03@univ.edu,OLD-SEC\n"
        )
        csv_file = SimpleUploadedFile("roster.csv", csv_data.encode('utf-8'), content_type="text/csv")
        res_preview = admin_client.post(
            reverse('accounts:admin-student-import-preview'),
            {'file': csv_file},
            format='multipart'
        )
        assert res_preview.status_code == 200
        p_data = res_preview.json()['data']
        assert p_data['valid_count'] == 0
        assert p_data['invalid_count'] == 3
        errors_by_row = {r['roll_number']: r['errors'] for r in p_data['rows']}
        assert any("Section is required" in e for e in errors_by_row['BAD01'])
        assert any("Unknown section" in e for e in errors_by_row['BAD02'])
        assert any("Section is inactive" in e for e in errors_by_row['BAD03'])


# ==============================================================================
# 4. Assessment Audience Configuration & Resolution Tests
# ==============================================================================

@pytest.mark.django_db
class TestAssessmentAudienceTargeting:
    def test_preview_audience_union_and_deduplication(self, draft_assessment, cohort_students, sections):
        """Preview correctly unions sections and explicit students with deduplication."""
        sec_a = sections["AIML-A"]
        s1 = cohort_students["s1"]  # in AIML-A (overlap)
        s5 = cohort_students["s5"]  # in CSE-A (additional)

        res = AssessmentAudienceService.resolve_audience(
            assessment=draft_assessment,
            section_ids=[sec_a.id],
            student_ids=[s1.id, s5.id]
        )
        # AIML-A has s1, s2. Explicit has s1, s5.
        # Union should be s1, s2, s5 (3 total).
        assert res['total_eligible'] == 3
        assert res['overlap_count'] == 1
        assert res['section_student_count'] == 2
        assert res['individual_student_count'] == 2
        assert set(res['eligible_student_ids']) == {str(s1.id), str(cohort_students["s2"].id), str(s5.id)}

    def test_configure_audience_draft_assessment(self, admin_client, draft_assessment, cohort_students, sections):
        """Admin can configure audience on a DRAFT assessment."""
        url = reverse('assessments:admin-assessment-audience', kwargs={'pk': draft_assessment.id})
        payload = {
            "target_section_ids": [str(sections["AIML-A"].id)],
            "target_student_ids": [str(cohort_students["s5"].id)]
        }
        res = admin_client.post(url, payload, format='json')
        assert res.status_code == status.HTTP_200_OK
        data = res.json()['data']
        assert data['total_eligible'] == 3

        # Verify DB persisted
        draft_assessment.refresh_from_db()
        assert draft_assessment.target_sections.count() == 1
        assert draft_assessment.target_students.count() == 1

    def test_non_student_or_inactive_student_rejected_in_audience(self, draft_assessment, admin_user, cohort_students):
        """Admin accounts or inactive accounts cannot be added to target_students."""
        # Non-student
        with pytest.raises(DRFValidationError) as exc:
            AssessmentAudienceService.configure_audience(
                draft_assessment,
                student_ids=[admin_user.id],
                actor=admin_user
            )
        assert "cannot be targeted as a student" in str(exc.value)

        # Inactive student
        s1 = cohort_students["s1"]
        s1.is_active = False
        s1.save()
        with pytest.raises(DRFValidationError) as exc2:
            AssessmentAudienceService.configure_audience(
                draft_assessment,
                student_ids=[s1.id],
                actor=admin_user
            )
        assert "cannot be targeted as a student" in str(exc2.value)


# ==============================================================================
# 5. Audience Immutability & Direct M2M Defense
# ==============================================================================

@pytest.mark.django_db
class TestAudienceImmutability:
    def test_cannot_configure_audience_on_published_assessment(self, admin_client, draft_assessment, cohort_students, sections, admin_user):
        """Audience configuration is rejected on PUBLISHED assessment."""
        AssessmentAudienceService.configure_audience(
            draft_assessment,
            section_ids=[sections["AIML-A"].id],
            actor=admin_user
        )
        AssessmentService.publish_assessment(draft_assessment, actor=admin_user, enforce_audience=True)
        draft_assessment.refresh_from_db()
        assert draft_assessment.status == AssessmentStatus.PUBLISHED

        # API attempt
        url = reverse('assessments:admin-assessment-audience', kwargs={'pk': draft_assessment.id})
        res = admin_client.post(url, {"target_section_ids": [str(sections["AIML-B"].id)]}, format='json')
        assert res.status_code == status.HTTP_403_FORBIDDEN

    def test_direct_m2m_mutation_blocked_by_signal_on_published(self, draft_assessment, cohort_students, sections, admin_user):
        """Direct Django ORM M2M operations (.add, .remove, .clear, .set) raise PermissionDenied."""
        AssessmentAudienceService.configure_audience(
            draft_assessment,
            section_ids=[sections["AIML-A"].id],
            actor=admin_user
        )
        AssessmentService.publish_assessment(draft_assessment, actor=admin_user, enforce_audience=True)
        draft_assessment.refresh_from_db()

        # Attempt M2M .add()
        with transaction.atomic():
            with pytest.raises(PermissionDenied):
                draft_assessment.target_sections.add(sections["AIML-B"])

        # Attempt M2M .remove()
        with transaction.atomic():
            with pytest.raises(PermissionDenied):
                draft_assessment.target_sections.remove(sections["AIML-A"])

        # Attempt M2M .clear()
        with transaction.atomic():
            with pytest.raises(PermissionDenied):
                draft_assessment.target_sections.clear()

        # Attempt target_students .add()
        with transaction.atomic():
            with pytest.raises(PermissionDenied):
                draft_assessment.target_students.add(cohort_students["s5"])

        # Reverse M2M mutation (.add from Section side)
        with transaction.atomic():
            with pytest.raises(PermissionDenied):
                sections["CSE-A"].targeted_assessments.add(draft_assessment)


# ==============================================================================
# 6. Publish Flow & Access Authorization
# ==============================================================================

@pytest.mark.django_db
class TestPublishFlowAndAccessControl:
    def test_publish_blocked_when_zero_audience(self, admin_client, draft_assessment):
        """Publishing with no target sections or students is rejected."""
        url = reverse('assessments:admin-assessment-publish', kwargs={'pk': draft_assessment.id})
        res = admin_client.post(url)
        assert res.status_code == status.HTTP_400_BAD_REQUEST
        body = res.json()
        error_msg = str(body.get('error', {})) + str(body.get('message', ''))
        assert "Select at least one student or section" in error_msg

    def test_publish_creates_authoritative_assignments(self, draft_assessment, cohort_students, sections, admin_user):
        """Publishing atomically creates AssessmentAssignment records for all eligible students."""
        AssessmentAudienceService.configure_audience(
            draft_assessment,
            section_ids=[sections["AIML-A"].id],
            student_ids=[cohort_students["s5"].id],
            actor=admin_user
        )
        AssessmentService.publish_assessment(draft_assessment, actor=admin_user, enforce_audience=True)

        # Assignments should exist for s1, s2 (AIML-A) and s5 (CSE-A)
        assigned_user_ids = set(AssessmentAssignment.objects.filter(assessment=draft_assessment).values_list('student_id', flat=True))
        assert assigned_user_ids == {cohort_students["s1"].id, cohort_students["s2"].id, cohort_students["s5"].id}

    def test_student_visibility_and_idor_protection(self, api_client, draft_assessment, cohort_students, sections, admin_user):
        """Assigned students can view the assessment; unassigned students cannot see it and are rejected on detail."""
        AssessmentAudienceService.configure_audience(
            draft_assessment,
            section_ids=[sections["AIML-A"].id],
            actor=admin_user
        )
        AssessmentService.publish_assessment(draft_assessment, actor=admin_user, enforce_audience=True)

        assigned_student = cohort_students["s1"]
        unassigned_student = cohort_students["s5"]

        # 1. Assigned student checks list
        api_client.force_authenticate(user=assigned_student)
        list_url = reverse('assessments:student-assessment-list')
        res_assigned = api_client.get(list_url)
        assert res_assigned.status_code == 200
        assigned_data = res_assigned.json()['data']
        assigned_pks = [a['id'] for a in (assigned_data['results'] if isinstance(assigned_data, dict) and 'results' in assigned_data else assigned_data)]
        assert str(draft_assessment.id) in assigned_pks

        # 2. Unassigned student checks list
        api_client.force_authenticate(user=unassigned_student)
        res_unassigned = api_client.get(list_url)
        assert res_unassigned.status_code == 200
        unassigned_data = res_unassigned.json()['data']
        unassigned_pks = [a['id'] for a in (unassigned_data['results'] if isinstance(unassigned_data, dict) and 'results' in unassigned_data else unassigned_data)]
        assert str(draft_assessment.id) not in unassigned_pks

        # 3. Unassigned student direct IDOR attempt
        detail_url = reverse('assessments:student-assessment-detail', kwargs={'pk': draft_assessment.id})
        res_idor = api_client.get(detail_url)
        assert res_idor.status_code in (status.HTTP_404_NOT_FOUND, status.HTTP_403_FORBIDDEN)

    def test_student_section_change_preserves_historical_assignments(self, draft_assessment, cohort_students, sections, admin_user):
        """Moving a student to a different section after publish does NOT delete their assignment."""
        AssessmentAudienceService.configure_audience(
            draft_assessment,
            section_ids=[sections["AIML-A"].id],
            actor=admin_user
        )
        AssessmentService.publish_assessment(draft_assessment, actor=admin_user, enforce_audience=True)

        s1 = cohort_students["s1"]
        profile = s1.student_profile
        # Move s1 from AIML-A to CSE-A
        StudentService.change_student_section(profile, new_section=sections["CSE-A"], actor=admin_user)

        # Assignment must still exist!
        has_assignment = AssessmentAssignment.objects.filter(assessment=draft_assessment, student=s1).exists()
        assert has_assignment is True
