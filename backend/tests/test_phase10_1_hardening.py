import io
import json
import os
import re
import uuid
import zipfile
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
from django.core.exceptions import PermissionDenied, ImproperlyConfigured
from django.test.utils import CaptureQueriesContext
from django.db import connection
from rest_framework import status
from rest_framework.test import APIClient
import pytest

from apps.accounts.models import User, Role, StudentProfile
from apps.questions.models import (
    Question,
    QuestionVersion,
    QuestionType,
    Difficulty,
    VersionStatus,
    TestCase,
)
from apps.assessments.models import (
    Assessment,
    AssessmentStatus,
    AssessmentQuestion,
    AssessmentAssignment,
    TestAttempt,
    AttemptStatus,
    AttemptAnswer,
)
from apps.results.models import AssessmentResult, ResultStatus
from apps.assessments.services import AssessmentService, AttemptService
from apps.evaluator.models import (
    CodeSubmission,
    CodeTestCaseResult,
    SubmissionType,
    SubmissionStatus,
    CodeVerdict,
    TestCaseVerdict,
)
from apps.evaluator.services import CodeSubmissionService, Judge0Adapter
from apps.invigilation.models import (
    ProctorAssignment,
    ProctorIntervention,
    InterventionType,
    ProctorChatMessage,
)
from apps.invigilation.services import (
    LiveInterventionService,
    ProctorTriageQueueService,
    InvigilationRetentionService,
)
from apps.retention.models import (
    RetentionRecord,
    LegalHold,
    LegalHoldScope,
    PurgeState,
)
from apps.retention.services import RetentionPolicyEngine
from apps.retention.services.scrubbing import AuthoritativeScrubbingService
from apps.retention.services.dsar import DsarExportService


@pytest.fixture
def base_setup(db):
    admin = User.objects.create_superuser(
        email="harden_admin@codeguard.test",
        password="AdminPassword123!"
    )
    student = User.objects.create_user(
        email="harden_student@codeguard.test",
        password="StudentPassword123!",
        role=Role.STUDENT
    )
    profile = StudentProfile.objects.create(
        user=student,
        roll_number="HARDEN-001",
        euid="EUID-HARDEN-001",
        first_login_required=False
    )
    proctor = User.objects.create_user(
        email="harden_proctor@codeguard.test",
        password="ProctorPassword123!",
        role=Role.ADMIN,
        is_staff=True
    )

    from apps.questions.services import QuestionService
    question, q_ver = QuestionService.create_question(
        question_type=QuestionType.CODING,
        title="Sum Numbers",
        description="Add two integers",
        points=10,
        difficulty=Difficulty.EASY,
        coding_config_data={
            'allowed_languages': ['PYTHON', 'CPP'],
            'time_limit_ms': 2000,
            'memory_limit_mb': 256,
        },
        test_cases_data=[
            {
                'input_data': '5 10',
                'expected_output': '15',
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
            }
        ],
        actor=admin
    )
    q_ver = QuestionService.publish_version(q_ver, actor=admin)

    now = timezone.now()
    assessment = Assessment.objects.create(
        title="Hardening Verification Exam",
        start_datetime=now - timedelta(minutes=10),
        end_datetime=now + timedelta(hours=2),
        duration_minutes=60,
        total_points=10,
        created_by=admin
    )
    AssessmentQuestion.objects.create(
        assessment=assessment,
        question_version=q_ver,
        order=1,
        points=10
    )
    AssessmentAssignment.objects.create(
        assessment=assessment,
        student=student,
        assigned_by=admin
    )
    pub_assessment = AssessmentService.publish_assessment(assessment, actor=admin)
    ProctorAssignment.objects.create(
        proctor=proctor,
        assessment=pub_assessment,
        assigned_by=admin
    )

    attempt, _ = AttemptService.start_attempt(
        student=student,
        assessment_id=str(pub_assessment.id),
        actor=student
    )
    snap_q = attempt.assessment_snapshot.snapshot_questions.first()

    return {
        'admin': admin,
        'student': student,
        'profile': profile,
        'proctor': proctor,
        'assessment': pub_assessment,
        'attempt': attempt,
        'snap_q': snap_q,
    }


