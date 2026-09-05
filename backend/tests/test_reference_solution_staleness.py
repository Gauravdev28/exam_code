import pytest
from django.contrib.auth import get_user_model
from rest_framework.exceptions import ValidationError as DRFValidationError

from apps.accounts.models import Role
from apps.evaluator.models import CodeVerdict, TestCaseVerdict
from apps.evaluator.serializers import StudentTestCaseResultSerializer
from apps.questions.models import (
    CodingLanguage,
    Difficulty,
    Question,
    QuestionStatus,
    QuestionType,
    QuestionVersion,
    TestCase,
    VersionStatus,
)
from apps.questions.services import (
    CodingQuestionValidationService,
    QuestionService,
    QuestionValidationService,
)

User = get_user_model()


@pytest.fixture
def admin_user(db):
    user, _ = User.objects.get_or_create(
        email="admin.staleness@codeguard.test",
        defaults={
            "role": Role.ADMIN,
            "is_active": True,
        }
    )
    return user


@pytest.fixture(autouse=True)
def mock_judge0_healthy(monkeypatch):
    from apps.evaluator.services import Judge0Adapter
    monkeypatch.setattr(Judge0Adapter, "check_health", classmethod(lambda cls, timeout=1.0: True))


@pytest.fixture
def base_coding_question(db, admin_user):
    """
    Creates a base coding question with Model A reference solution and verified test cases.
    """
    ref_code = "print(sum(map(int, input().split())))"
    ref_lang = CodingLanguage.PYTHON

    q, v = QuestionService.create_question(
        question_type=QuestionType.CODING,
        title="Sum Two Integers",
        description="Given two integers on stdin, print their sum.",
        points=10,
        coding_config_data={
            "problem_statement": "Given two integers on stdin, print their sum.",
            "allowed_languages": [CodingLanguage.PYTHON, CodingLanguage.CPP],
            "starter_codes": {
                CodingLanguage.PYTHON: "# Python starter\n",
                CodingLanguage.CPP: "// C++ starter\n",
            },
            "examples": [
                {"input": "3 5", "output": "8", "explanation": "3 + 5 = 8"}
            ],
            "reference_solutions": {
                ref_lang: ref_code
            },
            "reference_solution_language": ref_lang,
        },
        test_cases_data=[
            {
                "name": "Sample 1",
                "input_data": "3 5",
                "expected_output": "8",
                "points": 5,
                "is_hidden": False,
                "is_verified": True,
            },
            {
                "name": "Hidden 1",
                "input_data": "10 20",
                "expected_output": "30",
                "points": 5,
                "is_hidden": True,
                "is_verified": True,
            },
        ],
        actor=admin_user,
    )
    # Mark reference solution explicitly verified
    config = v.coding_config
    config.mark_reference_solution_verified(ref_lang, ref_code)
    config.save()
    return v


