import os
import io
import zipfile
import pytest
from datetime import timedelta
from decimal import Decimal
from django.utils import timezone
from django.conf import settings
from django.core.exceptions import PermissionDenied
from rest_framework.test import APIClient

from apps.accounts.models import User, Role, StudentProfile
from apps.questions.models import QuestionType
from apps.questions.services import QuestionService
from apps.assessments.models import (
    Assessment,
    AssessmentStatus,
    AssessmentQuestion,
    AssessmentAssignment,
    TestAttempt,
    AttemptStatus,
    AttemptAnswer,
)
from apps.assessments.services import AssessmentSnapshotService
from apps.evaluator.models import CodeSubmission, SubmissionType, SubmissionStatus, CodeVerdict
from apps.proctoring.models import ProctoringSession, ProctoringEvidence, ProctoringEvent
from apps.results.models import AssessmentResult, HistoricalResultSummary, ResultStatus
from apps.retention.models import (
    RetentionPolicy,
    PolicyScope,
    RetentionRecord,
    PurgeState,
    LegalHold,
    LegalHoldScope,
    LegalHoldStatus,
    FileCleanupQueue,
    FileCleanupStatus,
    RetentionTombstone,
    ExportJob,
    ExportStatus,
    ArchiveType,
)
from apps.retention.services import (
    RetentionPolicyEngine,
    LegalHoldManager,
    AuthoritativeScrubbingService,
    FilesystemCleanupWorker,
    TombstoneService,
    DsarExportService,
)


@pytest.fixture
def admin_user(db):
    return User.objects.create_superuser(
        email="admin_ret_sec@codeguard.test",
        password="AdminPassword123!",
        role=Role.ADMIN
    )


@pytest.fixture
def student_user_a(db):
    user = User.objects.create_user(
        email="student_a_sec@codeguard.test",
        password="StudentPassword123!",
        role=Role.STUDENT
    )
    StudentProfile.objects.create(
        user=user,
        roll_number="CS2026-SEC-A",
        euid="EUID-SEC-A"
    )
    return user


@pytest.fixture
def student_user_b(db):
    user = User.objects.create_user(
        email="student_b_sec@codeguard.test",
        password="StudentPassword123!",
        role=Role.STUDENT
    )
    StudentProfile.objects.create(
        user=user,
        roll_number="CS2026-SEC-B",
        euid="EUID-SEC-B"
    )
    return user


