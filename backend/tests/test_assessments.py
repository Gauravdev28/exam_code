import pytest
from datetime import timedelta
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from rest_framework.exceptions import ValidationError as DRFValidationError
from channels.testing import WebsocketCommunicator
from channels.db import database_sync_to_async

from apps.accounts.models import Role, AuditLog
from apps.questions.models import QuestionType, Difficulty, VersionStatus
from apps.questions.services import QuestionService
from apps.assessments.models import (
    Assessment,
    AssessmentStatus,
    AssessmentAssignment,
    AssignmentStatus,
    AssessmentQuestion,
    AssessmentSnapshot,
    AssessmentSnapshotQuestion,
    TestAttempt,
    AttemptStatus,
    AttemptAnswer,
)
from apps.assessments.services import (
    AssessmentService,
    AssessmentSnapshotService,
    AttemptService,
    AttemptTimerService,
    RandomizationService,
)
from codeguard.routing import websocket_urlpatterns
from channels.routing import URLRouter

User = get_user_model()


@pytest.fixture
def admin_user(db):
    return User.objects.create_superuser(
        email="admin_assess@codeguard.local",
        password="AdminSecurePass123!",
        role=Role.ADMIN
    )


@pytest.fixture
def student_user_1(db):
    return User.objects.create_user(
        email="student1_assess@codeguard.local",
        password="StudentPass123!",
        role=Role.STUDENT
    )


@pytest.fixture
def student_user_2(db):
    return User.objects.create_user(
        email="student2_assess@codeguard.local",
        password="StudentPass123!",
        role=Role.STUDENT
    )