# ==============================================================================
# 1. SEC-01: Sandboxed Execution & Fail-Closed Integrity
# ==============================================================================

@pytest.mark.django_db
class TestSandboxSecurityAndFailClosed:
    """Verifies that candidate code NEVER executes inside Django/Celery."""

    def test_candidate_code_executes_only_through_external_sandbox(self, base_setup):
        student = base_setup['student']
        attempt = base_setup['attempt']
        snap_q = base_setup['snap_q']

        # Code that would alter the host environment if run in-process
        poison_code = (
            "import os\n"
            "os.environ['HOST_POISON_FLAG'] = 'PWNED'\n"
            "print('15')\n"
        )

        sub, _ = CodeSubmissionService.create_submission(
            student=student,
            attempt_id=str(attempt.id),
            question_id=str(snap_q.snapshot_question_id),
            submission_type=SubmissionType.RUN,
            source_code=poison_code,
            language='PYTHON'
        )
        evaluated = CodeSubmissionService.evaluate_submission(str(sub.id))

        # Host environment must NOT have been modified
        assert 'HOST_POISON_FLAG' not in os.environ
        assert evaluated.status == SubmissionStatus.COMPLETED

    def test_sandbox_unavailable_fails_closed(self, base_setup):
        student = base_setup['student']
        attempt = base_setup['attempt']
        snap_q = base_setup['snap_q']

        sub, _ = CodeSubmissionService.create_submission(
            student=student,
            attempt_id=str(attempt.id),
            question_id=str(snap_q.snapshot_question_id),
            submission_type=SubmissionType.RUN,
            source_code="__SIMULATE_SANDBOX_DOWN__",
            language='PYTHON'
        )
        evaluated = CodeSubmissionService.evaluate_submission(str(sub.id))

        # Must fail closed with SYSTEM_ERROR verdict and FAILED status
        assert evaluated.status == SubmissionStatus.FAILED
        assert evaluated.verdict == CodeVerdict.SYSTEM_ERROR

        tc_res = evaluated.test_case_results.first()
        assert tc_res.verdict == TestCaseVerdict.RUNTIME_ERROR
        assert "FAIL_CLOSED" in tc_res.error_message

    def test_no_in_process_exec_or_eval_in_evaluator_services(self):
        """AST audit verifying no exec() or eval() call exists in evaluator services."""
        import ast
        services_path = os.path.join(
            os.path.dirname(__file__),
            '../apps/evaluator/services.py'
        )
        with open(services_path, 'r', encoding='utf-8') as f:
            tree = ast.parse(f.read(), filename=services_path)

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    assert node.func.id not in ('exec', 'eval'), (
                        f"Forbidden call to {node.func.id}() found at line {node.lineno}"
                    )


# ==============================================================================
# 2. RET-01: Phase 10 Retention Scrubbing Integration
# ==============================================================================

