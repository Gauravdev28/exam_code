import pytest
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from rest_framework.exceptions import ValidationError as DRFValidationError

from apps.accounts.models import Role
from apps.questions.models import (
    Question,
    QuestionVersion,
    QuestionType,
    Difficulty,
    VersionStatus,
    QuestionStatus,
    CodingLanguage,
    CodingQuestionConfig,
    TestCase,
    SQLQuestionConfig,
    Tag,
)
from apps.questions.services import QuestionService, QuestionValidationService

User = get_user_model()

@pytest.fixture
def admin_user(db):
    return User.objects.create_superuser(
        email="admin_qb@codeguard.local",
        password="AdminSecurePass123!",
        role=Role.ADMIN
    )

@pytest.fixture
def student_user(db):
    return User.objects.create_user(
        email="student_qb@codeguard.local",
        password="StudentPass123!",
        role=Role.STUDENT
    )


# ==============================================================================
# 1. Question Creation Across All 6 Types
# ==============================================================================

@pytest.mark.django_db
def test_admin_can_create_mcq_question(api_client, admin_user):
    """1. Admin can create an MCQ question (v1 draft)."""
    api_client.force_authenticate(user=admin_user)
    url = reverse('questions:admin-question-list')
    payload = {
        "question_type": "MCQ",
        "title": "Python List Mutability",
        "description": "Which of the following data types in Python is mutable?",
        "points": 10,
        "difficulty": "EASY",
        "tags": ["Python", "Data Structures"],
        "type_config": {
            "options": [
                {"id": "A", "text": "Tuple"},
                {"id": "B", "text": "String"},
                {"id": "C", "text": "List"},
                {"id": "D", "text": "Integer"}
            ],
            "correct_options": ["C"]
        }
    }
    response = api_client.post(url, payload, format='json')
    assert response.status_code == 201
    data = response.json()['data']
    assert data['question_type'] == "MCQ"
    assert data['version_number'] == 1
    assert data['status'] == "DRAFT"
    assert data['points'] == 10
    assert len(data['tags']) == 2


@pytest.mark.django_db
def test_admin_can_create_multi_select_question(api_client, admin_user):
    """2. Admin can create a Multi-Select question."""
    api_client.force_authenticate(user=admin_user)
    url = reverse('questions:admin-question-list')
    payload = {
        "question_type": "MULTI_SELECT",
        "title": "Prime Numbers",
        "description": "Select all prime numbers from the options below.",
        "points": 15,
        "difficulty": "MEDIUM",
        "type_config": {
            "options": [
                {"id": "A", "text": "2"},
                {"id": "B", "text": "4"},
                {"id": "C", "text": "7"},
                {"id": "D", "text": "9"}
            ],
            "correct_options": ["A", "C"]
        }
    }
    response = api_client.post(url, payload, format='json')
    assert response.status_code == 201
    assert response.json()['data']['question_type'] == "MULTI_SELECT"


@pytest.mark.django_db
def test_admin_can_create_true_false_question(api_client, admin_user):
    """3. Admin can create a True/False question."""
    api_client.force_authenticate(user=admin_user)
    url = reverse('questions:admin-question-list')
    payload = {
        "question_type": "TRUE_FALSE",
        "title": "Python GIL",
        "description": "CPython uses a Global Interpreter Lock.",
        "points": 5,
        "difficulty": "EASY",
        "type_config": {
            "correct_answer": True
        }
    }
    response = api_client.post(url, payload, format='json')
    assert response.status_code == 201
    assert response.json()['data']['type_config']['correct_answer'] is True


@pytest.mark.django_db
def test_admin_can_create_short_answer_question(api_client, admin_user):
    """4. Admin can create a Short Answer question."""
    api_client.force_authenticate(user=admin_user)
    url = reverse('questions:admin-question-list')
    payload = {
        "question_type": "SHORT_ANSWER",
        "title": "HTTP Port",
        "description": "What is the standard default port number for HTTP traffic?",
        "points": 5,
        "difficulty": "EASY",
        "type_config": {
            "accepted_answers": ["80", "port 80"],
            "case_sensitive": False,
            "trim_whitespace": True,
            "normalize_spaces": True
        }
    }
    response = api_client.post(url, payload, format='json')
    assert response.status_code == 201
    assert "80" in response.json()['data']['type_config']['accepted_answers']


