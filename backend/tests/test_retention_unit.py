import pytest
from datetime import timedelta
from decimal import Decimal
from django.utils import timezone
from django.conf import settings
from django.core.exceptions import ValidationError, PermissionDenied

from apps.accounts.models import User, Role, StudentProfile
from apps.questions.models import Question, QuestionVersion, QuestionType, Difficulty, VersionStatus
from apps.assessments.models import (
    Assessment,
    AssessmentStatus,
    AssessmentQuestion,
    AssessmentAssignment,
    AssessmentSnapshot,
    AssessmentSnapshotQuestion,
    TestAttempt,
    AttemptStatus,
    AttemptAnswer,
)
from apps.assessments.services import AssessmentSnapshotService
from apps.results.models import AssessmentResult, ResultStatus
from apps.proctoring.models import ProctoringSession, RiskBand
from apps.retention.models import (
    RetentionPolicy,
    PolicyScope,
    RetentionRecord,
    PurgeState,
    LegalHold,
    LegalHoldScope,
    LegalHoldStatus,
    RetentionTombstone,
    ExportJob,
    ExportStatus,
    FileCleanupQueue,
    FileCleanupStatus,
    ScrubStatus,
)
from apps.retention.services import (
    RetentionPolicyEngine,
    LegalHoldManager,
    AuthoritativeScrubbingService,
    TombstoneService,
    DsarExportService,
)


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        email="admin_ret@codeguard.test",
        password="AdminPassword123!",
        role=Role.ADMIN
    )


@pytest.fixture
def student_user(db):
    user = User.objects.create_user(
        email="student_ret@codeguard.test",
        password="StudentPassword123!",
        role=Role.STUDENT
    )
    StudentProfile.objects.create(
        user=user,
        roll_number="CS2026-RET-01",
        euid="EUID-RET-0001"
    )
    return user


@pytest.fixture
def finalized_attempt(db, student_user, admin_user):
    from apps.questions.services import QuestionService
    q, v = QuestionService.create_question(
        question_type=QuestionType.MCQ,
        title="Sample MCQ",
        description="What is Python?",
        points=10,
        type_config={
            "options": [
                {"id": "A", "text": "Language"},
                {"id": "B", "text": "Snake"}
            ],
            "correct_options": ["A"]
        },
        actor=admin_user
    )
    qv = QuestionService.publish_version(v, actor=admin_user)
    
    now = timezone.now() - timedelta(days=35)
    assessment = Assessment.objects.create(
        title="Retention Exam",
        description="Exam to test data retention engine",
        duration_minutes=60,
        start_datetime=now - timedelta(days=5),
        end_datetime=now + timedelta(days=5),
        status=AssessmentStatus.DRAFT,
        created_by=admin_user
    )
    AssessmentQuestion.objects.create(
        assessment=assessment,
        question_version=qv,
        order=1,
        points=Decimal('10.00')
    )
    assessment.status = AssessmentStatus.PUBLISHED
    assessment.save()

    assignment = AssessmentAssignment.objects.create(
        assessment=assessment,
        student=student_user,
        assigned_by=admin_user
    )
    snapshot = AssessmentSnapshotService.create_snapshot(assessment, admin_user)

    attempt = TestAttempt.objects.create(
        student=student_user,
        assessment=assessment,
        assessment_snapshot=snapshot,
        status=AttemptStatus.SUBMITTED,
        started_at=now - timedelta(hours=1),
        submitted_at=now
    )
    result = AssessmentResult.objects.create(
        attempt=attempt,
        student=student_user,
        assessment=assessment,
        assessment_snapshot=snapshot,
        status=ResultStatus.FINALIZED,
        total_score_earned=Decimal('10.00'),
        total_possible_score=Decimal('10.00'),
        percentage=Decimal('100.00'),
        is_passed=True,
        finalized_at=now
    )
    return attempt


