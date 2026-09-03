import uuid
from django.db import models
from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone

from apps.core.models import UUIDModel, TimeStampedModel


class PolicyScope(models.TextChoices):
    INSTITUTION = 'INSTITUTION', 'Institution-Wide'
    ASSESSMENT = 'ASSESSMENT', 'Assessment-Specific'


class PurgeState(models.TextChoices):
    SCHEDULED = 'SCHEDULED', 'Scheduled for Purge'
    DEFERRED_HOLD = 'DEFERRED_HOLD', 'Deferred: Active Legal Hold'
    DEFERRED_EXPORT = 'DEFERRED_EXPORT', 'Deferred: In-Flight DSAR Export'
    SCRUBBING_DB = 'SCRUBBING_DB', 'Scrubbing Database Telemetry'
    CLEANING_FILES = 'CLEANING_FILES', 'Unlinking Filesystem Evidence'
    PURGED = 'PURGED', 'Completely Purged & Tombstoned'


class ScrubStatus(models.TextChoices):
    PENDING = 'PENDING', 'Pending'
    IN_PROGRESS = 'IN_PROGRESS', 'In Progress'
    COMPLETED = 'COMPLETED', 'Completed'
    FAILED = 'FAILED', 'Failed'


class FileCleanupStatus(models.TextChoices):
    PENDING = 'PENDING', 'Pending Unlink'
    CONFIRMED = 'CONFIRMED', 'Confirmed Deleted'
    RETRYING = 'RETRYING', 'Retrying After Error'
    FAILED = 'FAILED', 'Failed Permanently'


class LegalHoldScope(models.TextChoices):
    ATTEMPT = 'ATTEMPT', 'Specific Test Attempt'
    STUDENT = 'STUDENT', 'All Attempts by Student'
    ASSESSMENT = 'ASSESSMENT', 'All Attempts in Assessment'


class LegalHoldStatus(models.TextChoices):
    ACTIVE = 'ACTIVE', 'Active & Enforcing Hold'
    RELEASED = 'RELEASED', 'Released'


class ExportStatus(models.TextChoices):
    REQUESTED = 'REQUESTED', 'Export Requested'
    SNAPSHOT_PENDING = 'SNAPSHOT_PENDING', 'Acquiring Consistent Snapshot'
    SNAPSHOT_ACQUIRED = 'SNAPSHOT_ACQUIRED', 'Snapshot Acquired (Protected from Purge)'
    GENERATING = 'GENERATING', 'Encrypting & Packaging Archive'
    READY = 'READY', 'Ready for Download'
    EXPIRED = 'EXPIRED', 'Archive Expired & Deleted'
    FAILED = 'FAILED', 'Generation Failed'


class ArchiveType(models.TextChoices):
    FULL_PRE_PURGE_TELEMETRY = 'FULL_PRE_PURGE_TELEMETRY', 'Full Pre-Purge Student Telemetry'
    AVAILABLE_PARTIAL_ARCHIVE = 'AVAILABLE_PARTIAL_ARCHIVE', 'Post-Purge Academic Summary & Tombstone'


class PurgeTriggerType(models.TextChoices):
    SCHEDULED_DAILY = 'SCHEDULED_DAILY', 'Scheduled Daily Task'
    MANUAL_ADMIN = 'MANUAL_ADMIN', 'Manual Administrator Purge'


class PurgeJobStatus(models.TextChoices):
    RUNNING = 'RUNNING', 'Running'
    COMPLETED = 'COMPLETED', 'Completed'
    FAILED = 'FAILED', 'Failed'


