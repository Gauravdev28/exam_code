import pytest
import io
import json
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status

from apps.accounts.models import User, Role, StudentProfile
from apps.questions.models import Question, QuestionVersion, QuestionType, Difficulty, VersionStatus
from apps.assessments.models import (
    Assessment,
    AssessmentStatus,
    AssessmentQuestion,
    AssessmentAssignment,
    TestAttempt,
    AttemptStatus,
    AttemptAnswer,
    ResultVisibility,
)
from apps.assessments.services import AssessmentSnapshotService
from apps.results.models import (
    AssessmentResult,
    ResultStatus,
    ReportJob,
    ReportType,
    ReportFormat,
    ReportStatus,
)
from apps.results.services import ResultFinalizationService, ReportService


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def test_data(db):
    admin = User.objects.create_user(
        email="admin_integ@codeguard.test",
        password="AdminPassword123!",
        role=Role.ADMIN
    )
    student1 = User.objects.create_user(
        email="student1_integ@codeguard.test",
        password="StudentPassword123!",
        role=Role.STUDENT
    )
    StudentProfile.objects.create(
        user=student1,
        roll_number="CS-001",
        euid="EUID-BOB-001"
    )

    student2 = User.objects.create_user(
        email="student2_integ@codeguard.test",
        password="StudentPassword123!",
        role=Role.STUDENT
    )
    StudentProfile.objects.create(
        user=student2,
        roll_number="CS-002",
        euid="EUID-CHARLIE-002"
    )

    q1 = Question.objects.create(created_by=admin)
    qv1 = QuestionVersion.objects.create(
        question=q1,
        version_number=1,
        title="Q1 MCQ",
        description="Select correct",
        question_type=QuestionType.MCQ,
        difficulty=Difficulty.EASY,
        status=VersionStatus.PUBLISHED,
        type_config={"options": [{"id": "1", "text": "A"}, {"id": "2", "text": "B"}], "correct_options": ["1"]},
        created_by=admin
    )
    qv1.tags.create(name="Mathematics")

    assessment = Assessment.objects.create(
        title="Integration Exam",
        description="Exam description",
        start_datetime=timezone.now() - timedelta(hours=2),
        end_datetime=timezone.now() + timedelta(hours=2),
        duration_minutes=60,
        total_points=10,
        passing_percentage=Decimal('50.00'),
        result_visibility=ResultVisibility.IMMEDIATE,
        created_by=admin,
        status=AssessmentStatus.DRAFT
    )
    AssessmentQuestion.objects.create(
        assessment=assessment,
        question_version=qv1,
        order=1,
        points=10
    )

    snapshot = AssessmentSnapshotService.create_snapshot(assessment, actor=admin)
    assessment.status = AssessmentStatus.PUBLISHED
    assessment.published_at = timezone.now()
    assessment.save()

    # Assign students
    AssessmentAssignment.objects.create(assessment=assessment, student=student1, assigned_by=admin)
    AssessmentAssignment.objects.create(assessment=assessment, student=student2, assigned_by=admin)

    # Attempt 1: student 1 correct
    att1 = TestAttempt.objects.create(
        assessment=assessment,
        assessment_snapshot=snapshot,
        student=student1,
        attempt_number=1,
        started_at=timezone.now() - timedelta(minutes=45),
        status=AttemptStatus.SUBMITTED,
        submitted_at=timezone.now() - timedelta(minutes=15)
    )
    sq1 = snapshot.snapshot_questions.first()
    AttemptAnswer.objects.create(
        attempt=att1,
        snapshot_question=sq1,
        question_id=sq1.snapshot_question_id,
        is_answered=True,
        selected_options=["1"]
    )
    res1 = ResultFinalizationService.finalize_attempt(attempt_id=str(att1.id))

    # Attempt 2: student 2 skipped
    att2 = TestAttempt.objects.create(
        assessment=assessment,
        assessment_snapshot=snapshot,
        student=student2,
        attempt_number=1,
        started_at=timezone.now() - timedelta(minutes=40),
        status=AttemptStatus.SUBMITTED,
        submitted_at=timezone.now() - timedelta(minutes=10)
    )
    res2 = ResultFinalizationService.finalize_attempt(attempt_id=str(att2.id))

    return {
        "admin": admin,
        "student1": student1,
        "student2": student2,
        "assessment": assessment,
        "attempt1": att1,
        "attempt2": att2,
        "result1": res1,
        "result2": res2
    }


@pytest.mark.django_db
def test_student_attempt_result_view(api_client, test_data):
    student1 = test_data['student1']
    att1 = test_data['attempt1']

    api_client.force_authenticate(user=student1)
    res = api_client.get(f"/api/v1/student/attempts/{att1.id}/result/")
    assert res.status_code == status.HTTP_200_OK
    assert res.data['data']['total_score_earned'] == '10.00'
    assert res.data['data']['is_passed'] is True
    assert len(res.data['data']['question_results']) == 1


@pytest.mark.django_db
def test_result_visibility_gating_after_deadline(api_client, test_data):
    student1 = test_data['student1']
    att1 = test_data['attempt1']
    assessment = test_data['assessment']

    # Set visibility to AFTER_DEADLINE with end_datetime in future
    Assessment.objects.filter(id=assessment.id).update(
        result_visibility=ResultVisibility.AFTER_DEADLINE,
        end_datetime=timezone.now() + timedelta(days=1)
    )

    api_client.force_authenticate(user=student1)
    res = api_client.get(f"/api/v1/student/attempts/{att1.id}/result/")
    assert res.status_code == status.HTTP_403_FORBIDDEN

    # Move deadline to past
    Assessment.objects.filter(id=assessment.id).update(
        end_datetime=timezone.now() - timedelta(minutes=5)
    )

    res = api_client.get(f"/api/v1/student/attempts/{att1.id}/result/")
    assert res.status_code == status.HTTP_200_OK


