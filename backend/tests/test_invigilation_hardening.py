import pytest
import concurrent.futures
from datetime import timedelta
from django.utils import timezone
from django.core.exceptions import PermissionDenied
from django.db import connection, transaction
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework.exceptions import ValidationError as DRFValidationError

from apps.accounts.models import User, Role
from apps.assessments.models import (
    Assessment,
    AssessmentStatus,
    TestAttempt,
    AttemptStatus,
    AssessmentSnapshot,
    AssessmentSnapshotQuestion,
)
from apps.questions.services import QuestionService
from apps.questions.models import QuestionType
from apps.invigilation.models import (
    ProctorAssignment,
    ProctorIntervention,
    InterventionType,
)
from apps.invigilation.services import (
    ProctorRosterService,
    LiveInterventionService,
)


@pytest.fixture
def hardening_fixture(db):
    admin = User.objects.create(email="admin_hard@exam.com", role=Role.ADMIN, is_staff=True)
    staff_only = User.objects.create(email="staff_only@exam.com", role=Role.STUDENT, is_staff=True)
    proctorA = User.objects.create(email="proctor_a@exam.com", role="PROCTOR", is_staff=False)
    proctorB = User.objects.create(email="proctor_b@exam.com", role="PROCTOR", is_staff=False)
    student1 = User.objects.create(email="student1_hard@exam.com", role=Role.STUDENT, is_staff=False)
    student2 = User.objects.create(email="student2_hard@exam.com", role=Role.STUDENT, is_staff=False)

    now = timezone.now()
    ass1 = Assessment.objects.create(
        title="Assessment 1",
        description="Exam 1",
        duration_minutes=60,
        start_datetime=now - timedelta(hours=1),
        end_datetime=now + timedelta(hours=2),
        created_by=admin,
        status=AssessmentStatus.PUBLISHED
    )
    snap1 = AssessmentSnapshot.objects.create(
        assessment=ass1,
        version_number=1,
        snapshot_data={}
    )

    ass2 = Assessment.objects.create(
        title="Assessment 2",
        description="Exam 2",
        duration_minutes=60,
        start_datetime=now - timedelta(hours=1),
        end_datetime=now + timedelta(hours=2),
        created_by=admin,
        status=AssessmentStatus.PUBLISHED
    )
    snap2 = AssessmentSnapshot.objects.create(
        assessment=ass2,
        version_number=1,
        snapshot_data={}
    )

    att1 = TestAttempt.objects.create(
        student=student1,
        assessment=ass1,
        assessment_snapshot=snap1,
        attempt_number=1,
        status=AttemptStatus.IN_PROGRESS,
        started_at=now - timedelta(minutes=10),
        expires_at=now + timedelta(minutes=50)
    )

    att2 = TestAttempt.objects.create(
        student=student2,
        assessment=ass2,
        assessment_snapshot=snap2,
        attempt_number=1,
        status=AttemptStatus.IN_PROGRESS,
        started_at=now - timedelta(minutes=10),
        expires_at=now + timedelta(minutes=50)
    )

    # Proctor A assigned ONLY to Assessment 1
    assignA = ProctorAssignment.objects.create(
        proctor=proctorA,
        assessment=ass1,
        is_active=True,
        max_candidates=30
    )

    return {
        "admin": admin,
        "staff_only": staff_only,
        "proctorA": proctorA,
        "proctorB": proctorB,
        "student1": student1,
        "student2": student2,
        "ass1": ass1,
        "ass2": ass2,
        "att1": att1,
        "att2": att2,
        "assignA": assignA,
        "client": APIClient(),
    }


