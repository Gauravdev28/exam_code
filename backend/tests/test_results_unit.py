import pytest
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
from django.core.exceptions import PermissionDenied

from apps.accounts.models import User, Role, StudentProfile, AuditLog
from apps.questions.models import Question, QuestionVersion, QuestionType, Difficulty, VersionStatus
from apps.assessments.models import (
    Assessment,
    AssessmentStatus,
    AssessmentQuestion,
    AssessmentAssignment,
    AssessmentSnapshot,
    AssessmentSnapshotQuestion,
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
    HistoricalResultSummary,
    ResultStatus,
)
from apps.results.services import ResultFinalizationService, RetentionService, _sanitize_formula_injection


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        email="admin_res@codeguard.test",
        password="AdminPassword123!",
        role=Role.ADMIN
    )


@pytest.fixture
def student_user(db):
    user = User.objects.create_user(
        email="student_res@codeguard.test",
        password="StudentPassword123!",
        role=Role.STUDENT
    )
    StudentProfile.objects.create(
        user=user,
        roll_number="CS-2026-001",
        euid="EUID-STU-001"
    )
    return user


@pytest.fixture
def setup_assessment_and_attempt(db, admin_user, student_user):
    # 1. Create Questions
    # MCQ
    q_mcq = Question.objects.create(created_by=admin_user)
    qv_mcq = QuestionVersion.objects.create(
        question=q_mcq,
        version_number=1,
        title="MCQ Question",
        description="What is 2+2?",
        question_type=QuestionType.MCQ,
        difficulty=Difficulty.EASY,
        status=VersionStatus.PUBLISHED,
        type_config={
            "options": [{"id": "1", "text": "3"}, {"id": "2", "text": "4"}],
            "correct_options": ["2"]
        },
        created_by=admin_user
    )

    # Multi Select
    q_multi = Question.objects.create(created_by=admin_user)
    qv_multi = QuestionVersion.objects.create(
        question=q_multi,
        version_number=1,
        title="Multi Select Question",
        description="Select even numbers",
        question_type=QuestionType.MULTI_SELECT,
        difficulty=Difficulty.MEDIUM,
        status=VersionStatus.PUBLISHED,
        type_config={
            "options": [{"id": "1", "text": "2"}, {"id": "2", "text": "4"}, {"id": "3", "text": "5"}],
            "correct_options": ["1", "2"]
        },
        created_by=admin_user
    )

    # Short Answer
    q_short = Question.objects.create(created_by=admin_user)
    qv_short = QuestionVersion.objects.create(
        question=q_short,
        version_number=1,
        title="Short Answer Question",
        description="Capital of France?",
        question_type=QuestionType.SHORT_ANSWER,
        difficulty=Difficulty.EASY,
        status=VersionStatus.PUBLISHED,
        type_config={
            "exact_matches": ["Paris", "paris"],
            "case_sensitive": False
        },
        created_by=admin_user
    )

    # 2. Create Assessment
    assessment = Assessment.objects.create(
        title="Unit Test Assessment",
        description="Assessment for unit tests",
        start_datetime=timezone.now() - timedelta(hours=1),
        end_datetime=timezone.now() + timedelta(hours=2),
        duration_minutes=60,
        total_points=30,
        passing_percentage=Decimal('60.00'),
        negative_marking_enabled=True,
        result_visibility=ResultVisibility.IMMEDIATE,
        created_by=admin_user,
        status=AssessmentStatus.DRAFT
    )

    aq1 = AssessmentQuestion.objects.create(
        assessment=assessment,
        question_version=qv_mcq,
        order=1,
        points=10,
        negative_marking_enabled=True,
        negative_points=2
    )
    aq2 = AssessmentQuestion.objects.create(
        assessment=assessment,
        question_version=qv_multi,
        order=2,
        points=10,
        negative_marking_enabled=True,
        negative_points=2
    )
    aq3 = AssessmentQuestion.objects.create(
        assessment=assessment,
        question_version=qv_short,
        order=3,
        points=10
    )

    # Create Snapshot
    snapshot = AssessmentSnapshotService.create_snapshot(assessment, actor=admin_user)
    assessment.status = AssessmentStatus.PUBLISHED
    assessment.published_at = timezone.now()
    assessment.save()

    # Assign student
    assignment = AssessmentAssignment.objects.create(
        assessment=assessment,
        student=student_user,
        assigned_by=admin_user
    )

    # Create Attempt
    attempt = TestAttempt.objects.create(
        assessment=assessment,
        assessment_snapshot=snapshot,
        student=student_user,
        attempt_number=1,
        started_at=timezone.now() - timedelta(minutes=30),
        status=AttemptStatus.SUBMITTED,
        submitted_at=timezone.now()
    )

    return {
        "admin": admin_user,
        "student": student_user,
        "assessment": assessment,
        "snapshot": snapshot,
        "attempt": attempt,
        "snapshot_questions": list(snapshot.snapshot_questions.all().order_by('order'))
    }


