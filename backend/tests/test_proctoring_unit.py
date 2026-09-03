import pytest
import math
from datetime import timedelta
from decimal import Decimal
from django.utils import timezone
from apps.accounts.models import User, Role
from apps.assessments.models import Assessment, AssessmentStatus, TestAttempt, AttemptStatus
from apps.proctoring.models import (
    ProctoringSession,
    ProctoringSessionStatus,
    ProctoringEvent,
    ProctoringEvidence,
    ProctoringWarning,
    RiskBand,
    ReviewStatus,
    EventSource,
    EventSeverity,
)
from apps.proctoring.policies import (
    PROCTORING_INFERENCE_POLICY_V1,
    PROCTORING_AUDIO_POLICY_V1,
    EVENT_FAMILY_CAPS,
)
from apps.proctoring.services import (
    ProctoringSessionService,
    ProctoringRiskService,
    ProctoringWarningService,
    ProctoringEvidenceService,
    set_cache_val,
)


@pytest.mark.django_db
class TestProctoringUnit:
    @pytest.fixture(autouse=True)
    def setup_data(self):
        self.student = User.objects.create_user(
            email="stu_proct_unit@example.com",
            password="Password123!",
            role=Role.STUDENT,
        )
        self.admin = User.objects.create_user(
            email="admin_proct_unit@example.com",
            password="Password123!",
            role=Role.ADMIN,
        )
        from apps.questions.services import QuestionService
        from apps.assessments.services import AssessmentService, AttemptService
        from apps.assessments.models import AssessmentQuestion, AssessmentAssignment

        self.question, self.q_v1 = QuestionService.create_question(
            question_type='MCQ',
            title='Sample Question',
            description='Question for proctoring test',
            points=100,
            type_config={'options': [{'id': 'A', 'text': 'Opt A'}, {'id': 'B', 'text': 'Opt B'}], 'correct_options': ['A']},
            actor=self.admin
        )
        self.q_v1 = QuestionService.publish_version(self.q_v1, actor=self.admin)

        now = timezone.now()
        self.assessment = Assessment.objects.create(
            title="Proctoring Unit Assessment",
            description="Testing proctoring unit logic",
            created_by=self.admin,
            status=AssessmentStatus.DRAFT,
            start_datetime=now - timedelta(hours=1),
            end_datetime=now + timedelta(hours=2),
            duration_minutes=60,
            total_points=100
        )
        AssessmentQuestion.objects.create(
            assessment=self.assessment,
            question_version=self.q_v1,
            order=1,
            points=100
        )
        AssessmentAssignment.objects.create(
            assessment=self.assessment,
            student=self.student,
            assigned_by=self.admin
        )
        self.published_assessment = AssessmentService.publish_assessment(self.assessment, actor=self.admin)

        self.attempt, _ = AttemptService.start_attempt(
            student=self.student,
            assessment_id=str(self.published_assessment.id),
            actor=self.student
        )

    def test_session_lifecycle(self):
        session = ProctoringSessionService.start_session(self.attempt)
        assert session.status == ProctoringSessionStatus.ACTIVE
        assert session.risk_score == Decimal('0.00')
        assert session.risk_band == RiskBand.NORMAL
        assert session.review_status == ReviewStatus.UNREVIEWED

        # Heartbeat updates session
        ProctoringSessionService.record_heartbeat(session)
        assert session.updated_at is not None

        # Degrade session
        ProctoringSessionService.degrade_session(session, reason="Camera disconnected")
        session.refresh_from_db()
        assert session.status == ProctoringSessionStatus.DEGRADED
        # System event recorded with zero risk delta
        degrade_event = ProctoringEvent.objects.filter(session=session, event_type='PROCTORING_DEGRADED').first()
        assert degrade_event is not None
        assert degrade_event.risk_delta == Decimal('0.00')
        assert session.risk_score == Decimal('0.00')

    def test_risk_score_bands(self):
        assert ProctoringRiskService.determine_risk_band(Decimal('0.00')) == RiskBand.NORMAL
        assert ProctoringRiskService.determine_risk_band(Decimal('20.00')) == RiskBand.NORMAL
        assert ProctoringRiskService.determine_risk_band(Decimal('20.01')) == RiskBand.LOW
        assert ProctoringRiskService.determine_risk_band(Decimal('40.00')) == RiskBand.LOW
        assert ProctoringRiskService.determine_risk_band(Decimal('40.01')) == RiskBand.MEDIUM
        assert ProctoringRiskService.determine_risk_band(Decimal('60.00')) == RiskBand.MEDIUM
        assert ProctoringRiskService.determine_risk_band(Decimal('60.01')) == RiskBand.HIGH
        assert ProctoringRiskService.determine_risk_band(Decimal('80.00')) == RiskBand.HIGH
        assert ProctoringRiskService.determine_risk_band(Decimal('80.01')) == RiskBand.CRITICAL
        assert ProctoringRiskService.determine_risk_band(Decimal('100.00')) == RiskBand.CRITICAL

    def test_deterministic_time_decay_formula(self):
        session = ProctoringSessionService.start_session(self.attempt)
        now = timezone.now()

        # Create an event with delta 40.0 that occurred 600 seconds ago (10 minutes = 1 half-life)
        event = ProctoringEvent.objects.create(
            session=session,
            event_type='PHONE_DETECTED',
            source=EventSource.AI,
            severity=EventSeverity.CRITICAL,
            confidence=0.90,
            started_at=now - timedelta(seconds=600),
            risk_delta=Decimal('40.00')
        )
        ProctoringEvent.objects.filter(id=event.id).update(server_received_at=now - timedelta(seconds=600))

        score, band = ProctoringRiskService.calculate_session_risk(session, now=now)
        # Expected: 40 * exp(-0.001155 * 600) = 40 * 0.500072... ≈ 20.00
        expected_decay = Decimal(str(40.0 * math.exp(-0.001155 * 600)))
        assert abs(score - expected_decay) < Decimal('0.50')

    def test_event_family_contribution_caps(self):
        session = ProctoringSessionService.start_session(self.attempt)
        now = timezone.now()

        # Add 10 TAB_SWITCH events (base delta 8.0 each -> 80.0 uncapped)
        # Focus Loss cap is 40.0
        for i in range(10):
            ev = ProctoringEvent.objects.create(
                session=session,
                event_type='TAB_SWITCH',
                source=EventSource.BROWSER,
                severity=EventSeverity.LOW,
                started_at=now - timedelta(seconds=i * 2),
                risk_delta=Decimal('8.00')
            )
            ProctoringEvent.objects.filter(id=ev.id).update(server_received_at=now - timedelta(seconds=i * 2))

        score, band = ProctoringRiskService.calculate_session_risk(session, now=now)
        # Focus loss family contribution must be capped at 40.00
        assert score <= EVENT_FAMILY_CAPS['FOCUS_LOSS']
        assert score == Decimal('40.00')

    def test_multi_signal_correlation_logic(self):
        session = ProctoringSessionService.start_session(self.attempt)
        now = timezone.now()

        # Case 1: Multiple events from the SAME family (Focus Loss) -> 1 family -> NO correlation bonus
        ev1 = ProctoringEvent.objects.create(
            session=session,
            event_type='TAB_SWITCH',
            source=EventSource.BROWSER,
            started_at=now - timedelta(seconds=10),
            risk_delta=Decimal('8.00')
        )
        ProctoringEvent.objects.filter(id=ev1.id).update(server_received_at=now - timedelta(seconds=10))

        ev2 = ProctoringEvent.objects.create(
            session=session,
            event_type='FULLSCREEN_EXIT',
            source=EventSource.BROWSER,
            started_at=now - timedelta(seconds=5),
            risk_delta=Decimal('10.00')
        )
        ProctoringEvent.objects.filter(id=ev2.id).update(server_received_at=now - timedelta(seconds=5))

        score_single_family, _ = ProctoringRiskService.calculate_session_risk(session, now=now)
        # 8 + 10 = 18.00 (no correlation bonus)
        assert score_single_family < Decimal('20.00')

        # Case 2: Add an event from a DISTINCT second family (Unauthorized Device) within 60s window
        ev3 = ProctoringEvent.objects.create(
            session=session,
            event_type='PHONE_DETECTED',
            source=EventSource.AI,
            started_at=now - timedelta(seconds=2),
            risk_delta=Decimal('40.00')
        )
        ProctoringEvent.objects.filter(id=ev3.id).update(server_received_at=now - timedelta(seconds=2))

        score_multi_family, band_multi = ProctoringRiskService.calculate_session_risk(session, now=now)
        # Contributions: Focus Loss (~18.0) + Phone (~40.0) + Correlation Bonus (+15.0) = ~73.0 (HIGH)
        assert score_multi_family >= Decimal('70.00')
        assert band_multi in [RiskBand.HIGH, RiskBand.CRITICAL]

    def test_ai_persistence_gate_requirement(self):
        session = ProctoringSessionService.start_session(self.attempt)
        session_id = str(session.id)

        # First frame detection -> count = 1 -> Gate returns False (Not persistent)
        assert ProctoringRiskService.check_persistence_gate(session_id, 'PHONE_DETECTED', 0.85) is False

        # Second frame detection within window -> count = 2 -> Gate returns True (Persistent)
        assert ProctoringRiskService.check_persistence_gate(session_id, 'PHONE_DETECTED', 0.85) is True

        # Low confidence -> Gate returns False regardless of count
        assert ProctoringRiskService.check_persistence_gate(session_id, 'PHONE_DETECTED', 0.40) is False

    def test_versioned_policy_contracts(self):
        inf_policy = PROCTORING_INFERENCE_POLICY_V1
        assert inf_policy['phone_confidence_threshold'] == 0.65
        assert inf_policy['multiple_face_confidence_threshold'] == 0.60
        assert inf_policy['required_persistent_frames'] == 2
        assert inf_policy['persistence_window_seconds'] == 4.0

        aud_policy = PROCTORING_AUDIO_POLICY_V1
        assert aud_policy['client_trigger_threshold_db'] == 65.0
        assert aud_policy['clip_duration_seconds'] == 2.0
        assert aud_policy['maximum_clip_size_bytes'] == 102400
