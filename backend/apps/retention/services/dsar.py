import io
import os
import zipfile
import json
import logging
from datetime import timedelta
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError, PermissionDenied

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes

from apps.accounts.models import User
from apps.assessments.models import Assessment, TestAttempt
from apps.results.models import HistoricalResultSummary, ResultStatus
from apps.evaluator.models import CodeSubmission
from apps.retention.models import (
    ExportJob,
    ExportStatus,
    ArchiveType,
    RetentionRecord,
    PurgeState,
    RetentionTombstone,
)

logger = logging.getLogger('codeguard.retention')


class DsarExportService:
    @classmethod
    def get_master_key(cls, version):
        """
        Retrieves master key bytes from Django settings by key version.
        """
        master_keys = getattr(settings, 'DSAR_MASTER_KEYS', {})
        key_hex = master_keys.get(version)
        if not key_hex:
            raise KeyError(f"No master key configured for DSAR key version '{version}'.")
        return bytes.fromhex(key_hex)

    @classmethod
    def derive_dek(cls, master_key, job_id, key_version):
        """
        Derives a 256-bit Data Encryption Key (DEK) via HKDF-SHA256.
        IKM: master_key
        Salt: job_id.bytes
        Info: b"codeguard:dsar:{key_version}"
        """
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=job_id.bytes,
            info=f"codeguard:dsar:{key_version}".encode('utf-8'),
        )
        return hkdf.derive(master_key)

    @classmethod
    def create_export_request(cls, student, attempt_id=None):
        """
        Creates a new DSAR export request for a student.
        Enforces daily rate-limiting (max 3 requests per 24 hours).
        """
        one_day_ago = timezone.now() - timedelta(days=1)
        recent_count = ExportJob.objects.filter(
            student=student,
            created_at__gte=one_day_ago
        ).count()
        if recent_count >= 3:
            raise ValidationError("Rate limit exceeded: You may only request up to 3 data exports per 24 hours.")

        attempt = None
        if attempt_id:
            attempt = TestAttempt.objects.filter(id=attempt_id, student=student).first()
            if not attempt:
                raise ValidationError("Specified assessment attempt does not exist or does not belong to you.")

        job = ExportJob.objects.create(
            student=student,
            attempt=attempt,
            status=ExportStatus.REQUESTED,
            encryption_key_version=getattr(settings, 'ACTIVE_DSAR_KEY_VERSION', 'v1')
        )
        return job

    @classmethod
    def materialize_allowlisted_payload(cls, attempt):
        """
        Extracts student-owned data strictly filtered against the approved DSAR allowlist.
        Hidden test cases, expected outputs, compiler flags, and peer data are excluded.
        """
        student = attempt.student
        assessment = attempt.assessment

        # Answers payload
        answers_data = []
        for ans in attempt.answers.select_related('snapshot_question').all():
            q_snap = ans.snapshot_question
            answers_data.append({
                'question_id': str(ans.question_id),
                'question_title': q_snap.title if q_snap else 'Question',
                'question_type': q_snap.question_type if q_snap else 'MCQ',
                'student_response': ans.selected_options or ans.text_response or '',
                'submitted_at': ans.created_at.isoformat() if ans.created_at else None,
            })

        # Code submissions payload (Public test cases only)
        submissions_data = []
        for sub in CodeSubmission.objects.filter(attempt=attempt).order_by('created_at'):
            # Filter test case results to only public ones
            filtered_cases = []
            if hasattr(sub, 'test_case_results'):
                for tc in sub.test_case_results.all():
                    if getattr(tc, 'is_public', True):
                        filtered_cases.append({
                            'test_case_number': getattr(tc, 'test_case_number', 1),
                            'verdict': getattr(tc, 'verdict', 'UNKNOWN'),
                            'execution_time_ms': getattr(tc, 'execution_time_ms', 0),
                        })

            submissions_data.append({
                'submission_id': str(sub.id),
                'language': sub.language,
                'source_code': sub.source_code,
                'status': sub.status,
                'verdict': getattr(sub, 'verdict', 'UNKNOWN'),
                'public_test_case_results': filtered_cases,
                'created_at': sub.created_at.isoformat(),
            })

        # Academic result summary
        result_data = None
        if hasattr(attempt, 'result'):
            res = attempt.result
            result_data = {
                'total_score_earned': str(res.total_score_earned),
                'total_possible_score': str(res.total_possible_score),
                'percentage': str(res.percentage),
                'is_passed': res.is_passed,
                'finalized_at': res.finalized_at.isoformat() if res.finalized_at else None,
            }

        # Phase 10: Candidate-visible invigilation events (RET-02)
        # Strictly redacts internal_notes and proctor identities pursuant to privacy allowlist
        candidate_interventions = []
        try:
            from apps.invigilation.models import ProctorIntervention
            for interv in ProctorIntervention.objects.filter(attempt=attempt).order_by('issued_at'):
                candidate_interventions.append({
                    'intervention_id': str(interv.id),
                    'event_type': interv.event_type,
                    'reason_code': interv.reason_code,
                    'reason_text': interv.reason_text,
                    'issued_at': interv.issued_at.isoformat() if interv.issued_at else None,
                })
        except Exception as e:
            logger.warning(f"Could not extract invigilation interventions for DSAR payload: {e}")

        # Phase 10: Ephemeral chat messages between candidate and proctor (RET-02)
        # Excludes internal staff user identifiers
        chat_messages = []
        try:
            from apps.invigilation.models import ProctorChatMessage
            for msg in ProctorChatMessage.objects.filter(attempt=attempt).order_by('sent_at'):
                chat_messages.append({
                    'message_id': str(msg.id),
                    'sender_type': 'CANDIDATE' if msg.sender_id == student.id else 'PROCTOR',
                    'message_text': msg.message_text,
                    'sent_at': msg.sent_at.isoformat() if msg.sent_at else None,
                })
        except Exception as e:
            logger.warning(f"Could not extract chat messages for DSAR payload: {e}")

        return {
            'student_profile': {
                'student_id': str(student.id),
                'euid': getattr(getattr(student, 'student_profile', None), 'euid', ''),
                'email': student.email,
                'role': student.role,
            },
            'assessment': {
                'assessment_id': str(assessment.id),
                'title': assessment.title,
                'description': assessment.description,
            },
            'attempt': {
                'attempt_id': str(attempt.id),
                'status': attempt.status,
                'started_at': attempt.started_at.isoformat() if attempt.started_at else None,
                'submitted_at': attempt.submitted_at.isoformat() if attempt.submitted_at else None,
                'time_spent_seconds': int((attempt.submitted_at - attempt.started_at).total_seconds()) if (attempt.started_at and attempt.submitted_at) else 0,
            },
            'academic_result': result_data,
            'student_answers': answers_data,
            'code_submissions': submissions_data,
            'candidate_interventions': candidate_interventions,
            'chat_messages': chat_messages,
        }

    @classmethod
    def materialize_partial_archive_payload(cls, attempt):
        """
        Builds partial archive payload when detailed data has already been purged.
        Captures permanent transcripts and tombstone certificates without reconstructing deleted data.
        """
        student = attempt.student
        summary = HistoricalResultSummary.objects.filter(
            student=student,
            assessment_id=attempt.assessment_id
        ).first()

        tombstone = RetentionTombstone.objects.filter(attempt_id=attempt.id).first()

        return {
            'archive_notice': "Detailed telemetry (answers, code, proctoring) for this attempt was purged pursuant to institutional retention policy.",
            'student_profile': {
                'student_id': str(student.id),
                'euid': getattr(getattr(student, 'student_profile', None), 'euid', ''),
                'email': student.email,
                'role': student.role,
            },
            'academic_transcript': {
                'assessment_title': summary.assessment_title_snapshot if summary else attempt.assessment.title,
                'total_score_earned': str(summary.total_score_earned) if summary else '0.00',
                'total_possible_score': str(summary.total_possible_score) if summary else '0.00',
                'percentage': str(summary.percentage) if summary else '0.00',
                'is_passed': summary.is_passed if summary else None,
                'completed_at': summary.completed_at.isoformat() if summary else None,
                'details_purged': True,
            },
            'retention_tombstone': {
                'tombstone_id': str(tombstone.id) if tombstone else None,
                'purged_at': tombstone.purged_at.isoformat() if tombstone else None,
                'sha256_audit_proof': tombstone.sha256_audit_proof if tombstone else None,
            }
        }

    @classmethod
    def acquire_snapshot(cls, export_job_id):
        """
        Executes DSAR Snapshot Acquisition under the authoritative serialization boundary:
        Scope Owner -> TestAttempt -> RetentionRecord -> ExportJob.
        Commits SNAPSHOT_ACQUIRED only after complete payload is materialized.
        """
        with transaction.atomic():
            export_job = ExportJob.objects.select_for_update().get(id=export_job_id)
            if not export_job.attempt_id:
                # Account-wide snapshot or simple job
                export_job.status = ExportStatus.SNAPSHOT_ACQUIRED
                export_job.save(update_fields=['status', 'updated_at'])
                return export_job

            # Canonical lock ordering
            attempt_raw = TestAttempt.objects.filter(id=export_job.attempt_id).values('id', 'assessment_id', 'student_id').first()
            if attempt_raw:
                Assessment.objects.select_for_update().get(id=attempt_raw['assessment_id'])
                User.objects.select_for_update().get(id=attempt_raw['student_id'])

            attempt = TestAttempt.objects.select_for_update().get(id=export_job.attempt_id)
            retention_record = RetentionRecord.objects.select_for_update().filter(attempt=attempt).first()

            now = timezone.now()
            timeout_sec = getattr(settings, 'DSAR_SNAPSHOT_PENDING_TIMEOUT', 900)
            export_job.started_at = now
            export_job.lease_expires_at = now + timedelta(seconds=timeout_sec)
            export_job.status = ExportStatus.SNAPSHOT_PENDING
            export_job.save(update_fields=['started_at', 'lease_expires_at', 'status', 'updated_at'])

            # Evaluate purge state under serialization locks
            if retention_record and retention_record.purge_state in [PurgeState.SCRUBBING_DB, PurgeState.CLEANING_FILES, PurgeState.PURGED]:
                payload = cls.materialize_partial_archive_payload(attempt)
                export_job.archive_type = ArchiveType.AVAILABLE_PARTIAL_ARCHIVE
            else:
                payload = cls.materialize_allowlisted_payload(attempt)
                export_job.archive_type = ArchiveType.FULL_PRE_PURGE_TELEMETRY

            export_job.snapshot_payload = payload
            export_job.status = ExportStatus.SNAPSHOT_ACQUIRED
            export_job.save(update_fields=['snapshot_payload', 'archive_type', 'status', 'updated_at'])
            return export_job

    @classmethod
    def renew_heartbeat(cls, export_job_id):
        """
        Renews active worker heartbeat and extends the short 15-minute lease,
        STRICTLY bounded by the absolute 60-minute ceiling from started_at.
        lease_expires_at <= started_at + 60 minutes.
        """
        with transaction.atomic():
            job = ExportJob.objects.select_for_update().get(id=export_job_id)
            if job.status != ExportStatus.SNAPSHOT_PENDING:
                return job

            now = timezone.now()
            job.heartbeat_at = now

            # Enforce 60-minute absolute hard ceiling from started_at
            started_at = job.started_at or now
            max_ceiling = started_at + timedelta(minutes=60)

            # Proposed 15-minute extension from now
            timeout_sec = getattr(settings, 'DSAR_SNAPSHOT_PENDING_TIMEOUT', 900)
            proposed_expiry = now + timedelta(seconds=timeout_sec)

            if proposed_expiry > max_ceiling:
                job.lease_expires_at = max_ceiling
            else:
                job.lease_expires_at = proposed_expiry

            job.save(update_fields=['heartbeat_at', 'lease_expires_at', 'updated_at'])
            return job

    @classmethod
    def generate_and_encrypt_archive(cls, export_job_id):
        """
        Compiles the staged snapshot into an AES-256-GCM encrypted ZIP archive.
        Executes without holding database row locks (No-I/O-under-lock rule).
        """
        export_job = ExportJob.objects.get(id=export_job_id)
        if export_job.status != ExportStatus.SNAPSHOT_ACQUIRED:
            # Re-acquire snapshot if needed
            export_job = cls.acquire_snapshot(export_job_id)

        export_job.status = ExportStatus.GENERATING
        export_job.save(update_fields=['status', 'updated_at'])

        try:
            # Build ZIP archive in memory
            payload = export_job.snapshot_payload or {}
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
                zf.writestr('dsar_export.json', json.dumps(payload, indent=2))
                zf.writestr('README.txt', "CODEGUARD Student Personal Data Export Archive.\n"
                                          "Encrypted at rest using AES-256-GCM.\n"
                                          "Retained for 7 days pursuant to privacy policy.")

            plaintext_bytes = zip_buffer.getvalue()

            # Resolve key version and derive DEK
            key_version = export_job.encryption_key_version or getattr(settings, 'ACTIVE_DSAR_KEY_VERSION', 'v1')
            master_key = cls.get_master_key(key_version)
            dek = cls.derive_dek(master_key, export_job.id, key_version)

            # Generate 96-bit (12-byte) random nonce
            nonce = os.urandom(12)
            aesgcm = AESGCM(dek)
            ciphertext = aesgcm.encrypt(nonce, plaintext_bytes, None)

            # AES-GCM ciphertext includes 16-byte auth tag at the end
            auth_tag = ciphertext[-16:]

            # Write to disk in media/exports/
            export_dir = os.path.join(settings.MEDIA_ROOT, 'exports')
            os.makedirs(export_dir, exist_ok=True)
            file_name = f"dsar_{export_job.id}.enc"
            dest_path = os.path.join(export_dir, file_name)

            with open(dest_path, 'wb') as f:
                f.write(ciphertext)

            ttl_days = getattr(settings, 'DSAR_ARCHIVE_TTL_DAYS', 7)
            export_job.file_path = dest_path
            export_job.file_bytes = len(ciphertext)
            export_job.nonce_hex = nonce.hex()
            export_job.auth_tag_hex = auth_tag.hex()
            export_job.expires_at = timezone.now() + timedelta(days=ttl_days)
            export_job.status = ExportStatus.READY
            export_job.save(update_fields=[
                'file_path', 'file_bytes', 'nonce_hex', 'auth_tag_hex',
                'expires_at', 'status', 'updated_at'
            ])
            return export_job
        except Exception as exc:
            logger.exception(f"DSAR archive generation failed for job {export_job_id}: {exc}")
            export_job.status = ExportStatus.FAILED
            export_job.error_message = str(exc)
            export_job.save(update_fields=['status', 'error_message', 'updated_at'])
            raise

    @classmethod
    def decrypt_archive(cls, export_job):
        """
        Decrypts an encrypted DSAR archive for authenticated student streaming download.
        Path traversal check is strictly enforced.
        """
        if export_job.status != ExportStatus.READY:
            raise ValidationError("Export archive is not ready for download.")

        if export_job.expires_at and export_job.expires_at <= timezone.now():
            raise ValidationError("Export archive has expired.")

        path = export_job.file_path
        if not path or not os.path.exists(path):
            raise ValidationError("Archive file not found on disk.")

        # Path traversal security check
        from .filesystem import FilesystemCleanupWorker
        if not FilesystemCleanupWorker.is_safe_path(path):
            raise PermissionDenied("Access to specified file path is forbidden.")

        with open(path, 'rb') as f:
            ciphertext = f.read()

        key_version = export_job.encryption_key_version
        master_key = cls.get_master_key(key_version)
        dek = cls.derive_dek(master_key, export_job.id, key_version)

        nonce = bytes.fromhex(export_job.nonce_hex)
        aesgcm = AESGCM(dek)
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        return plaintext

    @classmethod
    def recover_stale_jobs(cls):
        """
        Periodic recovery sweep for abandoned SNAPSHOT_PENDING jobs whose 15m lease has expired.
        Serializes through the authoritative TestAttempt + RetentionRecord boundary.
        Guarantees No False Failure for active workers.
        """
        now = timezone.now()
        candidates = ExportJob.objects.filter(
            status=ExportStatus.SNAPSHOT_PENDING,
            lease_expires_at__lte=now
        )
        recovered_count = 0

        for candidate in candidates:
            with transaction.atomic():
                # Canonical lock acquisition
                if candidate.attempt_id:
                    attempt_raw = TestAttempt.objects.filter(id=candidate.attempt_id).values('id', 'assessment_id', 'student_id').first()
                    if attempt_raw:
                        Assessment.objects.select_for_update().get(id=attempt_raw['assessment_id'])
                        User.objects.select_for_update().get(id=attempt_raw['student_id'])

                    attempt = TestAttempt.objects.select_for_update().get(id=candidate.attempt_id)
                    retention_record = RetentionRecord.objects.select_for_update().filter(attempt=attempt).first()
                else:
                    retention_record = None

                job = ExportJob.objects.select_for_update().get(id=candidate.id)

                # Re-verify lease expiry under exclusive lock (No False Failure Rule):
                if job.status == ExportStatus.SNAPSHOT_PENDING and job.lease_expires_at and job.lease_expires_at <= timezone.now():
                    job.status = ExportStatus.FAILED
                    job.error_message = "Snapshot acquisition lease expired after 15 minutes without worker progress."
                    job.save(update_fields=['status', 'error_message', 'updated_at'])

                    if retention_record and retention_record.purge_state == PurgeState.DEFERRED_EXPORT:
                        retention_record.purge_state = PurgeState.SCHEDULED
                        retention_record.save(update_fields=['purge_state', 'updated_at'])

                    recovered_count += 1

        return recovered_count

    @classmethod
    def cleanup_expired_archives(cls):
        """
        Unlinks expired encrypted archives after 7 days and marks status = EXPIRED.
        """
        now = timezone.now()
        expired_jobs = ExportJob.objects.filter(
            status=ExportStatus.READY,
            expires_at__lte=now
        )
        cleaned_count = 0

        for job in expired_jobs:
            if job.file_path and os.path.exists(job.file_path):
                try:
                    os.remove(job.file_path)
                except OSError as exc:
                    logger.warning(f"Failed to unlink expired archive {job.file_path}: {exc}")

            job.status = ExportStatus.EXPIRED
            job.save(update_fields=['status', 'updated_at'])
            cleaned_count += 1

        return cleaned_count