class RetentionPolicy(UUIDModel, TimeStampedModel):
    name = models.CharField(max_length=255)
    version = models.PositiveIntegerField(default=1)
    scope = models.CharField(
        max_length=20,
        choices=PolicyScope.choices,
        default=PolicyScope.INSTITUTION
    )
    assessment = models.ForeignKey(
        'assessments.Assessment',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='retention_policies'
    )
    detailed_data_ttl_days = models.PositiveIntegerField(
        default=30,
        help_text="Days after submission until detailed answers, code, and keyframes expire."
    )
    proctoring_evidence_ttl_days = models.PositiveIntegerField(
        default=30,
        help_text="Days after submission until proctoring webcam keyframes and evidence expire."
    )
    report_retention_ttl_days = models.PositiveIntegerField(
        default=7,
        help_text="Days generated compliance reports remain accessible."
    )
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='created_retention_policies'
    )

    class Meta:
        db_table = 'retention_policies'
        ordering = ['-created_at']
        constraints = [
            models.CheckConstraint(
                condition=models.Q(detailed_data_ttl_days__gte=1) & models.Q(detailed_data_ttl_days__lte=3650),
                name='chk_detailed_ttl_range'
            ),
            models.CheckConstraint(
                condition=models.Q(proctoring_evidence_ttl_days__gte=1) & models.Q(proctoring_evidence_ttl_days__lte=3650),
                name='chk_evidence_ttl_range'
            ),
        ]

    def clean(self):
        if self.scope == PolicyScope.ASSESSMENT and not self.assessment_id:
            raise ValidationError("Assessment-scoped retention policy must reference an Assessment.")
        if self.scope == PolicyScope.INSTITUTION and self.assessment_id:
            raise ValidationError("Institution-scoped retention policy must not reference an Assessment.")

    def __str__(self):
        return f"{self.name} (v{self.version}) - {self.get_scope_display()}"


class RetentionRecord(UUIDModel, TimeStampedModel):
    attempt = models.OneToOneField(
        'assessments.TestAttempt',
        on_delete=models.CASCADE,
        related_name='retention_record'
    )
    retention_policy = models.ForeignKey(
        RetentionPolicy,
        on_delete=models.PROTECT,
        related_name='retention_records'
    )
    policy_version = models.PositiveIntegerField(editable=False)
    detailed_data_expires_at = models.DateTimeField(db_index=True)
    proctoring_evidence_expires_at = models.DateTimeField(db_index=True)
    
    purge_state = models.CharField(
        max_length=25,
        choices=PurgeState.choices,
        default=PurgeState.SCHEDULED
    )
    database_scrub_status = models.CharField(
        max_length=20,
        choices=ScrubStatus.choices,
        default=ScrubStatus.PENDING
    )
    filesystem_cleanup_status = models.CharField(
        max_length=20,
        choices=FileCleanupStatus.choices,
        default=FileCleanupStatus.PENDING
    )
    last_scrubbed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        db_table = 'retention_records'
        ordering = ['detailed_data_expires_at']
        indexes = [
            models.Index(fields=['purge_state', 'detailed_data_expires_at'], name='idx_retention_purge_exp'),
        ]

    def __str__(self):
        return f"RetentionRecord(attempt={self.attempt_id}, state={self.purge_state}, expires={self.detailed_data_expires_at})"


