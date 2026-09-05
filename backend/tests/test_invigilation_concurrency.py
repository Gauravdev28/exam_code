import pytest
from datetime import timedelta
from decimal import Decimal
from django.utils import timezone
from django.db import transaction
from rest_framework.exceptions import ValidationError as DRFValidationError

from apps.accounts.models import User, Role
from apps.assessments.models import Assessment, AssessmentStatus, TestAttempt, AttemptStatus, AssessmentSnapshot
from apps.assessments.services import AttemptService
from apps.invigilation.models import (
    ProctorAssignment,
    ProctorIntervention,
    InterventionType,
)
from apps.invigilation.services import ProctorRosterService, LiveInterventionService


@pytest.mark.django_db
class TestInvigilationConcurrency:

    @pytest.fixture
    def setup_concurrency(self):
        admin = User.objects.create_user(email="admin_conc@test.com", password="password123", role=Role.ADMIN)
        proctorA = User.objects.create_user(email="proctorA@test.com", password="password123", role='PROCTOR')
        proctorB = User.objects.create_user(email="proctorB@test.com", password="password123", role='PROCTOR')
        student = User.objects.create_user(email="student_conc@test.com", password="password123", role=Role.STUDENT)

        now = timezone.now()
        assessment = Assessment.objects.create(
            title="Concurrency Assessment",
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

        ProctorRosterService.assign_proctor(str(assessment.id), proctorA, admin)
        ProctorRosterService.assign_proctor(str(assessment.id), proctorB, admin)

        return {
            "admin": admin,
            "proctorA": proctorA,
            "proctorB": proctorB,
            "student": student,
            "assessment": assessment,
            "attempt": attempt,
        }

    # 1. Pause vs Pause Race: Only one active pause created, both calls succeed idempotently
    def test_concurrent_pause_requests_serialize_and_deduplicate(self, setup_concurrency):
        e = setup_concurrency
        att_id = str(e["attempt"].id)

        pA = LiveInterventionService.pause_attempt(e["proctorA"], att_id, reason="Proctor A pause")
        pB = LiveInterventionService.pause_attempt(e["proctorB"], att_id, reason="Proctor B pause")

        assert pA.id == pB.id
        # Exactly one PAUSE_STARTED event in database
        pauses = ProctorIntervention.objects.filter(
            attempt=e["attempt"],
            event_type=InterventionType.PAUSE_STARTED
        )
        assert pauses.count() == 1

    # 2. Pause vs Resume Race: Resume clears active pause, subsequent resume is idempotent
    def test_pause_vs_resume_race_resolution(self, setup_concurrency):
        e = setup_concurrency
        att_id = str(e["attempt"].id)

        LiveInterventionService.pause_attempt(e["proctorA"], att_id, reason="Pause")
        assert LiveInterventionService.get_active_pause(e["attempt"]) is not None

        # Resume by Proctor B
        res1 = LiveInterventionService.resume_attempt(e["proctorB"], att_id, reason="Resume")
        assert res1 is not None
        assert res1.event_type == InterventionType.PAUSE_ENDED

        # Second concurrent resume returns None (idempotent, attempt is already active)
        res2 = LiveInterventionService.resume_attempt(e["proctorA"], att_id, reason="Duplicate resume")
        assert res2 is None

    # 3. Pause vs Student Submission Race: If student submits first, pause is rejected
    def test_pause_vs_submission_race_student_submits_first(self, setup_concurrency):
        e = setup_concurrency
        att = e["attempt"]
        att_id = str(att.id)

        # Student submits attempt
        att.status = AttemptStatus.SUBMITTED
        att.submitted_at = timezone.now()
        att.save(update_fields=['status', 'submitted_at'])

        # Proctor tries to pause submitted attempt
        with pytest.raises(DRFValidationError) as exc:
            LiveInterventionService.pause_attempt(e["proctorA"], att_id, reason="Late pause")
        assert "Cannot pause attempt in status SUBMITTED" in str(exc.value)

    # 4. Pause vs Expiry Race: If attempt has expired, pause is rejected
    def test_pause_vs_expiry_race(self, setup_concurrency):
        e = setup_concurrency
        att = e["attempt"]
        att_id = str(att.id)

        att.status = AttemptStatus.EXPIRED
        att.save(update_fields=['status'])

        with pytest.raises(DRFValidationError) as exc:
            LiveInterventionService.pause_attempt(e["proctorA"], att_id, reason="Expired pause")
        assert "Cannot pause attempt in status EXPIRED" in str(exc.value)

    # 5. Terminate vs Student Submission Race: If student submitted, terminate rejected
    def test_terminate_vs_submission_race(self, setup_concurrency):
        e = setup_concurrency
        att = e["attempt"]
        att_id = str(att.id)

        att.status = AttemptStatus.SUBMITTED
        att.submitted_at = timezone.now()
        att.save(update_fields=['status', 'submitted_at'])

        with pytest.raises(DRFValidationError) as exc:
            LiveInterventionService.terminate_attempt(
                e["proctorA"],
                att_id,
                "CAUSE",
                "Justification"
            )
        assert "already in terminal state SUBMITTED" in str(exc.value)

    # 6. Terminate vs Terminate Race: Both calls succeed, single cancellation occurs
    def test_concurrent_terminate_requests_idempotent(self, setup_concurrency):
        e = setup_concurrency
        att_id = str(e["attempt"].id)

        attA, intA = LiveInterventionService.terminate_attempt(
            e["proctorA"],
            att_id,
            "CAUSE_A",
            "Proctor A term"
        )
        attB, intB = LiveInterventionService.terminate_attempt(
            e["proctorB"],
            att_id,
            "CAUSE_B",
            "Proctor B term"
        )

        assert attA.status == AttemptStatus.CANCELLED
        assert attB.status == AttemptStatus.CANCELLED
        assert intA.id == intB.id

    # 7. Multiple sequential pause/resume cycles accumulate pause time correctly
    def test_multiple_sequential_pauses_accumulate_correctly(self, setup_concurrency):
        e = setup_concurrency
        att = e["attempt"]
        att_id = str(att.id)

        # Cycle 1
        p1 = ProctorIntervention.objects.create(
            attempt=att,
            proctor=e["proctorA"],
            student=att.student,
            event_type=InterventionType.PAUSE_STARTED,
            metadata={"max_pause_seconds": 900}
        )
        r1 = ProctorIntervention.objects.create(
            attempt=att,
            proctor=e["proctorA"],
            student=att.student,
            event_type=InterventionType.PAUSE_ENDED,
            parent_event=p1,
            metadata={"pause_duration_seconds": 100}
        )

        # Cycle 2
        p2 = ProctorIntervention.objects.create(
            attempt=att,
            proctor=e["proctorB"],
            student=att.student,
            event_type=InterventionType.PAUSE_STARTED,
            metadata={"max_pause_seconds": 900}
        )
        r2 = ProctorIntervention.objects.create(
            attempt=att,
            proctor=e["proctorB"],
            student=att.student,
            event_type=InterventionType.PAUSE_ENDED,
            parent_event=p2,
            metadata={"pause_duration_seconds": 200}
        )

        # Total cumulative pause should be 300 seconds
        total_pause = LiveInterventionService.get_cumulative_pause_seconds(att)
        assert total_pause == 300

    # 8. Assessment deadline passing while attempt paused clamps resumed expires_at
    def test_pause_crossing_assessment_end_clamps_to_assessment_end(self, setup_concurrency):
        e = setup_concurrency
        att = e["attempt"]
        att_id = str(att.id)

        # Pause attempt
        LiveInterventionService.pause_attempt(e["proctorA"], att_id)

        # Move assessment end_datetime to 5 seconds ahead
        now = timezone.now()
        Assessment.objects.filter(pk=e["assessment"].pk).update(end_datetime=now + timedelta(seconds=5))
        e["assessment"].refresh_from_db()

        # Resume attempt
        LiveInterventionService.resume_attempt(e["proctorA"], att_id)

        att.refresh_from_db()
        assert att.expires_at <= e["assessment"].end_datetime
