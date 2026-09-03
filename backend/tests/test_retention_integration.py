import os
import io
import zipfile
import pytest
from datetime import timedelta
from decimal import Decimal
from django.utils import timezone
from django.conf import settings
from django.core import signing
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
from apps.results.models import (
    AssessmentResult,
    HistoricalResultSummary,
    ResultStatus,
)
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
    PurgeJobRun,
)
from apps.retention.services import (
    RetentionPolicyEngine,
    LegalHoldManager,
    AuthoritativeScrubbingService,
    FilesystemCleanupWorker,
    TombstoneService,
    DsarExportService,
    RetentionMetricsService,
)
from apps.retention.tasks import (
    retention_scheduled_daily_purge,
    recover_stale_dsar_export_jobs,
    cleanup_expired_dsar_archives,
)


@pytest.fixture
def admin_user(db):
    return User.objects.create_superuser(
        email="admin_ret_int@codeguard.test",
        password="AdminPassword123!",
        role=Role.ADMIN
    )


@pytest.fixture
def student_user(db):
    user = User.objects.create_user(
        email="student_ret_int@codeguard.test",
        password="StudentPassword123!",
        role=Role.STUDENT
    )
    StudentProfile.objects.create(
        user=user,
        roll_number="CS2026-RET-INT",
        euid="EUID-RET-INT"
    )
    return user