@pytest.mark.django_db
class TestPhase10RetentionIntegration:
    """Verifies Phase 10 records participate in Phase 9 retention purges under strict immutability."""

    def test_direct_delete_on_interventions_raises_permission_denied(self, base_setup):
        attempt = base_setup['attempt']
        student = base_setup['student']
        proctor = base_setup['proctor']

        interv = ProctorIntervention.objects.create(
            attempt=attempt,
            student=student,
            proctor=proctor,
            event_type=InterventionType.WARNING_ISSUED,
            reason_code="MULTIPLE_FACES",
            reason_text="Candidate face not centered."
        )

        with pytest.raises(PermissionDenied):
            interv.delete()

        with pytest.raises(PermissionDenied):
            ProctorIntervention.objects.filter(id=interv.id).delete()

    def test_direct_delete_on_chat_raises_permission_denied(self, base_setup):
        attempt = base_setup['attempt']
        student = base_setup['student']
        proctor = base_setup['proctor']

        chat = ProctorChatMessage.objects.create(
            attempt=attempt,
            sender=proctor,
            recipient=student,
            message_text="Please adjust your camera."
        )

        with pytest.raises(PermissionDenied):
            chat.delete()

        with pytest.raises(PermissionDenied):
            ProctorChatMessage.objects.filter(id=chat.id).delete()

    def test_phase9_purge_scrubs_interventions_and_chats(self, base_setup):
        attempt = base_setup['attempt']
        student = base_setup['student']
        proctor = base_setup['proctor']

        ProctorIntervention.objects.create(
            attempt=attempt,
            student=student,
            proctor=proctor,
            event_type=InterventionType.WARNING_ISSUED,
            reason_code="AUDIO_NOISE",
            reason_text="Loud background noise."
        )
        ProctorChatMessage.objects.create(
            attempt=attempt,
            sender=proctor,
            recipient=student,
            message_text="Please remain silent."
        )

        attempt.status = AttemptStatus.SUBMITTED
        attempt.submitted_at = timezone.now()
        attempt.save(update_fields=['status', 'submitted_at'])

        AssessmentResult.objects.create(
            attempt=attempt,
            student=student,
            assessment=attempt.assessment,
            assessment_snapshot=attempt.assessment_snapshot,
            status=ResultStatus.FINALIZED,
            total_score_earned=Decimal('10.00'),
            total_possible_score=Decimal('10.00'),
            percentage=Decimal('100.00'),
            is_passed=True,
            finalized_at=timezone.now()
        )

        ret_record = RetentionPolicyEngine.create_retention_record_for_finalized_attempt(attempt)
        ret_record.detailed_data_expires_at = timezone.now() - timedelta(days=1)
        ret_record.save(update_fields=['detailed_data_expires_at'])

        summary = AuthoritativeScrubbingService.execute_purge_for_attempt(attempt.id)
        assert summary['status'] == 'SUCCESS'
        assert summary['purged'] is True
        assert summary['interventions_deleted'] >= 1
        assert summary['chat_deleted'] >= 1

        assert ProctorIntervention.objects.filter(attempt=attempt).count() == 0
        assert ProctorChatMessage.objects.filter(attempt=attempt).count() == 0

    def test_legal_hold_protects_phase10_records_from_purge(self, base_setup):
        attempt = base_setup['attempt']
        student = base_setup['student']
        proctor = base_setup['proctor']
        admin = base_setup['admin']

        ProctorIntervention.objects.create(
            attempt=attempt,
            student=student,
            proctor=proctor,
            event_type=InterventionType.WARNING_ISSUED,
            reason_code="DISQUALIFICATION_CAUSE",
            reason_text="Unauthorized aids."
        )
        ProctorChatMessage.objects.create(
            attempt=attempt,
            sender=proctor,
            recipient=student,
            message_text="Exam suspended."
        )

        LegalHold.objects.create(
            scope=LegalHoldScope.ATTEMPT,
            attempt=attempt,
            title="Integrity Investigation",
            case_reference="CASE-HOLD-001",
            reason="Investigation pending",
            placed_by=admin
        )

        attempt.status = AttemptStatus.SUBMITTED
        attempt.submitted_at = timezone.now()
        attempt.save(update_fields=['status', 'submitted_at'])

        AssessmentResult.objects.create(
            attempt=attempt,
            student=student,
            assessment=attempt.assessment,
            assessment_snapshot=attempt.assessment_snapshot,
            status=ResultStatus.FINALIZED,
            total_score_earned=Decimal('10.00'),
            total_possible_score=Decimal('10.00'),
            percentage=Decimal('100.00'),
            is_passed=True,
            finalized_at=timezone.now()
        )

        ret_record = RetentionPolicyEngine.create_retention_record_for_finalized_attempt(attempt)
        ret_record.detailed_data_expires_at = timezone.now() - timedelta(days=1)
        ret_record.save(update_fields=['detailed_data_expires_at'])

        summary = AuthoritativeScrubbingService.execute_purge_for_attempt(attempt.id)
        assert summary['purged'] is False
        assert summary['status'] == 'DEFERRED_HOLD'

        # Records must survive
        assert ProctorIntervention.objects.filter(attempt=attempt).count() == 1
        assert ProctorChatMessage.objects.filter(attempt=attempt).count() == 1