@pytest.mark.django_db
def test_result_finalization_scoring_and_passing_verdict(setup_assessment_and_attempt):
    ctx = setup_assessment_and_attempt
    attempt = ctx['attempt']
    sqs = ctx['snapshot_questions']

    # Q1 (MCQ): Correct (selected "2") -> 10 pts
    AttemptAnswer.objects.create(
        attempt=attempt,
        snapshot_question=sqs[0],
        question_id=sqs[0].snapshot_question_id,
        is_answered=True,
        selected_options=["2"]
    )
    # Q2 (Multi): Incorrect (selected ["1", "3"]) with negative marking -> -2 pts
    AttemptAnswer.objects.create(
        attempt=attempt,
        snapshot_question=sqs[1],
        question_id=sqs[1].snapshot_question_id,
        is_answered=True,
        selected_options=["1", "3"]
    )
    # Q3 (Short Answer): Correct (selected "Paris") -> 10 pts
    AttemptAnswer.objects.create(
        attempt=attempt,
        snapshot_question=sqs[2],
        question_id=sqs[2].snapshot_question_id,
        is_answered=True,
        text_response="Paris"
    )

    # Finalize result
    result = ResultFinalizationService.finalize_attempt(attempt_id=str(attempt.id))

    assert result.status == ResultStatus.FINALIZED
    # Total earned = 10 - 2 + 10 = 18.00 / 30.00 = 60.00%
    assert result.total_score_earned == Decimal('18.00')
    assert result.total_possible_score == Decimal('30.00')
    assert result.percentage == Decimal('60.00')
    assert result.is_passed is True
    assert result.correct_questions == 2
    assert result.incorrect_questions == 1
    assert result.skipped_questions == 0

    # Verify QuestionResult records
    q_results = result.question_results.all().order_by('snapshot_question__order')
    assert len(q_results) == 3
    assert q_results[0].earned_points == Decimal('10.00')
    assert q_results[0].is_correct is True
    assert q_results[1].earned_points == Decimal('-2.00')
    assert q_results[1].is_correct is False
    assert q_results[2].earned_points == Decimal('10.00')
    assert q_results[2].is_correct is True

    # Verify HistoricalResultSummary created
    summary = HistoricalResultSummary.objects.get(student=ctx['student'], assessment_id=ctx['assessment'].id)
    assert summary.total_score_earned == Decimal('18.00')
    assert summary.percentage == Decimal('60.00')
    assert summary.is_passed is True
    assert summary.student_euid == "EUID-STU-001"
    assert summary.student_roll_number == "CS-2026-001"


@pytest.mark.django_db
def test_finalized_result_immutability(setup_assessment_and_attempt):
    ctx = setup_assessment_and_attempt
    attempt = ctx['attempt']

    result = ResultFinalizationService.finalize_attempt(attempt_id=str(attempt.id))
    assert result.status == ResultStatus.FINALIZED

    # 1. Model.save() mutation blocked
    result.total_score_earned = Decimal('99.00')
    with pytest.raises(PermissionDenied):
        result.save()

    # 2. Model.delete() blocked
    with pytest.raises(PermissionDenied):
        result.delete()

    # 3. QuerySet.update() mutation blocked
    with pytest.raises(PermissionDenied):
        AssessmentResult.objects.filter(id=result.id).update(total_score_earned=Decimal('99.00'))

    # 4. bulk_update() mutation blocked
    with pytest.raises(PermissionDenied):
        AssessmentResult.objects.bulk_update([result], ['total_score_earned'])

    # 5. QuestionResult Model.save() blocked
    qr = result.question_results.first()
    assert qr is not None
    qr.earned_points = Decimal('50.00')
    with pytest.raises(PermissionDenied):
        qr.save()

    # 6. QuestionResult Model.delete() blocked
    with pytest.raises(PermissionDenied):
        qr.delete()

    # 7. QuestionResult QuerySet.update() blocked
    with pytest.raises(PermissionDenied):
        QuestionResult.objects.filter(id=qr.id).update(earned_points=Decimal('50.00'))

    # 8. QuestionResult bulk_update() blocked
    with pytest.raises(PermissionDenied):
        QuestionResult.objects.bulk_update([qr], ['earned_points'])

    # 9. Allowed administrative release state update succeeds
    AssessmentResult.objects.filter(id=result.id).update(is_released=True)
    result.refresh_from_db()
    assert result.is_released is True