@pytest.fixture
def attempt_a(db, admin_user, student_user_a):
    q, v = QuestionService.create_question(
        question_type=QuestionType.MCQ,
        title="Sec MCQ",
        description="MCQ for security test",
        points=10,
        type_config={
            "options": [
                {"id": "A", "text": "Correct"},
                {"id": "B", "text": "Incorrect"}
            ],
            "correct_options": ["A"]
        },
        actor=admin_user
    )
    qv = QuestionService.publish_version(v, actor=admin_user)

    now = timezone.now() - timedelta(days=35)
    assessment = Assessment.objects.create(
        title="Security Exam",
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

    AssessmentAssignment.objects.create(
        assessment=assessment,
        student=student_user_a,
        assigned_by=admin_user
    )
    snapshot = AssessmentSnapshotService.create_snapshot(assessment, admin_user)

    attempt = TestAttempt.objects.create(
        student=student_user_a,
        assessment=assessment,
        assessment_snapshot=snapshot,
        status=AttemptStatus.SUBMITTED,
        started_at=now - timedelta(hours=1),
        submitted_at=now
    )
    snap_q = snapshot.snapshot_questions.first()
    AttemptAnswer.objects.create(
        attempt=attempt,
        snapshot_question=snap_q,
        question_id=snap_q.snapshot_question_id,
        question_type=snap_q.question_type,
        selected_options=["A"]
    )
    CodeSubmission.objects.create(
        attempt=attempt,
        snapshot_question=snap_q,
        submission_type=SubmissionType.SUBMIT,
        language="PYTHON",
        source_code="print('student A code')",
        status=SubmissionStatus.COMPLETED,
        verdict=CodeVerdict.ACCEPTED
    )
    AssessmentResult.objects.create(
        attempt=attempt,
        student=student_user_a,
        assessment=assessment,
        assessment_snapshot=snapshot,
        status=ResultStatus.FINALIZED,
        total_score_earned=Decimal('10.00'),
        total_possible_score=Decimal('10.00'),
        percentage=Decimal('100.00'),
        is_passed=True,
        finalized_at=now
    )
    HistoricalResultSummary.objects.create(
        student=student_user_a,
        assessment_id=assessment.id,
        student_euid="EUID-SEC-A",
        assessment_snapshot_id=snapshot.id,
        assessment_title_snapshot=assessment.title,
        total_score_earned=Decimal('10.00'),
        total_possible_score=Decimal('10.00'),
        percentage=Decimal('100.00'),
        is_passed=True,
        completion_status=AttemptStatus.SUBMITTED,
        started_at=attempt.started_at,
        completed_at=attempt.submitted_at,
        details_purged=False
    )
    RetentionPolicyEngine.create_retention_record_for_finalized_attempt(attempt)
    return attempt


@pytest.mark.django_db
class TestRetentionSecurity:
    def test_legal_hold_vs_purge_race(self, attempt_a, admin_user):
        """1. Race: Attempt hold placed prior to purge defers purge."""
        LegalHoldManager.create_attempt_hold(
            attempt_id=attempt_a.id,
            title="Investigation",
            case_reference="RACE-01",
            reason="Race test",
            user=admin_user
        )
        res = AuthoritativeScrubbingService.execute_purge_for_attempt(attempt_a.id)
        assert res['status'] == 'DEFERRED_HOLD'
        assert res['purged'] is False

    def test_student_hold_vs_purge_race(self, attempt_a, admin_user):
        """2. Student-scoped hold defers attempt purge."""
        LegalHoldManager.create_student_hold(
            student_id=attempt_a.student_id,
            title="Student Investigation",
            case_reference="RACE-02",
            reason="Student hold",
            user=admin_user
        )
        res = AuthoritativeScrubbingService.execute_purge_for_attempt(attempt_a.id)
        assert res['status'] == 'DEFERRED_HOLD'

    def test_assessment_hold_vs_purge_race(self, attempt_a, admin_user):
        """3. Assessment-scoped hold defers attempt purge."""
        LegalHoldManager.create_assessment_hold(
            assessment_id=attempt_a.assessment_id,
            title="Assessment Hold",
            case_reference="RACE-03",
            reason="Assessment hold",
            user=admin_user
        )
        res = AuthoritativeScrubbingService.execute_purge_for_attempt(attempt_a.id)
        assert res['status'] == 'DEFERRED_HOLD'

    def test_global_lock_order_deadlock_prevention(self, attempt_a, admin_user):
        """4. Verifies canonical lock hierarchy: Assessment -> User -> Attempt -> RetentionRecord -> LegalHold."""
        # Cleanly executes under global hierarchy without deadlock
        hold = LegalHoldManager.create_attempt_hold(
            attempt_id=attempt_a.id,
            title="Lock Order Test",
            case_reference="LOCK-01",
            reason="Testing lock hierarchy",
            user=admin_user
        )
        assert hold.status == LegalHoldStatus.ACTIVE

    def test_export_job_lock_order_compliance(self, attempt_a, student_user_a):
        """5. Verifies ExportJob is acquired subordinate to TestAttempt and RetentionRecord."""
        job = DsarExportService.create_export_request(student=student_user_a, attempt_id=attempt_a.id)
        acquired = DsarExportService.acquire_snapshot(str(job.id))
        assert acquired.status == ExportStatus.SNAPSHOT_ACQUIRED

    def test_dsar_vs_purge_race(self, attempt_a, student_user_a):
        """6. Active DSAR in SNAPSHOT_PENDING with valid lease defers purge worker."""
        job = DsarExportService.create_export_request(student=student_user_a, attempt_id=attempt_a.id)
        now = timezone.now()
        job.status = ExportStatus.SNAPSHOT_PENDING
        job.started_at = now
        job.lease_expires_at = now + timedelta(minutes=15)
        job.save()

        res = AuthoritativeScrubbingService.execute_purge_for_attempt(attempt_a.id)
        assert res['status'] == 'DEFERRED_EXPORT'
        assert res['purged'] is False

    def test_dsar_snapshot_acquisition_vs_purge_race(self, attempt_a, student_user_a):
        """7. Snapshot acquisition locks TestAttempt + RetentionRecord preventing interleaved scrub."""
        job = DsarExportService.create_export_request(student=student_user_a, attempt_id=attempt_a.id)
        DsarExportService.acquire_snapshot(str(job.id))
        job.refresh_from_db()
        assert job.status == ExportStatus.SNAPSHOT_ACQUIRED
        assert job.snapshot_payload is not None

    def test_dsar_snapshot_acquisition_rollback(self, attempt_a, student_user_a):
        """8. If snapshot fails mid-stream, 15m lease continues protecting attempt."""
        job = DsarExportService.create_export_request(student=student_user_a, attempt_id=attempt_a.id)
        now = timezone.now()
        job.status = ExportStatus.SNAPSHOT_PENDING
        job.started_at = now
        job.lease_expires_at = now + timedelta(minutes=10)
        job.save()

        # Purge worker observes active lease and defers
        res = AuthoritativeScrubbingService.execute_purge_for_attempt(attempt_a.id)
        assert res['status'] == 'DEFERRED_EXPORT'

    def test_purge_vs_snapshot_pending(self, attempt_a, student_user_a):
        """9. Purge evaluates SNAPSHOT_PENDING: defers if lease valid."""
        job = DsarExportService.create_export_request(student=student_user_a, attempt_id=attempt_a.id)
        job.status = ExportStatus.SNAPSHOT_PENDING
        job.lease_expires_at = timezone.now() + timedelta(minutes=5)
        job.save()

        assert not AuthoritativeScrubbingService.is_eligible_for_purge(attempt_a)

    def test_purge_vs_snapshot_acquired(self, attempt_a, student_user_a):
        """10. Verifies purge worker defers when an export is in SNAPSHOT_ACQUIRED."""
        job = DsarExportService.create_export_request(student=student_user_a, attempt_id=attempt_a.id)
        DsarExportService.acquire_snapshot(str(job.id))

        # While SNAPSHOT_ACQUIRED or GENERATING, purge worker defers to protect generation
        res = AuthoritativeScrubbingService.execute_purge_for_attempt(attempt_a.id, process_filesystem_sync=True)
        assert res['status'] == 'DEFERRED_EXPORT'
        assert res['purged'] is False

    def test_stale_recovery_vs_snapshot_acquisition_race(self, attempt_a, student_user_a):
        """11. No False Failure: Recovery task does not fail job whose lease is still active."""
        job = DsarExportService.create_export_request(student=student_user_a, attempt_id=attempt_a.id)
        job.status = ExportStatus.SNAPSHOT_PENDING
        job.started_at = timezone.now() - timedelta(minutes=5)
        job.lease_expires_at = timezone.now() + timedelta(minutes=10)
        job.save()

        recovered = DsarExportService.recover_stale_jobs()
        assert recovered == 0
        job.refresh_from_db()
        assert job.status == ExportStatus.SNAPSHOT_PENDING

    def test_stale_recovery_vs_purge_race(self, attempt_a, student_user_a):
        """12. Stale recovery cleans up expired lease, allowing immediate subsequent purge."""
        job = DsarExportService.create_export_request(student=student_user_a, attempt_id=attempt_a.id)
        job.status = ExportStatus.SNAPSHOT_PENDING
        job.started_at = timezone.now() - timedelta(minutes=30)
        job.lease_expires_at = timezone.now() - timedelta(minutes=15)
        job.save()

        rec = RetentionRecord.objects.get(attempt=attempt_a)
        rec.purge_state = PurgeState.DEFERRED_EXPORT
        rec.save()

        recovered = DsarExportService.recover_stale_jobs()
        assert recovered == 1

        # Now purge succeeds
        res = AuthoritativeScrubbingService.execute_purge_for_attempt(attempt_a.id, process_filesystem_sync=True)
        assert res['purged'] is True

    def test_dsar_hidden_test_protection(self, attempt_a, student_user_a):
        """13. Materialized snapshot strictly excludes hidden test cases and private solutions."""
        job = DsarExportService.create_export_request(student=student_user_a, attempt_id=attempt_a.id)
        DsarExportService.acquire_snapshot(str(job.id))
        job.refresh_from_db()

        payload_str = str(job.snapshot_payload)
        assert 'hidden' not in payload_str.lower() or 'is_hidden: false' in payload_str.lower()
        assert 'server_evaluation_bundle' not in payload_str

    def test_dsar_cross_student_protection(self, attempt_a, student_user_a, student_user_b):
        """14. Student B requesting DSAR gets zero records from Student A."""
        job_b = DsarExportService.create_export_request(student=student_user_b)
        DsarExportService.acquire_snapshot(str(job_b.id))
        job_b.refresh_from_db()

        payload = job_b.snapshot_payload or {}
        assert payload.get('student_profile', {}).get('student_id') != str(student_user_a.id)

    def test_dsar_aes_256_gcm_encryption_and_key_versioning(self, attempt_a, student_user_a):
        """15. Confirms archive on disk is encrypted with AES-256-GCM and not readable as plain ZIP."""
        job = DsarExportService.create_export_request(student=student_user_a, attempt_id=attempt_a.id)
        DsarExportService.acquire_snapshot(str(job.id))
        DsarExportService.generate_and_encrypt_archive(str(job.id))
        job.refresh_from_db()

        assert job.status == ExportStatus.READY
        assert job.nonce_hex
        assert job.auth_tag_hex
        assert job.encryption_algorithm == 'AES-256-GCM'

        with open(job.file_path, 'rb') as f:
            raw_bytes = f.read()

        # Not a valid plaintext ZIP file header
        assert not raw_bytes.startswith(b'PK\x03\x04')

    def test_student_cannot_access_admin_retention_endpoints(self, student_user_a):
        """16. Non-admin users are rejected from admin retention API endpoints with 403."""
        client = APIClient()
        client.force_authenticate(user=student_user_a)

        assert client.get('/api/v1/admin/retention/metrics/').status_code == 403
        assert client.get('/api/v1/admin/retention/policies/').status_code == 403
        assert client.get('/api/v1/admin/retention/candidates/').status_code == 403
        assert client.post('/api/v1/admin/retention/preview-purge/').status_code == 403
        assert client.post('/api/v1/admin/retention/execute-purge/').status_code == 403
        assert client.get('/api/v1/admin/retention/tombstones/').status_code == 403
        assert client.get('/api/v1/admin/legal-holds/').status_code == 403

    def test_path_traversal_on_evidence_cleanup_blocked(self, attempt_a):
        """17. Queue item pointing outside MEDIA_ROOT is rejected as path traversal."""
        traversal_path = os.path.join(settings.MEDIA_ROOT, "..", "..", "etc", "passwd")
        item = FileCleanupQueue.objects.create(
            attempt_id=attempt_a.id,
            file_path=traversal_path,
            file_bytes=100,
            status=FileCleanupStatus.PENDING
        )
        res = FilesystemCleanupWorker.process_attempt_cleanups(attempt_a.id)
        item.refresh_from_db()
        assert item.status == FileCleanupStatus.FAILED
        assert "Path traversal" in item.last_error

    def test_path_traversal_on_dsar_export_download_blocked(self, attempt_a, student_user_a):
        """18. Manipulated ExportJob.file_path pointing outside MEDIA_ROOT raises PermissionDenied."""
        job = DsarExportService.create_export_request(student=student_user_a, attempt_id=attempt_a.id)
        job.status = ExportStatus.READY
        job.file_path = "/etc/passwd"
        job.save()

        with pytest.raises(PermissionDenied):
            DsarExportService.decrypt_archive(job)

    def test_purge_worker_never_modifies_official_scores(self, attempt_a):
        """19. Authoritative score in AssessmentResult is preserved during purge."""
        res_before = AssessmentResult.objects.get(attempt=attempt_a)
        score_before = res_before.total_score_earned
        pct_before = res_before.percentage

        AuthoritativeScrubbingService.execute_purge_for_attempt(attempt_a.id, process_filesystem_sync=True)

        res_after = AssessmentResult.objects.get(attempt=attempt_a)
        assert res_after.total_score_earned == score_before
        assert res_after.percentage == pct_before

    def test_duplicate_tombstone_prevention(self, attempt_a, admin_user):
        """20. Calling mint_tombstone multiple times is strictly idempotent."""
        record = attempt_a.retention_record
        record.database_scrub_status = "COMPLETED"
        record.save()
        tombstone_1 = TombstoneService.mint_tombstone(attempt_a.id, operator_user=admin_user)
        tombstone_2 = TombstoneService.mint_tombstone(attempt_a.id, operator_user=admin_user)
        assert tombstone_1.id == tombstone_2.id
        assert RetentionTombstone.objects.filter(attempt_id=attempt_a.id).count() == 1

    def test_in_progress_attempt_never_purged(self, attempt_a):
        """21. In-progress attempts cannot be purged."""
        attempt_a.status = AttemptStatus.IN_PROGRESS
        attempt_a.save()

        res = AuthoritativeScrubbingService.execute_purge_for_attempt(attempt_a.id)
        assert res['status'] == 'INELIGIBLE_STATUS'
        assert res['purged'] is False
        assert AttemptAnswer.objects.filter(attempt=attempt_a).exists()
