import pytest
from decimal import Decimal
from django.utils import timezone
from datetime import timedelta
from rest_framework.test import APIClient

from apps.accounts.models import User, StudentProfile
from apps.questions.models import (
    Question,
    QuestionVersion,
    CodingQuestionConfig,
    TestCase,
    QuestionType,
    Difficulty,
    VersionStatus,
)
from apps.assessments.models import (
    Assessment,
    AssessmentQuestion,
    AssessmentAssignment,
    AssessmentStatus,
    TestAttempt,
    AttemptStatus,
    AttemptAnswer,
)
from apps.assessments.services import AssessmentService, AttemptService
from apps.evaluator.models import (
    CodeSubmission,
    CodeTestCaseResult,
    SubmissionType,
    SubmissionStatus,
    CodeVerdict,
    TestCaseVerdict,
)
from apps.evaluator.services import (
    OutputComparisonService,
    ScoringService,
    CodeSubmissionService,
)


@pytest.mark.django_db
class TestOutputComparisonService:
    """Unit tests for deterministic output comparison modes."""

    def test_compare_exact_stripped_crlf_and_whitespace(self):
        actual = "Hello World  \r\n42\r\n\r\n"
        expected = "Hello World\n42\n"
        assert OutputComparisonService.compare_exact_stripped(actual, expected) is True

    def test_compare_exact_stripped_preserves_internal_spaces(self):
        actual = "1  2\n"
        expected = "1 2\n"
        assert OutputComparisonService.compare_exact_stripped(actual, expected) is False

    def test_compare_exact_stripped_case_sensitive(self):
        actual = "Result: TRUE\n"
        expected = "Result: true\n"
        assert OutputComparisonService.compare_exact_stripped(actual, expected, case_sensitive=True) is False
        assert OutputComparisonService.compare_exact_stripped(actual, expected, case_sensitive=False) is True

    def test_compare_float_tolerant_within_epsilon(self):
        actual = "3.14159265"
        expected = "3.14159260"
        assert OutputComparisonService.compare_float_tolerant(actual, expected, epsilon=1e-5) is True
        assert OutputComparisonService.compare_float_tolerant(actual, expected, epsilon=1e-8) is False

    def test_compare_token_match(self):
        actual = "  apple   banana   orange  \n  42  "
        expected = "apple banana orange 42"
        assert OutputComparisonService.compare_token_match(actual, expected) is True


@pytest.mark.django_db
class TestScoringService:
    """Unit tests for partial scoring and negative marking rules."""

    def test_calculate_score_all_passed(self):
        results = [
            {'verdict': TestCaseVerdict.PASSED, 'points_awarded': Decimal('5.00')},
            {'verdict': TestCaseVerdict.PASSED, 'points_awarded': Decimal('5.00')},
        ]
        score, passed, total = ScoringService.calculate_score(results, total_question_points=10)
        assert score == Decimal('10.00')
        assert passed == 2
        assert total == 2

    def test_calculate_score_partial_passed(self):
        results = [
            {'verdict': TestCaseVerdict.PASSED, 'points_awarded': Decimal('4.00')},
            {'verdict': TestCaseVerdict.FAILED, 'points_awarded': Decimal('0.00')},
            {'verdict': TestCaseVerdict.PASSED, 'points_awarded': Decimal('4.00')},
        ]
        score, passed, total = ScoringService.calculate_score(results, total_question_points=12)
        assert score == Decimal('8.00')
        assert passed == 2
        assert total == 3

    def test_calculate_score_zero_passed_with_negative_marking_floors_at_zero(self):
        results = [
            {'verdict': TestCaseVerdict.FAILED, 'points_awarded': Decimal('0.00')},
            {'verdict': TestCaseVerdict.FAILED, 'points_awarded': Decimal('0.00')},
        ]
        score, passed, total = ScoringService.calculate_score(
            results,
            total_question_points=20,
            negative_marking_enabled=True,
            negative_points=5
        )
        assert score == Decimal('0.00')
        assert passed == 0
        assert total == 2

    def test_calculate_score_partial_pass_with_negative_marking_no_penalty(self):
        results = [
            {'verdict': TestCaseVerdict.PASSED, 'points_awarded': Decimal('5.00')},
            {'verdict': TestCaseVerdict.FAILED, 'points_awarded': Decimal('0.00')},
        ]
        score, passed, total = ScoringService.calculate_score(
            results,
            total_question_points=10,
            negative_marking_enabled=True,
            negative_points=3
        )
        assert score == Decimal('5.00')
        assert passed == 1
        assert total == 2