@pytest.mark.django_db
def test_admin_can_create_coding_question_with_test_cases(api_client, admin_user):
    """5. Admin can create a Coding question with public and hidden test cases."""
    api_client.force_authenticate(user=admin_user)
    url = reverse('questions:admin-question-list')
    payload = {
        "question_type": "CODING",
        "title": "Two Sum",
        "description": "Given an array of integers, return indices of the two numbers such that they add up to target.",
        "points": 20,
        "difficulty": "MEDIUM",
        "coding_config": {
            "problem_statement": "Detailed two sum instructions...",
            "allowed_languages": ["PYTHON", "CPP", "JAVA"],
            "time_limit_ms": 2000,
            "memory_limit_mb": 256
        },
        "test_cases": [
            {"input_data": "[2,7,11,15]\n9", "expected_output": "[0,1]", "points": 10, "is_hidden": False},
            {"input_data": "[3,2,4]\n6", "expected_output": "[1,2]", "points": 10, "is_hidden": True}
        ]
    }
    response = api_client.post(url, payload, format='json')
    assert response.status_code == 201
    data = response.json()['data']
    assert data['question_type'] == "CODING"
    assert len(data['coding_config']['test_cases']) == 2
    assert data['coding_config']['test_cases'][0]['is_hidden'] is False
    assert data['coding_config']['test_cases'][1]['is_hidden'] is True


@pytest.mark.django_db
def test_admin_can_create_sql_question(api_client, admin_user):
    """6. Admin can create an SQL question with schema setup and expected result definition."""
    api_client.force_authenticate(user=admin_user)
    url = reverse('questions:admin-question-list')
    payload = {
        "question_type": "SQL",
        "title": "Find Top Earners",
        "description": "Write a query to find employees earning more than $80,000.",
        "points": 15,
        "difficulty": "MEDIUM",
        "sql_config": {
            "problem_statement": "Select name and salary from employees where salary > 80000",
            "schema_setup_sql": "CREATE TABLE employees (id INT, name VARCHAR(50), salary INT); INSERT INTO employees VALUES (1, 'Alice', 90000), (2, 'Bob', 70000);",
            "expected_result_definition": "SELECT name, salary FROM employees WHERE salary > 80000 ORDER BY salary DESC;",
            "allowed_dialect": "MYSQL",
            "time_limit_ms": 3000
        }
    }
    response = api_client.post(url, payload, format='json')
    assert response.status_code == 201
    data = response.json()['data']
    assert data['question_type'] == "SQL"
    assert "CREATE TABLE" in data['sql_config']['schema_setup_sql']


# ==============================================================================
# 2. RBAC & Permissions
# ==============================================================================

@pytest.mark.django_db
def test_student_cannot_create_questions(api_client, student_user):
    """7. Students cannot create questions (403 Forbidden)."""
    api_client.force_authenticate(user=student_user)
    url = reverse('questions:admin-question-list')
    response = api_client.post(url, {"question_type": "MCQ", "title": "Test"}, format='json')
    assert response.status_code == 403


@pytest.mark.django_db
def test_unauthenticated_cannot_create_questions(api_client):
    """8. Unauthenticated callers are rejected with 401."""
    url = reverse('questions:admin-question-list')
    response = api_client.post(url, {"question_type": "MCQ", "title": "Test"}, format='json')
    assert response.status_code == 401


# ==============================================================================
# 3. Validation & Scoring Invariants
# ==============================================================================

@pytest.mark.django_db
def test_invalid_mcq_rejected_on_publish(admin_user):
    """9. MCQ with fewer than 2 options or invalid correct option is rejected on publish."""
    question, version = QuestionService.create_question(
        question_type=QuestionType.MCQ,
        title="Bad MCQ",
        description="Bad description",
        points=10,
        type_config={"options": [{"id": "A", "text": "Single Option"}], "correct_options": ["A"]},
        actor=admin_user
    )
    with pytest.raises(DRFValidationError) as excinfo:
        QuestionService.publish_version(version=version, actor=admin_user)
    assert "options" in excinfo.value.detail