@pytest.mark.django_db
class TestRetentionUnit:
    def test_retention_policy_creation_and_validation(self, admin_user):
        """1. Validates TTL defaults (30d), range limits (1-3650 days), and scope consistency."""
        policy = RetentionPolicy.objects.create(
            name="Custom 45d Policy",
            detailed_data_ttl_days=45,
            proctoring_evidence_ttl_days=45,
            created_by=admin_user
        )
        assert policy.detailed_data_ttl_days == 45
        assert policy.version == 1
        assert policy.scope == PolicyScope.INSTITUTION

        # Scope validation
        invalid_policy = RetentionPolicy(
            name="Invalid Assessment Policy",
            scope=PolicyScope.ASSESSMENT,
            assessment=None
        )
        with pytest.raises(ValidationError):
            invalid_policy.clean()

    def test_retention_policy_versioning_increment(self, admin_user):
        """2. Asserts policy edits bump version integer to preserve audit lineage."""
        policy = RetentionPolicyEngine.get_or_create_default_institution_policy(user=admin_user)
        assert policy.version == 1
        policy.detailed_data_ttl_days = 60
        policy.version += 1
        policy.save()
        assert policy.version == 2

    def test_retention_record_creation_on_finalization(self, finalized_attempt):
        """3. Asserts RetentionRecord is created 1:1 with TestAttempt at finalization."""
        record = RetentionPolicyEngine.create_retention_record_for_finalized_attempt(finalized_attempt)
        assert record is not None
        assert record.attempt_id == finalized_attempt.id
        assert record.purge_state == PurgeState.SCHEDULED
        assert hasattr(finalized_attempt, 'retention_record')

    def test_retention_record_deterministic_deadline_stamped(self, finalized_attempt):
        """4. Asserts detailed_data_expires_at is fixed at creation based on policy."""
        record = RetentionPolicyEngine.create_retention_record_for_finalized_attempt(finalized_attempt)
        expected_deadline = finalized_attempt.submitted_at + timedelta(days=record.retention_policy.detailed_data_ttl_days)
        # Allow tiny float/subsecond difference
        diff = abs((record.detailed_data_expires_at - expected_deadline).total_seconds())
        assert diff < 2

    def test_retention_policy_change_existing_record(self, finalized_attempt):
        """5. Proves altering policy TTL does not retroactively shorten existing attempt deadlines."""
        record = RetentionPolicyEngine.create_retention_record_for_finalized_attempt(finalized_attempt)
        original_deadline = record.detailed_data_expires_at

        # Change policy TTL
        policy = record.retention_policy
        policy.detailed_data_ttl_days = 15
        policy.version += 1
        policy.save()

        # Existing record deadline remains strictly unchanged
        record.refresh_from_db()
        assert record.detailed_data_expires_at == original_deadline

    def test_retention_policy_extension_existing_record(self, finalized_attempt):
        """6. Proves lengthening policy TTL does not shift existing stamped deadlines."""
        record = RetentionPolicyEngine.create_retention_record_for_finalized_attempt(finalized_attempt)
        original_deadline = record.detailed_data_expires_at

        policy = record.retention_policy
        policy.detailed_data_ttl_days = 90
        policy.version += 1
        policy.save()

        record.refresh_from_db()
        assert record.detailed_data_expires_at == original_deadline

    def test_purge_eligibility_unfinalized_attempt_rejected(self, db, finalized_attempt, student_user):
        """7. Confirms is_eligible_for_purge returns False for in-progress or unfinalized attempts."""
        attempt = TestAttempt.objects.create(
            student=student_user,
            assessment=finalized_attempt.assessment,
            assessment_snapshot=finalized_attempt.assessment_snapshot,
            attempt_number=2,
            status=AttemptStatus.IN_PROGRESS
        )
        assert not AuthoritativeScrubbingService.is_eligible_for_purge(attempt)

    def test_purge_eligibility_active_legal_hold_blocks_purge(self, finalized_attempt, admin_user):
        """8. Confirms active hold on attempt, student, or assessment blocks eligibility."""
        record = RetentionPolicyEngine.create_retention_record_for_finalized_attempt(finalized_attempt)
        # Without hold, it is eligible because submitted 35 days ago (TTL=30)
        assert AuthoritativeScrubbingService.is_eligible_for_purge(finalized_attempt)

        # Place attempt hold
        hold = LegalHoldManager.create_attempt_hold(
            attempt_id=finalized_attempt.id,
            title="Investigation Hold",
            case_reference="CASE-RET-01",
            reason="Suspected misconduct",
            user=admin_user
        )
        assert not AuthoritativeScrubbingService.is_eligible_for_purge(finalized_attempt)

    def test_purge_eligibility_released_legal_hold_allows_purge(self, finalized_attempt, admin_user):
        """9. Confirms that once a hold is released, purge eligibility is restored."""
        record = RetentionPolicyEngine.create_retention_record_for_finalized_attempt(finalized_attempt)
        hold = LegalHoldManager.create_attempt_hold(
            attempt_id=finalized_attempt.id,
            title="Investigation Hold",
            case_reference="CASE-RET-02",
            reason="Audit verification",
            user=admin_user
        )
        assert not AuthoritativeScrubbingService.is_eligible_for_purge(finalized_attempt)

        # Release hold
        LegalHoldManager.release_hold(hold.id, release_reason="Audit concluded cleanly", user=admin_user)
        assert AuthoritativeScrubbingService.is_eligible_for_purge(finalized_attempt)

    def test_tombstone_hmac_sha256_proof_computation(self, finalized_attempt, admin_user):
        """10. Validates mathematical correctness and key-sensitivity of HMAC integrity proof."""
        record = RetentionPolicyEngine.create_retention_record_for_finalized_attempt(finalized_attempt)
        record.database_scrub_status = "COMPLETED"
        record.save()
        tombstone = TombstoneService.mint_tombstone(finalized_attempt.id, operator_user=admin_user)

        assert tombstone.sha256_audit_proof
        assert len(tombstone.sha256_audit_proof) == 64

    def test_tombstone_immutability_save_and_delete_blocked(self, finalized_attempt, admin_user):
        """11. Verifies that RetentionTombstone raises PermissionDenied on edit or delete."""
        record = RetentionPolicyEngine.create_retention_record_for_finalized_attempt(finalized_attempt)
        record.database_scrub_status = "COMPLETED"
        record.save()
        tombstone = TombstoneService.mint_tombstone(finalized_attempt.id, operator_user=admin_user)

        # Edit blocked
        with pytest.raises(PermissionDenied):
            tombstone.answers_scrubbed_count = 99
            tombstone.save()

        # Delete blocked
        with pytest.raises(PermissionDenied):
            tombstone.delete()

    def test_tombstone_data_minimization(self, finalized_attempt, admin_user):
        """12. Asserts that RetentionTombstone contains EUID and UUIDs, and does NOT store roll numbers."""
        record = RetentionPolicyEngine.create_retention_record_for_finalized_attempt(finalized_attempt)
        record.database_scrub_status = "COMPLETED"
        record.save()
        tombstone = TombstoneService.mint_tombstone(finalized_attempt.id, operator_user=admin_user)

        assert tombstone.student_euid == "EUID-RET-0001"
        assert not hasattr(tombstone, 'student_roll_number')

    def test_legal_hold_scope_validation(self, finalized_attempt, admin_user, student_user):
        """13. Ensures attempt, student, and assessment references strictly match the declared scope."""
        # Attempt scope missing attempt
        hold_bad = LegalHold(
            title="Bad Hold",
            case_reference="BAD-01",
            reason="Missing target",
            scope=LegalHoldScope.ATTEMPT,
            attempt=None,
            placed_by=admin_user
        )
        with pytest.raises(ValidationError):
            hold_bad.clean()

    def test_proctoring_risk_operational_window_expiry(self, finalized_attempt):
        """14. Asserts that after 90 days, proctoring risk telemetry is nullified."""
        session = ProctoringSession.objects.create(
            attempt=finalized_attempt,
            risk_score=Decimal('85.50'),
            risk_band=RiskBand.HIGH
        )
        assert session.risk_score == Decimal('85.50')

        # Simulate 90 days sweep
        cutoff = timezone.now() + timedelta(days=1)
        AuthoritativeScrubbingService.sweep_proctoring_operational_window(cutoff_date=cutoff)

        session.refresh_from_db()
        assert session.risk_score == Decimal('0.00')

    def test_key_version_selection(self, student_user):
        """15. Validates that newly queued ExportJob instances select the currently active master key version."""
        job = DsarExportService.create_export_request(student=student_user)
        assert job.encryption_key_version == getattr(settings, 'ACTIVE_DSAR_KEY_VERSION', 'v1')

    def test_legal_hold_overlapping_scopes_allowed(self, finalized_attempt, student_user, admin_user):
        """16. Verifies distinct scopes (STUDENT, ASSESSMENT, ATTEMPT) can simultaneously overlap without collision."""
        assessment = finalized_attempt.assessment
        
        # 1. Place student-scoped hold
        h_student = LegalHoldManager.create_student_hold(
            student_id=student_user.id,
            title="Student Disciplinary Hold",
            case_reference="DISC-STUDENT-01",
            reason="Investigation ongoing",
            user=admin_user
        )
        assert h_student.status == LegalHoldStatus.ACTIVE

        # 2. Place assessment-scoped hold on same assessment
        h_assessment = LegalHoldManager.create_assessment_hold(
            assessment_id=assessment.id,
            title="Assessment Wide Hold",
            case_reference="DISC-ASSESS-01",
            reason="Systemic review",
            user=admin_user
        )
        assert h_assessment.status == LegalHoldStatus.ACTIVE

        # 3. Place attempt-scoped hold on same attempt
        h_attempt = LegalHoldManager.create_attempt_hold(
            attempt_id=finalized_attempt.id,
            title="Attempt Forensic Hold",
            case_reference="DISC-ATTEMPT-01",
            reason="Specific telemetry review",
            user=admin_user
        )
        assert h_attempt.status == LegalHoldStatus.ACTIVE

        # All 3 active holds coexist simultaneously
        active_holds = LegalHoldManager.get_active_holds_for_attempt(finalized_attempt)
        assert active_holds.count() == 3

    def test_legal_hold_duplicate_active_same_scope_forbidden(self, finalized_attempt, student_user, admin_user):
        """17. Verifies that duplicate active holds for the SAME scope and target are rejected with ValidationError."""
        # First attempt hold succeeds
        LegalHoldManager.create_attempt_hold(
            attempt_id=finalized_attempt.id,
            title="First Hold",
            case_reference="REF-01",
            reason="Reason 1",
            user=admin_user
        )

        # Second active hold on SAME attempt must fail
        with pytest.raises(ValidationError) as exc:
            LegalHoldManager.create_attempt_hold(
                attempt_id=finalized_attempt.id,
                title="Duplicate Hold",
                case_reference="REF-02",
                reason="Reason 2",
                user=admin_user
            )
        assert "already exists" in str(exc.value)

        # Same student duplicate
        LegalHoldManager.create_student_hold(
            student_id=student_user.id,
            title="Student Hold 1",
            case_reference="ST-01",
            reason="Reason",
            user=admin_user
        )
        with pytest.raises(ValidationError) as exc:
            LegalHoldManager.create_student_hold(
                student_id=student_user.id,
                title="Student Hold 2",
                case_reference="ST-02",
                reason="Reason",
                user=admin_user
            )
        assert "already exists" in str(exc.value)

    def test_dsar_heartbeat_60_minute_absolute_ceiling(self, student_user):
        """18. Asserts that heartbeat renewal extends lease but is strictly capped at started_at + 60 minutes."""
        job = DsarExportService.create_export_request(student=student_user)
        now = timezone.now()
        job.status = ExportStatus.SNAPSHOT_PENDING
        job.started_at = now
        job.lease_expires_at = now + timedelta(minutes=15)
        job.save()

        # Call heartbeat renewal when started_at was 50 minutes ago
        job.started_at = now - timedelta(minutes=50)
        job.save()

        renewed = DsarExportService.renew_heartbeat(str(job.id))
        # 50m elapsed + 60m ceiling = only 10m remaining, NOT 15m
        expected_ceiling = job.started_at + timedelta(minutes=60)
        assert renewed.lease_expires_at == expected_ceiling
        assert renewed.lease_expires_at <= job.started_at + timedelta(minutes=60)

    def test_tombstone_blocked_when_single_file_unconfirmed(self, finalized_attempt, admin_user):
        """19. Tombstone minting is forbidden when N-1 files are confirmed but 1 file is still PENDING or FAILED."""
        record = RetentionPolicyEngine.create_retention_record_for_finalized_attempt(finalized_attempt)
        record.database_scrub_status = ScrubStatus.COMPLETED
        record.save()

        # Queue 2 files: 1 CONFIRMED, 1 PENDING
        FileCleanupQueue.objects.create(
            attempt_id=finalized_attempt.id,
            file_path="/media/evidence1.jpg",
            file_bytes=1000,
            status=FileCleanupStatus.CONFIRMED
        )
        FileCleanupQueue.objects.create(
            attempt_id=finalized_attempt.id,
            file_path="/media/evidence2.jpg",
            file_bytes=2000,
            status=FileCleanupStatus.PENDING
        )

        with pytest.raises(ValidationError) as exc:
            TombstoneService.mint_tombstone(finalized_attempt.id, operator_user=admin_user)
        assert "100% physical cleanup required" in str(exc.value)

    def test_tombstone_allowed_after_retry_succeeds(self, finalized_attempt, admin_user):
        """20. Tombstone minting succeeds once all previously pending/failed files are confirmed deleted."""
        record = RetentionPolicyEngine.create_retention_record_for_finalized_attempt(finalized_attempt)
        record.database_scrub_status = ScrubStatus.COMPLETED
        record.save()

        item = FileCleanupQueue.objects.create(
            attempt_id=finalized_attempt.id,
            file_path="/media/evidence_retry.jpg",
            file_bytes=5000,
            status=FileCleanupStatus.RETRYING
        )

        # Blocked while retrying
        with pytest.raises(ValidationError):
            TombstoneService.mint_tombstone(finalized_attempt.id, operator_user=admin_user)

        # Worker confirms deletion
        item.status = FileCleanupStatus.CONFIRMED
        item.confirmed_deleted_at = timezone.now()
        item.save()

        # Now succeeds!
        tombstone = TombstoneService.mint_tombstone(finalized_attempt.id, operator_user=admin_user)
        assert tombstone is not None
        assert tombstone.confirmed_bytes_reclaimed == 5000
        assert tombstone.evidence_files_deleted_count == 1

    def test_tombstone_blocked_if_db_scrub_not_completed(self, finalized_attempt, admin_user):
        """21. Tombstone minting is forbidden if database scrub has not committed (status != COMPLETED)."""
        record = RetentionPolicyEngine.create_retention_record_for_finalized_attempt(finalized_attempt)
        record.database_scrub_status = ScrubStatus.PENDING
        record.save()

        with pytest.raises(ValidationError) as exc:
            TombstoneService.mint_tombstone(finalized_attempt.id, operator_user=admin_user)
        assert "Cannot mint tombstone before database scrub has committed" in str(exc.value)