# ==============================================================================
# 3. RET-02: Phase 10 DSAR Inclusion & Redaction
# ==============================================================================

@pytest.mark.django_db
class TestPhase10DSARIntegration:
    """Verifies that student-visible Phase 10 records are included in DSAR while redacting internal notes."""

    def test_dsar_payload_includes_candidate_interventions_and_redacts_internal_notes(self, base_setup):
        attempt = base_setup['attempt']
        student = base_setup['student']
        proctor = base_setup['proctor']

        ProctorIntervention.objects.create(
            attempt=attempt,
            student=student,
            proctor=proctor,
            event_type=InterventionType.WARNING_ISSUED,
            reason_code="LOOKING_AWAY",
            reason_text="Please focus on your screen.",
            internal_notes="INTERNAL_SECRET: Candidate glanced at smart watch repeatedly."
        )
        ProctorChatMessage.objects.create(
            attempt=attempt,
            sender=student,
            recipient=proctor,
            message_text="My screen glitched."
        )
        ProctorChatMessage.objects.create(
            attempt=attempt,
            sender=proctor,
            recipient=student,
            message_text="Understood, continue your exam."
        )

        payload = DsarExportService.materialize_allowlisted_payload(attempt)

        assert 'candidate_interventions' in payload
        assert len(payload['candidate_interventions']) == 1
        interv_data = payload['candidate_interventions'][0]
        assert interv_data['reason_text'] == "Please focus on your screen."
        assert 'internal_notes' not in interv_data
        assert 'INTERNAL_SECRET' not in json.dumps(payload)

        # Proctor email / user ID must be redacted
        assert 'chat_messages' in payload
        assert len(payload['chat_messages']) == 2
        for msg in payload['chat_messages']:
            assert proctor.email not in json.dumps(msg)
            assert str(proctor.id) not in json.dumps(msg)
            assert msg['sender_type'] in ['CANDIDATE', 'PROCTOR']


# ==============================================================================
# 4. SEC-02: First-Login Server-Side Enforcement
# ==============================================================================

@pytest.mark.django_db
class TestFirstLoginSecurityEnforcement:
    """Verifies that direct API access to assessments is blocked when first_login_required=True."""

    def test_first_login_required_blocks_assessment_start_and_detail(self, base_setup):
        student = base_setup['student']
        profile = base_setup['profile']
        assessment = base_setup['assessment']
        attempt = base_setup['attempt']
        snap_q = base_setup['snap_q']

        # Enforce temporary password state
        profile.first_login_required = True
        profile.save(update_fields=['first_login_required'])

        client = APIClient()
        client.force_authenticate(user=student)

        # 1. Assessment List
        res = client.get('/api/v1/student/assessments/')
        assert res.status_code == status.HTTP_403_FORBIDDEN
        assert res.data.get('error', {}).get('code') == 'PERMISSION_DENIED'
        assert 'Initial password change is mandatory' in res.data.get('error', {}).get('message', '')

        # 2. Assessment Detail
        res = client.get(f'/api/v1/student/assessments/{assessment.id}/')
        assert res.status_code == status.HTTP_403_FORBIDDEN

        # 3. Assessment Start
        res = client.post(f'/api/v1/student/assessments/{assessment.id}/start/')
        assert res.status_code == status.HTTP_403_FORBIDDEN

        # 4. Attempt Detail
        res = client.get(f'/api/v1/student/attempts/{attempt.id}/')
        assert res.status_code == status.HTTP_403_FORBIDDEN

        # 5. Save Answer
        res = client.post(
            f'/api/v1/student/attempts/{attempt.id}/answers/{snap_q.snapshot_question_id}/',
            data={'code_response': 'print(1)'},
            format='json'
        )
        assert res.status_code == status.HTTP_403_FORBIDDEN

        # 6. Submit Attempt
        res = client.post(f'/api/v1/student/attempts/{attempt.id}/submit/')
        assert res.status_code == status.HTTP_403_FORBIDDEN

        # 7. Code Run
        res = client.post(
            f'/api/v1/student/attempts/{attempt.id}/questions/{snap_q.snapshot_question_id}/run/',
            data={'source_code': 'print(1)', 'language': 'PYTHON'},
            format='json'
        )
        assert res.status_code == status.HTTP_403_FORBIDDEN

        # Now satisfy first-login requirement (password reset)
        profile.first_login_required = False
        profile.save(update_fields=['first_login_required'])

        res = client.get('/api/v1/student/assessments/')
        assert res.status_code == status.HTTP_200_OK