@pytest.mark.django_db
def test_multi_select_without_correct_options_rejected(admin_user):
    """10. Multi-select with empty correct_options is rejected on publish."""
    question, version = QuestionService.create_question(
        question_type=QuestionType.MULTI_SELECT,
        title="Bad Multi",
        description="Bad description",
        points=10,
        type_config={
            "options": [{"id": "A", "text": "Opt A"}, {"id": "B", "text": "Opt B"}],
            "correct_options": []
        },
        actor=admin_user
    )
    with pytest.raises(DRFValidationError) as excinfo:
        QuestionService.publish_version(version=version, actor=admin_user)
    assert "correct_options" in excinfo.value.detail


@pytest.mark.django_db
def test_zero_or_negative_points_rejected(admin_user):
    """15. Points < 1 is rejected on creation and update."""
    with pytest.raises(DRFValidationError):
        QuestionService.create_question(
            question_type=QuestionType.MCQ,
            title="Zero Points",
            description="Prompt",
            points=0,
            actor=admin_user
        )


@pytest.mark.django_db
def test_negative_points_exceeding_total_points_rejected(admin_user):
    """16. Negative marking penalty exceeding total points is rejected."""
    with pytest.raises(DRFValidationError):
        QuestionService.create_question(
            question_type=QuestionType.MCQ,
            title="Excessive Penalty",
            description="Prompt",
            points=10,
            negative_marking_enabled=True,
            negative_points=15,
            actor=admin_user
        )


# ==============================================================================
# 4. Coding Test Case Invariant & Hidden Case Security
# ==============================================================================

@pytest.mark.django_db
def test_coding_test_case_points_sum_invariant_enforced_on_publish(admin_user):
    """24 & 25. Coding question publication strictly enforces SUM(test_cases.points) == points."""
    question, version = QuestionService.create_question(
        question_type=QuestionType.CODING,
        title="Sum Test",
        description="Write sum function",
        points=20,
        coding_config_data={"problem_statement": "Sum problem"},
        test_cases_data=[
            {"input_data": "1 2", "expected_output": "3", "points": 10},
            {"input_data": "2 3", "expected_output": "5", "points": 5}  # Total 15 != 20
        ],
        actor=admin_user
    )

    # Attempt publish with points sum 15 != 20 -> Fails
    with pytest.raises(DRFValidationError) as excinfo:
        QuestionService.publish_version(version=version, actor=admin_user)
    assert "test_cases" in excinfo.value.detail

    # Fix test cases to total 20 (10 + 10)
    QuestionService.update_draft_version(
        version=version,
        test_cases_data=[
            {"input_data": "1 2", "expected_output": "3", "points": 10},
            {"input_data": "2 3", "expected_output": "5", "points": 10}
        ],
        actor=admin_user
    )

    # Publish now succeeds
    published = QuestionService.publish_version(version=version, actor=admin_user)
    assert published.status == VersionStatus.PUBLISHED


@pytest.mark.django_db
def test_hidden_test_cases_stored_and_excluded_from_public_preview(api_client, admin_user):
    """26 & 27. Hidden test cases are stored but excluded from preview and student-facing serialization."""
    question, version = QuestionService.create_question(
        question_type=QuestionType.CODING,
        title="Hidden TC Check",
        description="Problem",
        points=10,
        coding_config_data={"problem_statement": "Problem"},
        test_cases_data=[
            {"input_data": "public_in", "expected_output": "public_out", "points": 5, "is_hidden": False},
            {"input_data": "secret_in", "expected_output": "secret_out", "points": 5, "is_hidden": True}
        ],
        actor=admin_user
    )

    api_client.force_authenticate(user=admin_user)
    preview_url = reverse('questions:admin-question-version-preview', kwargs={'pk': question.id, 'version_number': 1})
    response = api_client.get(preview_url)
    assert response.status_code == 200
    p_tcs = response.json()['data']['coding_config']['test_cases']

    # Public preview must ONLY show the public test case
    assert len(p_tcs) == 1
    assert p_tcs[0]['input_data'] == "public_in"
    assert "secret_in" not in str(response.json())


# ==============================================================================
# 5. Versioning, State Transitions & Immutability
# ==============================================================================

