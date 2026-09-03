import pytest
import os
import hashlib
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status

from apps.accounts.models import User, Role, StudentProfile, AuditLog
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
from apps.evaluator.models import CodeSubmission, SubmissionType, CodeVerdict
from apps.results.models import (
    AssessmentResult,
    QuestionResult,
    ResultStatus,
    ReportJob,
    ReportType,
    ReportFormat,
    ReportStatus,
)
from apps.results.services import ResultFinalizationService, ReportService, AnalyticsService


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def security_setup(db):
    admin = User.objects.create_user(
        email="admin_sec@codeguard.test",
        password="AdminPassword123!",
        role=Role.ADMIN
    )
    student_alice = User.objects.create_user(
        email="alice_sec@codeguard.test",
        password="StudentPassword123!",
        role=Role.STUDENT
    )
    StudentProfile.objects.create(
        user=student_alice,
        roll_number="CS-ALICE-01",
        euid="EUID-ALICE-01"
    )

    student_bob = User.objects.create_user(
        email="bob_sec@codeguard.test",
        password="StudentPassword123!",
        role=Role.STUDENT
    )
    StudentProfile.objects.create(
        user=student_bob,
        roll_number="CS-BOB-02",
        euid="EUID-BOB-02"
    )

    q = Question.objects.create(created_by=admin)
    qv = QuestionVersion.objects.create(
        question=q,
        version_number=1,
        title="Coding Question with Hidden Tests",
        description="Write solution",
        question_type=QuestionType.CODING,
        difficulty=Difficulty.HARD,
        status=VersionStatus.PUBLISHED,
        type_config={
            "initial_templates": {"python": "def solve(): pass"},
            "test_cases": [
                {"input_data": "1", "expected_output": "1", "is_hidden": False, "points": 5},
                {"input_data": "SECRET_INPUT_999", "expected_output": "SECRET_OUTPUT_999", "is_hidden": True, "points": 5}
            ]
        },
        created_by=admin
    )

    assessment = Assessment.objects.create(
        title="Security Exam",
        description="Exam description",
        start_datetime=timezone.now() - timedelta(hours=1),
        end_datetime=timezone.now() + timedelta(hours=1),
        duration_minutes=60,
        total_points=10,
        passing_percentage=Decimal('50.00'),
        result_visibility=ResultVisibility.IMMEDIATE,
        created_by=admin,
        status=AssessmentStatus.DRAFT
    )
    AssessmentQuestion.objects.create(
        assessment=assessment,
        question_version=qv,
        order=1,
        points=10
    )

    snapshot = AssessmentSnapshotService.create_snapshot(assessment, actor=admin)
    assessment.status = AssessmentStatus.PUBLISHED
    assessment.published_at = timezone.now()
    assessment.save()

    AssessmentAssignment.objects.create(assessment=assessment, student=student_alice, assigned_by=admin)
    AssessmentAssignment.objects.create(assessment=assessment, student=student_bob, assigned_by=admin)

    # Alice attempt
    att_alice = TestAttempt.objects.create(
        assessment=assessment,
        assessment_snapshot=snapshot,
        student=student_alice,
        attempt_number=1,
        started_at=timezone.now() - timedelta(minutes=30),
        status=AttemptStatus.SUBMITTED,
        submitted_at=timezone.now()
    )
    # Alice coding submission
    sq = snapshot.snapshot_questions.first()
    CodeSubmission.objects.create(
        attempt=att_alice,
        snapshot_question=sq,
        language='python',
        source_code="def solve(): return 1",
        submission_type=SubmissionType.SUBMIT,
        status='COMPLETED',
        verdict=CodeVerdict.ACCEPTED,
        score_awarded=Decimal('10.00'),
        passed_test_cases=2,
        total_test_cases=2,
        execution_time_ms=45,
        memory_used_kb=2048
    )
    res_alice = ResultFinalizationService.finalize_attempt(attempt_id=str(att_alice.id))

    # Bob attempt
    att_bob = TestAttempt.objects.create(
        assessment=assessment,
        assessment_snapshot=snapshot,
        student=student_bob,
        attempt_number=1,
        started_at=timezone.now() - timedelta(minutes=30),
        status=AttemptStatus.SUBMITTED,
        submitted_at=timezone.now()
    )
    res_bob = ResultFinalizationService.finalize_attempt(attempt_id=str(att_bob.id))

    return {
        "admin": admin,
        "alice": student_alice,
        "bob": student_bob,
        "assessment": assessment,
        "attempt_alice": att_alice,
        "attempt_bob": att_bob,
        "result_alice": res_alice,
        "result_bob": res_bob
    }