@pytest.mark.django_db
class TestEvaluatorIntegration:
    """End-to-end integration tests for CodeSubmissionService and REST APIs."""

    @pytest.fixture(autouse=True)
    def setup_assessment_and_attempt(self):
        self.admin = User.objects.create_superuser(
            email='eval_admin@codeguard.internal',
            password='AdminPassword123!'
        )
        self.student_user = User.objects.create_user(
            email='student_eval@university.edu',
            password='StudentPassword123!',
            role='STUDENT'
        )
        self.profile = StudentProfile.objects.create(
            user=self.student_user,
            roll_number='ROLL-9999',
            euid='EUID-9999',
            first_login_required=False
        )

        from apps.questions.services import QuestionService

        # Create and Publish Coding Question
        self.question, self.q_v1 = QuestionService.create_question(
            question_type=QuestionType.CODING,
            title='Two Sum Problem',
            description='Read two integers from stdin and output their sum.',
            points=10,
            difficulty=Difficulty.EASY,
            coding_config_data={
                'allowed_languages': ['PYTHON', 'CPP'],
                'time_limit_ms': 2000,
                'memory_limit_mb': 256,
            },
            test_cases_data=[
                {
                    'input_data': '2 3',
                    'expected_output': '5',
                    'points': 5,
                    'is_hidden': False,
                    'execution_order': 1,
                },
                {
                    'input_data': '10 20',
                    'expected_output': '30',
                    'points': 5,
                    'is_hidden': True,
                    'execution_order': 2,
                },
            ],
            actor=self.admin
        )
        self.q_v1 = QuestionService.publish_version(self.q_v1, actor=self.admin)

        # Create Assessment & Publish
        now = timezone.now()
        self.assessment = Assessment.objects.create(
            title='Midterm Coding Exam',
            description='Test coding skills',
            start_datetime=now - timedelta(minutes=10),
            end_datetime=now + timedelta(hours=2),
            duration_minutes=60,
            total_points=10,
            created_by=self.admin
        )
        AssessmentQuestion.objects.create(
            assessment=self.assessment,
            question_version=self.q_v1,
            order=1,
            points=10
        )
        AssessmentAssignment.objects.create(
            assessment=self.assessment,
            student=self.student_user,
            assigned_by=self.admin
        )
        self.published_assessment = AssessmentService.publish_assessment(self.assessment, actor=self.admin)

        # Start Attempt
        self.attempt, _ = AttemptService.start_attempt(
            student=self.student_user,
            assessment_id=str(self.published_assessment.id),
            actor=self.student_user
        )
        self.snap_q = self.attempt.assessment_snapshot.snapshot_questions.first()

    def test_run_code_executes_public_tests_only(self):
        valid_code = "import sys\nraw = sys.stdin.read().split()\nif raw:\n    print(int(raw[0]) + int(raw[1]))\n"
        submission, created = CodeSubmissionService.create_submission(
            student=self.student_user,
            attempt_id=str(self.attempt.id),
            question_id=str(self.snap_q.snapshot_question_id),
            submission_type=SubmissionType.RUN,
            source_code=valid_code,
            language='PYTHON'
        )
        assert created is True
        assert submission.status == SubmissionStatus.QUEUED

        # Evaluate
        eval_sub = CodeSubmissionService.evaluate_submission(str(submission.id))
        assert eval_sub.status == SubmissionStatus.COMPLETED
        assert eval_sub.verdict == CodeVerdict.ACCEPTED
        assert eval_sub.total_test_cases == 1  # 1 public test case only
        assert eval_sub.passed_test_cases == 1

        # Check AttemptAnswer was NOT modified on RUN
        ans = AttemptAnswer.objects.filter(attempt=self.attempt, snapshot_question=self.snap_q).first()
        assert ans is None or ans.code_response != valid_code

    def test_submit_code_evaluates_all_tests_and_updates_attempt_answer(self):
        valid_code = "import sys\nraw = sys.stdin.read().split()\nif raw:\n    print(int(raw[0]) + int(raw[1]))\n"
        submission, created = CodeSubmissionService.create_submission(
            student=self.student_user,
            attempt_id=str(self.attempt.id),
            question_id=str(self.snap_q.snapshot_question_id),
            submission_type=SubmissionType.SUBMIT,
            source_code=valid_code,
            language='PYTHON'
        )
        assert created is True

        # Evaluate
        eval_sub = CodeSubmissionService.evaluate_submission(str(submission.id))
        assert eval_sub.status == SubmissionStatus.COMPLETED
        assert eval_sub.verdict == CodeVerdict.ACCEPTED
        assert eval_sub.total_test_cases == 2  # 1 public + 1 hidden
        assert eval_sub.passed_test_cases == 2
        assert eval_sub.score_awarded == Decimal('10.00')

        # Check AttemptAnswer was updated
        ans = AttemptAnswer.objects.get(attempt=self.attempt, snapshot_question=self.snap_q)
        assert ans.code_response == valid_code
        assert ans.code_language == 'PYTHON'
        assert ans.is_answered is True

        # Check hidden test case result redacts inputs
        hidden_res = eval_sub.test_case_results.get(is_hidden=True)
        assert hidden_res.public_input is None
        assert hidden_res.expected_output is None
        assert hidden_res.actual_output is None

    def test_idempotency_returns_existing_or_rejects_conflict(self):
        code_1 = "print('hello')"
        code_2 = "print('world')"

        sub1, created1 = CodeSubmissionService.create_submission(
            student=self.student_user,
            attempt_id=str(self.attempt.id),
            question_id=str(self.snap_q.snapshot_question_id),
            submission_type=SubmissionType.RUN,
            source_code=code_1,
            language='PYTHON',
            client_nonce='nonce-123'
        )
        assert created1 is True

        # Same nonce and same code -> returns existing
        sub2, created2 = CodeSubmissionService.create_submission(
            student=self.student_user,
            attempt_id=str(self.attempt.id),
            question_id=str(self.snap_q.snapshot_question_id),
            submission_type=SubmissionType.RUN,
            source_code=code_1,
            language='PYTHON',
            client_nonce='nonce-123'
        )
        assert created2 is False
        assert sub1.id == sub2.id

    def test_student_code_run_api_endpoint(self):
        client = APIClient()
        client.force_authenticate(user=self.student_user)

        url = f"/api/v1/student/attempts/{self.attempt.id}/questions/{self.snap_q.snapshot_question_id}/run/"
        payload = {
            "source_code": "print('test')",
            "language": "PYTHON"
        }
        res = client.post(url, data=payload, format='json')
        assert res.status_code == 202
        assert res.data['data']['submission_type'] == 'RUN'
        assert 'submission_id' in res.data['data']

    def test_student_submission_detail_redacts_hidden_data(self):
        client = APIClient()
        client.force_authenticate(user=self.student_user)

        valid_code = "import sys\nraw = sys.stdin.read().split()\nif raw:\n    print(int(raw[0]) + int(raw[1]))\n"
        submission, _ = CodeSubmissionService.create_submission(
            student=self.student_user,
            attempt_id=str(self.attempt.id),
            question_id=str(self.snap_q.snapshot_question_id),
            submission_type=SubmissionType.SUBMIT,
            source_code=valid_code,
            language='PYTHON'
        )
        CodeSubmissionService.evaluate_submission(str(submission.id))

        detail_url = f"/api/v1/student/submissions/{submission.id}/"
        res = client.get(detail_url)
        assert res.status_code == 200
        test_cases = res.data['data']['test_cases']
        assert len(test_cases) == 2

        # Verify hidden test case has null input and output
        hidden_tc = next(tc for tc in test_cases if tc['is_hidden'] is True)
        assert hidden_tc['input'] is None
        assert hidden_tc['expected_output'] is None
        assert hidden_tc['actual_output'] is None
