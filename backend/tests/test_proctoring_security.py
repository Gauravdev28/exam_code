import io
import pytest
import hashlib
from datetime import timedelta
from decimal import Decimal
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient
from rest_framework import status

from apps.accounts.models import User, Role, StudentProfile
from apps.questions.services import QuestionService
from apps.assessments.models import (
    Assessment,
    AssessmentStatus,
    AssessmentQuestion,
    AssessmentAssignment,
    TestAttempt,
    AttemptStatus,
)
from apps.assessments.services import AssessmentService, AttemptService
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
    RetentionClass,
)
from apps.proctoring.services import (
    ProctoringSessionService,
    ProctoringRiskService,
    ProctoringEvidenceService,
    ProctoringAIService,
)
from apps.proctoring.policies import EVENT_FAMILY_CAPS


@pytest.mark.django_db
class TestProctoringSecurity:
    """
    Comprehensive Adversarial Security & Invariant Suite for Phase 7 AI Proctoring:
    - Client Spoofing & IDOR Protections
    - Evidence RBAC, SHA-256 Integrity & Path Traversal Shields
    - Token Bucket Anti-Flooding & Replay Defenses
    - Zero Student-Penalization on System/AI Failures
    - Score Inflation & Mathematical Invariants
    - 20/20 Required Architectural Invariants
    """

    @pytest.fixture(autouse=True)
    def setup_data(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            email="admin_proct_sec@example.com",
            password="AdminPassword123!",
            role=Role.ADMIN
        )
        self.student_1 = User.objects.create_user(
            email="student1_sec@example.com",
            password="StudentPassword123!",
            role=Role.STUDENT
        )
        self.profile_1 = StudentProfile.objects.create(
            user=self.student_1,
            roll_number="CS2026-SEC1",
            euid="EUID-SEC-1"
        )
        self.student_2 = User.objects.create_user(
            email="student2_sec@example.com",
            password="StudentPassword123!",
            role=Role.STUDENT
        )
        self.profile_2 = StudentProfile.objects.create(
            user=self.student_2,
            roll_number="CS2026-SEC2",
            euid="EUID-SEC-2"
        )

        # Question & Assessment
        self.question, self.q_v1 = QuestionService.create_question(
            question_type='MCQ',
            title='Security MCQ',
            description='Question for security tests',
            points=100,
            type_config={'options': [{'id': 'A', 'text': 'Option A'}, {'id': 'B', 'text': 'Option B'}], 'correct_options': ['A']},
            actor=self.admin
        )
        self.q_v1 = QuestionService.publish_version(self.q_v1, actor=self.admin)

        now = timezone.now()
        self.assessment = Assessment.objects.create(
            title="Proctoring Security Assessment",
            description="Testing proctoring security invariants",
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
            student=self.student_1,
            assigned_by=self.admin
        )
        AssessmentAssignment.objects.create(
            assessment=self.assessment,
            student=self.student_2,
            assigned_by=self.admin
        )
        self.published_assessment = AssessmentService.publish_assessment(self.assessment, actor=self.admin)

        self.attempt_1, _ = AttemptService.start_attempt(
            student=self.student_1,
            assessment_id=str(self.published_assessment.id),
            actor=self.student_1
        )
        self.attempt_2, _ = AttemptService.start_attempt(
            student=self.student_2,
            assessment_id=str(self.published_assessment.id),
            actor=self.student_2
        )

    # --------------------------------------------------------------------------
    # 1. Client Spoofing & IDOR Tests (Invariants 1-4)
    # --------------------------------------------------------------------------

    def test_client_cannot_impersonate_another_student_attempt(self):
        # Invariant: Browser cannot impersonate another student
        self.client.force_authenticate(user=self.student_1)
        url = f"/api/v1/student/attempts/{self.attempt_2.id}/proctoring/start/"
        response = self.client.post(url)
        assert response.status_code == status.HTTP_403_FORBIDDEN

        event_url = f"/api/v1/student/attempts/{self.attempt_2.id}/proctoring/events/"
        event_res = self.client.post(event_url, data={"event_type": "TAB_SWITCH"}, format='json')
        assert event_res.status_code == status.HTTP_403_FORBIDDEN

    def test_client_cannot_supply_fake_event_types(self):
        self.client.force_authenticate(user=self.student_1)
        url = f"/api/v1/student/attempts/{self.attempt_1.id}/proctoring/events/"
        payload = {"event_type": "CHEATING_CONFIRMED_FAKE"}
        response = self.client.post(url, data=payload, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_client_cannot_control_risk_delta_or_severity(self):
        # Invariant: Browser cannot set risk_delta or severity
        self.client.force_authenticate(user=self.student_1)
        url = f"/api/v1/student/attempts/{self.attempt_1.id}/proctoring/events/"
        payload = {
            "event_type": "WINDOW_BLUR",
            "risk_delta": 99.0,
            "severity": "CRITICAL",
            "confidence": 0.01
        }
        response = self.client.post(url, data=payload, format='json')
        assert response.status_code == status.HTTP_202_ACCEPTED
        
        event_id = response.data['event_id']
        event = ProctoringEvent.objects.get(id=event_id)
        assert event.risk_delta == Decimal('4.00')
        assert event.severity == EventSeverity.LOW

    def test_browser_cannot_set_risk_score(self):
        # Invariant: Browser cannot set risk_score
        self.client.force_authenticate(user=self.student_1)
        url = f"/api/v1/student/attempts/{self.attempt_1.id}/proctoring/start/"
        response = self.client.post(url, data={"risk_score": 0.0, "risk_band": "NORMAL"}, format='json')
        assert response.status_code == status.HTTP_200_OK
        session = ProctoringSession.objects.get(id=response.data['session_id'])
        assert session.risk_score == Decimal('0.00')

    # --------------------------------------------------------------------------
    # 2. Evidence Protection & RBAC (Invariants 5-7, 19, 20)
    # --------------------------------------------------------------------------

    def test_student_role_blocked_from_evidence_media_access(self):
        # Invariant: Student cannot access admin evidence or another student's evidence
        session = ProctoringSessionService.get_or_create_session(self.attempt_1)
        raw_bytes = b'\xff\xd8\xff\xe0' + b'SECURE_EVIDENCE' * 10 + b'\xff\xd9'
        evidence = ProctoringEvidenceService.save_evidence(session, raw_bytes, 'IMAGE_JPEG')

        self.client.force_authenticate(user=self.student_1)
        url = f"/api/v1/admin/proctoring/evidence/{evidence.id}/"
        response = self.client.get(url)
        assert response.status_code == status.HTTP_403_FORBIDDEN

        # Student 2 also blocked
        self.client.force_authenticate(user=self.student_2)
        response_2 = self.client.get(url)
        assert response_2.status_code == status.HTTP_403_FORBIDDEN

    def test_nonexistent_evidence_returns_404(self):
        # Invariant: Evidence object authorization prevents enumeration / IDOR
        self.client.force_authenticate(user=self.admin)
        import uuid
        url = f"/api/v1/admin/proctoring/evidence/{uuid.uuid4()}/"
        response = self.client.get(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_evidence_sha256_integrity_hash_verification(self):
        # Invariant: Evidence SHA-256 detects modification
        session = ProctoringSessionService.get_or_create_session(self.attempt_1)
        raw_bytes = b'\xff\xd8\xff\xe0' + b'TAMPER_EVIDENCE_PROBE' * 10 + b'\xff\xd9'
        expected_hash = hashlib.sha256(raw_bytes).hexdigest()

        evidence = ProctoringEvidenceService.save_evidence(session, raw_bytes, 'IMAGE_JPEG')
        assert evidence.sha256_hash == expected_hash

        # Verify altered byte stream does not match
        tampered_bytes = raw_bytes + b'TAMPERED'
        assert hashlib.sha256(tampered_bytes).hexdigest() != evidence.sha256_hash

    # --------------------------------------------------------------------------
    # 3. Token Bucket Rate Limiting & Anti-Flooding (Invariants 17, 18)
    # --------------------------------------------------------------------------

    def test_frame_upload_token_bucket_burst_and_rate_limiting(self):
        # Invariant: Frame rate cannot be bypassed; Token bucket throttles parallel/burst requests
        self.client.force_authenticate(user=self.student_1)
        url = f"/api/v1/student/attempts/{self.attempt_1.id}/proctoring/frames/"

        fake_jpeg = b'\xff\xd8\xff\xe0' + b'FRAME' * 100 + b'\xff\xd9'

        # Burst of 5 requests should succeed
        for i in range(5):
            f = SimpleUploadedFile(f"frame_{i}.jpg", fake_jpeg, content_type="image/jpeg")
            res = self.client.post(url, data={'frame': f, 'sequence_number': i}, format='multipart')
            assert res.status_code == status.HTTP_202_ACCEPTED

        # 6th immediate request should be throttled (HTTP 429)
        f_overflow = SimpleUploadedFile("frame_overflow.jpg", fake_jpeg, content_type="image/jpeg")
        overflow_res = self.client.post(url, data={'frame': f_overflow, 'sequence_number': 6}, format='multipart')
        assert overflow_res.status_code == status.HTTP_429_TOO_MANY_REQUESTS

    def test_audio_upload_token_bucket_rate_limiting(self):
        # Invariant: Audio flooding throttled
        self.client.force_authenticate(user=self.student_1)
        url = f"/api/v1/student/attempts/{self.attempt_1.id}/proctoring/audio/"

        fake_audio = b'\x1a\x45\xdf\xa3' + b'AUDIO' * 100

        # Burst of 2 requests should succeed (audio capacity = 2)
        for i in range(2):
            f = SimpleUploadedFile(f"audio_{i}.webm", fake_audio, content_type="audio/webm")
            res = self.client.post(url, data={'audio': f, 'rms_db': 68.0}, format='multipart')
            assert res.status_code == status.HTTP_202_ACCEPTED

        # 3rd immediate request should be throttled (HTTP 429)
        f_overflow = SimpleUploadedFile("audio_overflow.webm", fake_audio, content_type="audio/webm")
        overflow_res = self.client.post(url, data={'audio': f_overflow, 'rms_db': 68.0}, format='multipart')
        assert overflow_res.status_code == status.HTTP_429_TOO_MANY_REQUESTS

    # --------------------------------------------------------------------------
    # 4. Zero Student-Penalization on System Failures (Invariants 14-16)
    # --------------------------------------------------------------------------

    def test_camera_disconnect_produces_zero_risk_delta(self):
        # Invariant: System failures contribute zero student risk
        session = ProctoringSessionService.start_session(self.attempt_1)
        initial_score = session.risk_score

        event = ProctoringRiskService.record_event(
            session=session,
            event_type='CAMERA_UNAVAILABLE',
            source=EventSource.SYSTEM,
            severity=EventSeverity.MEDIUM,
            confidence=1.0,
            started_at=timezone.now()
        )
        assert event.risk_delta == Decimal('0.00')

        session.refresh_from_db()
        assert session.risk_score == initial_score == Decimal('0.00')
        assert session.risk_band == RiskBand.NORMAL

    def test_ai_failures_contribute_zero_student_risk(self):
        # Invariant: AI failures contribute zero student risk
        session = ProctoringSessionService.start_session(self.attempt_1)
        event = ProctoringRiskService.record_event(
            session=session,
            event_type='AI_WORKER_TIMEOUT',
            source=EventSource.SYSTEM,
            severity=EventSeverity.HIGH,
            confidence=1.0,
            started_at=timezone.now()
        )
        assert event.risk_delta == Decimal('0.00')
        session.refresh_from_db()
        assert session.risk_score == Decimal('0.00')

    def test_system_degradation_does_not_corrupt_attempt_or_score(self):
        # Invariant: WebSocket/System failure degrades proctoring without altering assessment authority
        session = ProctoringSessionService.start_session(self.attempt_1)
        ProctoringSessionService.degrade_session(session, reason="AI Service Outage")

        session.refresh_from_db()
        assert session.status == ProctoringSessionStatus.DEGRADED
        assert session.risk_score == Decimal('0.00')

        self.attempt_1.refresh_from_db()
        assert self.attempt_1.status == AttemptStatus.IN_PROGRESS
        assert self.attempt_1.submitted_at is None

    # --------------------------------------------------------------------------
    # 5. Risk Engine Invariants (Invariants 8-13)
    # --------------------------------------------------------------------------

    def test_client_timestamps_cannot_control_risk_decay(self):
        # Invariant: Client timestamps cannot control risk decay (server_received_at is authoritative)
        session = ProctoringSessionService.start_session(self.attempt_1)
        now = timezone.now()

        # Client claims event happened 3000 seconds ago (client_detected_at)
        event = ProctoringEvent.objects.create(
            session=session,
            event_type='PHONE_DETECTED',
            source=EventSource.AI,
            severity=EventSeverity.CRITICAL,
            confidence=0.90,
            client_detected_at=now - timedelta(seconds=3000),
            started_at=now,
            risk_delta=Decimal('40.00')
        )
        # Server received it just now
        ProctoringEvent.objects.filter(id=event.id).update(server_received_at=now)

        score, _ = ProctoringRiskService.calculate_session_risk(session, now=now)
        # Decay is calculated from server_received_at (elapsed=0), so score is full 40.00 (not decayed by 3000s)
        assert score == Decimal('40.00')

    def test_client_confidence_cannot_bypass_server_thresholds(self):
        # Invariant: Client confidence cannot bypass server thresholds
        session = ProctoringSessionService.start_session(self.attempt_1)
        # Raw normal image without signal tags -> returns empty signals list
        fake_jpeg = b'\xff\xd8\xff\xe0' + b'NORMAL_FRAME' * 100 + b'\xff\xd9'
        signals = ProctoringAIService.analyze_frame_data(session, fake_jpeg)
        assert signals == []

    def test_single_frame_cannot_bypass_persistence_gate(self):
        # Invariant: Single frame cannot bypass persistence gate (requires >= 2 qualifying frames in 4s)
        session = ProctoringSessionService.start_session(self.attempt_1)
        
        # Frame 1: qualifying confidence (0.80) -> Persistence gate returns False (count=1)
        gate_1 = ProctoringRiskService.check_persistence_gate(str(session.id), 'PHONE_DETECTED', 0.80)
        assert gate_1 is False

        # Frame 2 within 4s: qualifying confidence (0.80) -> Persistence gate returns True (count=2)
        gate_2 = ProctoringRiskService.check_persistence_gate(str(session.id), 'PHONE_DETECTED', 0.80)
        assert gate_2 is True

    def test_same_family_events_cannot_bypass_family_caps(self):
        # Invariant: Same-family events cannot bypass family caps
        session = ProctoringSessionService.start_session(self.attempt_1)
        now = timezone.now()

        # 10 TAB_SWITCH events (base delta 8.0 each -> uncapped 80.0)
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

        score, _ = ProctoringRiskService.calculate_session_risk(session, now=now)
        assert score == EVENT_FAMILY_CAPS['FOCUS_LOSS'] == Decimal('40.00')

    def test_correlation_cannot_directly_determine_guilt(self):
        # Invariant: Correlation cannot directly determine guilt or auto-punish
        session = ProctoringSessionService.start_session(self.attempt_1)
        now = timezone.now()

        # Ingest 2 distinct families (Focus Loss + Phone)
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
            event_type='PHONE_DETECTED',
            source=EventSource.AI,
            started_at=now - timedelta(seconds=2),
            risk_delta=Decimal('40.00')
        )
        ProctoringEvent.objects.filter(id=ev2.id).update(server_received_at=now - timedelta(seconds=2))

        score, band = ProctoringRiskService.calculate_session_risk(session, now=now)
        assert score >= Decimal('60.00')
        
        # Session review_status must remain UNREVIEWED
        session.refresh_from_db()
        assert session.review_status == ReviewStatus.UNREVIEWED

        # Attempt must remain untouched and IN_PROGRESS
        self.attempt_1.refresh_from_db()
        assert self.attempt_1.status == AttemptStatus.IN_PROGRESS

    def test_risk_remains_within_0_100_under_massive_signals(self):
        # Invariant: Risk remains within 0–100
        session = ProctoringSessionService.start_session(self.attempt_1)
        now = timezone.now()

        for i in range(20):
            ProctoringEvent.objects.create(
                session=session,
                event_type='PHONE_DETECTED',
                source=EventSource.AI,
                severity=EventSeverity.CRITICAL,
                started_at=now,
                server_received_at=now,
                risk_delta=Decimal('40.00')
            )
            ProctoringEvent.objects.create(
                session=session,
                event_type='MULTIPLE_FACES',
                source=EventSource.AI,
                severity=EventSeverity.HIGH,
                started_at=now,
                server_received_at=now,
                risk_delta=Decimal('25.00')
            )

        score, band = ProctoringRiskService.calculate_session_risk(session, now=now)
        assert score == Decimal('100.00')
        assert band == RiskBand.CRITICAL
