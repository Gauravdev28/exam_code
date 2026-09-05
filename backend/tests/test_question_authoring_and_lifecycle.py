import io
import pytest
from datetime import timedelta
from django.utils import timezone
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from rest_framework.exceptions import ValidationError as DRFValidationError

from apps.accounts.models import Role, AuditLog
from apps.assessments.models import (
    Assessment,
    AssessmentQuestion,
    AssessmentSnapshot,
    AssessmentStatus,
)
from apps.questions.models import (
    Question,
    QuestionVersion,
    QuestionType,
    Difficulty,
    VersionStatus,
    CodingQuestionConfig,
    TestCase,
)
from apps.questions.services import QuestionService
from apps.questions.services_ingestion import ImageQuestionExtractor
from apps.questions.serializers import QuestionVersionPublicDetailSerializer

User = get_user_model()


@pytest.fixture
def admin_user(db):
    return User.objects.create_superuser(
        email="admin_author@codeguard.local",
        password="ValidAdminPass123!",
        role=Role.ADMIN
    )


@pytest.fixture
def student_user(db):
    return User.objects.create_user(
        email="student_author@codeguard.local",
        password="ValidStudentPass123!",
        role=Role.STUDENT
    )


@pytest.fixture
def coding_question(db, admin_user):
    """Creates a sample coding question with 1 draft version and 2 test cases (1 visible, 1 hidden)."""
    q, v = QuestionService.create_question(
        question_type=QuestionType.CODING,
        title="Sum of Two Numbers",
        description="Write a program that takes two integers from standard input and prints their sum.",
        points=10,
        difficulty=Difficulty.EASY,
        actor=admin_user,
        tags=["Math", "Basics"],
        instructions="Read from stdin and write to stdout.",
        type_config={
            "admin_notes": "Hidden solution details: use direct addition without recursion.",
            "solution_notes": "Strict O(1) time complexity."
        },
        coding_config_data={
            "problem_statement": "Given two numbers a and b, output a + b.",
            "constraints": "1 <= a, b <= 10^5",
            "allowed_languages": ["PYTHON", "CPP"],
        },
        test_cases_data=[
            {
                "input_data": "5 10",
                "expected_output": "15\n",
                "points": 5,
                "is_hidden": False,
                "execution_order": 1,
            },
            {
                "input_data": "100 200",
                "expected_output": "300\n",
                "points": 5,
                "is_hidden": True,
                "execution_order": 2,
            }
        ]
    )
    return q, v