@pytest.fixture
def published_mcq_version(db, admin_user):
    q, v = QuestionService.create_question(
        question_type=QuestionType.MCQ,
        title="Python Data Structures",
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
    return QuestionService.publish_version(v, actor=admin_user)


@pytest.fixture
def published_coding_version(db, admin_user):
    q, v = QuestionService.create_question(
        question_type=QuestionType.CODING,
        title="Sum of Two Numbers",
        description="Return sum of integers",
        points=20,
        coding_config_data={
            "problem_statement": "Read two integers and print sum",
            "allowed_languages": ["PYTHON", "CPP"],
            "time_limit_ms": 2000,
            "memory_limit_mb": 256
        },
        test_cases_data=[
            {"input_data": "2 3", "expected_output": "5", "points": 10, "is_hidden": False},
            {"input_data": "100 200", "expected_output": "300", "points": 10, "is_hidden": True}
        ],
        actor=admin_user
    )
    return QuestionService.publish_version(v, actor=admin_user)


# ==============================================================================
# 1. Assessment Lifecycle & Points Invariant (Correction 5)
# ==============================================================================

@pytest.mark.django_db
def test_admin_can_create_draft_assessment(api_client, admin_user):
    api_client.force_authenticate(user=admin_user)
    url = reverse('assessments:admin-assessment-list')
    now = timezone.now()
    payload = {
        "title": "CS101 Midterm Exam",
        "description": "Midterm assessment covering basic programming",
        "start_datetime": now.isoformat(),
        "end_datetime": (now + timedelta(days=2)).isoformat(),
        "duration_minutes": 60,
        "total_points": 30,
        "negative_marking_enabled": True,
        "attempt_limit": 1,
        "randomize_questions": True,
        "randomize_options": True
    }
    res = api_client.post(url, payload, format='json')
    assert res.status_code == 201
    data = res.json()['data']
    assert data['title'] == "CS101 Midterm Exam"
    assert data['status'] == "DRAFT"
    assert data['duration_minutes'] == 60


@pytest.mark.django_db
def test_cannot_add_draft_question_to_assessment(admin_user):
    q, draft_v = QuestionService.create_question(
        question_type=QuestionType.MCQ,
        title="Draft Only Question",
        description="Prompt",
        actor=admin_user
    )
    now = timezone.now()
    assessment = AssessmentService.create_assessment(
        title="Assessment with Draft Q",
        description="Desc",
        start_datetime=now,
        end_datetime=now + timedelta(days=1),
        duration_minutes=30,
        total_points=10,
        created_by=admin_user
    )
    with pytest.raises(DRFValidationError) as excinfo:
        AssessmentService.add_question(
            assessment=assessment,
            question_version=draft_v,
            actor=admin_user
        )
    assert "question_version" in excinfo.value.detail


@pytest.mark.django_db
def test_publish_rejected_if_total_points_mismatches_sum_of_question_points(admin_user, published_mcq_version, published_coding_version):
    """Correction 5: Enforce SUM(AssessmentQuestion.points) == Assessment.total_points on publish."""
    now = timezone.now()
    assessment = AssessmentService.create_assessment(
        title="Point Invariant Test",
        description="Desc",
        start_datetime=now,
        end_datetime=now + timedelta(days=1),
        duration_minutes=45,
        total_points=50,  # Deliberately set 50 while questions sum to 10 + 20 = 30
        created_by=admin_user
    )
    AssessmentService.add_question(assessment=assessment, question_version=published_mcq_version, actor=admin_user, points=10)
    AssessmentService.add_question(assessment=assessment, question_version=published_coding_version, actor=admin_user, points=20)

    with pytest.raises(DRFValidationError) as excinfo:
        AssessmentService.publish_assessment(assessment=assessment, actor=admin_user)
    assert "total_points" in excinfo.value.detail

    # Fix total points to 30 and verify publish succeeds
    AssessmentService.update_draft_assessment(assessment=assessment, actor=admin_user, total_points=30)
    published = AssessmentService.publish_assessment(assessment=assessment, actor=admin_user)
    assert published.status == AssessmentStatus.PUBLISHED
    assert hasattr(published, 'snapshot')


# ==============================================================================
# 2. Snapshot Immutability & Self-Contained Isolation (Corrections 2, 3, 4)
# ==============================================================================

@pytest.mark.django_db
def test_future_question_version_edits_do_not_alter_published_assessment_snapshot(admin_user, published_coding_version):
    """
    Correction 2 & 4: Snapshot Isolation.
    Tests that publishing an assessment freezes the snapshot and future mutations to Question Bank leave snapshot untouched.
    """
    now = timezone.now()
    assessment = AssessmentService.create_assessment(
        title="Frozen Snapshot Test",
        description="Desc",
        start_datetime=now,
        end_datetime=now + timedelta(days=1),
        duration_minutes=60,
        total_points=20,
        created_by=admin_user
    )
    AssessmentService.add_question(assessment=assessment, question_version=published_coding_version, actor=admin_user, points=20)
    published_assessment = AssessmentService.publish_assessment(assessment=assessment, actor=admin_user)

    snapshot = published_assessment.snapshot
    initial_snapshot_data = dict(snapshot.snapshot_data)
    initial_q = initial_snapshot_data['questions'][0]
    initial_title = initial_q['title']
    initial_points = initial_q['points']
    initial_public_tcs = initial_q['coding_config']['public_test_cases']

    # Now mutate the Question Bank: Create version 2 of the coding question with new title and points
    q_obj = published_coding_version.question
    v2 = QuestionService.create_new_version(question=q_obj, actor=admin_user)
    QuestionService.update_draft_version(
        version=v2,
        title="V2 Heavily Modified Coding Problem",
        points=50,
        test_cases_data=[{"input_data": "999", "expected_output": "999", "points": 50}],
        actor=admin_user
    )
    QuestionService.publish_version(version=v2, actor=admin_user)

    # Re-fetch snapshot and assert it is 100% identical to initial snapshot
    snapshot.refresh_from_db()
    current_q = snapshot.snapshot_data['questions'][0]
    assert current_q['title'] == initial_title
    assert current_q['points'] == initial_points
    assert current_q['coding_config']['public_test_cases'] == initial_public_tcs
    assert current_q['title'] != "V2 Heavily Modified Coding Problem"


@pytest.mark.django_db
def test_snapshot_data_redacts_hidden_test_cases_from_students(api_client, admin_user, student_user_1, published_coding_version):
    """Correction 3: Student APIs and snapshots strictly hide secret/hidden test cases."""
    now = timezone.now()
    assessment = AssessmentService.create_assessment(
        title="Security Test",
        description="Desc",
        start_datetime=now - timedelta(hours=1),
        end_datetime=now + timedelta(hours=2),
        duration_minutes=60,
        total_points=20,
        created_by=admin_user
    )
    AssessmentService.add_question(assessment=assessment, question_version=published_coding_version, actor=admin_user, points=20)
    published = AssessmentService.publish_assessment(assessment=assessment, actor=admin_user)
    AssessmentService.assign_students(assessment=published, student_ids=[str(student_user_1.id)], actor=admin_user)

    # Start attempt as student
    api_client.force_authenticate(user=student_user_1)
    start_url = reverse('assessments:student-assessment-start', kwargs={'pk': published.id})
    start_res = api_client.post(start_url)
    assert start_res.status_code == 201
    attempt_id = start_res.json()['data']['attempt_id']

    # Retrieve attempt state
    attempt_url = reverse('assessments:student-attempt-detail', kwargs={'pk': attempt_id})
    attempt_res = api_client.get(attempt_url)
    assert attempt_res.status_code == 200

    data = attempt_res.json()['data']
    raw_response_str = str(attempt_res.json())

    # Public test case (2 3 -> 5) is visible
    public_tcs = data['questions'][0]['coding_config']['public_test_cases']
    assert len(public_tcs) == 1
    assert public_tcs[0]['input_data'] == "2 3"
    assert public_tcs[0]['expected_output'] == "5"

    # Hidden test case (100 200) must NEVER appear in student API payload
    assert "100 200" not in raw_response_str
    assert not any(tc.get('input_data') == "100 200" for tc in public_tcs)
    assert "server_evaluation_bundle" not in raw_response_str
    assert "hidden_test_cases" not in raw_response_str


# ==============================================================================
# 3. Assessment Assignment (Correction 1)
# ==============================================================================

@pytest.mark.django_db
def test_unassigned_student_cannot_start_assessment(api_client, admin_user, student_user_1, published_mcq_version):
    """Correction 1: Unassigned student receives 403 / PermissionDenied on start."""
    now = timezone.now()
    assessment = AssessmentService.create_assessment(
        title="Assignment Enforced Assessment",
        description="Desc",
        start_datetime=now - timedelta(minutes=10),
        end_datetime=now + timedelta(hours=1),
        duration_minutes=30,
        total_points=10,
        created_by=admin_user
    )
    AssessmentService.add_question(assessment=assessment, question_version=published_mcq_version, actor=admin_user, points=10)
    published = AssessmentService.publish_assessment(assessment=assessment, actor=admin_user)

    # student_user_1 is NOT assigned
    api_client.force_authenticate(user=student_user_1)
    start_url = reverse('assessments:student-assessment-start', kwargs={'pk': published.id})
    res = api_client.post(start_url)
    assert res.status_code == 403


@pytest.mark.django_db
def test_admin_can_assign_and_revoke_student(api_client, admin_user, student_user_1, published_mcq_version):
    """Correction 1: Admin can assign and revoke student access."""
    now = timezone.now()
    assessment = AssessmentService.create_assessment(
        title="Assignment API Test",
        description="Desc",
        start_datetime=now,
        end_datetime=now + timedelta(hours=1),
        duration_minutes=30,
        total_points=10,
        created_by=admin_user
    )
    AssessmentService.add_question(assessment=assessment, question_version=published_mcq_version, actor=admin_user, points=10)
    published = AssessmentService.publish_assessment(assessment=assessment, actor=admin_user)

    api_client.force_authenticate(user=admin_user)
    assign_url = reverse('assessments:admin-assessment-assignment-list', kwargs={'pk': published.id})

    # Assign student 1
    res = api_client.post(assign_url, {"student_ids": [str(student_user_1.id)]}, format='json')
    assert res.status_code == 201
    assert len(res.json()['data']) == 1

    # Revoke assignment
    revoke_url = reverse('assessments:admin-assessment-assignment-revoke', kwargs={'pk': published.id, 'student_id': student_user_1.id})
    del_res = api_client.delete(revoke_url)
    assert del_res.status_code == 200
    assert del_res.json()['data']['status'] == "REVOKED"


# ==============================================================================
# 4. Deterministic Randomization & Seed Persistence (Correction 7)
# ==============================================================================

@pytest.mark.django_db
def test_same_attempt_maintains_exact_order_across_fetches(admin_user, student_user_1, published_mcq_version, published_coding_version):
    """Correction 7: Randomization seed is stored on attempt and produces identical ordering on refresh."""
    now = timezone.now()
    assessment = AssessmentService.create_assessment(
        title="Randomization Test",
        description="Desc",
        start_datetime=now - timedelta(minutes=10),
        end_datetime=now + timedelta(hours=2),
        duration_minutes=60,
        total_points=30,
        randomize_questions=True,
        randomize_options=True,
        created_by=admin_user
    )
    AssessmentService.add_question(assessment=assessment, question_version=published_mcq_version, actor=admin_user, points=10)
    AssessmentService.add_question(assessment=assessment, question_version=published_coding_version, actor=admin_user, points=20)
    published = AssessmentService.publish_assessment(assessment=assessment, actor=admin_user)
    AssessmentService.assign_students(assessment=published, student_ids=[str(student_user_1.id)], actor=admin_user)

    attempt, _ = AttemptService.start_attempt(student=student_user_1, assessment_id=str(published.id), actor=student_user_1)
    saved_q_order = list(attempt.question_order)
    saved_opt_order = dict(attempt.option_orders)

    # Simulate refresh / reconnect by re-fetching
    attempt.refresh_from_db()
    assert attempt.question_order == saved_q_order
    assert attempt.option_orders == saved_opt_order


# ==============================================================================
# 5. Server-Authoritative Timer & Scheduling (Correction 10)
# ==============================================================================

@pytest.mark.django_db
def test_start_attempt_rejected_too_early_and_too_late(admin_user, student_user_1, published_mcq_version):
    now = timezone.now()

    # Early assessment
    early_assessment = AssessmentService.create_assessment(
        title="Early Exam",
        description="Desc",
        start_datetime=now + timedelta(hours=1),
        end_datetime=now + timedelta(hours=2),
        duration_minutes=30,
        total_points=10,
        created_by=admin_user
    )
    AssessmentService.add_question(early_assessment, published_mcq_version, admin_user, points=10)
    published_early = AssessmentService.publish_assessment(early_assessment, admin_user)
    AssessmentService.assign_students(published_early, [str(student_user_1.id)], admin_user)

    with pytest.raises(DRFValidationError) as excinfo:
        AttemptService.start_attempt(student_user_1, str(published_early.id), student_user_1)
    assert "START_REJECTED_TOO_EARLY" in str(excinfo.value.detail)

    # Late assessment
    late_assessment = AssessmentService.create_assessment(
        title="Late Exam",
        description="Desc",
        start_datetime=now - timedelta(hours=3),
        end_datetime=now - timedelta(hours=1),
        duration_minutes=30,
        total_points=10,
        created_by=admin_user
    )
    AssessmentService.add_question(late_assessment, published_mcq_version, admin_user, points=10)
    published_late = AssessmentService.publish_assessment(late_assessment, admin_user)
    AssessmentService.assign_students(published_late, [str(student_user_1.id)], admin_user)

    with pytest.raises(DRFValidationError) as excinfo:
        AttemptService.start_attempt(student_user_1, str(published_late.id), student_user_1)
    assert "START_REJECTED_TOO_LATE" in str(excinfo.value.detail)


@pytest.mark.django_db
def test_effective_expiry_computed_as_min_duration_and_assessment_end(admin_user, student_user_1, published_mcq_version):
    now = timezone.now()
    # Assessment duration is 60 min, but end_datetime is in 20 min -> expires_at MUST equal end_datetime
    assessment = AssessmentService.create_assessment(
        title="Min Expiry Test",
        description="Desc",
        start_datetime=now - timedelta(minutes=10),
        end_datetime=now + timedelta(minutes=20),
        duration_minutes=60,
        total_points=10,
        created_by=admin_user
    )
    AssessmentService.add_question(assessment, published_mcq_version, admin_user, points=10)
    published = AssessmentService.publish_assessment(assessment, admin_user)
    AssessmentService.assign_students(published, [str(student_user_1.id)], admin_user)

    attempt, _ = AttemptService.start_attempt(student_user_1, str(published.id), student_user_1)
    assert attempt.expires_at == assessment.end_datetime


# ==============================================================================
# 6. Answer Persistence & Revision Protection (Correction 8)
# ==============================================================================

@pytest.mark.django_db
def test_stale_answer_revision_rejected_without_overwriting_newer_server_state(admin_user, student_user_1, published_mcq_version):
    """Correction 8: Revision protection prevents stale overwrite races."""
    now = timezone.now()
    assessment = AssessmentService.create_assessment(
        title="Revision Test",
        description="Desc",
        start_datetime=now - timedelta(minutes=5),
        end_datetime=now + timedelta(hours=1),
        duration_minutes=30,
        total_points=10,
        created_by=admin_user
    )
    AssessmentService.add_question(assessment, published_mcq_version, admin_user, points=10)
    published = AssessmentService.publish_assessment(assessment, admin_user)
    AssessmentService.assign_students(published, [str(student_user_1.id)], admin_user)

    attempt, _ = AttemptService.start_attempt(student_user_1, str(published.id), student_user_1)
    q_id = str(published_mcq_version.id)

    # Save Revision 10
    res1 = AttemptService.save_answer(
        student=student_user_1,
        attempt_id=str(attempt.id),
        snapshot_question_id=q_id,
        answer_data={"selected_options": ["B"]},
        client_revision=10
    )
    assert res1['status'] == "SAVED"
    assert res1['server_revision'] == 10

    # Save Stale Revision 5 (e.g. out-of-order network delay)
    res2 = AttemptService.save_answer(
        student=student_user_1,
        attempt_id=str(attempt.id),
        snapshot_question_id=q_id,
        answer_data={"selected_options": ["A"]},
        client_revision=5
    )
    assert res2['status'] == "STALE_REVISION"

    # Verify server database still has Option B (not overwritten by A)
    ans = AttemptAnswer.objects.get(attempt=attempt, question_id=q_id)
    assert ans.selected_options == ["B"]


# ==============================================================================
# 7. IDOR & Security
# ==============================================================================

@pytest.mark.django_db
def test_idor_student_cannot_save_or_submit_another_students_attempt(admin_user, student_user_1, student_user_2, published_mcq_version):
    now = timezone.now()
    assessment = AssessmentService.create_assessment(
        title="IDOR Test",
        description="Desc",
        start_datetime=now - timedelta(minutes=5),
        end_datetime=now + timedelta(hours=1),
        duration_minutes=30,
        total_points=10,
        created_by=admin_user
    )
    AssessmentService.add_question(assessment, published_mcq_version, admin_user, points=10)
    published = AssessmentService.publish_assessment(assessment, admin_user)
    AssessmentService.assign_students(published, [str(student_user_1.id), str(student_user_2.id)], admin_user)

    # Student 1 starts attempt
    attempt_1, _ = AttemptService.start_attempt(student_user_1, str(published.id), student_user_1)

    # Student 2 tries to save answer to Student 1's attempt -> PermissionDenied
    with pytest.raises(PermissionDenied):
        AttemptService.save_answer(
            student=student_user_2,
            attempt_id=str(attempt_1.id),
            snapshot_question_id=str(published_mcq_version.id),
            answer_data={"selected_options": ["B"]}
        )

    # Student 2 tries to submit Student 1's attempt -> PermissionDenied
    with pytest.raises(PermissionDenied):
        AttemptService.submit_attempt(student=student_user_2, attempt_id=str(attempt_1.id))


# ==============================================================================
# 8. Idempotent Submission & State Locking
# ==============================================================================

@pytest.mark.django_db
def test_submission_is_idempotent_and_locks_attempt(admin_user, student_user_1, published_mcq_version):
    now = timezone.now()
    assessment = AssessmentService.create_assessment(
        title="Submission Lock Test",
        description="Desc",
        start_datetime=now - timedelta(minutes=5),
        end_datetime=now + timedelta(hours=1),
        duration_minutes=30,
        total_points=10,
        created_by=admin_user
    )
    AssessmentService.add_question(assessment, published_mcq_version, admin_user, points=10)
    published = AssessmentService.publish_assessment(assessment, admin_user)
    AssessmentService.assign_students(published, [str(student_user_1.id)], admin_user)

    attempt, _ = AttemptService.start_attempt(student_user_1, str(published.id), student_user_1)

    # First Submit
    sub1 = AttemptService.submit_attempt(student_user_1, str(attempt.id))
    assert sub1.status == AttemptStatus.SUBMITTED

    # Second Submit (Idempotent)
    sub2 = AttemptService.submit_attempt(student_user_1, str(attempt.id))
    assert sub2.status == AttemptStatus.SUBMITTED

    # Attempting to save an answer after submission raises ValidationError
    with pytest.raises(DRFValidationError) as excinfo:
        AttemptService.save_answer(
            student=student_user_1,
            attempt_id=str(attempt.id),
            snapshot_question_id=str(published_mcq_version.id),
            answer_data={"selected_options": ["B"]}
        )
    assert "status" in excinfo.value.detail


# ==============================================================================
# 9. Audit Logging (Correction 19)
# ==============================================================================

@pytest.mark.django_db
def test_assessment_and_attempt_lifecycle_generates_audit_logs(admin_user, student_user_1, published_mcq_version):
    now = timezone.now()
    assessment = AssessmentService.create_assessment(
        title="Audit Test Exam",
        description="Desc",
        start_datetime=now - timedelta(minutes=5),
        end_datetime=now + timedelta(hours=1),
        duration_minutes=30,
        total_points=10,
        created_by=admin_user
    )
    assert AuditLog.objects.filter(action="ASSESSMENT_CREATED").exists()

    AssessmentService.add_question(assessment, published_mcq_version, admin_user, points=10)
    assert AuditLog.objects.filter(action="QUESTION_ADDED_TO_ASSESSMENT").exists()

    published = AssessmentService.publish_assessment(assessment, admin_user)
    assert AuditLog.objects.filter(action="ASSESSMENT_PUBLISHED").exists()
    assert AuditLog.objects.filter(action="SNAPSHOT_CREATED").exists()

    AssessmentService.assign_students(published, [str(student_user_1.id)], admin_user)
    assert AuditLog.objects.filter(action="ASSESSMENT_ASSIGNMENT_CREATED").exists()

    attempt, _ = AttemptService.start_attempt(student_user_1, str(published.id), student_user_1)
    assert AuditLog.objects.filter(action="ATTEMPT_STARTED").exists()

    AttemptService.submit_attempt(student_user_1, str(attempt.id))
    assert AuditLog.objects.filter(action="ATTEMPT_SUBMITTED").exists()


# ==============================================================================
# 10. Attempt Limits & Concurrency (Rule 11)
# ==============================================================================

@pytest.mark.django_db
def test_attempt_limit_enforced_server_side(admin_user, student_user_1, published_mcq_version):
    """Enforces attempt limit strictly server-side."""
    now = timezone.now()
    assessment = AssessmentService.create_assessment(
        title="Single Attempt Exam",
        description="Desc",
        start_datetime=now - timedelta(minutes=5),
        end_datetime=now + timedelta(hours=1),
        duration_minutes=30,
        total_points=10,
        attempt_limit=1,
        created_by=admin_user
    )
    AssessmentService.add_question(assessment, published_mcq_version, admin_user, points=10)
    published = AssessmentService.publish_assessment(assessment, admin_user)
    AssessmentService.assign_students(published, [str(student_user_1.id)], admin_user)

    # Attempt 1: Start and Submit
    attempt1, created1 = AttemptService.start_attempt(student_user_1, str(published.id), student_user_1)
    assert created1 is True
    AttemptService.submit_attempt(student_user_1, str(attempt1.id))

    # Attempt 2: Rejected because limit is 1
    with pytest.raises(DRFValidationError) as excinfo:
        AttemptService.start_attempt(student_user_1, str(published.id), student_user_1)
    assert "attempt_limit" in excinfo.value.detail


# ==============================================================================
# 11. All 6 Question Types Answer Persistence
# ==============================================================================

@pytest.mark.django_db
def test_save_answers_for_all_6_question_types(admin_user, student_user_1):
    """Tests student response storage across MCQ, Multi-Select, True/False, Short Answer, Coding, and SQL."""
    # Create published questions for remaining types
    q_multi, v_multi = QuestionService.create_question(
        question_type=QuestionType.MULTI_SELECT,
        title="Multi Select Q",
        description="Select all",
        points=10,
        type_config={"options": [{"id": "A", "text": "1"}, {"id": "B", "text": "2"}], "correct_options": ["A", "B"]},
        actor=admin_user
    )
    v_multi = QuestionService.publish_version(v_multi, admin_user)

    q_tf, v_tf = QuestionService.create_question(
        question_type=QuestionType.TRUE_FALSE,
        title="TF Q",
        description="True or false",
        points=5,
        type_config={"correct_answer": True},
        actor=admin_user
    )
    v_tf = QuestionService.publish_version(v_tf, admin_user)

    q_sa, v_sa = QuestionService.create_question(
        question_type=QuestionType.SHORT_ANSWER,
        title="Short Answer Q",
        description="Type answer",
        points=5,
        type_config={"accepted_answers": ["42"]},
        actor=admin_user
    )
    v_sa = QuestionService.publish_version(v_sa, admin_user)

    q_code, v_code = QuestionService.create_question(
        question_type=QuestionType.CODING,
        title="Coding Q",
        description="Code",
        points=20,
        coding_config_data={"problem_statement": "Print 42"},
        test_cases_data=[{"input_data": "", "expected_output": "42", "points": 20}],
        actor=admin_user
    )
    v_code = QuestionService.publish_version(v_code, admin_user)

    q_sql, v_sql = QuestionService.create_question(
        question_type=QuestionType.SQL,
        title="SQL Q",
        description="Query",
        points=10,
        sql_config_data={
            "problem_statement": "Select all",
            "schema_setup_sql": "CREATE TABLE t (id INT);",
            "expected_result_definition": "SELECT * FROM t;"
        },
        actor=admin_user
    )
    v_sql = QuestionService.publish_version(v_sql, admin_user)

    # Create assessment with all questions
    now = timezone.now()
    assessment = AssessmentService.create_assessment(
        title="All 6 Types Assessment",
        description="Desc",
        start_datetime=now - timedelta(minutes=5),
        end_datetime=now + timedelta(hours=1),
        duration_minutes=30,
        total_points=50,
        created_by=admin_user
    )
    AssessmentService.add_question(assessment, v_multi, admin_user, points=10)
    AssessmentService.add_question(assessment, v_tf, admin_user, points=5)
    AssessmentService.add_question(assessment, v_sa, admin_user, points=5)
    AssessmentService.add_question(assessment, v_code, admin_user, points=20)
    AssessmentService.add_question(assessment, v_sql, admin_user, points=10)

    published = AssessmentService.publish_assessment(assessment, admin_user)
    AssessmentService.assign_students(published, [str(student_user_1.id)], admin_user)

    attempt, _ = AttemptService.start_attempt(student_user_1, str(published.id), student_user_1)

    # Save answers
    res_m = AttemptService.save_answer(student_user_1, str(attempt.id), str(v_multi.id), {"selected_options": ["A", "B"]}, 2)
    assert res_m['is_answered'] is True

    res_tf = AttemptService.save_answer(student_user_1, str(attempt.id), str(v_tf.id), {"selected_options": ["True"]}, 2)
    assert res_tf['is_answered'] is True

    res_sa = AttemptService.save_answer(student_user_1, str(attempt.id), str(v_sa.id), {"text_response": "42"}, 2)
    assert res_sa['is_answered'] is True

    res_c = AttemptService.save_answer(student_user_1, str(attempt.id), str(v_code.id), {"code_response": "print(42)", "code_language": "PYTHON"}, 2)
    assert res_c['is_answered'] is True

    res_sq = AttemptService.save_answer(student_user_1, str(attempt.id), str(v_sql.id), {"sql_response": "SELECT * FROM t;"}, 2)
    assert res_sq['is_answered'] is True


# ==============================================================================
# 12. Server Timer Expiration (Rule 14, 15)
# ==============================================================================

@pytest.mark.django_db
def test_timer_expiration_blocks_answer_writes(admin_user, student_user_1, published_mcq_version):
    now = timezone.now()
    assessment = AssessmentService.create_assessment(
        title="Expired Timer Assessment",
        description="Desc",
        start_datetime=now - timedelta(minutes=40),
        end_datetime=now + timedelta(hours=1),
        duration_minutes=30,  # 30 min duration started 40 min ago -> expired
        total_points=10,
        created_by=admin_user
    )
    AssessmentService.add_question(assessment, published_mcq_version, admin_user, points=10)
    published = AssessmentService.publish_assessment(assessment, admin_user)
    AssessmentService.assign_students(published, [str(student_user_1.id)], admin_user)

    attempt, _ = AttemptService.start_attempt(student_user_1, str(published.id), student_user_1)
    # Manually backdate started_at and expires_at
    attempt.started_at = now - timedelta(minutes=40)
    attempt.expires_at = now - timedelta(minutes=10)
    attempt.save()

    # Attempting to save an answer after expiry raises ValidationError
    with pytest.raises(DRFValidationError) as excinfo:
        AttemptService.save_answer(
            student_user_1,
            str(attempt.id),
            str(published_mcq_version.id),
            {"selected_options": ["B"]}
        )
    assert "timer" in excinfo.value.detail
    attempt.refresh_from_db()
    assert attempt.status == AttemptStatus.EXPIRED


# ==============================================================================
# 13. WebSocket Channel Sync (Rule 19)
# ==============================================================================

@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_websocket_attempt_connection_and_sync(admin_user, student_user_1, published_mcq_version):
    now = timezone.now()
    assessment = await database_sync_to_async(AssessmentService.create_assessment)(
        title="WebSocket Assessment",
        description="Desc",
        start_datetime=now - timedelta(minutes=5),
        end_datetime=now + timedelta(hours=1),
        duration_minutes=30,
        total_points=10,
        created_by=admin_user
    )
    await database_sync_to_async(AssessmentService.add_question)(assessment, published_mcq_version, admin_user, points=10)
    published = await database_sync_to_async(AssessmentService.publish_assessment)(assessment, admin_user)
    await database_sync_to_async(AssessmentService.assign_students)(published, [str(student_user_1.id)], admin_user)

    attempt, _ = await database_sync_to_async(AttemptService.start_attempt)(student_user_1, str(published.id), student_user_1)

    # Setup communicator with student_user_1 in scope
    application = URLRouter(websocket_urlpatterns)
    communicator = WebsocketCommunicator(application, f"/ws/attempts/{attempt.id}/")
    communicator.scope['user'] = student_user_1

    connected, _ = await communicator.connect()
    assert connected

    # Receive initial sync message
    initial_msg = await communicator.receive_json_from()
    assert initial_msg['type'] == "SYNC_STATE"
    assert initial_msg['data']['attempt_id'] == str(attempt.id)

    # Send PING
    await communicator.send_json_to({"action": "PING"})
    pong_msg = await communicator.receive_json_from()
    assert pong_msg['type'] == "PONG"
    assert pong_msg['remaining_seconds'] > 0

    await communicator.disconnect()


# ==============================================================================
# 14. Advanced Concurrency & Multi-Revision Ordering (Audit #3)
# ==============================================================================

@pytest.mark.django_db
def test_concurrency_multi_revision_ordering_race(admin_user, student_user_1, published_mcq_version):
    """
    Audit #3.B: Out-of-order revisions:
    Revisions sent in order: 13, 12, 14, 11 -> final persisted state is revision 14.
    """
    now = timezone.now()
    assessment = AssessmentService.create_assessment(
        title="Multi Revision Race Exam",
        description="Desc",
        start_datetime=now - timedelta(minutes=5),
        end_datetime=now + timedelta(hours=1),
        duration_minutes=30,
        total_points=10,
        created_by=admin_user
    )
    AssessmentService.add_question(assessment, published_mcq_version, admin_user, points=10)
    published = AssessmentService.publish_assessment(assessment, admin_user)
    AssessmentService.assign_students(published, [str(student_user_1.id)], admin_user)

    attempt, _ = AttemptService.start_attempt(student_user_1, str(published.id), student_user_1)
    q_id = str(published_mcq_version.id)

    # 1. Send Rev 13 (Option C)
    r13 = AttemptService.save_answer(student_user_1, str(attempt.id), q_id, {"selected_options": ["C"]}, client_revision=13)
    assert r13['status'] == "SAVED"
    assert r13['server_revision'] == 13

    # 2. Send Stale Rev 12 (Option A)
    r12 = AttemptService.save_answer(student_user_1, str(attempt.id), q_id, {"selected_options": ["A"]}, client_revision=12)
    assert r12['status'] == "STALE_REVISION"

    # 3. Send Newer Rev 14 (Option B)
    r14 = AttemptService.save_answer(student_user_1, str(attempt.id), q_id, {"selected_options": ["B"]}, client_revision=14)
    assert r14['status'] == "SAVED"
    assert r14['server_revision'] == 14

    # 4. Send Stale Rev 11 (Option D)
    r11 = AttemptService.save_answer(student_user_1, str(attempt.id), q_id, {"selected_options": ["D"]}, client_revision=11)
    assert r11['status'] == "STALE_REVISION"

    # Verify final database state is strictly Revision 14 with Option B
    ans = AttemptAnswer.objects.get(attempt=attempt, question_id=q_id)
    assert ans.revision == 14
    assert ans.selected_options == ["B"]


# ==============================================================================
# 15. Assignment Revocation Semantics (Audit #5)
# ==============================================================================

@pytest.mark.django_db
def test_assignment_revocation_allows_in_progress_attempt_to_finish_but_blocks_new_attempts(admin_user, student_user_1, published_mcq_version):
    """
    Audit #5:
    1. Student is assigned Assessment A.
    2. Student starts attempt -> IN_PROGRESS.
    3. Admin revokes assignment.
    4. Existing IN_PROGRESS attempt continues normally to save and submit.
    5. Starting a NEW attempt is blocked.
    """
    now = timezone.now()
    assessment = AssessmentService.create_assessment(
        title="Revocation Semantics Exam",
        description="Desc",
        start_datetime=now - timedelta(minutes=5),
        end_datetime=now + timedelta(hours=1),
        duration_minutes=30,
        total_points=10,
        attempt_limit=2,
        created_by=admin_user
    )
    AssessmentService.add_question(assessment, published_mcq_version, admin_user, points=10)
    published = AssessmentService.publish_assessment(assessment, admin_user)
    AssessmentService.assign_students(published, [str(student_user_1.id)], admin_user)

    # 1. Start attempt 1
    attempt1, created1 = AttemptService.start_attempt(student_user_1, str(published.id), student_user_1)
    assert created1 is True
    assert attempt1.status == AttemptStatus.IN_PROGRESS

    # 2. Admin revokes assignment
    AssessmentService.revoke_assignment(published, str(student_user_1.id), admin_user)

    # 3. Existing attempt 1 can still save answers
    save_res = AttemptService.save_answer(
        student_user_1,
        str(attempt1.id),
        str(published_mcq_version.id),
        {"selected_options": ["B"]},
        client_revision=2
    )
    assert save_res['status'] == "SAVED"

    # 4. Existing attempt 1 can submit normally
    sub = AttemptService.submit_attempt(student_user_1, str(attempt1.id))
    assert sub.status == AttemptStatus.SUBMITTED

    # 5. Starting a NEW attempt is blocked because assignment is REVOKED
    with pytest.raises(PermissionDenied):
        AttemptService.start_attempt(student_user_1, str(published.id), student_user_1)


# ==============================================================================
# 16. Snapshot & Question Model Immutability (Audit #14)
# ==============================================================================

@pytest.mark.django_db
def test_snapshot_and_snapshot_question_model_level_immutability_on_save_and_delete(admin_user, published_mcq_version):
    """Audit #14: Direct ORM .save() on existing snapshot and .delete() must raise PermissionDenied."""
    now = timezone.now()
    assessment = AssessmentService.create_assessment(
        title="Immutability Direct Test",
        description="Desc",
        start_datetime=now,
        end_datetime=now + timedelta(hours=1),
        duration_minutes=30,
        total_points=10,
        created_by=admin_user
    )
    AssessmentService.add_question(assessment, published_mcq_version, admin_user, points=10)
    published = AssessmentService.publish_assessment(assessment, admin_user)

    snapshot = published.snapshot
    snap_q = snapshot.snapshot_questions.first()

    # Attempt to update AssessmentSnapshot via ORM
    snapshot.version_number = 99
    with pytest.raises(PermissionDenied):
        snapshot.save()

    # Attempt to delete AssessmentSnapshot via ORM
    with pytest.raises(PermissionDenied):
        snapshot.delete()

    # Attempt to update AssessmentSnapshotQuestion via ORM
    snap_q.title = "Hacked Title"
    with pytest.raises(PermissionDenied):
        snap_q.save()

    # Attempt to delete AssessmentSnapshotQuestion via ORM
    with pytest.raises(PermissionDenied):
        snap_q.delete()


# ==============================================================================
# 17. Student Tampering Protection (Audit #9)
# ==============================================================================

@pytest.mark.django_db
def test_student_cannot_override_authoritative_fields_in_start_save_submit(api_client, admin_user, student_user_1, published_mcq_version):
    """
    Audit #9: Students cannot override authoritative fields (started_at, expires_at, points, etc.) via API payloads.
    """
    now = timezone.now()
    assessment = AssessmentService.create_assessment(
        title="Tampering Test Exam",
        description="Desc",
        start_datetime=now - timedelta(minutes=5),
        end_datetime=now + timedelta(hours=1),
        duration_minutes=30,
        total_points=10,
        created_by=admin_user
    )
    AssessmentService.add_question(assessment, published_mcq_version, admin_user, points=10)
    published = AssessmentService.publish_assessment(assessment, admin_user)
    AssessmentService.assign_students(published, [str(student_user_1.id)], admin_user)

    api_client.force_authenticate(user=student_user_1)

    # 1. Tampered Start Attempt payload
    start_url = reverse('assessments:student-assessment-start', kwargs={'pk': published.id})
    res_start = api_client.post(
        start_url,
        {
            "started_at": (now - timedelta(days=10)).isoformat(),
            "expires_at": (now + timedelta(days=10)).isoformat(),
            "randomization_seed": "fake_seed",
            "attempt_number": 999
        },
        format='json'
    )
    assert res_start.status_code == 201
    attempt_id = res_start.json()['data']['attempt_id']

    attempt = TestAttempt.objects.get(id=attempt_id)
    assert attempt.attempt_number == 1  # Server authoritative
    assert attempt.randomization_seed != "fake_seed"  # Server authoritative
    assert attempt.expires_at == attempt.started_at + timedelta(minutes=30)  # Server authoritative

    # 2. Tampered Save Answer payload
    save_url = reverse('assessments:student-attempt-save-answer', kwargs={'pk': attempt_id, 'question_id': published_mcq_version.id})
    res_save = api_client.post(
        save_url,
        {
            "selected_options": ["B"],
            "revision": 2,
            "points": 9999,  # Attempting to assign 9999 points
            "is_answered": True,
            "is_correct": True
        },
        format='json'
    )
    assert res_save.status_code == 200

    # Ensure question points on snapshot_question remains exactly 10
    ans = AttemptAnswer.objects.get(attempt=attempt, question_id=published_mcq_version.id)
    assert ans.snapshot_question.points == 10