class LegalHold(UUIDModel, TimeStampedModel):
    title = models.CharField(max_length=255)
    case_reference = models.CharField(max_length=100, db_index=True)
    reason = models.TextField()
    scope = models.CharField(max_length=20, choices=LegalHoldScope.choices)
    
    attempt = models.ForeignKey(
        'assessments.TestAttempt',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='legal_holds'
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='student_legal_holds'
    )
    assessment = models.ForeignKey(
        'assessments.Assessment',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='assessment_legal_holds'
    )
    status = models.CharField(
        max_length=20,
        choices=LegalHoldStatus.choices,
        default=LegalHoldStatus.ACTIVE
    )
    placed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='placed_legal_holds'
    )
    placed_at = models.DateTimeField(default=timezone.now)
    released_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name='released_legal_holds'
    )
    released_at = models.DateTimeField(null=True, blank=True)
    release_reason = models.TextField(blank=True)

    class Meta:
        db_table = 'retention_legal_holds'
        ordering = ['-placed_at']
        indexes = [
            models.Index(fields=['scope', 'status'], name='idx_hold_scope_status'),
            models.Index(fields=['attempt', 'status'], name='idx_hold_attempt_stat'),
            models.Index(fields=['student', 'status'], name='idx_hold_student_stat'),
            models.Index(fields=['assessment', 'status'], name='idx_hold_assessment_stat'),
        ]

    def clean(self):
        if self.scope == LegalHoldScope.ATTEMPT and not self.attempt_id:
            raise ValidationError("Attempt-scoped legal hold requires attempt reference.")
        if self.scope == LegalHoldScope.STUDENT and not self.student_id:
            raise ValidationError("Student-scoped legal hold requires student reference.")
        if self.scope == LegalHoldScope.ASSESSMENT and not self.assessment_id:
            raise ValidationError("Assessment-scoped legal hold requires assessment reference.")

        # Prevent duplicate active holds for the SAME scope and target.
        # Distinct scopes (STUDENT, ASSESSMENT, ATTEMPT) are explicitly allowed to overlap.
        if self.status == LegalHoldStatus.ACTIVE:
            qs = LegalHold.objects.filter(scope=self.scope, status=LegalHoldStatus.ACTIVE)
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if self.scope == LegalHoldScope.ATTEMPT and self.attempt_id and qs.filter(attempt_id=self.attempt_id).exists():
                raise ValidationError(f"An active legal hold already exists for attempt {self.attempt_id}.")
            elif self.scope == LegalHoldScope.STUDENT and self.student_id and qs.filter(student_id=self.student_id).exists():
                raise ValidationError(f"An active legal hold already exists for student {self.student_id}.")
            elif self.scope == LegalHoldScope.ASSESSMENT and self.assessment_id and qs.filter(assessment_id=self.assessment_id).exists():
                raise ValidationError(f"An active legal hold already exists for assessment {self.assessment_id}.")

    def __str__(self):
        return f"LegalHold({self.case_reference} - {self.scope}: {self.status})"


class FileCleanupQueue(UUIDModel, TimeStampedModel):
    attempt_id = models.UUIDField(db_index=True)
    file_path = models.CharField(max_length=512)
    file_bytes = models.BigIntegerField(default=0)
    status = models.CharField(
        max_length=20,
        choices=FileCleanupStatus.choices,
        default=FileCleanupStatus.PENDING
    )
    retry_count = models.PositiveIntegerField(default=0)
    last_error = models.TextField(blank=True)
    confirmed_deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'retention_file_cleanup_queue'
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['status', 'created_at'], name='idx_file_cleanup_status'),
            models.Index(fields=['attempt_id', 'status'], name='idx_file_cleanup_attempt'),
        ]

    def __str__(self):
        return f"FileCleanupQueue({self.attempt_id}, {self.file_path}, status={self.status})"