@pytest.mark.django_db
class TestQuestionAuthoringAndLifecycle:
    """Comprehensive tests for Question and QuestionVersion immutability, branching, sandbox, and deletion."""

    def test_published_version_is_permanently_immutable(self, admin_user, coding_question):
        """Published question versions cannot be modified; mutations must raise PermissionDenied."""
        q, v = coding_question
        QuestionService.publish_version(v, admin_user)
        v.refresh_from_db()
        assert v.status == VersionStatus.PUBLISHED

        # Attempting to mutate the published version must raise PermissionDenied
        with pytest.raises(PermissionDenied) as exc:
            QuestionService.update_draft_version(
                v,
                title="Mutated Title Attempt",
                description="Should never happen"
            )
        assert "cannot edit" in str(exc.value).lower() or "immutable" in str(exc.value).lower()

    def test_get_or_create_draft_version_reuses_existing_draft(self, admin_user, coding_question):
        """If a question already has a DRAFT version, get_or_create_draft_version returns it without duplication."""
        q, v1 = coding_question
        assert v1.status == VersionStatus.DRAFT

        draft, created = QuestionService.get_or_create_draft_version(q, admin_user)
        assert created is False
        assert draft.id == v1.id
        assert q.versions.count() == 1

    def test_get_or_create_draft_version_branches_new_version(self, admin_user, coding_question):
        """When only PUBLISHED versions exist, get_or_create_draft_version creates v{n+1} as DRAFT."""
        q, v1 = coding_question
        QuestionService.publish_version(v1, admin_user)
        assert q.versions.count() == 1

        v2, created = QuestionService.get_or_create_draft_version(q, admin_user)
        assert created is True
        assert v2.version_number == 2
        assert v2.status == VersionStatus.DRAFT
        assert q.versions.count() == 2

        # Verify deep copy of coding config and test cases
        assert v2.coding_config.problem_statement == v1.coding_config.problem_statement
        assert v2.coding_config.test_cases.count() == v1.coding_config.test_cases.count()

    def test_assessment_snapshots_remain_locked_across_question_branches(self, admin_user, student_user, coding_question):
        """
        Assessments lock their questions via AssessmentSnapshot.
        Subsequent branching or publishing of Question versions does not alter the historical snapshot.
        """
        q, v1 = coding_question
        QuestionService.publish_version(v1, admin_user)

        now = timezone.now()
        ass = Assessment.objects.create(
            title="Snapshot Lock Assessment",
            description="Testing snapshot immutability",
            duration_minutes=60,
            start_datetime=now - timedelta(minutes=5),
            end_datetime=now + timedelta(hours=2),
            created_by=admin_user,
            status=AssessmentStatus.DRAFT,
            passing_percentage=50.0
        )
        aq = AssessmentQuestion.objects.create(
            assessment=ass,
            question_version=v1,
            order=1,
            points=10
        )
        ass.status = AssessmentStatus.PUBLISHED
        ass.save()
        snap = AssessmentSnapshot.objects.create(
            assessment=ass,
            version_number=1,
            snapshot_data={
                "questions": [
                    {
                        "question_id": str(q.id),
                        "version_id": str(v1.id),
                        "version_number": v1.version_number,
                        "title": v1.title
                    }
                ]
            }
        )

        # Branch to v2 and publish
        v2, _ = QuestionService.get_or_create_draft_version(q, admin_user)
        QuestionService.update_draft_version(v2, title="Updated Title for V2")
        QuestionService.publish_version(v2, admin_user)

        # Verify that snapshot still strictly references v1
        snap.refresh_from_db()
        snap_q = snap.snapshot_data["questions"][0]
        assert snap_q["version_number"] == 1
        assert snap_q["title"] == "Sum of Two Numbers"
        assert snap_q["version_id"] == str(v1.id)

    def test_candidate_preview_strips_internal_notes_and_hidden_test_cases(self, coding_question):
        """Candidate / Student representation must omit internal admin notes and hidden test cases."""
        q, v = coding_question
        serializer = QuestionVersionPublicDetailSerializer(v)
        data = serializer.data

        # Internal notes in type_config must not be exposed
        assert "admin_notes" not in data
        assert "internal_notes" not in data
        assert "solution_notes" not in data

        if "type_config" in data and isinstance(data["type_config"], dict):
            assert "admin_notes" not in data["type_config"]
            assert "solution_notes" not in data["type_config"]

        # Hidden test cases must be stripped from public coding_config
        if "coding_config" in data and data["coding_config"]:
            test_cases = data["coding_config"].get("test_cases", [])
            for tc in test_cases:
                assert tc.get("is_hidden") is not True

    def test_admin_sandbox_execution_success(self, api_client, admin_user):
        """Admin can evaluate untrusted code against a test case via external Judge0 runner."""
        api_client.force_authenticate(user=admin_user)
        url = reverse('questions:admin-question-run-sandbox')

        source_code = "import sys\nparts = sys.stdin.read().split()\nprint(int(parts[0]) + int(parts[1]))"
        payload = {
            "source_code": source_code,
            "language": "PYTHON",
            "stdin": "5 10",
            "expected_output": "15\n",
            "time_limit_ms": 2000,
            "memory_limit_mb": 256
        }
        resp = api_client.post(url, payload, format='json')
        assert resp.status_code == 200
        result = resp.json()['data']

        assert result['status_description'] in ('Accepted', 'ACCEPTED')
        assert result['passed'] is True
        assert result['time'] is not None

    def test_admin_sandbox_execution_fails_closed(self, api_client, admin_user):
        """If Judge0 is unavailable, sandbox strictly fails closed (never runs in Django process)."""
        api_client.force_authenticate(user=admin_user)
        url = reverse('questions:admin-question-run-sandbox')

        payload = {
            "source_code": "__SIMULATE_SANDBOX_DOWN__",
            "language": "PYTHON",
            "stdin": "1 2",
            "expected_output": "3\n"
        }
        resp = api_client.post(url, payload, format='json')
        assert resp.status_code == 200
        result = resp.json()['data']
        assert result['status_description'] == "Sandbox Unavailable"
        assert "FAIL_CLOSED" in result['stderr']
        assert result['passed'] is not True

    def test_sandbox_forbidden_for_students(self, api_client, student_user):
        """Students cannot call the admin sandbox endpoint."""
        api_client.force_authenticate(user=student_user)
        url = reverse('questions:admin-question-run-sandbox')
        resp = api_client.post(url, {"source_code": "print(1)"}, format='json')
        assert resp.status_code == 403

    def test_unreferenced_draft_question_safe_deletion(self, api_client, admin_user, coding_question):
        """An unreferenced draft question can be hard-deleted, recording an audit log."""
        q, v = coding_question
        api_client.force_authenticate(user=admin_user)

        # Check usage endpoint returns deletable
        usage_url = reverse('questions:admin-question-usage', kwargs={'pk': q.id})
        resp = api_client.get(usage_url)
        assert resp.status_code == 200
        usage = resp.json()['data']
        assert usage['is_deletable'] is True
        assert usage['assessment_count'] == 0

        # Delete question
        delete_url = reverse('questions:admin-question-detail', kwargs={'pk': q.id})
        del_resp = api_client.delete(delete_url)
        assert del_resp.status_code == 200

        # Verify gone from database
        assert not Question.objects.filter(id=q.id).exists()

        # Verify audit log
        assert AuditLog.objects.filter(
            action="QUESTION_DELETED",
            actor=admin_user,
            target_id=str(q.id)
        ).exists()

    def test_referenced_question_deletion_is_blocked(self, api_client, admin_user, coding_question):
        """A question referenced by an assessment cannot be deleted; DELETE returns 400."""
        q, v = coding_question
        QuestionService.publish_version(v, admin_user)

        now = timezone.now()
        ass = Assessment.objects.create(
            title="Referenced Exam",
            description="Blocks deletion",
            duration_minutes=30,
            start_datetime=now,
            end_datetime=now + timedelta(hours=1),
            created_by=admin_user,
            status=AssessmentStatus.DRAFT
        )
        AssessmentQuestion.objects.create(
            assessment=ass,
            question_version=v,
            order=1,
            points=10
        )

        api_client.force_authenticate(user=admin_user)

        # Check usage
        usage_url = reverse('questions:admin-question-usage', kwargs={'pk': q.id})
        resp = api_client.get(usage_url)
        assert resp.status_code == 200
        usage = resp.json()['data']
        assert usage['is_deletable'] is False
        assert usage['assessment_count'] == 1

        # Attempt delete
        delete_url = reverse('questions:admin-question-detail', kwargs={'pk': q.id})
        del_resp = api_client.delete(delete_url)
        assert del_resp.status_code == 400
        err = del_resp.json()['error']
        assert "archive" in err['message'].lower() or "referenced" in err['message'].lower()

    def test_referenced_question_can_be_archived(self, api_client, admin_user, coding_question):
        """A question that cannot be deleted can still be safely archived."""
        q, v = coding_question
        QuestionService.publish_version(v, admin_user)

        api_client.force_authenticate(user=admin_user)
        archive_url = reverse('questions:admin-question-archive', kwargs={'pk': q.id})
        resp = api_client.post(archive_url)
        assert resp.status_code == 200

        q.refresh_from_db()
        assert q.status == "ARCHIVED"

    def test_ocr_ingestion_rejects_corrupted_image(self):
        """ImageQuestionExtractor rejects corrupt image data and invalid extensions."""
        corrupt_data = io.BytesIO(b"NOT_A_VALID_IMAGE_HEADER_DATA")
        with pytest.raises(DRFValidationError) as exc:
            ImageQuestionExtractor.validate_and_store_image(corrupt_data, "bad.png")
        assert "cannot identify image" in str(exc.value).lower() or "corrupt" in str(exc.value).lower()