@pytest.mark.django_db
def test_student_cannot_view_other_student_result_idor(api_client, security_setup):
    bob = security_setup['bob']
    att_alice = security_setup['attempt_alice']
    res_alice = security_setup['result_alice']

    api_client.force_authenticate(user=bob)

    # 1. Attempt endpoint IDOR
    res1 = api_client.get(f"/api/v1/student/attempts/{att_alice.id}/result/")
    assert res1.status_code == status.HTTP_403_FORBIDDEN

    # 2. Result detail endpoint IDOR
    res2 = api_client.get(f"/api/v1/student/results/{res_alice.id}/")
    assert res2.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_student_cannot_access_admin_endpoints(api_client, security_setup):
    alice = security_setup['alice']
    assessment = security_setup['assessment']

    api_client.force_authenticate(user=alice)

    # Admin results list
    res1 = api_client.get(f"/api/v1/admin/assessments/{assessment.id}/results/")
    assert res1.status_code == status.HTTP_403_FORBIDDEN

    # Admin analytics
    res2 = api_client.get(f"/api/v1/admin/assessments/{assessment.id}/analytics/")
    assert res2.status_code == status.HTTP_403_FORBIDDEN

    # Admin question analytics
    res3 = api_client.get(f"/api/v1/admin/assessments/{assessment.id}/analytics/questions/")
    assert res3.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_hidden_test_cases_confidentiality(api_client, security_setup):
    alice = security_setup['alice']
    att_alice = security_setup['attempt_alice']

    api_client.force_authenticate(user=alice)
    res = api_client.get(f"/api/v1/student/attempts/{att_alice.id}/result/")
    assert res.status_code == status.HTTP_200_OK

    data_str = str(res.data)
    assert "SECRET_INPUT_999" not in data_str
    assert "SECRET_OUTPUT_999" not in data_str


@pytest.mark.django_db
def test_small_cohort_proctoring_privacy_safeguard(security_setup):
    assessment = security_setup['assessment']
    analytics = AnalyticsService.get_assessment_analytics(str(assessment.id))

    # Cohort size is 2 (N < 10)
    proct_corr = analytics['proctoring_risk_correlation']
    assert proct_corr['is_available'] is False
    assert "privacy threshold" in proct_corr['reason']


@pytest.mark.django_db
def test_report_sha256_integrity_verification(api_client, security_setup):
    alice = security_setup['alice']
    assessment = security_setup['assessment']

    api_client.force_authenticate(user=alice)

    job = ReportService.create_report_job(
        user=alice,
        report_type=ReportType.STUDENT_SCORECARD,
        format=ReportFormat.PDF,
        assessment_id=str(assessment.id),
        student_id=str(alice.id)
    )
    ReportService.generate_report(str(job.id))
    job.refresh_from_db()

    # Tamper with the report file
    with open(job.file_path, 'a') as f:
        f.write("TAMPERED_CONTENT")

    # Download must fail SHA-256 verification
    dl_res = api_client.get(f"/api/v1/student/reports/{job.id}/download/")
    assert dl_res.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_client_cannot_patch_or_modify_results(api_client, security_setup):
    alice = security_setup['alice']
    res_alice = security_setup['result_alice']

    api_client.force_authenticate(user=alice)

    # Attempting to PUT or PATCH the result endpoint must be rejected
    res_patch = api_client.patch(f"/api/v1/student/results/{res_alice.id}/", {"total_score_earned": "100.00"})
    assert res_patch.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    res_put = api_client.put(f"/api/v1/student/results/{res_alice.id}/", {"total_score_earned": "100.00"})
    assert res_put.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