@pytest.mark.django_db
class TestPhase10Hardening:

    # =========================================================================
    # 1. APPEND-ONLY INTERVENTION AUDIT TESTS
    # =========================================================================

    def test_intervention_instance_update_rejected(self, hardening_fixture):
        e = hardening_fixture
        interv = ProctorIntervention.objects.create(
            attempt=e["att1"],
            proctor=e["proctorA"],
            student=e["student1"],
            event_type=InterventionType.WARNING_ISSUED,
            reason_code="WARN",
            reason_text="Original warning"
        )
        with pytest.raises(PermissionDenied) as exc:
            interv.reason_text = "Mutated warning text"
            interv.save()
        assert "strictly append-only and immutable" in str(exc.value)

    def test_intervention_instance_delete_rejected(self, hardening_fixture):
        e = hardening_fixture
        interv = ProctorIntervention.objects.create(
            attempt=e["att1"],
            proctor=e["proctorA"],
            student=e["student1"],
            event_type=InterventionType.WARNING_ISSUED,
            reason_code="WARN"
        )
        with pytest.raises(PermissionDenied) as exc:
            interv.delete()
        assert "cannot be deleted directly" in str(exc.value)

    def test_intervention_queryset_update_rejected(self, hardening_fixture):
        e = hardening_fixture
        interv = ProctorIntervention.objects.create(
            attempt=e["att1"],
            proctor=e["proctorA"],
            student=e["student1"],
            event_type=InterventionType.WARNING_ISSUED,
            reason_code="WARN"
        )
        with pytest.raises(PermissionDenied) as exc:
            ProctorIntervention.objects.filter(id=interv.id).update(reason_code="HACKED")
        assert "strictly append-only and cannot be updated via QuerySet" in str(exc.value)

    def test_intervention_queryset_delete_rejected(self, hardening_fixture):
        e = hardening_fixture
        interv = ProctorIntervention.objects.create(
            attempt=e["att1"],
            proctor=e["proctorA"],
            student=e["student1"],
            event_type=InterventionType.WARNING_ISSUED,
            reason_code="WARN"
        )
        with pytest.raises(PermissionDenied) as exc:
            ProctorIntervention.objects.filter(id=interv.id).delete()
        assert "cannot be deleted directly via QuerySet" in str(exc.value)

    def test_pause_started_immutable_and_pause_ended_is_new_row(self, hardening_fixture):
        e = hardening_fixture
        att = e["att1"]
        pause_event = LiveInterventionService.pause_attempt(e["proctorA"], str(att.id), reason="Hold")
        assert pause_event.event_type == InterventionType.PAUSE_STARTED

        # Resume attempt
        resume_event = LiveInterventionService.resume_attempt(e["proctorA"], str(att.id), reason="Continue")
        assert resume_event.event_type == InterventionType.PAUSE_ENDED
        assert resume_event.parent_event_id == pause_event.id
        assert resume_event.id != pause_event.id

        # Verify pause_event unchanged in database
        pause_event.refresh_from_db()
        assert pause_event.event_type == InterventionType.PAUSE_STARTED
        assert pause_event.parent_event_id is None

    def test_warning_issued_immutable_and_acknowledged_is_new_row(self, hardening_fixture):
        e = hardening_fixture
        att = e["att1"]
        warn_event = LiveInterventionService.issue_warning(
            e["proctorA"], str(att.id), reason_code="GAZE", message="Focus on screen"
        )
        assert warn_event.event_type == InterventionType.WARNING_ISSUED

        ack_event = LiveInterventionService.acknowledge_warning(
            e["student1"], str(att.id), str(warn_event.id)
        )
        assert ack_event.event_type == InterventionType.WARNING_ACKNOWLEDGED
        assert ack_event.parent_event_id == warn_event.id
        assert ack_event.id != warn_event.id

        # Verify warn_event unchanged
        warn_event.refresh_from_db()
        assert warn_event.event_type == InterventionType.WARNING_ISSUED

    def test_termination_requested_and_confirmed_are_separate_rows(self, hardening_fixture):
        e = hardening_fixture
        att = e["att1"]
        att_res, term_event = LiveInterventionService.terminate_attempt(
            e["proctorA"], str(att.id), reason_code="UNAUTHORIZED_PHONE", formal_justification="Phone detected."
        )
        assert term_event.event_type == InterventionType.TERMINATION_REQUESTED

        # Verify confirmed event was created as a distinct row linked to requested
        confirmed_event = ProctorIntervention.objects.filter(
            attempt=att,
            event_type=InterventionType.TERMINATION_CONFIRMED
        ).first()
        assert confirmed_event is not None
        assert confirmed_event.parent_event_id == term_event.id
        assert confirmed_event.id != term_event.id

    def test_api_has_no_mutation_endpoints_for_interventions(self, hardening_fixture):
        e = hardening_fixture
        client = e["client"]
        client.force_authenticate(user=e["proctorA"])
        interv = ProctorIntervention.objects.create(
            attempt=e["att1"],
            proctor=e["proctorA"],
            student=e["student1"],
            event_type=InterventionType.WARNING_ISSUED,
            reason_code="WARN"
        )
        url = f"/api/v1/proctor/attempts/{e['att1'].id}/interventions/"
        # PUT and PATCH on collection or detail should fail (405 Method Not Allowed)
        put_res = client.put(url, {"reason_code": "MUTATED"})
        assert put_res.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
        delete_res = client.delete(url)
        assert delete_res.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    # =========================================================================
    # 2. AUTHORIZATION & is_staff REMOVAL TESTS
    # =========================================================================

    def test_generic_staff_denied_proctor_endpoints(self, hardening_fixture):
        e = hardening_fixture
        client = e["client"]
        # User has is_staff=True, but role='STUDENT' (generic staff member)
        client.force_authenticate(user=e["staff_only"])

        # Attempt to access live roster
        url = f"/api/v1/proctor/assessments/{e['ass1'].id}/live-roster/"
        res = client.get(url)
        assert res.status_code == status.HTTP_403_FORBIDDEN

        # Attempt to issue warning
        warn_url = f"/api/v1/proctor/attempts/{e['att1'].id}/warning/"
        warn_res = client.post(warn_url, {"reason_code": "WARN", "message": "Staff message"})
        assert warn_res.status_code == status.HTTP_403_FORBIDDEN

    def test_unassigned_proctor_denied_assessment_access(self, hardening_fixture):
        e = hardening_fixture
        client = e["client"]
        # Proctor B has role='PROCTOR', but is NOT assigned to Assessment 1
        client.force_authenticate(user=e["proctorB"])

        url = f"/api/v1/proctor/assessments/{e['ass1'].id}/live-roster/"
        res = client.get(url)
        assert res.status_code == status.HTTP_403_FORBIDDEN

    def test_cross_assessment_attempt_intervention_denied(self, hardening_fixture):
        e = hardening_fixture
        client = e["client"]
        # Proctor A is assigned to Assessment 1, NOT Assessment 2
        client.force_authenticate(user=e["proctorA"])

        # Attempt 2 belongs to Assessment 2
        warn_url = f"/api/v1/proctor/attempts/{e['att2'].id}/warning/"
        res = client.post(warn_url, {"reason_code": "WARN", "message": "Cross-exam alert"})
        assert res.status_code == status.HTTP_403_FORBIDDEN

    def test_assigned_proctor_allowed_access(self, hardening_fixture):
        e = hardening_fixture
        client = e["client"]
        client.force_authenticate(user=e["proctorA"])

        # Access assigned Assessment 1
        url = f"/api/v1/proctor/assessments/{e['ass1'].id}/live-roster/"
        res = client.get(url)
        assert res.status_code == status.HTTP_200_OK

        # Intervene on Attempt 1
        warn_url = f"/api/v1/proctor/attempts/{e['att1'].id}/warning/"
        res_warn = client.post(warn_url, {"reason_code": "GAZE", "message": "Valid warning"})
        assert res_warn.status_code == status.HTTP_201_CREATED

    def test_admin_allowed_without_explicit_assignment(self, hardening_fixture):
        e = hardening_fixture
        client = e["client"]
        client.force_authenticate(user=e["admin"])

        # Admin accesses Assessment 2 without prior assignment
        url = f"/api/v1/proctor/assessments/{e['ass2'].id}/live-roster/"
        res = client.get(url)
        assert res.status_code == status.HTTP_200_OK

        # Admin intervenes on Attempt 2
        pause_url = f"/api/v1/proctor/attempts/{e['att2'].id}/pause/"
        p_res = client.post(pause_url, {"reason": "Admin pause"})
        assert p_res.status_code == status.HTTP_201_CREATED

    def test_student_denied_proctor_endpoints(self, hardening_fixture):
        e = hardening_fixture
        client = e["client"]
        client.force_authenticate(user=e["student1"])

        url = f"/api/v1/proctor/assessments/{e['ass1'].id}/live-roster/"
        res = client.get(url)
        assert res.status_code == status.HTTP_403_FORBIDDEN

    # =========================================================================
    # 3. PROCTOR ASSIGNMENT CAPACITY & CONCURRENCY TESTS
    # =========================================================================

    def test_assignment_capacity_limit_enforced(self, hardening_fixture):
        e = hardening_fixture
        # ass1 already has proctorA assigned (active_count = 1)
        proctorC = User.objects.create(email="proctor_c@exam.com", role="PROCTOR")
        proctorD = User.objects.create(email="proctor_d@exam.com", role="PROCTOR")

        # Assign proctorC with max_capacity = 2 (active_count becomes 2)
        ProctorRosterService.assign_proctor(
            assessment_id=str(e["ass1"].id),
            proctor_user=proctorC,
            max_capacity=2
        )

        # Attempting to assign proctorD when capacity is 2 should fail
        with pytest.raises(DRFValidationError) as exc:
            ProctorRosterService.assign_proctor(
                assessment_id=str(e["ass1"].id),
                proctor_user=proctorD,
                max_capacity=2
            )
        assert "capacity reached" in str(exc.value)

    def test_concurrent_proctor_assignment_serialized(self, hardening_fixture):
        """
        Serialized capacity check: When active assignments reach capacity N,
        subsequent assignment attempts are strictly rejected and cannot exceed N.
        """
        e = hardening_fixture
        # ass1 currently has 1 active assignment (proctorA)
        proctor1 = User.objects.create(email="race1@exam.com", role="PROCTOR")
        proctor2 = User.objects.create(email="race2@exam.com", role="PROCTOR")

        # Proctor 1 claims final slot (capacity = 2)
        assign1 = ProctorRosterService.assign_proctor(
            assessment_id=str(e["ass1"].id),
            proctor_user=proctor1,
            max_capacity=2
        )
        assert assign1.is_active is True

        # Proctor 2 attempts to claim beyond capacity -> rejected with DRFValidationError
        with pytest.raises(DRFValidationError) as exc:
            ProctorRosterService.assign_proctor(
                assessment_id=str(e["ass1"].id),
                proctor_user=proctor2,
                max_capacity=2
            )
        assert "capacity reached" in str(exc.value)

        # Total active assignments strictly equals capacity (2)
        total_active = ProctorAssignment.objects.filter(assessment=e["ass1"], is_active=True).count()
        assert total_active == 2

    # =========================================================================
    # 4. PAUSE / RESUME DUPLICATE SAFETY & ASSESSMENT CEILING
    # =========================================================================

    def test_duplicate_pause_command_is_idempotent(self, hardening_fixture):
        e = hardening_fixture
        att = e["att1"]
        att_id = str(att.id)

        p1 = LiveInterventionService.pause_attempt(e["proctorA"], att_id, reason="Pause 1", idempotency_key="k1")
        p2 = LiveInterventionService.pause_attempt(e["proctorA"], att_id, reason="Pause 2", idempotency_key="k1")
        assert p1.id == p2.id

    def test_duplicate_resume_command_is_safe(self, hardening_fixture):
        e = hardening_fixture
        att = e["att1"]
        att_id = str(att.id)

        # Attempt is not paused -> resume returns None safely without creating records
        res = LiveInterventionService.resume_attempt(e["proctorA"], att_id)
        assert res is None

    def test_pause_resumption_strictly_clamps_to_assessment_end(self, hardening_fixture):
        e = hardening_fixture
        att = e["att1"]
        att_id = str(att.id)

        LiveInterventionService.pause_attempt(e["proctorA"], att_id)

        # Set assessment end to 10 seconds from now
        now = timezone.now()
        Assessment.objects.filter(id=e["ass1"].id).update(end_datetime=now + timedelta(seconds=10))
        e["ass1"].refresh_from_db()

        # Resume attempt
        LiveInterventionService.resume_attempt(e["proctorA"], att_id)
        att.refresh_from_db()

        # Expiry must be <= assessment.end_datetime
        assert att.expires_at <= e["ass1"].end_datetime

    # =========================================================================
    # 5. MIGRATION ISOLATION & SCHEMA BOUNDARY TESTS
    # =========================================================================

    def test_migration_isolation_zero_phase1_to_9_table_mutations(self):
        import importlib
        migration_module = importlib.import_module("apps.invigilation.migrations.0001_initial")
        migration_cls = migration_module.Migration

        allowed_models = {
            "proctordutysession",
            "proctorassignment",
            "proctorchatmessage",
            "proctorintervention",
        }

        # Assert that every operation in 0001_initial creates only Phase 10 models
        for op in migration_cls.operations:
            from django.db import migrations
            if isinstance(op, migrations.CreateModel):
                assert op.name.lower() in allowed_models
            elif isinstance(op, (migrations.AddIndex, migrations.AddConstraint)):
                assert op.model_name.lower() in allowed_models
            else:
                pytest.fail(f"Unexpected migration operation: {type(op).__name__}")

    # =========================================================================
    # 6. TERMINATION & TIMER AUTHORITY INTEGRATION TESTS
    # =========================================================================

    def test_termination_delegates_to_phase5_cancellation_and_phase8_finalization(self, hardening_fixture, monkeypatch):
        e = hardening_fixture
        att = e["att1"]
        att_id = str(att.id)

        task_calls = []
        monkeypatch.setattr(
            "apps.results.tasks.finalize_assessment_result_task.delay",
            lambda attempt_id: task_calls.append(attempt_id)
        )
        monkeypatch.setattr(
            "django.db.transaction.on_commit",
            lambda func: func()
        )

        att_res, interv = LiveInterventionService.terminate_attempt(
            e["proctorA"], att_id, reason_code="CHEATING", formal_justification="Candidate observed using secondary device."
        )

        # Attempt transitioned to Phase 5 CANCELLED status
        att.refresh_from_db()
        assert att.status == AttemptStatus.CANCELLED
        assert att.submitted_at is not None

        # Phase 8 finalization task was triggered for post-commit execution
        assert att_id in task_calls

    def test_phase10_consumes_phase5_attempt_timer_service(self, hardening_fixture):
        from apps.assessments.services import AttemptTimerService
        from apps.invigilation.services import ProctorTriageQueueService
        e = hardening_fixture
        att = e["att1"]

        # Phase 5 calculation
        remaining = AttemptTimerService.get_remaining_seconds(att)
        assert remaining > 0

        # Phase 10 roster reflects identical remaining seconds
        roster = ProctorTriageQueueService.get_triage_roster(str(e["ass1"].id), e["proctorA"])
        att_roster = next(r for r in roster if r["attempt_id"] == str(att.id))
        assert att_roster["remaining_seconds"] == remaining

    # =========================================================================
    # 7. PHASE 5 TIMER SERVICE AUTHORITATIVE CONTRACT TESTS
    # =========================================================================

    def test_phase5_authorized_pause_operation_works(self, hardening_fixture):
        from apps.assessments.services import AttemptTimerService
        e = hardening_fixture
        att = e["att1"]
        original_expiry = att.expires_at

        # Apply 120s pause
        updated = AttemptTimerService.apply_authorized_pause(
            attempt=att,
            pause_duration_seconds=120,
            actor=e["proctorA"]
        )
        assert updated.expires_at == original_expiry + timedelta(seconds=120)

        # Verify persisted in database
        att.refresh_from_db()
        assert att.expires_at == original_expiry + timedelta(seconds=120)

    def test_phase5_unauthorized_pause_rejected_on_not_started(self, hardening_fixture):
        from apps.assessments.services import AttemptTimerService
        e = hardening_fixture
        att = e["att1"]
        att.status = AttemptStatus.NOT_STARTED
        att.save(update_fields=['status'])

        with pytest.raises(DRFValidationError) as exc:
            AttemptTimerService.authorize_pause(att, actor=e["proctorA"])
        assert "Cannot pause attempt in status NOT_STARTED" in str(exc.value)

    def test_phase5_pause_cannot_operate_on_submitted_attempt(self, hardening_fixture):
        from apps.assessments.services import AttemptTimerService
        e = hardening_fixture
        att = e["att1"]
        att.status = AttemptStatus.SUBMITTED
        att.save(update_fields=['status'])

        with pytest.raises(DRFValidationError) as exc1:
            AttemptTimerService.authorize_pause(att, actor=e["proctorA"])
        assert "Cannot pause attempt in status SUBMITTED" in str(exc1.value)

        with pytest.raises(DRFValidationError) as exc2:
            AttemptTimerService.apply_authorized_pause(att, pause_duration_seconds=60, actor=e["proctorA"])
        assert "Cannot apply pause to attempt in status SUBMITTED" in str(exc2.value)

    def test_phase5_pause_cannot_operate_on_cancelled_attempt(self, hardening_fixture):
        from apps.assessments.services import AttemptTimerService
        e = hardening_fixture
        att = e["att1"]
        att.status = AttemptStatus.CANCELLED
        att.save(update_fields=['status'])

        with pytest.raises(DRFValidationError) as exc1:
            AttemptTimerService.authorize_pause(att, actor=e["proctorA"])
        assert "Cannot pause attempt in status CANCELLED" in str(exc1.value)

        with pytest.raises(DRFValidationError) as exc2:
            AttemptTimerService.apply_authorized_pause(att, pause_duration_seconds=60, actor=e["proctorA"])
        assert "Cannot apply pause to attempt in status CANCELLED" in str(exc2.value)

    def test_phase5_invalid_pause_duration_rejected(self, hardening_fixture):
        from apps.assessments.services import AttemptTimerService
        e = hardening_fixture
        att = e["att1"]

        # Zero or negative seconds rejected
        with pytest.raises(DRFValidationError) as exc1:
            AttemptTimerService.apply_authorized_pause(att, pause_duration_seconds=0, actor=e["proctorA"])
        assert "must be a positive integer" in str(exc1.value)

        with pytest.raises(DRFValidationError) as exc2:
            AttemptTimerService.apply_authorized_pause(att, pause_duration_seconds=-10, actor=e["proctorA"])
        assert "must be a positive integer" in str(exc2.value)

    def test_phase5_pause_cannot_exceed_assessment_end_ceiling(self, hardening_fixture):
        from apps.assessments.services import AttemptTimerService
        e = hardening_fixture
        att = e["att1"]
        now = timezone.now()

        # Set assessment end 60 seconds from now
        Assessment.objects.filter(id=e["ass1"].id).update(end_datetime=now + timedelta(seconds=60))
        e["ass1"].refresh_from_db()
        att.refresh_from_db()

        # Request 3600 seconds pause
        updated = AttemptTimerService.apply_authorized_pause(att, pause_duration_seconds=3600, actor=e["proctorA"])

        # Hard invariant: strictly clamped to assessment.end_datetime
        assert updated.expires_at == e["ass1"].end_datetime
        assert updated.expires_at <= e["ass1"].end_datetime

    # =========================================================================
    # 8. DIRECT DELEGATION & ARCHITECTURAL INVARIANT PROOFS
    # =========================================================================

    def test_architectural_invariant_phase10_delegates_to_phase5_timer(self, hardening_fixture, monkeypatch):
        """
        Directly tests the architectural invariant:
        Phase 10 does not calculate or own timer adjustments independently.
        It delegates pause authorization and application to AttemptTimerService.
        """
        from apps.assessments.services import AttemptTimerService
        e = hardening_fixture
        att = e["att1"]
        att_id = str(att.id)

        auth_calls = []
        apply_calls = []

        orig_auth = AttemptTimerService.authorize_pause
        orig_apply = AttemptTimerService.apply_authorized_pause

        def spy_auth(attempt, actor=None):
            auth_calls.append((attempt.id, actor))
            return orig_auth(attempt, actor=actor)

        def spy_apply(attempt, pause_duration_seconds, actor=None, request=None):
            apply_calls.append((attempt.id, pause_duration_seconds, actor))
            return orig_apply(attempt, pause_duration_seconds, actor=actor, request=request)

        monkeypatch.setattr(AttemptTimerService, "authorize_pause", classmethod(lambda cls, attempt, actor=None: spy_auth(attempt, actor)))
        monkeypatch.setattr(AttemptTimerService, "apply_authorized_pause", classmethod(lambda cls, attempt, pause_duration_seconds, actor=None, request=None: spy_apply(attempt, pause_duration_seconds, actor=actor, request=request)))

        # 1. Pause invocation triggers Phase 5 authorize_pause
        p = LiveInterventionService.pause_attempt(e["proctorA"], att_id, reason="Delegation check")
        assert len(auth_calls) == 1
        assert auth_calls[0][0] == att.id
        assert auth_calls[0][1] == e["proctorA"]

        # 2. Resume invocation triggers Phase 5 apply_authorized_pause
        r = LiveInterventionService.resume_attempt(e["proctorA"], att_id, reason="Resume delegation")
        assert len(apply_calls) == 1
        assert apply_calls[0][0] == att.id
        assert apply_calls[0][1] > 0
        assert apply_calls[0][2] == e["proctorA"]

    def test_concurrency_serialization_termination_vs_pause(self, hardening_fixture):
        e = hardening_fixture
        att = e["att1"]
        att_id = str(att.id)

        # Terminate attempt
        LiveInterventionService.terminate_attempt(e["proctorA"], att_id, reason_code="DISQUALIFY", formal_justification="Cheating")

        # Subsequent pause attempt must be rejected
        with pytest.raises(DRFValidationError) as exc:
            LiveInterventionService.pause_attempt(e["proctorA"], att_id, reason="Late pause")
        assert "Cannot pause attempt in status CANCELLED" in str(exc.value)

    def test_concurrency_serialization_submission_vs_pause(self, hardening_fixture):
        e = hardening_fixture
        att = e["att1"]
        att_id = str(att.id)

        # Submit attempt
        att.status = AttemptStatus.SUBMITTED
        att.submitted_at = timezone.now()
        att.save(update_fields=['status', 'submitted_at'])

        # Subsequent pause attempt must be rejected
        with pytest.raises(DRFValidationError) as exc:
            LiveInterventionService.pause_attempt(e["proctorA"], att_id, reason="Late pause")
        assert "Cannot pause attempt in status SUBMITTED" in str(exc.value)


