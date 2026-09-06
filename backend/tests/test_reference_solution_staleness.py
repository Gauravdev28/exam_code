import pytest
from django.contrib.auth import get_user_model
from rest_framework.exceptions import ValidationError as DRFValidationError

from apps.accounts.models import Role
from apps.evaluator.models import CodeVerdict, TestCaseVerdict
from apps.evaluator.serializers import StudentTestCaseResultSerializer
from apps.questions.models import (
    CodingLanguage,
    CodingQuestionConfig,
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


@pytest.mark.django_db
class TestReferenceSolutionLanguageHandling:
    """
    Comprehensive regression test suite for reference-solution language handling:
    1. Lookup with mixed case (Python, python, PYTHON)
    2. Lookup with whitespace ('  python  ')
    3. Missing language returns empty string
    4. Non-dict reference_solutions safely handled
    5. reference_solution_language stored in canonical form (trimmed uppercase)
    6. Hashing stays identical regardless of lookup case
    7. Modifying reference code with different language casing still invalidates verification
    8. Modifying language to equivalent canonical form does NOT falsely invalidate verification
    9. Modifying language to genuinely different language DOES invalidate verification
    10. Verified test cases are invalidated whenever reference verification is invalidated
    11. Question health reflects staleness correctly across case variations
    """

    @pytest.fixture
    def admin_user(self):
        return User.objects.create_user(
            email="admin_lang@codeguard.test",
            role=Role.ADMIN,
            is_active=True,
        )

    def test_1_lookup_with_mixed_case_and_whitespace(self):
        # Case A: Keys stored as canonical uppercase
        sol_canonical = {"PYTHON": "print('hello')", "CPP": "#include <iostream>"}
        assert CodingQuestionConfig.get_code_for_language(sol_canonical, "python") == "print('hello')"
        assert CodingQuestionConfig.get_code_for_language(sol_canonical, "Python") == "print('hello')"
        assert CodingQuestionConfig.get_code_for_language(sol_canonical, "PYTHON") == "print('hello')"
        assert CodingQuestionConfig.get_code_for_language(sol_canonical, "  python  ") == "print('hello')"
        assert CodingQuestionConfig.get_code_for_language(sol_canonical, "  CPP\n") == "#include <iostream>"

        # Case B: Keys stored with lowercase or whitespace in dict
        sol_sloppy = {" python ": "print('sloppy')", "cPp": "int main() {}"}
        assert CodingQuestionConfig.get_code_for_language(sol_sloppy, "PYTHON") == "print('sloppy')"
        assert CodingQuestionConfig.get_code_for_language(sol_sloppy, "python") == "print('sloppy')"
        assert CodingQuestionConfig.get_code_for_language(sol_sloppy, "cpp") == "int main() {}"

    def test_2_missing_language_returns_empty_string(self):
        sol = {"PYTHON": "print('hello')"}
        assert CodingQuestionConfig.get_code_for_language(sol, "JAVA") == ""
        assert CodingQuestionConfig.get_code_for_language(sol, "") == ""
        assert CodingQuestionConfig.get_code_for_language(sol, "   ") == ""
        assert CodingQuestionConfig.get_code_for_language(sol, None) == ""
        assert CodingQuestionConfig.get_code_for_language({}, "PYTHON") == ""

    def test_3_non_dict_reference_solutions_safely_handled(self):
        assert CodingQuestionConfig.get_code_for_language(None, "PYTHON") == ""
        assert CodingQuestionConfig.get_code_for_language("not a dict", "PYTHON") == ""
        assert CodingQuestionConfig.get_code_for_language(["PYTHON"], "PYTHON") == ""
        assert CodingQuestionConfig.get_code_for_language(12345, "PYTHON") == ""

    def test_4_reference_solution_language_stored_in_canonical_form(self, admin_user):
        q, v = QuestionService.create_question(
            question_type=QuestionType.CODING,
            title="Canonical Lang Question",
            description="Test canonical language",
            difficulty=Difficulty.EASY,
            actor=admin_user,
            coding_config_data={
                "problem_statement": "Print hi",
                "allowed_languages": ["PYTHON"],
                "reference_solutions": {"PYTHON": "print('hi')"},
                "reference_solution_language": "  python  ",
            },
        )
        conf = v.coding_config
        assert conf.reference_solution_language == "PYTHON"

        # Updating via mark_reference_solution_verified
        conf.mark_reference_solution_verified("  python  ", "print('hi')")
        conf.save()
        conf.refresh_from_db()
        assert conf.reference_solution_language == "PYTHON"

    def test_5_hashing_stays_identical_regardless_of_lookup_case(self):
        code = "print(42)"
        h1 = CodingQuestionConfig.compute_reference_hash(code, "PYTHON")
        h2 = CodingQuestionConfig.compute_reference_hash(code, "python")
        h3 = CodingQuestionConfig.compute_reference_hash(code, "  Python  ")
        assert h1 == h2 == h3
        assert len(h1) == 64

        # Empty code or lang returns empty string
        assert CodingQuestionConfig.compute_reference_hash("", "PYTHON") == ""
        assert CodingQuestionConfig.compute_reference_hash(code, "") == ""
        assert CodingQuestionConfig.compute_reference_hash(None, "PYTHON") == ""
        assert CodingQuestionConfig.compute_reference_hash(code, None) == ""

    def test_6_modifying_reference_code_with_different_language_casing_invalidates_verification(self, admin_user):
        code = "print(sum([1, 2]))"
        q, v = QuestionService.create_question(
            question_type=QuestionType.CODING,
            title="Staleness Test",
            description="Testing staleness detection",
            difficulty=Difficulty.EASY,
            actor=admin_user,
            coding_config_data={
                "problem_statement": "Compute sum",
                "allowed_languages": ["PYTHON"],
                "reference_solutions": {"PYTHON": code},
                "reference_solution_language": "PYTHON",
            },
            test_cases_data=[
                {"name": "TC1", "input_data": "1", "expected_output": "3", "points": 5, "is_verified": True},
                {"name": "TC2", "input_data": "2", "expected_output": "3", "points": 5, "is_verified": True},
            ],
        )
        conf = v.coding_config
        conf.mark_reference_solution_verified("PYTHON", code)
        conf.save()

        assert conf.reference_solution_verified is True
        assert conf.test_cases.filter(is_verified=True).count() == 2

        # Modify code using lowercase key in dictionary
        conf.reference_solutions = {"python": "print('modified code')"}
        conf.save()
        conf.refresh_from_db()

        assert conf.reference_solution_verified is False
        assert conf.reference_solution_verified_at is None
        # Invariant: associated verified test cases invalidated
        assert conf.test_cases.filter(is_verified=True).count() == 0

    def test_7_modifying_language_to_equivalent_canonical_form_does_not_falsely_invalidate(self, admin_user):
        code = "print('constant')"
        q, v = QuestionService.create_question(
            question_type=QuestionType.CODING,
            title="No False Invalidation Test",
            description="Testing equivalent language change",
            difficulty=Difficulty.EASY,
            actor=admin_user,
            coding_config_data={
                "problem_statement": "Statement",
                "allowed_languages": ["PYTHON"],
                "reference_solutions": {"PYTHON": code},
                "reference_solution_language": "PYTHON",
            },
            test_cases_data=[
                {"name": "TC1", "input_data": "1", "expected_output": "1", "points": 5, "is_verified": True},
            ],
        )
        conf = v.coding_config
        conf.mark_reference_solution_verified("PYTHON", code)
        conf.save()
        assert conf.reference_solution_verified is True

        # Change language to lowercase with surrounding whitespace
        conf.reference_solution_language = "  python  "
        conf.save()
        conf.refresh_from_db()

        # Should NOT be invalidated because normalized language is still 'PYTHON' and code is untouched
        assert conf.reference_solution_verified is True
        assert conf.reference_solution_language == "PYTHON"
        assert conf.test_cases.filter(is_verified=True).count() == 1

    def test_8_modifying_language_to_genuinely_different_language_invalidates_verification(self, admin_user):
        code = "print('python')"
        q, v = QuestionService.create_question(
            question_type=QuestionType.CODING,
            title="Diff Lang Invalidation",
            description="Testing diff language change",
            difficulty=Difficulty.EASY,
            actor=admin_user,
            coding_config_data={
                "problem_statement": "Statement",
                "allowed_languages": ["PYTHON", "CPP"],
                "reference_solutions": {"PYTHON": code, "CPP": "cout << 1;"},
                "reference_solution_language": "PYTHON",
            },
            test_cases_data=[
                {"name": "TC1", "input_data": "1", "expected_output": "1", "points": 5, "is_verified": True},
            ],
        )
        conf = v.coding_config
        conf.mark_reference_solution_verified("PYTHON", code)
        conf.save()
        assert conf.reference_solution_verified is True

        # Switch reference language to CPP
        conf.reference_solution_language = "CPP"
        conf.save()
        conf.refresh_from_db()

        assert conf.reference_solution_verified is False
        assert conf.test_cases.filter(is_verified=True).count() == 0

    def test_9_question_health_reflects_staleness_correctly_across_case_variations(self, admin_user):
        code = "print('health test')"
        q, v = QuestionService.create_question(
            question_type=QuestionType.CODING,
            title="Health Staleness Case Test",
            description="Desc",
            difficulty=Difficulty.EASY,
            actor=admin_user,
            coding_config_data={
                "problem_statement": "Desc",
                "allowed_languages": ["PYTHON"],
                "starter_codes": {"PYTHON": "# code"},
                "examples": [{"input": "1", "output": "1"}],
                "reference_solutions": {"PYTHON": code},
                "reference_solution_language": "python",
            },
            test_cases_data=[
                {"name": "TC1", "input_data": "1", "expected_output": "1", "points": 5, "is_verified": True, "is_hidden": False},
                {"name": "TC2", "input_data": "2", "expected_output": "2", "points": 5, "is_verified": True, "is_hidden": True},
            ],
        )
        conf = v.coding_config
        conf.mark_reference_solution_verified("Python", code)
        conf.save()

        # Check health: ready
        status = CodingQuestionValidationService.get_health_status(v)
        assert status["is_ready"] is True

        # Invalidate via code change in lowercase key
        conf.reference_solutions = {"python": "print('stale')"}
        conf.save()
        conf.refresh_from_db()

        status_stale = CodingQuestionValidationService.get_health_status(v)
        assert status_stale["is_ready"] is False
        assert any(c["key"] == "expected_output_verification" and not c["passed"] for c in status_stale["checks"])