@pytest.mark.django_db
def test_formula_injection_sanitization():
    assert _sanitize_formula_injection("Normal Text") == "Normal Text"
    assert _sanitize_formula_injection("=SUM(A1:A10)") == "'=SUM(A1:A10)"
    assert _sanitize_formula_injection("+CMD|' /C calc'!A0") == "'+CMD|' /C calc'!A0"
    assert _sanitize_formula_injection("-2+3") == "'-2+3"
    assert _sanitize_formula_injection("@HYPERLINK") == "'@HYPERLINK"
    assert _sanitize_formula_injection("\tTabbed") == "'\tTabbed"
    assert _sanitize_formula_injection("\rCarriage") == "'\rCarriage"
    assert _sanitize_formula_injection(123) == 123
    assert _sanitize_formula_injection(None) is None


@pytest.mark.django_db
def test_coding_partial_score_projection(db, admin_user, student_user):
    # Create Coding Question
    q_code = Question.objects.create(created_by=admin_user)
    qv_code = QuestionVersion.objects.create(
        question=q_code,
        version_number=1,
        title="Coding Question",
        description="Write code",
        question_type=QuestionType.CODING,
        difficulty=Difficulty.MEDIUM,
        status=VersionStatus.PUBLISHED,
        created_by=admin_user
    )
    assessment = Assessment.objects.create(
        title="Coding Exam",
        description="Coding assessment",
        start_datetime=timezone.now() - timedelta(hours=1),
        end_datetime=timezone.now() + timedelta(hours=1),
        duration_minutes=30,
        total_points=20,
        passing_percentage=Decimal('50.00'),
        result_visibility=ResultVisibility.IMMEDIATE,
        created_by=admin_user,
        status=AssessmentStatus.DRAFT
    )
    AssessmentQuestion.objects.create(
        assessment=assessment,
        question_version=qv_code,
        order=1,
        points=20
    )
    snapshot = AssessmentSnapshotService.create_snapshot(assessment, actor=admin_user)
    assessment.status = AssessmentStatus.PUBLISHED
    assessment.published_at = timezone.now()
    assessment.save()

    attempt = TestAttempt.objects.create(
        assessment=assessment,
        assessment_snapshot=snapshot,
        student=student_user,
        attempt_number=1,
        started_at=timezone.now() - timedelta(minutes=20),
        status=AttemptStatus.SUBMITTED,
        submitted_at=timezone.now()
    )

    sq = snapshot.snapshot_questions.first()

    # Create authoritative partial code submission from Phase 6
    CodeSubmission.objects.create(
        attempt=attempt,
        snapshot_question=sq,
        language='python',
        source_code="def solve(): pass",
        submission_type=SubmissionType.SUBMIT,
        status='COMPLETED',
        verdict=CodeVerdict.WRONG_ANSWER,
        score_awarded=Decimal('10.00'), # 10 / 20 points
        passed_test_cases=1,
        total_test_cases=2,
        execution_time_ms=50,
        memory_used_kb=1024
    )

    result = ResultFinalizationService.finalize_attempt(attempt_id=str(attempt.id))
    assert result.status == ResultStatus.FINALIZED
    assert result.total_score_earned == Decimal('10.00')
    assert result.total_possible_score == Decimal('20.00')
    assert result.percentage == Decimal('50.00')
    assert result.is_passed is True
    assert result.partially_correct_questions == 1
    assert result.correct_questions == 0


@pytest.mark.django_db
def test_historical_summary_stability_against_metadata_edits(setup_assessment_and_attempt):
    ctx = setup_assessment_and_attempt
    attempt = ctx['attempt']
    assessment = ctx['assessment']

    # Finalize
    result = ResultFinalizationService.finalize_attempt(attempt_id=str(attempt.id))
    summary = HistoricalResultSummary.objects.get(student=ctx['student'], assessment_id=assessment.id)
    assert summary.assessment_title_snapshot == "Unit Test Assessment"

    # Even if title changes on live assessment or details get purged, historical summary stays intact
    summary.details_purged = True
    summary.save()

    reloaded = HistoricalResultSummary.objects.get(id=summary.id)
    assert reloaded.details_purged is True
    assert reloaded.total_score_earned == result.total_score_earned