@pytest.mark.django_db
class TestReferenceSolutionStaleness:
    """
    Tests proving invariants A through J for reference-solution staleness and verification.
    """

    def test_a_verified_reference_solution_initially_current(self, base_coding_question):
        """A. A verified reference solution is initially considered current."""
        config = base_coding_question.coding_config
        assert config.reference_solution_verified is True
        assert config.reference_solution_hash != ""
        assert config.is_reference_solution_current() is True

        health = CodingQuestionValidationService.get_health_status(base_coding_question)
        assert health["is_ready"] is True
        assert health["status"] == "DRAFT_READY"
        verification_check = next(c for c in health["checks"] if c["key"] == "expected_output_verification")
        assert verification_check["passed"] is True
        assert "Reference solution verified" in verification_check["message"]

    def test_b_source_code_change_invalidates_verification(self, base_coding_question):
        """B. Changing reference solution source code invalidates its previous verification."""
        config = base_coding_question.coding_config
        assert config.is_reference_solution_current() is True

        # Modify reference solution source code
        config.reference_solutions[CodingLanguage.PYTHON] = "print('tampered code')"
        config.save()

        config.refresh_from_db()
        assert config.reference_solution_verified is False
        assert config.reference_solution_verified_at is None
        assert config.is_reference_solution_current() is False

    def test_c_language_change_invalidates_verification(self, base_coding_question):
        """C. Changing reference solution language invalidates its previous verification."""
        config = base_coding_question.coding_config
        assert config.is_reference_solution_current() is True

        # Switch reference solution language to CPP without re-verifying
        config.reference_solution_language = CodingLanguage.CPP
        config.reference_solutions[CodingLanguage.CPP] = "#include <iostream>\nint main(){}"
        config.save()

        config.refresh_from_db()
        assert config.reference_solution_verified is False
        assert config.is_reference_solution_current() is False

    def test_d_stale_verification_causes_health_not_ready(self, base_coding_question):
        """D. Stale reference-solution verification causes Question Health to become NOT READY."""
        config = base_coding_question.coding_config
        config.reference_solutions[CodingLanguage.PYTHON] = "print('new output')"
        config.save()

        health = CodingQuestionValidationService.get_health_status(base_coding_question)
        assert health["is_ready"] is False
        assert health["status"] == "DRAFT_INCOMPLETE"

        verification_check = next(c for c in health["checks"] if c["key"] == "expected_output_verification")
        assert verification_check["passed"] is False
        assert "stale" in verification_check["message"].lower() or "verification" in verification_check["message"].lower()

    def test_e_stale_verification_blocks_publishing(self, base_coding_question, admin_user):
        """E. Stale reference-solution verification blocks publishing."""
        config = base_coding_question.coding_config
        config.reference_solutions[CodingLanguage.PYTHON] = "print('modified')"
        config.save()

        with pytest.raises(DRFValidationError) as exc:
            QuestionService.publish_version(base_coding_question, actor=admin_user)

        assert "reference_solution" in exc.value.detail or "expected_output_verification" in exc.value.detail

    def test_f_affected_test_cases_become_unverified_on_reference_solution_change(self, base_coding_question):
        """F. Previously verified affected test cases become unverified after reference-solution changes."""
        config = base_coding_question.coding_config
        assert config.test_cases.filter(is_verified=True).count() == 2

        config.reference_solutions[CodingLanguage.PYTHON] = "print('different output')"
        config.save()

        # All test cases under this config must now be unverified
        assert config.test_cases.filter(is_verified=True).count() == 0
        assert config.test_cases.filter(is_verified=False).count() == 2

    def test_g_re_verifying_restores_valid_state(self, base_coding_question, admin_user):
        """G. Rerunning the reference solution and explicitly confirming outputs restores the valid verification state."""
        config = base_coding_question.coding_config
        new_code = "import sys; print(sum(int(x) for x in sys.stdin.read().split()))"
        config.reference_solutions[CodingLanguage.PYTHON] = new_code
        config.save()

        # Initially invalidated
        assert config.reference_solution_verified is False
        assert config.test_cases.filter(is_verified=False).count() == 2

        # Admin reviews new output, confirms test cases, and marks reference solution verified
        config.test_cases.update(is_verified=True)
        config.mark_reference_solution_verified(CodingLanguage.PYTHON, new_code)
        config.save()

        config.refresh_from_db()
        assert config.is_reference_solution_current() is True
        assert config.test_cases.filter(is_verified=True).count() == 2

        health = CodingQuestionValidationService.get_health_status(base_coding_question)
        assert health["is_ready"] is True

        # Now publishing succeeds
        published = QuestionService.publish_version(base_coding_question, actor=admin_user)
        assert published.status == VersionStatus.PUBLISHED

    def test_h_model_b_manual_verification_without_reference_solution(self, db, admin_user):
        """H. Model B manual expected-output verification continues to work without a reference solution."""
        q, v = QuestionService.create_question(
            question_type=QuestionType.CODING,
            title="Manual Verification Question",
            description="Problem without reference solution",
            points=10,
            coding_config_data={
                "problem_statement": "Problem without reference solution",
                "allowed_languages": [CodingLanguage.PYTHON],
                "starter_codes": {CodingLanguage.PYTHON: "# pass"},
                "examples": [{"input": "1", "output": "1", "explanation": "Identity"}],
                "reference_solutions": {},  # Model B: No reference solution
            },
            test_cases_data=[
                {"name": "Sample", "input_data": "1", "expected_output": "1", "points": 5, "is_hidden": False, "is_verified": True},
                {"name": "Hidden", "input_data": "2", "expected_output": "2", "points": 5, "is_hidden": True, "is_verified": True},
            ],
            actor=admin_user,
        )

        health = CodingQuestionValidationService.get_health_status(v)
        verification_check = next(c for c in health["checks"] if c["key"] == "expected_output_verification")
        assert verification_check["passed"] is True
        assert "manually verified" in verification_check["message"].lower()

        published = QuestionService.publish_version(v, actor=admin_user)
        assert published.status == VersionStatus.PUBLISHED

    def test_i_editing_verified_test_case_invalidates_verification(self, base_coding_question):
        """I. Editing an already verified test case continues to invalidate its verification."""
        tc = base_coding_question.coding_config.test_cases.first()
        assert tc.is_verified is True

        # Modifying expected output
        tc.expected_output = "999"
        tc.save()

        tc.refresh_from_db()
        assert tc.is_verified is False

        # Modifying input data
        tc.is_verified = True
        tc.save()
        assert tc.is_verified is True

        tc.input_data = "99 1"
        tc.save()
        tc.refresh_from_db()
        assert tc.is_verified is False

    def test_j_no_hidden_test_data_or_points_exposed_to_candidates(self, base_coding_question):
        """J. No hidden test data or per-hidden-test points are exposed to candidates."""
        from apps.evaluator.models import CodeTestCaseResult

        public_tc = CodeTestCaseResult(
            test_case_index=1,
            is_hidden=False,
            verdict=TestCaseVerdict.PASSED,
            points_awarded=5,
            max_points=5,
            public_input="3 5",
            expected_output="8",
            actual_output="8",
        )

        hidden_tc = CodeTestCaseResult(
            test_case_index=2,
            is_hidden=True,
            verdict=TestCaseVerdict.FAILED,
            points_awarded=0,
            max_points=5,
            public_input=None,
            expected_output=None,
            actual_output=None,
        )

        serializer_pub = StudentTestCaseResultSerializer(public_tc).data
        assert serializer_pub["points_awarded"] == 5
        assert serializer_pub["max_points"] == 5
        assert serializer_pub["input"] == "3 5"

        serializer_hid = StudentTestCaseResultSerializer(hidden_tc).data
        assert serializer_hid["points_awarded"] is None
        assert serializer_hid["max_points"] is None
        assert serializer_hid["input"] is None
        assert serializer_hid["expected_output"] is None
        assert serializer_hid["actual_output"] is None
        assert serializer_hid["is_hidden"] is True
