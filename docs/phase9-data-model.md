# CODEGUARD — Phase 9 Data Model Specification (Micro-Hardened)

## Retention, Archival & Compliance Models

**Document Version:** 1.3.0  
**Target App:** `apps.retention`  
**Database Engine:** MySQL 8.0+ / SQLite (Test)  
**Frozen Tables Invariant:** Phase 1–8 tables (`TestAttempt`, `Assessment`, `AssessmentResult`, `HistoricalResultSummary`) remain 100% frozen with zero schema modifications.

---

## 1. Entity-Relationship Overview

```text
┌───────────────────────────┐
│     apps.assessments      │
│       TestAttempt         │ ◄── FROZEN (Phase 5)
└─────────────┬─────────────┘
              │ 1
              │ (Strict 1:1)
              │
┌─────────────▼─────────────┐       0..* ┌───────────────────────────┐
│       apps.retention      ├───────────►│       apps.retention      │
│      RetentionRecord      │            │         LegalHold         │
│  (Owns Retention Lifecycle│            │  (Hierarchical Scope Lock)│
│   & Deterministic TTLs)   │            └───────────────────────────┘
└─────────────┬─────────────┘
              │
              ├── 1:1 per policy ──► RetentionPolicy (versioned)
              │
              ├── 1:N ─────────────► FileCleanupQueue (retryable disk unlinks)
              │
              ├── 1:0..1 ──────────► RetentionTombstone (minted upon full confirmation)
              │
              └── 0..* ────────────► ExportJob (DSAR export snapshot & encryption state)
```

---

## 2. Model Specifications

### 2.1 `RetentionRecord`
Exclusively owns the retention lifecycle, deterministic deadlines, and scrubbing status for each attempt without touching the frozen `TestAttempt` schema.

```python
class PurgeState(models.TextChoices):
    SCHEDULED = "SCHEDULED", "Purge Scheduled"
    DEFERRED_HOLD = "DEFERRED_HOLD", "Deferred Due to Active Legal Hold"
    DEFERRED_EXPORT = "DEFERRED_EXPORT", "Deferred Due to In-Flight DSAR Export"
    SCRUBBING_DB = "SCRUBBING_DB", "Authoritative Database Scrubbing"
    CLEANING_FILES = "CLEANING_FILES", "Asynchronous Filesystem Cleanup"
    PURGED = "PURGED", "Fully Destroyed & Confirmed"

class ScrubStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    COMPLETED = "COMPLETED", "Completed"
    FAILED = "FAILED", "Failed"

class FilesystemCleanupStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    IN_PROGRESS = "IN_PROGRESS", "In Progress"
    COMPLETED = "COMPLETED", "Confirmed Deleted"
    PARTIAL = "PARTIAL", "Partially Deleted (Retry Scheduled)"
    FAILED = "FAILED", "Failed (Exhausted Retries)"

class RetentionRecord(UUIDModel, TimeStampedModel):
    """
    Phase 9-owned entity governing the retention lifecycle of a single TestAttempt.
    Enforces a strict 1:1 relationship with TestAttempt while keeping Phase 5 frozen.
    Created strictly upon TestAttempt terminal state + AssessmentResult FINALIZED.
    """
    attempt = models.OneToOneField(
        'assessments.TestAttempt',
        on_delete=models.CASCADE,
        related_name='retention_record'
    )
    retention_policy = models.ForeignKey(
        'retention.RetentionPolicy',
        on_delete=models.PROTECT,
        related_name='governed_records'
    )
    policy_version = models.PositiveIntegerField(
        default=1,
        help_text="Immutable policy version captured at the time of deadline calculation."
    )
    detailed_data_expires_at = models.DateTimeField(
        db_index=True,
        help_text="Deterministic deadline after which detailed answers and telemetry are purged."
    )
    proctoring_evidence_expires_at = models.DateTimeField(
        db_index=True,
        help_text="Deterministic deadline after which webcam keyframes are wiped."
    )
    
    # Operational Lifecycle State
    purge_state = models.CharField(
        max_length=25,
        choices=PurgeState.choices,
        default=PurgeState.SCHEDULED
    )
    database_scrub_status = models.CharField(
        max_length=25,
        choices=ScrubStatus.choices,
        default=ScrubStatus.PENDING
    )
    filesystem_cleanup_status = models.CharField(
        max_length=25,
        choices=FilesystemCleanupStatus.choices,
        default=FilesystemCleanupStatus.PENDING
    )
    purged_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'retention_records'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['detailed_data_expires_at', 'purge_state'], name='idx_ret_rec_exp_state'),
            models.Index(fields=['purge_state'], name='idx_ret_rec_state'),
        ]
```

### 2.2 `RetentionPolicy`
Defines operational retention windows, time-to-live thresholds, and policy versioning.