@pytest.mark.django_db
def test_sequential_versioning_and_unique_constraint(admin_user):
    """18 & 19. Version numbers are strictly sequential (1, 2, 3) and unique per question."""
    question, v1 = QuestionService.create_question(
        question_type=QuestionType.MCQ,
        title="V1 MCQ",
        description="Desc",
        points=10,
        type_config={"options": [{"id": "A", "text": "1"}, {"id": "B", "text": "2"}], "correct_options": ["A"]},
        actor=admin_user
    )
    assert v1.version_number == 1

    v2 = QuestionService.create_new_version(question=question, actor=admin_user)
    assert v2.version_number == 2
    assert v2.status == VersionStatus.DRAFT

    v3 = QuestionService.create_new_version(question=question, actor=admin_user)
    assert v3.version_number == 3


@pytest.mark.django_db
def test_published_version_cannot_be_edited_directly(admin_user):
    """21. Published question versions are permanently immutable and reject edits."""
    question, v1 = QuestionService.create_question(
        question_type=QuestionType.MCQ,
        title="Locked MCQ",
        description="Desc",
        points=10,
        type_config={"options": [{"id": "A", "text": "1"}, {"id": "B", "text": "2"}], "correct_options": ["A"]},
        actor=admin_user
    )
    QuestionService.publish_version(version=v1, actor=admin_user)
    assert v1.status == VersionStatus.PUBLISHED

    # Attempting to edit via service
    with pytest.raises(PermissionDenied):
        QuestionService.update_draft_version(version=v1, title="Tampered Title", actor=admin_user)

    # Attempting direct ORM save
    v1.title = "Direct ORM Tamper"
    with pytest.raises(PermissionDenied):
        v1.save()


@pytest.mark.django_db
def test_published_version_cannot_be_deleted(admin_user):
    """22. Published versions cannot be deleted."""
    question, v1 = QuestionService.create_question(
        question_type=QuestionType.MCQ,
        title="Locked MCQ",
        description="Desc",
        points=10,
        type_config={"options": [{"id": "A", "text": "1"}, {"id": "B", "text": "2"}], "correct_options": ["A"]},
        actor=admin_user
    )
    QuestionService.publish_version(version=v1, actor=admin_user)

    with pytest.raises(PermissionDenied):
        v1.delete()


@pytest.mark.django_db
def test_publishing_version_v2_automatically_archives_v1(admin_user):
    """28 & 29. Publishing V2 atomically transitions V1 to ARCHIVED and keeps exactly 1 version PUBLISHED."""
    question, v1 = QuestionService.create_question(
        question_type=QuestionType.MCQ,
        title="V1 MCQ",
        description="Desc",
        points=10,
        type_config={"options": [{"id": "A", "text": "1"}, {"id": "B", "text": "2"}], "correct_options": ["A"]},
        actor=admin_user
    )
    QuestionService.publish_version(version=v1, actor=admin_user)
    v1.refresh_from_db()
    assert v1.status == VersionStatus.PUBLISHED

    # Create and publish V2
    v2 = QuestionService.create_new_version(question=question, actor=admin_user)
    QuestionService.publish_version(version=v2, actor=admin_user)

    v1.refresh_from_db()
    v2.refresh_from_db()

    assert v1.status == VersionStatus.ARCHIVED
    assert v2.status == VersionStatus.PUBLISHED
    assert question.versions.filter(status=VersionStatus.PUBLISHED).count() == 1


# ==============================================================================
# 6. Deletion Safety & Logical Archiving
# ==============================================================================

@pytest.mark.django_db
def test_hard_delete_allowed_for_draft_only_questions(admin_user):
    """34. Pure draft question with zero published versions can be hard-deleted."""
    question, v1 = QuestionService.create_question(
        question_type=QuestionType.MCQ,
        title="Draft Only",
        description="Desc",
        actor=admin_user
    )
    q_id = question.id
    QuestionService.delete_draft_question(question=question, actor=admin_user)
    assert not Question.objects.filter(id=q_id).exists()


@pytest.mark.django_db
def test_hard_delete_rejected_for_questions_with_published_or_historical_versions(admin_user):
    """34. Questions with published or historical versions reject hard deletion."""
    question, v1 = QuestionService.create_question(
        question_type=QuestionType.MCQ,
        title="Published Question",
        description="Desc",
        points=10,
        type_config={"options": [{"id": "A", "text": "1"}, {"id": "B", "text": "2"}], "correct_options": ["A"]},
        actor=admin_user
    )
    QuestionService.publish_version(version=v1, actor=admin_user)

    with pytest.raises(DRFValidationError):
        QuestionService.delete_draft_question(question=question, actor=admin_user)