@pytest.mark.django_db
def test_unreleased_results_blocked_across_all_student_endpoints(api_client, security_setup):
    alice = security_setup['alice']
    att_alice = security_setup['attempt_alice']
    res_alice = security_setup['result_alice']
    assessment = security_setup['assessment']

    # Set visibility to MANUAL and unreleased
    Assessment.objects.filter(id=assessment.id).update(result_visibility=ResultVisibility.MANUAL)
    AssessmentResult.objects.filter(id=res_alice.id).update(is_released=False)

    api_client.force_authenticate(user=alice)

    # 1. Attempt result endpoint -> 403
    r1 = api_client.get(f"/api/v1/student/attempts/{att_alice.id}/result/")
    assert r1.status_code == status.HTTP_403_FORBIDDEN

    # 2. Result detail endpoint -> 403
    r2 = api_client.get(f"/api/v1/student/results/{res_alice.id}/")
    assert r2.status_code == status.HTTP_403_FORBIDDEN

    # 3. Result list endpoint -> filtered out
    r3 = api_client.get("/api/v1/student/results/")
    assert r3.status_code == status.HTTP_200_OK
    assert r3.data['count'] == 0


@pytest.mark.django_db
def test_expired_report_download_returns_410_gone(api_client, security_setup):
    alice = security_setup['alice']
    assessment = security_setup['assessment']

    api_client.force_authenticate(user=alice)

    job = ReportService.create_report_job(
        user=alice,
        report_type=ReportType.STUDENT_SCORECARD,
        format=ReportFormat.PDF,
        assessment_id=str(assessment.id),
        student_id=str(alice.id)
    )
    ReportService.generate_report(str(job.id))
    job.refresh_from_db()

    # Move expiry into past
    ReportJob.objects.filter(id=job.id).update(expires_at=timezone.now() - timedelta(days=1))

    dl_res = api_client.get(f"/api/v1/student/reports/{job.id}/download/")
    assert dl_res.status_code == status.HTTP_410_GONE


@pytest.mark.django_db
def test_controlled_csv_export_schema_whitelisted_columns_only(api_client, security_setup):
    admin = security_setup['admin']
    assessment = security_setup['assessment']

    api_client.force_authenticate(user=admin)

    job = ReportService.create_report_job(
        user=admin,
        report_type=ReportType.ASSESSMENT_ROSTER,
        format=ReportFormat.CSV,
        assessment_id=str(assessment.id)
    )
    ReportService.generate_report(str(job.id))
    job.refresh_from_db()

    with open(job.file_path, 'r') as f:
        header_line = f.readline().strip()

    expected_columns = "euid,roll_number,student_name,student_email,assessment_id,assessment_title,total_score_earned,total_possible_score,percentage,is_passed,started_at,submitted_at,time_spent_seconds"
    assert header_line == expected_columns
    assert "password" not in header_line
    assert "token" not in header_line
    assert "secret" not in header_line


@pytest.mark.django_db
def test_path_traversal_on_report_download_blocked(api_client, security_setup):
    alice = security_setup['alice']
    assessment = security_setup['assessment']

    api_client.force_authenticate(user=alice)

    job = ReportService.create_report_job(
        user=alice,
        report_type=ReportType.STUDENT_SCORECARD,
        format=ReportFormat.PDF,
        assessment_id=str(assessment.id),
        student_id=str(alice.id)
    )
    ReportService.generate_report(str(job.id))
    job.refresh_from_db()

    # Tamper path to point outside reports directory
    ReportJob.objects.filter(id=job.id).update(file_path="/etc/passwd")

    dl_res = api_client.get(f"/api/v1/student/reports/{job.id}/download/")
    assert dl_res.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_report_download_audit_logging(api_client, security_setup):
    alice = security_setup['alice']
    assessment = security_setup['assessment']

    api_client.force_authenticate(user=alice)

    job = ReportService.create_report_job(
        user=alice,
        report_type=ReportType.STUDENT_SCORECARD,
        format=ReportFormat.PDF,
        assessment_id=str(assessment.id),
        student_id=str(alice.id)
    )
    ReportService.generate_report(str(job.id))
    job.refresh_from_db()

    dl_res = api_client.get(f"/api/v1/student/reports/{job.id}/download/")
    assert dl_res.status_code == status.HTTP_200_OK

    assert AuditLog.objects.filter(action="REPORT_DOWNLOADED", target_id=str(job.id)).exists() is True