```python
class RetentionPolicyScope(models.TextChoices):
    GLOBAL = "GLOBAL", "Global Institutional Default"
    ASSESSMENT = "ASSESSMENT", "Assessment-Specific Override"

class RetentionPolicy(UUIDModel, TimeStampedModel):
    name = models.CharField(max_length=120, unique=True)
    version = models.PositiveIntegerField(
        default=1,
        help_text="Incremental policy version to trace audit lineage."
    )
    scope = models.CharField(
        max_length=20,
        choices=RetentionPolicyScope.choices,
        default=RetentionPolicyScope.GLOBAL
    )
    assessment = models.ForeignKey(
        'assessments.Assessment',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='retention_policy_overrides'
    )
    detailed_data_ttl_days = models.PositiveIntegerField(
        default=30,
        help_text="Days after submission/expiry before detailed answers and telemetry are purged."
    )
    proctoring_evidence_ttl_days = models.PositiveIntegerField(
        default=30,
        help_text="Days before webcam keyframes and telemetry are wiped."
    )
    report_artifacts_ttl_days = models.PositiveIntegerField(
        default=7,
        help_text="Days before generated PDF/XLSX/CSV reports are purged from media storage."
    )
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='created_retention_policies'
    )

    class Meta:
        db_table = 'retention_policies'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['scope', 'is_active'], name='idx_ret_pol_scope_act'),
            models.Index(fields=['name', 'version'], name='idx_ret_pol_name_ver'),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(detailed_data_ttl_days__gte=1) & models.Q(detailed_data_ttl_days__lte=3650),
                name='chk_ret_pol_detailed_ttl_range'
            ),
            models.CheckConstraint(
                check=(
                    (models.Q(scope='ASSESSMENT') & models.Q(assessment__isnull=False)) |
                    (models.Q(scope='GLOBAL') & models.Q(assessment__isnull=True))
                ),
                name='chk_ret_pol_scope_assessment_consistency'
            )
        ]
```

### 2.3 `LegalHold`
Places a binding administrative hold on an attempt, student, or assessment with strict scope-owner serialization.

```python
class LegalHoldScope(models.TextChoices):
    ATTEMPT = "ATTEMPT", "Specific Test Attempt"
    STUDENT = "STUDENT", "All Attempts of a Specific Student"
    ASSESSMENT = "ASSESSMENT", "All Attempts of an Assessment"

class LegalHoldStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Active Immunity Hold"
    RELEASED = "RELEASED", "Hold Released"

class LegalHold(UUIDModel, TimeStampedModel):
    title = models.CharField(max_length=255)
    case_reference = models.CharField(
        max_length=100,
        help_text="Official institutional inquiry / disciplinary / grievance reference ID."
    )
    scope = models.CharField(
        max_length=20,
        choices=LegalHoldScope.choices
    )
    status = models.CharField(
        max_length=20,
        choices=LegalHoldStatus.choices,
        default=LegalHoldStatus.ACTIVE
    )
    attempt = models.ForeignKey(
        'assessments.TestAttempt',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='legal_holds'
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='student_legal_holds'
    )
    assessment = models.ForeignKey(
        'assessments.Assessment',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='assessment_legal_holds'
    )
    reason = models.TextField(help_text="Justification for hold placement.")
    placed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='placed_legal_holds'
    )
    released_at = models.DateTimeField(null=True, blank=True)
    released_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='released_legal_holds'
    )
    release_reason = models.TextField(null=True, blank=True)

    class Meta:
        db_table = 'retention_legal_holds'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'scope'], name='idx_leg_hold_stat_scope'),
            models.Index(fields=['attempt', 'status'], name='idx_leg_hold_attempt_stat'),
            models.Index(fields=['student', 'status'], name='idx_leg_hold_student_stat'),
            models.Index(fields=['assessment', 'status'], name='idx_leg_hold_assess_stat'),
        ]
        constraints = [
            models.CheckConstraint(
                check=(
                    (models.Q(scope='ATTEMPT') & models.Q(attempt__isnull=False) & models.Q(student__isnull=True) & models.Q(assessment__isnull=True)) |
                    (models.Q(scope='STUDENT') & models.Q(student__isnull=False) & models.Q(attempt__isnull=True) & models.Q(assessment__isnull=True)) |
                    (models.Q(scope='ASSESSMENT') & models.Q(assessment__isnull=False) & models.Q(attempt__isnull=True) & models.Q(student__isnull=True))
                ),
                name='chk_legal_hold_target_mutually_exclusive'
            )
        ]
```

### 2.4 `FileCleanupQueue`
Operational queue decoupling authoritative database scrubbing from asynchronous, retryable filesystem unlinks.