@pytest.fixture
def populated_attempt(db, admin_user, student_user, tmp_path):
    # Create question & assessment
    q, v = QuestionService.create_question(
        question_type=QuestionType.MCQ,
        title="Integration MCQ",
        description="MCQ for integration test",
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
        title="Integration Retention Exam",
        description="Exam testing full retention lifecycle",
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
        source_code="print('Hello World')",
        status=SubmissionStatus.COMPLETED,
        verdict=CodeVerdict.ACCEPTED
    )

    # Proctoring session, events and evidence file
    proc_session = ProctoringSession.objects.create(attempt=attempt)
    ProctoringEvent.objects.create(
        session=proc_session,
        event_type="TAB_SWITCH",
        severity="WARNING",
        started_at=now
    )

    # Physical evidence file in media root
    media_ev_dir = os.path.join(settings.MEDIA_ROOT, "evidence")
    os.makedirs(media_ev_dir, exist_ok=True)
    ev_path = os.path.join(media_ev_dir, f"evidence_{attempt.id}.jpg")
    with open(ev_path, "wb") as f:
        f.write(b"SAMPLE_IMAGE_EVIDENCE_BYTES")

    ProctoringEvidence.objects.create(
        session=proc_session,
        storage_path=ev_path,
        file_size_bytes=len(b"SAMPLE_IMAGE_EVIDENCE_BYTES")
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
    HistoricalResultSummary.objects.create(
        student=student_user,
        assessment_id=assessment.id,
        student_euid="EUID-RET-INT",
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
class TestRetentionIntegration:
    def test_end_to_end_30_day_purge_workflow(self, populated_attempt):
        """1. Complete lifecycle: DB scrub, queue creation, file unlink, and tombstone generation."""
        attempt_id = populated_attempt.id
        ev = ProctoringEvidence.objects.filter(session__attempt=populated_attempt).first()
        ev_file = ev.storage_path
        assert os.path.exists(ev_file)

        # Execute purge
        res = AuthoritativeScrubbingService.execute_purge_for_attempt(attempt_id, process_filesystem_sync=True)
        assert res['purged'] is True

        # Database rows scrubbed
        assert not AttemptAnswer.objects.filter(attempt_id=attempt_id).exists()
        assert not CodeSubmission.objects.filter(attempt_id=attempt_id).exists()
        assert not ProctoringEvent.objects.filter(session__attempt_id=attempt_id).exists()
        assert not ProctoringEvidence.objects.filter(session__attempt_id=attempt_id).exists()

        # Filesystem unlinked
        assert not os.path.exists(ev_file)

        # Permanent summary updated
        summary = HistoricalResultSummary.objects.get(student=populated_attempt.student, assessment_id=populated_attempt.assessment_id)
        assert summary.details_purged is True
        assert summary.total_score_earned == Decimal('10.00')

        # Tombstone sealed
        tombstone = RetentionTombstone.objects.get(attempt_id=attempt_id)
        assert tombstone.confirmed_bytes_reclaimed > 0
        assert tombstone.sha256_audit_proof

    def test_decoupled_file_cleanup_queue(self, populated_attempt):
        """2. Proves that DB scrub completes and queues file unlinks before files are deleted."""
        attempt_id = populated_attempt.id
        # Run DB scrub without filesystem sync or worker
        res = AuthoritativeScrubbingService.execute_purge_for_attempt(
            attempt_id, process_filesystem_sync=False, trigger_async_worker=False
        )
        assert res['purged'] is True

        rec = RetentionRecord.objects.get(attempt_id=attempt_id)
        assert rec.purge_state == PurgeState.CLEANING_FILES
        assert FileCleanupQueue.objects.filter(attempt_id=attempt_id, status=FileCleanupStatus.PENDING).exists()

    def test_partial_filesystem_cleanup(self, populated_attempt, monkeypatch):
        """3. When 1 file fails, tombstone is NOT minted until all files are confirmed."""
        attempt_id = populated_attempt.id
        AuthoritativeScrubbingService.execute_purge_for_attempt(
            attempt_id, process_filesystem_sync=False, trigger_async_worker=False
        )

        # Simulate os.remove failure for the queue item
        def failing_remove(path):
            raise OSError("Disk busy")
        monkeypatch.setattr(os, "remove", failing_remove)

        FilesystemCleanupWorker.process_attempt_cleanups(attempt_id)
        assert not RetentionTombstone.objects.filter(attempt_id=attempt_id).exists()

        rec = RetentionRecord.objects.get(attempt_id=attempt_id)
        assert rec.purge_state == PurgeState.CLEANING_FILES

    def test_filesystem_failure_after_db_commit(self, populated_attempt, monkeypatch):
        """4. Even if filesystem worker crashes, committed DB scrub is never rolled back."""
        attempt_id = populated_attempt.id
        AuthoritativeScrubbingService.execute_purge_for_attempt(
            attempt_id, process_filesystem_sync=False, trigger_async_worker=False
        )

        # DB scrub committed
        assert not AttemptAnswer.objects.filter(attempt_id=attempt_id).exists()

        def failing_remove(path):
            raise OSError("Filesystem unavailable")
        monkeypatch.setattr(os, "remove", failing_remove)

        FilesystemCleanupWorker.process_attempt_cleanups(attempt_id)
        # Still committed
        assert not AttemptAnswer.objects.filter(attempt_id=attempt_id).exists()
        assert FileCleanupQueue.objects.filter(attempt_id=attempt_id, status=FileCleanupStatus.RETRYING).exists()

    def test_filesystem_cleanup_retry_idempotency(self, populated_attempt):
        """5. Unlinking a file already unlinked treats FileNotFoundError as confirmed."""
        attempt_id = populated_attempt.id
        AuthoritativeScrubbingService.execute_purge_for_attempt(
            attempt_id, process_filesystem_sync=False, trigger_async_worker=False
        )

        # Pre-remove file manually
        item = FileCleanupQueue.objects.filter(attempt_id=attempt_id).first()
        if os.path.exists(item.file_path):
            os.remove(item.file_path)

        res = FilesystemCleanupWorker.process_attempt_cleanups(attempt_id)
        assert res['confirmed'] >= 1
        assert RetentionTombstone.objects.filter(attempt_id=attempt_id).exists()

    def test_admin_retention_metrics_calculation(self, populated_attempt, admin_user):
        """6. Tests /api/v1/admin/retention/metrics/ calculates physical reclaimed bytes and counts."""
        client = APIClient()
        client.force_authenticate(user=admin_user)

        res = client.get('/api/v1/admin/retention/metrics/')
        assert res.status_code == 200
        data = res.json()['data']
        assert 'confirmed_bytes_reclaimed' in data
        assert 'due_today_count' in data
        assert data['due_today_count'] >= 1

    def test_admin_dry_run_purge_preview(self, populated_attempt, admin_user):
        """7. Tests /api/v1/admin/retention/preview-purge/ returns token and candidate list."""
        client = APIClient()
        client.force_authenticate(user=admin_user)

        res = client.post('/api/v1/admin/retention/preview-purge/', {}, format='json')
        assert res.status_code == 200
        data = res.json()['data']
        assert 'preview_token' in data
        assert data['eligible_count'] >= 1

    def test_manual_purge_stale_preview_rejected(self, admin_user):
        """8. Submitting an invalid or expired token is rejected."""
        client = APIClient()
        client.force_authenticate(user=admin_user)

        res = client.post('/api/v1/admin/retention/execute-purge/', {'preview_token': 'bad.tampered.token'}, format='json')
        assert res.status_code == 400

    def test_manual_purge_final_eligibility_recheck(self, populated_attempt, admin_user):
        """9. When hold is placed after preview is generated, execute re-checks and defers."""
        client = APIClient()
        client.force_authenticate(user=admin_user)

        # Generate preview
        preview_res = client.post('/api/v1/admin/retention/preview-purge/', {}, format='json')
        token = preview_res.json()['data']['preview_token']

        # Place hold on attempt
        LegalHoldManager.create_attempt_hold(
            attempt_id=populated_attempt.id,
            title="Last minute hold",
            case_reference="HOLD-LATE",
            reason="Investigation",
            user=admin_user
        )

        exec_res = client.post('/api/v1/admin/retention/execute-purge/', {'preview_token': token}, format='json')
        assert exec_res.status_code == 200
        data = exec_res.json()['data']
        assert data['deferred_hold_count'] == 1
        assert data['purged_count'] == 0

    def test_legal_hold_placement_and_release_workflow(self, populated_attempt, admin_user):
        """10. Full hold placement and release through REST API."""
        client = APIClient()
        client.force_authenticate(user=admin_user)

        post_res = client.post('/api/v1/admin/legal-holds/', {
            'title': 'Test REST Hold',
            'case_reference': 'CASE-API-01',
            'reason': 'Audit review',
            'scope': 'ATTEMPT',
            'attempt': str(populated_attempt.id)
        }, format='json')
        assert post_res.status_code == 201
        hold_id = post_res.json()['data']['id']

        # Release hold
        rel_res = client.post(f'/api/v1/admin/legal-holds/{hold_id}/release/', {
            'release_reason': 'Audit successfully passed'
        }, format='json')
        assert rel_res.status_code == 200
        assert rel_res.json()['data']['status'] == 'RELEASED'

    def test_student_dsar_export_job_generation(self, populated_attempt, student_user):
        """11. Student requests DSAR, archive is encrypted, student downloads and unzips."""
        client = APIClient()
        client.force_authenticate(user=student_user)

        req_res = client.post('/api/v1/student/privacy/export-requests/', {
            'attempt_id': str(populated_attempt.id)
        }, format='json')
        assert req_res.status_code == 201
        job_id = req_res.json()['data']['id']

        # Download archive
        dl_res = client.get(f'/api/v1/student/privacy/export-requests/{job_id}/download/')
        assert dl_res.status_code == 200
        assert dl_res['Content-Type'] == 'application/zip'

        # Verify ZIP contains dsar_export.json
        zip_bytes = io.BytesIO(dl_res.content)
        with zipfile.ZipFile(zip_bytes, 'r') as zf:
            assert 'dsar_export.json' in zf.namelist()

    def test_dsar_after_detailed_purge(self, populated_attempt, student_user):
        """12. DSAR requested after detailed data purge generates AVAILABLE_PARTIAL_ARCHIVE."""
        AuthoritativeScrubbingService.execute_purge_for_attempt(populated_attempt.id, process_filesystem_sync=True)

        job = DsarExportService.create_export_request(student=student_user, attempt_id=populated_attempt.id)
        DsarExportService.acquire_snapshot(str(job.id))
        job.refresh_from_db()
        assert job.archive_type == ArchiveType.AVAILABLE_PARTIAL_ARCHIVE
        assert 'retention_tombstone' in job.snapshot_payload

    def test_student_retention_lifecycle_view(self, populated_attempt, student_user):
        """13. Student checks retention status endpoint and views days remaining."""
        client = APIClient()
        client.force_authenticate(user=student_user)

        res = client.get('/api/v1/student/privacy/retention-status/')
        assert res.status_code == 200
        data = res.json()['data']
        assert 'attempts' in data
        assert len(data['attempts']) >= 1

    def test_celery_beat_purge_batch_task(self, populated_attempt):
        """14. retention_scheduled_daily_purge runs as Celery task and purges candidate."""
        run_id = retention_scheduled_daily_purge()
        assert run_id is not None
        run = PurgeJobRun.objects.get(id=run_id)
        assert run.attempts_purged_count >= 1

    def test_key_rotation_while_old_archive_valid(self, populated_attempt, student_user, monkeypatch):
        """15. Archive encrypted with v1 can be decrypted even if active key version is set to v2."""
        job = DsarExportService.create_export_request(student=student_user, attempt_id=populated_attempt.id)
        DsarExportService.acquire_snapshot(str(job.id))
        DsarExportService.generate_and_encrypt_archive(str(job.id))
        job.refresh_from_db()
        assert job.encryption_key_version == 'v1'

        # Now simulate active key version bumped to v2
        new_keys = dict(settings.DSAR_MASTER_KEYS)
        new_keys['v2'] = '22' * 32
        monkeypatch.setattr(settings, 'DSAR_MASTER_KEYS', new_keys)
        monkeypatch.setattr(settings, 'ACTIVE_DSAR_KEY_VERSION', 'v2')

        # Decrypt old v1 archive succeeds
        decrypted = DsarExportService.decrypt_archive(job)
        assert len(decrypted) > 0

    def test_old_key_unavailable_fails_safely(self, populated_attempt, student_user, monkeypatch):
        """16. If v1 master key is removed, decrypt raises KeyError."""
        job = DsarExportService.create_export_request(student=student_user, attempt_id=populated_attempt.id)
        DsarExportService.acquire_snapshot(str(job.id))
        DsarExportService.generate_and_encrypt_archive(str(job.id))
        job.refresh_from_db()

        # Remove v1 key from settings
        monkeypatch.setattr(settings, 'DSAR_MASTER_KEYS', {})
        with pytest.raises(KeyError):
            DsarExportService.decrypt_archive(job)

    def test_expired_archive_no_longer_requires_old_key(self, populated_attempt, student_user):
        """17. Expired archive is unlinked and marked EXPIRED without needing decryption."""
        job = DsarExportService.create_export_request(student=student_user, attempt_id=populated_attempt.id)
        DsarExportService.acquire_snapshot(str(job.id))
        DsarExportService.generate_and_encrypt_archive(str(job.id))
        job.refresh_from_db()

        # Artificially expire archive
        job.expires_at = timezone.now() - timedelta(hours=1)
        job.save()

        count = cleanup_expired_dsar_archives()
        assert count >= 1
        job.refresh_from_db()
        assert job.status == ExportStatus.EXPIRED

    def test_stale_snapshot_pending_recovery(self, populated_attempt, student_user):
        """18. SNAPSHOT_PENDING job older than 15 minutes is failed, restoring attempt purge readiness."""
        job = DsarExportService.create_export_request(student=student_user, attempt_id=populated_attempt.id)
        job.status = ExportStatus.SNAPSHOT_PENDING
        job.started_at = timezone.now() - timedelta(minutes=20)
        job.lease_expires_at = timezone.now() - timedelta(minutes=5)
        job.save()

        rec = RetentionRecord.objects.get(attempt=populated_attempt)
        rec.purge_state = PurgeState.DEFERRED_EXPORT
        rec.save()

        count = recover_stale_dsar_export_jobs()
        assert count == 1

        job.refresh_from_db()
        assert job.status == ExportStatus.FAILED
        rec.refresh_from_db()
        assert rec.purge_state == PurgeState.SCHEDULED