class RetentionTombstone(UUIDModel, TimeStampedModel):
    attempt_id = models.UUIDField(unique=True, editable=False)
    student_id = models.UUIDField(editable=False)
    student_euid = models.CharField(
        max_length=64,
        editable=False,
        help_text="Retained strictly pursuant to documented institutional accreditation & transcript audit requirements."
    )
    assessment_id = models.UUIDField(editable=False)
    assessment_title_snapshot = models.CharField(max_length=255, editable=False)
    
    purged_at = models.DateTimeField(editable=False)
    purged_by_system = models.BooleanField(default=True, editable=False)
    operator_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        editable=False,
        related_name='triggered_tombstones'
    )
    
    # Audit metrics
    answers_scrubbed_count = models.PositiveIntegerField(editable=False)
    code_submissions_scrubbed_count = models.PositiveIntegerField(editable=False)
    proctoring_events_scrubbed_count = models.PositiveIntegerField(editable=False)
    evidence_files_deleted_count = models.PositiveIntegerField(editable=False)
    confirmed_bytes_reclaimed = models.BigIntegerField(editable=False)
    
    # Keyed HMAC-SHA256 integrity proof
    sha256_audit_proof = models.CharField(
        max_length=64,
        editable=False,
        help_text="HMAC-SHA256 keyed integrity and authenticity proof."
    )

    class Meta:
        db_table = 'retention_tombstones'
        ordering = ['-purged_at']
        indexes = [
            models.Index(fields=['attempt_id'], name='idx_tombstone_attempt'),
            models.Index(fields=['student_euid'], name='idx_tombstone_euid'),
            models.Index(fields=['assessment_id'], name='idx_tombstone_assessment'),
            models.Index(fields=['purged_at'], name='idx_tombstone_purged_at'),
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise PermissionDenied("RetentionTombstone records are append-only and permanently immutable.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionDenied("RetentionTombstone records cannot be deleted.")

    def __str__(self):
        return f"RetentionTombstone(attempt={self.attempt_id}, student_euid={self.student_euid}, purged_at={self.purged_at})"


class ExportJob(UUIDModel, TimeStampedModel):
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='dsar_export_jobs'
    )
    attempt = models.ForeignKey(
        'assessments.TestAttempt',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='dsar_export_jobs'
    )
    status = models.CharField(
        max_length=25,
        choices=ExportStatus.choices,
        default=ExportStatus.REQUESTED
    )
    archive_type = models.CharField(
        max_length=35,
        choices=ArchiveType.choices,
        default=ArchiveType.FULL_PRE_PURGE_TELEMETRY
    )
    snapshot_payload = models.JSONField(null=True, blank=True)

    # Concurrency Lease & Heartbeat (Bounded 15-Minute Timeout)
    started_at = models.DateTimeField(null=True, blank=True)
    heartbeat_at = models.DateTimeField(null=True, blank=True)
    lease_expires_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Bounded lease expiration (15m default). SNAPSHOT_PENDING only protects while lease_expires_at > now()."
    )

    # Cryptographic & Storage Metadata
    encryption_algorithm = models.CharField(max_length=25, default="AES-256-GCM")
    encryption_key_version = models.CharField(max_length=20, default="v1")
    nonce_hex = models.CharField(max_length=32, blank=True)
    auth_tag_hex = models.CharField(max_length=32, blank=True)
    file_path = models.CharField(max_length=512, blank=True)
    file_bytes = models.BigIntegerField(default=0)
    expires_at = models.DateTimeField(null=True, blank=True)
    
    error_message = models.TextField(null=True, blank=True)

    class Meta:
        db_table = 'retention_export_jobs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['student', 'status'], name='idx_export_student_stat'),
            models.Index(fields=['attempt', 'status'], name='idx_export_attempt_stat'),
            models.Index(fields=['status', 'lease_expires_at'], name='idx_export_stat_lease'),
            models.Index(fields=['expires_at'], name='idx_export_expires_at'),
        ]

    def __str__(self):
        return f"ExportJob(id={self.id}, student={self.student_id}, status={self.status}, type={self.archive_type})"


class PurgeJobRun(UUIDModel, TimeStampedModel):
    trigger_type = models.CharField(max_length=20, choices=PurgeTriggerType.choices)
    status = models.CharField(
        max_length=20,
        choices=PurgeJobStatus.choices,
        default=PurgeJobStatus.RUNNING
    )
    operator_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='executed_purge_jobs'
    )
    started_at = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(null=True, blank=True)
    attempts_evaluated_count = models.PositiveIntegerField(default=0)
    attempts_purged_count = models.PositiveIntegerField(default=0)
    attempts_deferred_hold_count = models.PositiveIntegerField(default=0)
    attempts_deferred_export_count = models.PositiveIntegerField(default=0)
    total_bytes_reclaimed = models.BigIntegerField(default=0)
    error_summary = models.TextField(blank=True)

    class Meta:
        db_table = 'retention_purge_job_runs'
        ordering = ['-started_at']

    def __str__(self):
        return f"PurgeJobRun({self.trigger_type} - {self.status} at {self.started_at})"
