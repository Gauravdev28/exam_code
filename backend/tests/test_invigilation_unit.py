import pytest
from datetime import timedelta
from decimal import Decimal
from django.utils import timezone
from django.core.exceptions import PermissionDenied
from rest_framework.exceptions import ValidationError as DRFValidationError

from apps.accounts.models import User, Role
from apps.assessments.models import Assessment, AssessmentStatus, TestAttempt, AttemptStatus, AssessmentSnapshot
from apps.proctoring.models import ProctoringSession, RiskBand
from apps.invigilation.models import (
    ProctorAssignment,
    ProctorIntervention,
    InterventionType,
    ProctorDutySession,
    ProctorChatMessage,
)
from apps.invigilation.services import (
    ProctorRosterService,
    LiveInterventionService,
    ProctorTriageQueueService,
    ProctorChatService,
)


@pytest.mark.django_db
class TestInvigilationUnit:

    @pytest.fixture
    def setup_entities(self):
        admin = User.objects.create_user(email="admin_unit@test.com", password="password123", role=Role.ADMIN)
        proctor = User.objects.create_user(email="proctor_unit@test.com", password="password123", role='PROCTOR')
        proctor2 = User.objects.create_user(email="proctor2_unit@test.com", password="password123", role='PROCTOR')
        student = User.objects.create_user(email="student_unit@test.com", password="password123", role=Role.STUDENT)

        now = timezone.now()
        assessment = Assessment.objects.create(
            title="Unit Test Assessment",
            status=AssessmentStatus.PUBLISHED,
            duration_minutes=60,
            start_datetime=now - timedelta(minutes=10),
            end_datetime=now + timedelta(minutes=120),
            created_by=admin
        )
        snapshot = AssessmentSnapshot.objects.create(assessment=assessment, version_number=1)

        attempt = TestAttempt.objects.create(
            student=student,
            assessment=assessment,
            assessment_snapshot=snapshot,
            status=AttemptStatus.IN_PROGRESS,
            started_at=now - timedelta(minutes=5),
            expires_at=now + timedelta(minutes=55)
        )

        assignment = ProctorRosterService.assign_proctor(
            assessment_id=str(assessment.id),
            proctor_user=proctor,
            assigned_by_user=admin
        )

        return {
            "admin": admin,
            "proctor": proctor,
            "proctor2": proctor2,
            "student": student,
            "assessment": assessment,
            "snapshot": snapshot,
            "attempt": attempt,
            "assignment": assignment,
        }

    # 1. Proctor Assignment & Authorization
    def test_proctor_assignment_creation(self, setup_entities):
        e = setup_entities
        assert e["assignment"].is_active is True
        assert e["assignment"].max_candidates == 30
        assert ProctorRosterService.is_proctor_assigned(e["proctor"], str(e["assessment"].id)) is True
        assert ProctorRosterService.is_proctor_assigned(e["proctor2"], str(e["assessment"].id)) is False

    def test_proctor_unassignment(self, setup_entities):
        e = setup_entities
        res = ProctorRosterService.unassign_proctor(str(e["assessment"].id), e["proctor"])
        assert res is True
        assert ProctorRosterService.is_proctor_assigned(e["proctor"], str(e["assessment"].id)) is False

    def test_admin_has_universal_proctor_access(self, setup_entities):
        e = setup_entities
        assert ProctorRosterService.is_proctor_assigned(e["admin"], str(e["assessment"].id)) is True

    # 2. Append-Only Immutability
    def test_proctor_intervention_cannot_be_updated(self, setup_entities):
        e = setup_entities
        interv = LiveInterventionService.issue_warning(
            proctor=e["proctor"],
            attempt_id=str(e["attempt"].id),
            reason_code="UNIT_WARN",
            message="Please focus on screen."
        )
        with pytest.raises(PermissionDenied) as exc_info:
            interv.reason_text = "Mutated message"
            interv.save()
        assert "strictly append-only and immutable" in str(exc_info.value)

    def test_proctor_intervention_cannot_be_deleted_directly(self, setup_entities):
        e = setup_entities
        interv = LiveInterventionService.issue_warning(
            proctor=e["proctor"],
            attempt_id=str(e["attempt"].id),
            reason_code="UNIT_WARN",
            message="Warning message"
        )
        with pytest.raises(PermissionDenied) as exc_info:
            interv.delete()
        assert "cannot be deleted directly" in str(exc_info.value)

    # 3. Warning & Acknowledgement
    def test_issue_warning_success(self, setup_entities):
        e = setup_entities
        interv = LiveInterventionService.issue_warning(
            proctor=e["proctor"],
            attempt_id=str(e["attempt"].id),
            reason_code="HEAD_TURN",
            message="Please look straight.",
            internal_notes="Suspicious head turn left"
        )
        assert interv.event_type == InterventionType.WARNING_ISSUED
        assert interv.student == e["student"]
        assert interv.proctor == e["proctor"]
        assert interv.internal_notes == "Suspicious head turn left"

    def test_acknowledge_warning_success(self, setup_entities):
        e = setup_entities
        interv = LiveInterventionService.issue_warning(
            proctor=e["proctor"],
            attempt_id=str(e["attempt"].id),
            reason_code="AUDIO",
            message="Quiet down please."
        )
        ack = LiveInterventionService.acknowledge_warning(
            student=e["student"],
            attempt_id=str(e["attempt"].id),
            intervention_id=str(interv.id)
        )
        assert ack.event_type == InterventionType.WARNING_ACKNOWLEDGED
        assert ack.parent_event == interv
        assert ack.proctor is None

    def test_acknowledge_warning_idempotent(self, setup_entities):
        e = setup_entities
        interv = LiveInterventionService.issue_warning(
            proctor=e["proctor"],
            attempt_id=str(e["attempt"].id),
            reason_code="AUDIO",
            message="Quiet down."
        )
        ack1 = LiveInterventionService.acknowledge_warning(e["student"], str(e["attempt"].id), str(interv.id))
        ack2 = LiveInterventionService.acknowledge_warning(e["student"], str(e["attempt"].id), str(interv.id))
        assert ack1.id == ack2.id

    # 4. Pause and Resume Logic
    def test_single_active_pause_enforcement(self, setup_entities):
        e = setup_entities
        p1 = LiveInterventionService.pause_attempt(e["proctor"], str(e["attempt"].id), reason="First pause")
        assert p1.event_type == InterventionType.PAUSE_STARTED

        # Second pause returns active pause idempotently
        p2 = LiveInterventionService.pause_attempt(e["proctor"], str(e["attempt"].id), reason="Second pause")
        assert p1.id == p2.id

    def test_resume_not_paused_is_idempotent(self, setup_entities):
        e = setup_entities
        res = LiveInterventionService.resume_attempt(e["proctor"], str(e["attempt"].id))
        assert res is None

    def test_pause_and_resume_extends_expiry(self, setup_entities):
        e = setup_entities
        att = e["attempt"]
        original_expiry = att.expires_at

        pause = LiveInterventionService.pause_attempt(e["proctor"], str(att.id), reason="Check connection")
        assert LiveInterventionService.get_active_pause(att) is not None

        # Simulate small delay
        resume = LiveInterventionService.resume_attempt(e["proctor"], str(att.id), reason="Connection verified")
        assert resume.event_type == InterventionType.PAUSE_ENDED
        assert resume.parent_event == pause

        att.refresh_from_db()
        assert att.expires_at > original_expiry

    def test_assessment_end_datetime_hard_ceiling(self, setup_entities):
        e = setup_entities
        att = e["attempt"]
        # Set assessment end to only 10 seconds ahead
        now = timezone.now()
        Assessment.objects.filter(pk=e["assessment"].pk).update(end_datetime=now + timedelta(seconds=10))
        e["assessment"].refresh_from_db()

        LiveInterventionService.pause_attempt(e["proctor"], str(att.id))
        LiveInterventionService.resume_attempt(e["proctor"], str(att.id))

        att.refresh_from_db()
        assert att.expires_at <= e["assessment"].end_datetime

    def test_cannot_pause_if_assessment_deadline_passed(self, setup_entities):
        e = setup_entities
        att = e["attempt"]
        Assessment.objects.filter(pk=e["assessment"].pk).update(end_datetime=timezone.now() - timedelta(seconds=1))
        e["assessment"].refresh_from_db()

        with pytest.raises(DRFValidationError) as exc:
            LiveInterventionService.pause_attempt(e["proctor"], str(att.id))
        assert "end datetime has passed" in str(exc.value)

    def test_cumulative_pause_cap_enforcement(self, setup_entities):
        e = setup_entities
        att = e["attempt"]
        # Cap at 60 seconds
        pause = LiveInterventionService.pause_attempt(e["proctor"], str(att.id), max_pause_seconds=60)

        # End pause with 65 seconds recorded
        ProctorIntervention.objects.create(
            attempt=att,
            proctor=e["proctor"],
            student=e["student"],
            event_type=InterventionType.PAUSE_ENDED,
            parent_event=pause,
            metadata={"pause_duration_seconds": 65}
        )

        # Attempt next pause exceeds 60s cap
        with pytest.raises(DRFValidationError) as exc:
            LiveInterventionService.pause_attempt(e["proctor"], str(att.id), max_pause_seconds=60)
        assert "limit of 1 minutes has been exhausted" in str(exc.value)

    # 5. Room Scan Workflow
    def test_room_scan_request_and_complete(self, setup_entities):
        e = setup_entities
        scan_req = LiveInterventionService.request_room_scan(e["proctor"], str(e["attempt"].id), reason="Show desk")
        assert scan_req.event_type == InterventionType.ROOM_SCAN_REQUESTED

        comp = LiveInterventionService.complete_room_scan(e["student"], str(e["attempt"].id), str(scan_req.id))
        assert comp.event_type == InterventionType.ROOM_SCAN_COMPLETED
        assert comp.parent_event == scan_req

    # 6. Termination Flow
    def test_terminate_attempt_transitions_to_cancelled(self, setup_entities):
        e = setup_entities
        att, interv = LiveInterventionService.terminate_attempt(
            proctor=e["proctor"],
            attempt_id=str(e["attempt"].id),
            reason_code="PHONE_USE",
            formal_justification="Candidate observed using cell phone repeatedly.",
            internal_notes="Audio evidence timestamp 12:44"
        )
        assert att.status == AttemptStatus.CANCELLED
        assert att.submitted_at is not None
        assert interv.event_type == InterventionType.TERMINATION_REQUESTED
        assert interv.internal_notes == "Audio evidence timestamp 12:44"

    def test_terminate_already_terminal_attempt_rejected(self, setup_entities):
        e = setup_entities
        e["attempt"].status = AttemptStatus.SUBMITTED
        e["attempt"].save(update_fields=['status'])

        with pytest.raises(DRFValidationError) as exc:
            LiveInterventionService.terminate_attempt(
                e["proctor"],
                str(e["attempt"].id),
                "CAUSE",
                "Justification"
            )
        assert "already in terminal state" in str(exc.value)

    def test_terminate_attempt_is_idempotent(self, setup_entities):
        e = setup_entities
        att1, interv1 = LiveInterventionService.terminate_attempt(
            e["proctor"],
            str(e["attempt"].id),
            "CAUSE",
            "Justification"
        )
        att2, interv2 = LiveInterventionService.terminate_attempt(
            e["proctor"],
            str(e["attempt"].id),
            "CAUSE",
            "Justification"
        )
        assert att1.id == att2.id
        assert interv1.id == interv2.id

    # 7. Triage Queue Sorting
    def test_triage_queue_prioritizes_risk_bands(self, setup_entities):
        e = setup_entities
        # Create second student & attempt with CRITICAL risk
        student2 = User.objects.create_user(email="crit_stud@test.com", password="pw", role=Role.STUDENT)
        att2 = TestAttempt.objects.create(
            student=student2,
            assessment=e["assessment"],
            assessment_snapshot=e["snapshot"],
            status=AttemptStatus.IN_PROGRESS,
            started_at=timezone.now()
        )
        ProctoringSession.objects.create(
            attempt=att2,
            risk_band=RiskBand.CRITICAL,
            risk_score=Decimal('85.00')
        )
        # Attempt 1 has NORMAL risk
        ProctoringSession.objects.create(
            attempt=e["attempt"],
            risk_band=RiskBand.NORMAL,
            risk_score=Decimal('5.00')
        )

        roster = ProctorTriageQueueService.get_triage_roster(str(e["assessment"].id))
        assert len(roster) == 2
        # CRITICAL should be first
        assert roster[0]["attempt_id"] == str(att2.id)
        assert roster[0]["risk_band"] == RiskBand.CRITICAL
        assert roster[1]["attempt_id"] == str(e["attempt"].id)

    # 8. Bilateral Chat
    def test_chat_message_flow(self, setup_entities):
        e = setup_entities
        msg = ProctorChatService.send_message(
            sender=e["proctor"],
            attempt_id=str(e["attempt"].id),
            message_text="Please adjust your camera angle."
        )
        assert msg.sender == e["proctor"]
        assert msg.recipient == e["student"]
        assert msg.is_read is False

        # Read history as student
        history = ProctorChatService.get_chat_history(str(e["attempt"].id), e["student"])
        assert len(history) == 1
        msg.refresh_from_db()
        assert msg.is_read is True

    def test_chat_message_cannot_be_mutated(self, setup_entities):
        e = setup_entities
        msg = ProctorChatService.send_message(
            sender=e["proctor"],
            attempt_id=str(e["attempt"].id),
            message_text="Original text"
        )
        with pytest.raises(PermissionDenied):
            msg.message_text = "Hacked text"
            msg.save()

    # 9. Proctor Duty Session
    def test_proctor_duty_session_lifecycle(self, setup_entities):
        e = setup_entities
        session = ProctorDutySession.objects.create(
            proctor=e["proctor"],
            assessment=e["assessment"],
            active_monitored_count=5
        )
        assert session.is_active is True
        assert session.active_monitored_count == 5

        # End session
        session.is_active = False
        session.ended_at = timezone.now()
        session.save()
        session.refresh_from_db()
        assert session.is_active is False
        assert session.ended_at is not None

    # 10. Idempotency Keys across Interventions
    def test_issue_warning_idempotency_key(self, setup_entities):
        e = setup_entities
        w1 = LiveInterventionService.issue_warning(
            e["proctor"], str(e["attempt"].id), "WARN", "Msg", idempotency_key="key_1"
        )
        w2 = LiveInterventionService.issue_warning(
            e["proctor"], str(e["attempt"].id), "WARN", "Msg", idempotency_key="key_1"
        )
        assert w1.id == w2.id

    def test_pause_attempt_idempotency_key(self, setup_entities):
        e = setup_entities
        p1 = LiveInterventionService.pause_attempt(
            e["proctor"], str(e["attempt"].id), reason="Pause", idempotency_key="key_pause"
        )
        p2 = LiveInterventionService.pause_attempt(
            e["proctor"], str(e["attempt"].id), reason="Pause", idempotency_key="key_pause"
        )
        assert p1.id == p2.id

    def test_resume_attempt_idempotency_key(self, setup_entities):
        e = setup_entities
        LiveInterventionService.pause_attempt(e["proctor"], str(e["attempt"].id), reason="Pause")
        r1 = LiveInterventionService.resume_attempt(
            e["proctor"], str(e["attempt"].id), reason="Resume", idempotency_key="key_resume"
        )
        r2 = LiveInterventionService.resume_attempt(
            e["proctor"], str(e["attempt"].id), reason="Resume", idempotency_key="key_resume"
        )
        assert r1.id == r2.id

    def test_terminate_attempt_idempotency_key(self, setup_entities):
        e = setup_entities
        att1, t1 = LiveInterventionService.terminate_attempt(
            e["proctor"], str(e["attempt"].id), "CAUSE", "Just", idempotency_key="key_term"
        )
        att2, t2 = LiveInterventionService.terminate_attempt(
            e["proctor"], str(e["attempt"].id), "CAUSE", "Just", idempotency_key="key_term"
        )
        assert t1.id == t2.id

    # 11. Error Handling on Non-Existent Resources
    def test_issue_warning_non_existent_attempt_raises_not_found(self, setup_entities):
        e = setup_entities
        from rest_framework.exceptions import NotFound
        import uuid
        with pytest.raises(NotFound):
            LiveInterventionService.issue_warning(e["proctor"], str(uuid.uuid4()), "CODE", "Msg")

    def test_pause_non_existent_attempt_raises_not_found(self, setup_entities):
        e = setup_entities
        from rest_framework.exceptions import NotFound
        import uuid
        with pytest.raises(NotFound):
            LiveInterventionService.pause_attempt(e["proctor"], str(uuid.uuid4()))

    def test_resume_non_existent_attempt_raises_not_found(self, setup_entities):
        e = setup_entities
        from rest_framework.exceptions import NotFound
        import uuid
        with pytest.raises(NotFound):
            LiveInterventionService.resume_attempt(e["proctor"], str(uuid.uuid4()))

    def test_terminate_non_existent_attempt_raises_not_found(self, setup_entities):
        e = setup_entities
        from rest_framework.exceptions import NotFound
        import uuid
        with pytest.raises(NotFound):
            LiveInterventionService.terminate_attempt(e["proctor"], str(uuid.uuid4()), "C", "J")

    def test_acknowledge_non_existent_warning_raises_not_found(self, setup_entities):
        e = setup_entities
        from rest_framework.exceptions import NotFound
        import uuid
        with pytest.raises(NotFound):
            LiveInterventionService.acknowledge_warning(e["student"], str(e["attempt"].id), str(uuid.uuid4()))

    def test_complete_room_scan_non_existent_raises_not_found(self, setup_entities):
        e = setup_entities
        from rest_framework.exceptions import NotFound
        import uuid
        with pytest.raises(NotFound):
            LiveInterventionService.complete_room_scan(e["student"], str(e["attempt"].id), str(uuid.uuid4()))