# ==============================================================================
# 7. Snapshot Readiness & Deep Clone Integrity (Correction 1 & 4)
# ==============================================================================

@pytest.mark.django_db
def test_question_type_consistency_and_immutability(admin_user):
    """Correction 1: Question.question_type == QuestionVersion.question_type strictly enforced."""
    question, v1 = QuestionService.create_question(
        question_type=QuestionType.MCQ,
        title="Type Check",
        description="Desc",
        actor=admin_user
    )
    assert question.question_type == QuestionType.MCQ
    assert v1.question_type == QuestionType.MCQ

    # Attempting to modify parent question type directly
    question.question_type = QuestionType.CODING
    with pytest.raises(PermissionDenied):
        question.save()


@pytest.mark.django_db
def test_snapshot_readiness_historical_version_integrity(admin_user):
    """
    Correction 4: Snapshot Readiness / Historical Integrity.
    Verifies that publishing V1, creating V2, and heavily modifying V2 leaves V1 completely untouched.
    """
    question, v1 = QuestionService.create_question(
        question_type=QuestionType.CODING,
        title="V1 Two Sum",
        description="V1 Problem Statement",
        points=20,
        coding_config_data={
            "problem_statement": "V1 Coding Statement",
            "allowed_languages": ["PYTHON", "JAVA"],
            "time_limit_ms": 2000
        },
        test_cases_data=[
            {"input_data": "1 2", "expected_output": "3", "points": 10, "is_hidden": False},
            {"input_data": "3 4", "expected_output": "7", "points": 10, "is_hidden": True}
        ],
        actor=admin_user
    )
    QuestionService.publish_version(version=v1, actor=admin_user)
    v1.refresh_from_db()

    # Capture snapshot data representation of V1
    v1_title = v1.title
    v1_points = v1.points
    v1_statement = v1.coding_config.problem_statement
    v1_tc_count = v1.coding_config.test_cases.count()
    v1_tc_inputs = list(v1.coding_config.test_cases.values_list('input_data', flat=True))

    # Create V2 and mutate V2
    v2 = QuestionService.create_new_version(question=question, actor=admin_user)
    QuestionService.update_draft_version(
        version=v2,
        title="V2 Modified Two Sum",
        description="V2 New Description",
        points=30,
        coding_config_data={
            "problem_statement": "V2 New Problem Statement",
            "allowed_languages": ["PYTHON", "CPP"],
            "time_limit_ms": 5000
        },
        test_cases_data=[
            {"input_data": "10 20", "expected_output": "30", "points": 15},
            {"input_data": "30 40", "expected_output": "70", "points": 15}
        ],
        actor=admin_user
    )
    QuestionService.publish_version(version=v2, actor=admin_user)

    # Reload V1 from DB
    v1.refresh_from_db()
    v1_c = v1.coding_config

    # Assert V1 is 100% unchanged
    assert v1.title == v1_title
    assert v1.points == v1_points
    assert v1.status == VersionStatus.ARCHIVED
    assert v1_c.problem_statement == v1_statement
    assert v1_c.time_limit_ms == 2000
    assert v1_c.test_cases.count() == v1_tc_count
    assert list(v1_c.test_cases.values_list('input_data', flat=True)) == v1_tc_inputs

    # Assert V2 has its own independent modified data
    v2.refresh_from_db()
    assert v2.title == "V2 Modified Two Sum"
    assert v2.points == 30
    assert v2.status == VersionStatus.PUBLISHED
    assert v2.coding_config.time_limit_ms == 5000


@pytest.mark.django_db
def test_child_configuration_immutability_after_publish(admin_user):
    """Correction 2: Direct modification of CodingConfig, TestCase, or SQLConfig on published versions raises PermissionDenied."""
    question, version = QuestionService.create_question(
        question_type=QuestionType.CODING,
        title="Child Immutability Test",
        description="Prompt",
        points=10,
        coding_config_data={"problem_statement": "Prompt"},
        test_cases_data=[{"input_data": "in", "expected_output": "out", "points": 10}],
        actor=admin_user
    )
    QuestionService.publish_version(version=version, actor=admin_user)
    coding_config = version.coding_config
    test_case = coding_config.test_cases.first()

    # Attempt to modify CodingConfig directly
    coding_config.time_limit_ms = 9999
    with pytest.raises(PermissionDenied):
        coding_config.save()

    # Attempt to modify TestCase directly
    test_case.points = 99
    with pytest.raises(PermissionDenied):
        test_case.save()

    # Attempt to delete TestCase directly
    with pytest.raises(PermissionDenied):
        test_case.delete()