```python
class FileCleanupStatus(models.TextChoices):
    PENDING = "PENDING", "Pending Unlink"
    RETRYING = "RETRYING", "Retrying After Failure"
    CONFIRMED = "CONFIRMED", "Confirmed Deleted"
    FAILED_PERMANENT = "FAILED_PERMANENT", "Failed Exhausted"

class FileCleanupQueue(UUIDModel, TimeStampedModel):
    attempt_id = models.UUIDField(db_index=True)
    file_path = models.CharField(max_length=512)
    file_type = models.CharField(max_length=50, default='PROCTORING_KEYFRAME')
    file_bytes = models.BigIntegerField(default=0)
    status = models.CharField(
        max_length=20,
        choices=FileCleanupStatus.choices,
        default=FileCleanupStatus.PENDING
    )
    retry_count = models.PositiveIntegerField(default=0)
    last_error = models.TextField(null=True, blank=True)
    confirmed_deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'retention_file_cleanup_queue'
        indexes = [
            models.Index(fields=['attempt_id', 'status'], name='idx_file_clean_att_stat'),
            models.Index(fields=['status'], name='idx_file_clean_stat'),
        ]
```

### 2.5 `RetentionTombstone` (Data Minimized & Keyed HMAC Integrity)
Minted ONLY when both DB scrub and all linked `FileCleanupQueue` items are confirmed deleted.

```python
class RetentionTombstone(UUIDModel):
    """
    Immutable compliance proof generated when an attempt's telemetry is permanently destroyed.
    Data minimized: roll numbers excluded; internal UUIDs and EUID audit reference preserved.
    Classification: INTERNAL AUDIT DATA — RESTRICTED — PERMANENT (Admin only).
    """
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
```

### 2.6 `ExportJob` (DSAR Export Lifecycle & Encryption Metadata)
Manages self-service DSAR export requests, snapshot protection state, and cryptographic key metadata.

```python
class ExportStatus(models.TextChoices):
    REQUESTED = "REQUESTED", "Export Requested"
    SNAPSHOT_PENDING = "SNAPSHOT_PENDING", "Acquiring Consistent Snapshot"
    SNAPSHOT_ACQUIRED = "SNAPSHOT_ACQUIRED", "Snapshot Acquired (Protected from Purge)"
    GENERATING = "GENERATING", "Encrypting & Packaging Archive"
    READY = "READY", "Ready for Download"
    EXPIRED = "EXPIRED", "Archive Expired & Deleted"
    FAILED = "FAILED", "Generation Failed"

class ArchiveType(models.TextChoices):
    FULL_PRE_PURGE_TELEMETRY = "FULL_PRE_PURGE_TELEMETRY", "Full Pre-Purge Student Telemetry"
    AVAILABLE_PARTIAL_ARCHIVE = "AVAILABLE_PARTIAL_ARCHIVE", "Post-Purge Academic Summary & Tombstone"

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
```

### 2.7 `PurgeJobRun`
Tracks operational batch execution metrics.

```python
class PurgeJobStatus(models.TextChoices):
    RUNNING = "RUNNING", "Running"
    COMPLETED = "COMPLETED", "Completed"
    FAILED = "FAILED", "Failed"

class PurgeJobRun(UUIDModel, TimeStampedModel):
    status = models.CharField(
        max_length=20,
        choices=PurgeJobStatus.choices,
        default=PurgeJobStatus.RUNNING
    )
    triggered_by = models.CharField(max_length=50, default="CELERY_BEAT")
    started_at = models.DateTimeField()
    completed_at = models.DateTimeField(null=True, blank=True)
    scanned_attempts_count = models.PositiveIntegerField(default=0)
    purged_attempts_count = models.PositiveIntegerField(default=0)
    skipped_held_count = models.PositiveIntegerField(default=0)
    skipped_unfinalized_count = models.PositiveIntegerField(default=0)
    confirmed_bytes_reclaimed = models.BigIntegerField(default=0)
    error_summary = models.TextField(null=True, blank=True)

    class Meta:
        db_table = 'retention_purge_job_runs'
        ordering = ['-started_at']
```

---

## 3. Data Ownership Matrix (Micro-Hardened)

| Data Entity | Primary Creator | Modifier | Deleter | Reader | Classification | Immutability |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `RetentionRecord` | Finalization Worker | Purge Worker (updates status) | Prohibited | Admin | Authoritative Lifecycle | Fixed deadlines; mutable state |
| `RetentionPolicy` | Admin | Admin | Prohibited | Admin | Authoritative Config | Mutable by Admin |
| `LegalHold` | Admin | Admin (release only) | Prohibited | Admin | Compliance Authority | State controlled (`ACTIVE` -> `RELEASED`) |
| `FileCleanupQueue` | Purge Worker | Purge Worker | Purge Worker | Admin | Operational Telemetry | Transient / Auto-cleaned |
| `RetentionTombstone` | System Worker | Prohibited | Prohibited | Admin | Legal Audit Proof | Strictly Immutable |
| `ExportJob` | Student | Export Worker | TTL Worker (7d) | Student Owner | Ephemeral Export | 7-day TTL Auto-purge |
| `PurgeJobRun` | System Worker | System Worker | Prohibited | Admin | Operational Telemetry | System Append-Only |
| `HistoricalResultSummary` | Phase 8 Worker | System (mark `details_purged`) | Prohibited | Student / Admin | Permanent Academic Record | Academic Score Immutable |