# ==============================================================================
# 5. SEC-03: Production DSAR Master Key Fail-Closed
# ==============================================================================

class TestProductionDSARKeyConfiguration:
    """Verifies that production settings fail-fast if DSAR_MASTER_KEY_V1 is missing or insecure."""

    def test_production_fails_when_dsar_key_missing(self, monkeypatch):
        monkeypatch.delenv('DSAR_MASTER_KEY_V1', raising=False)
        with pytest.raises(ImproperlyConfigured, match="mandatory in production"):
            import importlib
            import codeguard.settings.production as prod_settings
            importlib.reload(prod_settings)

    def test_production_fails_when_dsar_key_is_dev_default(self, monkeypatch):
        monkeypatch.setenv('DSAR_MASTER_KEY_V1', '0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef')
        with pytest.raises(ImproperlyConfigured, match="cannot use the insecure development default"):
            import importlib
            import codeguard.settings.production as prod_settings
            importlib.reload(prod_settings)

    def test_production_fails_when_dsar_key_has_invalid_hex_format(self, monkeypatch):
        monkeypatch.setenv('DSAR_MASTER_KEY_V1', 'not_a_valid_hex_key_32_bytes')
        with pytest.raises(ImproperlyConfigured, match="valid 64-character hexadecimal"):
            import importlib
            import codeguard.settings.production as prod_settings
            importlib.reload(prod_settings)

    def test_production_succeeds_with_valid_key(self, monkeypatch):
        valid_key = 'abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789'
        monkeypatch.setenv('DSAR_MASTER_KEY_V1', valid_key)
        import importlib
        import codeguard.settings.production as prod_settings
        reloaded = importlib.reload(prod_settings)
        assert reloaded.v1_key_clean == valid_key


# ==============================================================================
# 6. PERF-01: Phase 10 Triage Batch Query Verification
# ==============================================================================

@pytest.mark.django_db
class TestTriagePerformanceQueryCount:
    """Verifies that ProctorTriageQueueService.get_triage_roster executes constant queries."""

    def test_triage_query_count_is_constant_with_multiple_candidates(self, base_setup):
        assessment = base_setup['assessment']
        admin = base_setup['admin']

        # Create 5 additional students with attempts
        for i in range(2, 7):
            std = User.objects.create_user(
                email=f"perf_student_{i}@codeguard.test",
                password="StudentPassword123!",
                role=Role.STUDENT
            )
            StudentProfile.objects.create(
                user=std,
                roll_number=f"PERF-{i:03d}",
                euid=f"EUID-PERF-{i:03d}",
                first_login_required=False
            )
            AssessmentAssignment.objects.create(
                assessment=assessment,
                student=std,
                assigned_by=admin
            )
            att, _ = AttemptService.start_attempt(
                student=std,
                assessment_id=str(assessment.id),
                actor=std
            )
            # Add a pause for every alternate attempt
            if i % 2 == 0:
                ProctorIntervention.objects.create(
                    attempt=att,
                    student=std,
                    proctor=base_setup['proctor'],
                    event_type=InterventionType.PAUSE_STARTED,
                    reason_code="MANUAL_REVIEW"
                )

        # Count queries during triage roster retrieval
        with CaptureQueriesContext(connection) as ctx:
            roster = ProctorTriageQueueService.get_triage_roster(str(assessment.id))

        assert len(roster) >= 6
        # Assessment + Attempts + ProctoringSessions + ProctorInterventions = 4 queries!
        assert len(ctx.captured_queries) <= 6, (
            f"Expected <= 6 bulk queries for triage queue, got {len(ctx.captured_queries)}"
        )
