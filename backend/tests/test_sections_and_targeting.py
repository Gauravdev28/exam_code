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
from apps.assessments.models import Assessment, AssessmentStatus, AssessmentAssignment, AssignmentStatus
from apps.assessments.services import AssessmentService, AssessmentAudienceService
from apps.assessments.serializers import AssessmentAssignmentSerializer
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


# ==============================================================================
# 7. Assessment Audience and Student Assignment Relationship Bug Fixes (Scenarios 1-25)
# ==============================================================================

@pytest.mark.django_db
class TestAssessmentAudienceAndAssignmentBugs:
    """
    Comprehensive regression suite covering Scenarios 1 through 25:
    - Section Audience selection, persistence, GET/refresh survival, and counts (1-7)
    - Student Assignment identity resolution (User.id canonical vs StudentProfile.id),
      serializers, student portal visibility, and access (8-14)
    - Audience vs Assignment consistency across UI paths (15-17)
    - Negative cases, invalid IDs, inactive users, revoked reactivation, lifecycle immutability,
      concurrency, and rollback semantics (18-25)
    """

    def test_01_select_section_save_db_persistence(self, admin_client, draft_assessment, sections):
        """Scenario 1: Select section -> save -> DB persistence."""
        url = reverse('assessments:admin-assessment-audience', kwargs={'pk': draft_assessment.id})
        res = admin_client.post(url, {"section_ids": [str(sections["AIML-A"].id)]}, format='json')
        assert res.status_code == status.HTTP_200_OK
        draft_assessment.refresh_from_db()
        assert list(draft_assessment.target_sections.values_list('id', flat=True)) == [sections["AIML-A"].id]

    def test_02_persisted_section_get_audience_returned(self, admin_client, draft_assessment, sections, cohort_students):
        """Scenario 2: Persisted section -> GET audience -> section returned."""
        draft_assessment.target_sections.set([sections["AIML-A"]])
        url = reverse('assessments:admin-assessment-audience', kwargs={'pk': draft_assessment.id})
        res = admin_client.get(url)
        assert res.status_code == status.HTTP_200_OK
        data = res.json()['data']
        section_codes = [s['code'] for s in data['sections']]
        assert "AIML-A" in section_codes
        assert data['total_eligible'] == 2

    def test_03_refresh_equivalent_api_request_section_remains(self, admin_client, draft_assessment, sections, cohort_students):
        """Scenario 3: Refresh-equivalent API request -> section remains."""
        url = reverse('assessments:admin-assessment-audience', kwargs={'pk': draft_assessment.id})
        res1 = admin_client.post(url, {"section_ids": [str(sections["AIML-A"].id)]}, format='json')
        assert res1.status_code == status.HTTP_200_OK

        # Simulate browser reload by performing GET request
        res2 = admin_client.get(url)
        assert res2.status_code == status.HTTP_200_OK
        data2 = res2.json()['data']
        assert any(s['code'] == 'AIML-A' for s in data2['sections'])
        assert data2['total_eligible'] == 2

    def test_04_section_with_one_enrolled_student_eligible_count_1(self, admin_client, draft_assessment):
        """Scenario 4: Section with one enrolled student -> eligible count = 1."""
        single_sec = Section.objects.create(code="SINGLE-SEC", name="Single Student Section", is_active=True)
        st, _ = StudentService.create_student("single@univ.edu", "SS001", section=single_sec)
        st.student_profile.first_login_required = False
        st.student_profile.save()

        url = reverse('assessments:admin-assessment-audience', kwargs={'pk': draft_assessment.id})
        res = admin_client.post(url, {"section_ids": [str(single_sec.id)]}, format='json')
        assert res.status_code == status.HTTP_200_OK
        data = res.json()['data']
        assert data['total_eligible'] == 1
        assert data['section_student_count'] == 1
        assert data['eligible_student_ids'] == [str(st.id)]

    def test_05_section_publish_creates_correct_assignment(self, admin_client, draft_assessment, sections, cohort_students):
        """Scenario 5: Section -> publish -> correct assignment."""
        url_aud = reverse('assessments:admin-assessment-audience', kwargs={'pk': draft_assessment.id})
        admin_client.post(url_aud, {"section_ids": [str(sections["AIML-A"].id)]}, format='json')

        url_pub = reverse('assessments:admin-assessment-publish', kwargs={'pk': draft_assessment.id})
        res_pub = admin_client.post(url_pub)
        assert res_pub.status_code == status.HTTP_200_OK

        assignments = AssessmentAssignment.objects.filter(assessment=draft_assessment)
        assert assignments.count() == 2
        assigned_user_ids = set(assignments.values_list('student_id', flat=True))
        assert assigned_user_ids == {cohort_students["s1"].id, cohort_students["s2"].id}

    def test_06_multiple_sections_unique_eligible_count(self, admin_client, draft_assessment, sections, cohort_students):
        """Scenario 6: Multiple sections -> unique eligible count."""
        url = reverse('assessments:admin-assessment-audience', kwargs={'pk': draft_assessment.id})
        res = admin_client.post(url, {"section_ids": [str(sections["AIML-A"].id), str(sections["AIML-B"].id)]}, format='json')
        assert res.status_code == status.HTTP_200_OK
        data = res.json()['data']
        assert data['total_eligible'] == 4
        assert data['section_student_count'] == 4

    def test_07_student_in_multiple_sections_or_individual_deduplication(self, admin_client, draft_assessment, sections, cohort_students):
        """Scenario 7: Student in multiple sections/section + individual -> one assignment."""
        url = reverse('assessments:admin-assessment-audience', kwargs={'pk': draft_assessment.id})
        res = admin_client.post(url, {
            "section_ids": [str(sections["AIML-A"].id)],
            "student_ids": [str(cohort_students["s1"].id)]
        }, format='json')
        assert res.status_code == status.HTTP_200_OK
        data = res.json()['data']
        assert data['total_eligible'] == 2
        assert data['overlap_count'] == 1

        url_pub = reverse('assessments:admin-assessment-publish', kwargs={'pk': draft_assessment.id})
        admin_client.post(url_pub)
        assert AssessmentAssignment.objects.filter(assessment=draft_assessment, student=cohort_students["s1"]).count() == 1

    def test_08_individual_assignment_creates_correct_assignment(self, admin_client, draft_assessment, cohort_students):
        """Scenario 8: Individual assignment -> correct AssessmentAssignment."""
        url = reverse('assessments:admin-assessment-assignment-list', kwargs={'pk': draft_assessment.id})
        res = admin_client.post(url, {"student_ids": [str(cohort_students["s7"].id)]}, format='json')
        assert res.status_code == status.HTTP_201_CREATED

        assignment = AssessmentAssignment.objects.filter(assessment=draft_assessment, student=cohort_students["s7"]).first()
        assert assignment is not None
        assert assignment.status == AssignmentStatus.ASSIGNED

    def test_09_student_profile_id_input_creates_canonical_user_id_assignment(self, admin_client, draft_assessment, cohort_students):
        """Scenario 9: StudentProfile.id input -> correct User ID assignment."""
        s7_profile_id = str(cohort_students["s7"].student_profile.id)
        url = reverse('assessments:admin-assessment-assignment-list', kwargs={'pk': draft_assessment.id})
        res = admin_client.post(url, {"student_ids": [s7_profile_id]}, format='json')
        assert res.status_code == status.HTTP_201_CREATED

        assignment = AssessmentAssignment.objects.filter(assessment=draft_assessment, student_id=cohort_students["s7"].id).first()
        assert assignment is not None
        assert assignment.student_id == cohort_students["s7"].id

    def test_10_assignment_serializer_fields_and_ids(self, admin_client, draft_assessment, cohort_students):
        """Scenario 10: Serializer returns student_id/user_id/student_profile_id."""
        s7 = cohort_students["s7"]
        url_post = reverse('assessments:admin-assessment-assignment-list', kwargs={'pk': draft_assessment.id})
        admin_client.post(url_post, {"student_ids": [str(s7.id)]}, format='json')

        url_get = reverse('assessments:admin-assessment-assignment-list', kwargs={'pk': draft_assessment.id})
        res = admin_client.get(url_get)
        assert res.status_code == status.HTTP_200_OK
        data = res.json()['data']
        item = [d for d in data if str(d['student_id']) == str(s7.id)][0]

        assert str(item['student_id']) == str(s7.id)
        assert str(item['user_id']) == str(s7.id)
        assert str(item['student_profile_id']) == str(s7.student_profile.id)
        assert item['student_email'] == s7.email
        assert item['student_roll_number'] == s7.student_profile.roll_number
        assert item['status'] == AssignmentStatus.ASSIGNED

    def test_11_student_assessments_endpoint_returns_assignment(self, api_client, draft_assessment, cohort_students, admin_user):
        """Scenario 11: /student/assessments/ returns assignment."""
        s7 = cohort_students["s7"]
        draft_assessment.start_datetime = timezone.now() - timedelta(minutes=5)
        draft_assessment.save()
        AssessmentService.assign_students(draft_assessment, [str(s7.id)], actor=admin_user)
        AssessmentService.publish_assessment(draft_assessment, actor=admin_user, enforce_audience=False)

        api_client.force_authenticate(user=s7)
        url = reverse('assessments:student-assessment-list')
        res = api_client.get(url)
        assert res.status_code == status.HTTP_200_OK
        assessments = res.json()['data']
        results = assessments['results'] if isinstance(assessments, dict) and 'results' in assessments else assessments
        pks = [a['id'] for a in results]
        assert str(draft_assessment.id) in pks

    def test_12_student_can_access_assigned_assessment(self, api_client, draft_assessment, cohort_students, admin_user):
        """Scenario 12: Student can access and start assigned assessment."""
        s7 = cohort_students["s7"]
        draft_assessment.start_datetime = timezone.now() - timedelta(minutes=5)
        draft_assessment.save()
        AssessmentService.assign_students(draft_assessment, [str(s7.id)], actor=admin_user)
        AssessmentService.publish_assessment(draft_assessment, actor=admin_user, enforce_audience=False)

        api_client.force_authenticate(user=s7)
        detail_url = reverse('assessments:student-assessment-detail', kwargs={'pk': draft_assessment.id})
        res_detail = api_client.get(detail_url)
        assert res_detail.status_code == status.HTTP_200_OK

        start_url = reverse('assessments:student-assessment-start', kwargs={'pk': draft_assessment.id})
        res_start = api_client.post(start_url)
        assert res_start.status_code == status.HTTP_201_CREATED

    def test_13_assign_same_student_twice_no_duplicate(self, admin_client, draft_assessment, cohort_students):
        """Scenario 13: Assign same student twice -> no duplicate."""
        s7 = cohort_students["s7"]
        url = reverse('assessments:admin-assessment-assignment-list', kwargs={'pk': draft_assessment.id})
        res1 = admin_client.post(url, {"student_ids": [str(s7.id)]}, format='json')
        assert res1.status_code == status.HTTP_201_CREATED
        res2 = admin_client.post(url, {"student_ids": [str(s7.id)]}, format='json')
        assert res2.status_code == status.HTTP_201_CREATED

        assert AssessmentAssignment.objects.filter(assessment=draft_assessment, student=s7).count() == 1

    def test_14_section_plus_individual_one_assignment(self, draft_assessment, sections, cohort_students, admin_user):
        """Scenario 14: Section + individual -> one assignment."""
        AssessmentAudienceService.configure_audience(
            draft_assessment,
            section_ids=[sections["AIML-A"].id],
            student_ids=[cohort_students["s1"].id],
            actor=admin_user
        )
        AssessmentService.publish_assessment(draft_assessment, actor=admin_user)
        assert AssessmentAssignment.objects.filter(assessment=draft_assessment, student=cohort_students["s1"]).count() == 1

    def test_15_assignment_through_target_audience(self, admin_client, draft_assessment, cohort_students):
        """Scenario 15: Assignment through Target Audience."""
        s7 = cohort_students["s7"]
        url_aud = reverse('assessments:admin-assessment-audience', kwargs={'pk': draft_assessment.id})
        res_aud = admin_client.post(url_aud, {"student_ids": [str(s7.id)]}, format='json')
        assert res_aud.status_code == status.HTTP_200_OK
        assert res_aud.json()['data']['total_eligible'] == 1

        url_pub = reverse('assessments:admin-assessment-publish', kwargs={'pk': draft_assessment.id})
        res_pub = admin_client.post(url_pub)
        assert res_pub.status_code == status.HTTP_200_OK

        assignment = AssessmentAssignment.objects.filter(assessment=draft_assessment, student=s7).first()
        assert assignment is not None
        assert assignment.status == AssignmentStatus.ASSIGNED

    def test_16_assignment_through_external_assignment_modal(self, admin_client, draft_assessment, cohort_students):
        """Scenario 16: Assignment through external Assignment Modal reflected in Target Audience."""
        s7 = cohort_students["s7"]
        url_assign = reverse('assessments:admin-assessment-assignment-list', kwargs={'pk': draft_assessment.id})
        res_assign = admin_client.post(url_assign, {"student_ids": [str(s7.id)]}, format='json')
        assert res_assign.status_code == status.HTTP_201_CREATED

        url_aud = reverse('assessments:admin-assessment-audience', kwargs={'pk': draft_assessment.id})
        res_aud = admin_client.get(url_aud)
        assert res_aud.status_code == status.HTTP_200_OK
        data = res_aud.json()['data']
        assert str(s7.id) in data['eligible_student_ids']
        assert any(st['id'] == str(s7.id) for st in data['students'])

    def test_17_both_paths_create_equivalent_authoritative_relationships(self, admin_user, cohort_students):
        """Scenario 17: Both paths create equivalent authoritative assignment relationships."""
        q, v = QuestionService.create_question(
            question_type=QuestionType.MCQ,
            title="Q17",
            description="Q17 desc",
            points=10,
            type_config={
                "options": [{"id": "A", "text": "1"}, {"id": "B", "text": "2"}],
                "correct_options": ["A"]
            },
            actor=admin_user
        )
        pv = QuestionService.publish_version(v, actor=admin_user)

        now = timezone.now()
        a1 = AssessmentService.create_assessment(
            "Path 1",
            start_datetime=now,
            end_datetime=now + timedelta(days=1),
            total_points=10,
            created_by=admin_user
        )
        AssessmentService.add_question(assessment=a1, question_version=pv, actor=admin_user, points=10)
        AssessmentAudienceService.configure_audience(a1, student_ids=[cohort_students["s1"].id], actor=admin_user)
        AssessmentService.publish_assessment(a1, actor=admin_user, enforce_audience=False)

        a2 = AssessmentService.create_assessment(
            "Path 2",
            start_datetime=now,
            end_datetime=now + timedelta(days=1),
            total_points=10,
            created_by=admin_user
        )
        AssessmentService.add_question(assessment=a2, question_version=pv, actor=admin_user, points=10)
        AssessmentService.assign_students(a2, [str(cohort_students["s1"].id)], actor=admin_user)
        AssessmentService.publish_assessment(a2, actor=admin_user, enforce_audience=False)

        ass1 = AssessmentAssignment.objects.get(assessment=a1, student=cohort_students["s1"])
        ass2 = AssessmentAssignment.objects.get(assessment=a2, student=cohort_students["s1"])

        assert ass1.status == ass2.status == AssignmentStatus.ASSIGNED
        assert ass1.student_id == ass2.student_id == cohort_students["s1"].id

    def test_18_invalid_student_or_profile_id_returns_400_zero_mutation(self, admin_client, draft_assessment):
        """TEST 18: Invalid student/profile ID -> HTTP 400 -> zero mutation."""
        url = reverse('assessments:admin-assessment-assignment-list', kwargs={'pk': draft_assessment.id})
        bad_id = "00000000-0000-0000-0000-000000000000"
        res = admin_client.post(url, {"student_ids": [bad_id]}, format='json')
        assert res.status_code == status.HTTP_400_BAD_REQUEST
        body = res.json()
        error_dict = body.get('error', {})
        details = error_dict.get('details', error_dict) if isinstance(error_dict, dict) else {}
        assert details.get('error') == "INVALID_STUDENT_IDS" or body.get('error') == "INVALID_STUDENT_IDS"
        assert bad_id in details.get('invalid_ids', []) or bad_id in str(body)
        assert AssessmentAssignment.objects.filter(assessment=draft_assessment).count() == 0

    def test_19_mixed_user_ids_and_student_profile_ids(self, admin_client, draft_assessment, cohort_students):
        """TEST 19: Mixed User IDs + StudentProfile IDs -> both resolve correctly -> canonical User IDs stored."""
        s1 = cohort_students["s1"]
        s2 = cohort_students["s2"]
        payload = {
            "student_ids": [str(s1.id), str(s2.student_profile.id)]
        }
        url = reverse('assessments:admin-assessment-assignment-list', kwargs={'pk': draft_assessment.id})
        res = admin_client.post(url, payload, format='json')
        assert res.status_code == status.HTTP_201_CREATED

        assignments = AssessmentAssignment.objects.filter(assessment=draft_assessment)
        assert assignments.count() == 2
        student_user_ids = set(assignments.values_list('student_id', flat=True))
        assert student_user_ids == {s1.id, s2.id}

    def test_20_inactive_student_cannot_be_assigned(self, admin_client, draft_assessment):
        """TEST 20: Inactive student -> cannot be assigned."""
        inactive_s, _ = StudentService.create_student("inactive_s@univ.edu", "INACT99")
        inactive_s.is_active = False
        inactive_s.save()

        url = reverse('assessments:admin-assessment-assignment-list', kwargs={'pk': draft_assessment.id})
        res = admin_client.post(url, {"student_ids": [str(inactive_s.id)]}, format='json')
        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert AssessmentAssignment.objects.filter(assessment=draft_assessment, student=inactive_s).count() == 0

    def test_21_revoked_assignment_reactivation_no_duplicate(self, admin_client, draft_assessment, cohort_students):
        """TEST 21: Revoked assignment -> reactivation follows existing lifecycle -> no duplicate assignment."""
        s1 = cohort_students["s1"]
        # 1. Assign
        url_assign = reverse('assessments:admin-assessment-assignment-list', kwargs={'pk': draft_assessment.id})
        admin_client.post(url_assign, {"student_ids": [str(s1.id)]}, format='json')
        assignment = AssessmentAssignment.objects.get(assessment=draft_assessment, student=s1)
        assert assignment.status == AssignmentStatus.ASSIGNED

        # 2. Revoke using StudentProfile.id
        url_revoke = reverse('assessments:admin-assessment-assignment-revoke', kwargs={
            'pk': draft_assessment.id,
            'student_id': str(s1.student_profile.id)
        })
        res_revoke = admin_client.delete(url_revoke)
        assert res_revoke.status_code == status.HTTP_200_OK
        assignment.refresh_from_db()
        assert assignment.status == AssignmentStatus.REVOKED

        # 3. Reactivate
        res_reassign = admin_client.post(url_assign, {"student_ids": [str(s1.id)]}, format='json')
        assert res_reassign.status_code == status.HTTP_201_CREATED
        assignment.refresh_from_db()
        assert assignment.status == AssignmentStatus.ASSIGNED
        assert AssessmentAssignment.objects.filter(assessment=draft_assessment, student=s1).count() == 1

    def test_22_published_assessment_audience_mutation_preserves_snapshot(self, admin_client, draft_assessment, sections, admin_user):
        """TEST 22: Published assessment audience mutation -> existing lifecycle restrictions preserved -> snapshot integrity remains intact."""
        AssessmentAudienceService.configure_audience(draft_assessment, section_ids=[sections["AIML-A"].id], actor=admin_user)
        published = AssessmentService.publish_assessment(draft_assessment, actor=admin_user)
        snapshot = published.snapshot
        assert snapshot is not None
        snap_data_before = snapshot.snapshot_data

        url = reverse('assessments:admin-assessment-audience', kwargs={'pk': published.id})
        res = admin_client.post(url, {"section_ids": [str(sections["CSE-A"].id)]}, format='json')
        assert res.status_code in (status.HTTP_403_FORBIDDEN, status.HTTP_400_BAD_REQUEST)

        snapshot.refresh_from_db()
        assert snapshot.snapshot_data == snap_data_before

    def test_23_concurrent_duplicate_assignment_creates_single_assignment(self, draft_assessment, cohort_students, admin_user):
        """TEST 23: Concurrent duplicate assignment -> exactly one AssessmentAssignment."""
        s1 = cohort_students["s1"]
        resA = AssessmentService.assign_students(draft_assessment, [str(s1.id)], actor=admin_user)
        resB = AssessmentService.assign_students(draft_assessment, [str(s1.id)], actor=admin_user)

        assert len(resA) == 1
        assert len(resB) == 1
        assert resA[0].id == resB[0].id
        assert AssessmentAssignment.objects.filter(assessment=draft_assessment, student=s1).count() == 1

    def test_24_audience_request_valid_and_invalid_rollback_no_partial_mutation(self, admin_client, draft_assessment, cohort_students):
        """TEST 24: Audience request containing valid + invalid student -> HTTP 400 -> complete rollback -> zero partial mutation."""
        s1 = cohort_students["s1"]
        bad_id = "00000000-0000-0000-0000-000000000000"
        url = reverse('assessments:admin-assessment-audience', kwargs={'pk': draft_assessment.id})
        payload = {
            "student_ids": [str(s1.id), bad_id]
        }
        res = admin_client.post(url, payload, format='json')
        assert res.status_code == status.HTTP_400_BAD_REQUEST
        body = res.json()
        error_dict = body.get('error', {})
        details = error_dict.get('details', error_dict) if isinstance(error_dict, dict) else {}
        assert details.get('error') == "INVALID_STUDENT_IDS" or body.get('error') == "INVALID_STUDENT_IDS"
        assert bad_id in details.get('invalid_ids', []) or bad_id in str(body)

        draft_assessment.refresh_from_db()
        assert draft_assessment.target_students.count() == 0

    def test_25_assignment_serializer_canonical_identities(self, draft_assessment, cohort_students, admin_user):
        """TEST 25: Assignment serializer -> student_id == User.id -> user_id == User.id -> student_profile_id == profile ID."""
        s1 = cohort_students["s1"]
        assignment = AssessmentAssignment.objects.create(
            assessment=draft_assessment,
            student=s1,
            assigned_by=admin_user,
            status=AssignmentStatus.ASSIGNED
        )
        serializer = AssessmentAssignmentSerializer(assignment)
        data = serializer.data

        assert str(data['student_id']) == str(s1.id)
        assert str(data['user_id']) == str(s1.id)
        assert str(data['student_profile_id']) == str(s1.student_profile.id)
        assert data['student_email'] == s1.email
        assert data['student_roll_number'] == s1.student_profile.roll_number
        assert data['status'] == AssignmentStatus.ASSIGNED
        assert data['assigned_by_email'] == admin_user.email

    def test_26_malformed_student_id_returns_400_invalid_student_ids(self, draft_assessment):
        """TEST 26: Malformed non-UUID student ID -> HTTP 400 INVALID_STUDENT_IDS safely without DB crash."""
        from apps.assessments.services import resolve_student_users
        with pytest.raises(DRFValidationError) as exc:
            resolve_student_users(["not-a-valid-uuid"])
        err = exc.value.detail if hasattr(exc.value, 'detail') else exc.value.args[0]
        assert err.get('error') == "INVALID_STUDENT_IDS"
        assert "not-a-valid-uuid" in err.get('invalid_ids', [])

    def test_27_assign_students_preserves_input_order(self, draft_assessment, cohort_students, admin_user):
        """TEST 27: assign_students processes deterministically while preserving caller's requested input order."""
        s1 = cohort_students["s1"]
        s2 = cohort_students["s2"]
        # Intentionally pass s2 before s1
        res = AssessmentService.assign_students(draft_assessment, [str(s2.id), str(s1.id)], actor=admin_user)
        assert len(res) == 2
        assert res[0].student_id == s2.id
        assert res[1].student_id == s1.id