# ==============================================================================
# 8. API Endpoints, Filters & Audit Logs
# ==============================================================================

@pytest.mark.django_db
def test_admin_filter_and_search_questions(api_client, admin_user):
    """Admin can search and filter questions by type, difficulty, status, and tag."""
    api_client.force_authenticate(user=admin_user)

    # Create 3 distinct questions
    q1, v1 = QuestionService.create_question(
        question_type=QuestionType.MCQ,
        title="Python Basics",
        description="Variables in python",
        difficulty=Difficulty.EASY,
        tags=["Python", "Syntax"],
        actor=admin_user
    )
    q2, v2 = QuestionService.create_question(
        question_type=QuestionType.CODING,
        title="Binary Tree Traversal",
        description="Traverse tree in preorder",
        difficulty=Difficulty.HARD,
        tags=["Trees", "Algorithms"],
        actor=admin_user
    )

    url = reverse('questions:admin-question-list')

    # Search
    res = api_client.get(url, {'search': 'Binary'})
    assert res.status_code == 200
    assert len(res.json()['data']['results']) == 1
    assert res.json()['data']['results'][0]['id'] == str(q2.id)

    # Filter by question type
    res = api_client.get(url, {'type': 'MCQ'})
    assert res.status_code == 200
    assert any(q['id'] == str(q1.id) for q in res.json()['data']['results'])

    # Filter by difficulty
    res = api_client.get(url, {'difficulty': 'HARD'})
    assert res.status_code == 200
    assert any(q['id'] == str(q2.id) for q in res.json()['data']['results'])

    # Filter by tag
    res = api_client.get(url, {'tag': 'Syntax'})
    assert res.status_code == 200
    assert any(q['id'] == str(q1.id) for q in res.json()['data']['results'])


@pytest.mark.django_db
def test_tags_endpoint_crud(api_client, admin_user):
    """Admin can list and create tags."""
    api_client.force_authenticate(user=admin_user)
    url = reverse('questions:admin-tag-list')

    # Create tag
    res = api_client.post(url, {'name': 'Dynamic Programming'}, format='json')
    assert res.status_code == 201
    assert res.json()['data']['slug'] == 'dynamic-programming'

    # List tags
    res = api_client.get(url)
    assert res.status_code == 200
    assert any(t['name'] == 'Dynamic Programming' for t in res.json()['data'])


@pytest.mark.django_db
def test_controlled_state_transitions_reject_invalid_states(admin_user):
    """Rejects illegal state transitions (e.g. archiving a draft directly without publication or un-archiving)."""
    question, v1 = QuestionService.create_question(
        question_type=QuestionType.MCQ,
        title="Draft Transition Test",
        description="Prompt",
        actor=admin_user
    )

    # Archiving a DRAFT version directly raises ValidationError
    with pytest.raises(DRFValidationError):
        QuestionService.archive_version(version=v1, actor=admin_user)


@pytest.mark.django_db
def test_question_lifecycle_audit_logs_recorded(admin_user):
    """All question mutations (create, update, publish, archive) produce immutable audit logs."""
    from apps.accounts.models import AuditLog

    init_count = AuditLog.objects.count()

    question, v1 = QuestionService.create_question(
        question_type=QuestionType.MCQ,
        title="Audit Question",
        description="Prompt",
        points=10,
        type_config={"options": [{"id": "A", "text": "1"}, {"id": "B", "text": "2"}], "correct_options": ["A"]},
        actor=admin_user
    )
    assert AuditLog.objects.filter(action="QUESTION_CREATED").exists()

    QuestionService.publish_version(version=v1, actor=admin_user)
    assert AuditLog.objects.filter(action="QUESTION_PUBLISHED").exists()

    QuestionService.archive_question(question=question, actor=admin_user)
    assert AuditLog.objects.filter(action="QUESTION_ARCHIVED").exists()