@pytest.mark.django_db
def test_passing_percentage_lifecycle_and_freeze(admin_user, student_user):
    # 1. Configurable in DRAFT
    assessment = Assessment.objects.create(
        title="Passing Percentage Freeze Test",
        description="Test freeze",
        start_datetime=timezone.now() - timedelta(hours=1),
        end_datetime=timezone.now() + timedelta(hours=1),
        duration_minutes=30,
        total_points=10,
        passing_percentage=Decimal('65.00'),
        result_visibility=ResultVisibility.IMMEDIATE,
        created_by=admin_user,
        status=AssessmentStatus.DRAFT
    )
    assert assessment.passing_percentage == Decimal('65.00')

    # Update in draft
    assessment.passing_percentage = Decimal('70.00')
    assessment.save()
    assert assessment.passing_percentage == Decimal('70.00')

    # Add question & publish
    q = Question.objects.create(created_by=admin_user)
    qv = QuestionVersion.objects.create(
        question=q,
        version_number=1,
        title="Q1",
        description="D1",
        question_type=QuestionType.MCQ,
        difficulty=Difficulty.EASY,
        status=VersionStatus.PUBLISHED,
        created_by=admin_user,
        type_config={"options": [{"id": "1", "text": "A"}], "correct_option_id": "1"}
    )
    AssessmentQuestion.objects.create(assessment=assessment, question_version=qv, order=1, points=10)
    
    snapshot = AssessmentSnapshotService.create_snapshot(assessment, actor=admin_user)
    assessment.status = AssessmentStatus.PUBLISHED
    assessment.published_at = timezone.now()
    assessment.save()

    # 2. Frozen into AssessmentSnapshot
    assert snapshot.snapshot_data['passing_percentage'] == 70.0

    # 3. Post-publish modification rejected
    assessment.passing_percentage = Decimal('40.00')
    with pytest.raises(PermissionDenied):
        assessment.save()


@pytest.mark.django_db
def test_finalization_concurrency_and_idempotency(setup_assessment_and_attempt):
    ctx = setup_assessment_and_attempt
    attempt = ctx['attempt']

    # First finalization
    res1 = ResultFinalizationService.finalize_attempt(attempt_id=str(attempt.id))
    assert res1.status == ResultStatus.FINALIZED

    # Second finalization (concurrent or duplicated task)
    res2 = ResultFinalizationService.finalize_attempt(attempt_id=str(attempt.id))
    assert res2.id == res1.id
    assert res2.status == ResultStatus.FINALIZED

    # Exactly ONE AssessmentResult exists
    assert AssessmentResult.objects.filter(attempt=attempt).count() == 1

    # Exactly ONE HistoricalResultSummary exists
    assert HistoricalResultSummary.objects.filter(student=ctx['student'], assessment_id=ctx['assessment'].id).count() == 1


@pytest.mark.django_db
def test_retention_purge_synchronization_and_race(setup_assessment_and_attempt):
    ctx = setup_assessment_and_attempt
    attempt = ctx['attempt']

    # In-progress attempt is NOT eligible for purge
    attempt.status = AttemptStatus.IN_PROGRESS
    attempt.save(update_fields=['status'])
    assert RetentionService.is_eligible_for_purge(str(attempt.id)) is False
    assert RetentionService.purge_detailed_attempt_data(str(attempt.id)) is False

    # Submitted but unfinalized attempt is NOT eligible for purge
    attempt.status = AttemptStatus.SUBMITTED
    attempt.save(update_fields=['status'])
    assert RetentionService.is_eligible_for_purge(str(attempt.id)) is False
    assert RetentionService.purge_detailed_attempt_data(str(attempt.id)) is False

    # Once finalized, becomes eligible for purge
    result = ResultFinalizationService.finalize_attempt(attempt_id=str(attempt.id))
    assert result.status == ResultStatus.FINALIZED
    assert RetentionService.is_eligible_for_purge(str(attempt.id)) is True

    # Execute purge
    purged = RetentionService.purge_detailed_attempt_data(str(attempt.id))
    assert purged is True

    # Verify answers deleted while HistoricalResultSummary and AssessmentResult remain
    assert attempt.answers.count() == 0
    assert AssessmentResult.objects.filter(attempt=attempt).exists() is True
    summary = HistoricalResultSummary.objects.get(student=ctx['student'], assessment_id=ctx['assessment'].id)
    assert summary.details_purged is True
    assert summary.total_score_earned == result.total_score_earned


@pytest.mark.django_db
def test_audit_logging_events_coverage(setup_assessment_and_attempt):
    ctx = setup_assessment_and_attempt
    attempt = ctx['attempt']

    # Finalization audit log
    ResultFinalizationService.finalize_attempt(attempt_id=str(attempt.id))
    assert AuditLog.objects.filter(action="ASSESSMENT_RESULT_FINALIZED").exists() is True