@pytest.mark.django_db
def test_result_visibility_gating_manual_release(api_client, test_data):
    admin = test_data['admin']
    student1 = test_data['student1']
    att1 = test_data['attempt1']
    assessment = test_data['assessment']

    # Set visibility to MANUAL
    Assessment.objects.filter(id=assessment.id).update(
        result_visibility=ResultVisibility.MANUAL
    )
    AssessmentResult.objects.filter(assessment_id=assessment.id).update(is_released=False)

    # Student cannot view yet
    api_client.force_authenticate(user=student1)
    res = api_client.get(f"/api/v1/student/attempts/{att1.id}/result/")
    assert res.status_code == status.HTTP_403_FORBIDDEN

    # Admin releases results
    api_client.force_authenticate(user=admin)
    rel_res = api_client.post(f"/api/v1/admin/assessments/{assessment.id}/release-results/")
    assert rel_res.status_code == status.HTTP_200_OK
    assert rel_res.data['data']['released_count'] == 2

    # Student can now view
    api_client.force_authenticate(user=student1)
    res = api_client.get(f"/api/v1/student/attempts/{att1.id}/result/")
    assert res.status_code == status.HTTP_200_OK


@pytest.mark.django_db
def test_admin_assessment_results_roster_and_analytics(api_client, test_data):
    admin = test_data['admin']
    assessment = test_data['assessment']

    api_client.force_authenticate(user=admin)

    # 1. Roster
    res = api_client.get(f"/api/v1/admin/assessments/{assessment.id}/results/?search=EUID-BOB-001")
    assert res.status_code == status.HTTP_200_OK
    assert res.data['count'] == 1
    assert res.data['results'][0]['student']['euid'] == "EUID-BOB-001"

    # 2. Assessment Analytics
    res_analytics = api_client.get(f"/api/v1/admin/assessments/{assessment.id}/analytics/")
    assert res_analytics.status_code == status.HTTP_200_OK
    cohort = res_analytics.data['data']['cohort_metrics']
    assert cohort['total_completed'] == 2
    assert cohort['pass_rate_percentage'] == 50.0

    # 3. Question Item Analytics
    res_q = api_client.get(f"/api/v1/admin/assessments/{assessment.id}/analytics/questions/")
    assert res_q.status_code == status.HTTP_200_OK
    assert len(res_q.data['data']['questions']) == 1
    q_data = res_q.data['data']['questions'][0]
    assert q_data['difficulty_index_p'] == 0.50
    assert q_data['breakdown']['correct'] == 1
    assert q_data['breakdown']['skipped'] == 1


@pytest.mark.django_db
def test_report_generation_and_download(api_client, test_data):
    admin = test_data['admin']
    assessment = test_data['assessment']

    api_client.force_authenticate(user=admin)

    # 1. Request CSV report
    req_res = api_client.post("/api/v1/admin/reports/", {
        "report_type": ReportType.ASSESSMENT_ROSTER,
        "format": ReportFormat.CSV,
        "assessment_id": str(assessment.id)
    })
    assert req_res.status_code == status.HTTP_202_ACCEPTED
    job_id = req_res.data['data']['id']

    # 2. Run report generation synchronously
    job = ReportService.generate_report(job_id)
    assert job.status == ReportStatus.COMPLETED
    assert job.sha256_hash is not None

    # 3. Download
    dl_res = api_client.get(f"/api/v1/admin/reports/{job_id}/download/")
    assert dl_res.status_code == status.HTTP_200_OK
    assert dl_res.headers['Content-Type'] == 'text/csv'


@pytest.mark.django_db
def test_admin_results_pagination_boundary_and_sorting(api_client, test_data):
    admin = test_data['admin']
    assessment = test_data['assessment']

    api_client.force_authenticate(user=admin)

    # Max page_size <= 100 enforced
    res_max = api_client.get(f"/api/v1/admin/assessments/{assessment.id}/results/?page_size=200")
    assert res_max.status_code == status.HTTP_200_OK
    assert len(res_max.data['results']) <= 100

    # Invalid sorting fallback (does not crash or 500)
    res_sort = api_client.get(f"/api/v1/admin/assessments/{assessment.id}/results/?ordering=malicious_field_injection")
    assert res_sort.status_code == status.HTTP_200_OK

    # Valid sort
    res_asc = api_client.get(f"/api/v1/admin/assessments/{assessment.id}/results/?ordering=total_score_earned")
    assert res_asc.status_code == status.HTTP_200_OK


@pytest.mark.django_db
def test_student_topic_performance_analytics(api_client, test_data):
    student1 = test_data['student1']

    api_client.force_authenticate(user=student1)

    res = api_client.get("/api/v1/student/analytics/topics/")
    assert res.status_code == status.HTTP_200_OK
    assert 'topics' in res.data['data']
    topics = res.data['data']['topics']
    assert len(topics) >= 1
    assert topics[0]['tag_name'] == "Mathematics"
    assert topics[0]['questions_attempted'] == 1
    assert topics[0]['accuracy_percentage'] == 100.0

