# CODEGUARD — Phase 9 Data Lifecycle & Retention Architecture (Micro-Hardened)

**Document Version:** 1.2.0  
**Scope:** Data Lifecycle States, Shared Serialization Boundaries, Two-Stage Scrubbing Pipeline, DSAR Lifecycle, and Tombstone Minting  

---

## 1. Lifecycle State Progression

```text
               [Attempt Active / In-Progress]
                             │
                             ▼ (Submit / Auto-Expire)
               [Attempt Submitted / Expired]
                             │
                             ▼ (Phase 8 Finalization Service)
          [Result Finalized & HistoricalResultSummary Created]
                             │
                             ▼ (Strict 1:1 Binding)
           [RetentionRecord Created with Deterministic TTLs]
                             │
              ┌──────────────┴──────────────┐
              ▼                             ▼
   [DSAR Export Pipeline]          [Purge Eligibility Scan]
              │                             │
    (POST /export-request/)                 ▼ (Day 31+)
              │                [DATABASE SERIALIZATION BOUNDARY]
              ▼                  (Locks Scope Owners, Attempt,
      SNAPSHOT_PENDING                  RetentionRecord)
              │                             │
   [DATABASE SERIALIZATION]                 │
              │                             ▼
      SNAPSHOT_ACQUIRED ──────────► Protected by active DSAR or Hold?
              │                            /                \
      (DB Locks Released)                YES                 NO
              │                           │                  │
          GENERATING                      ▼                  ▼
    (AES-256-GCM Encrypt)           [PURGE DEFERRED]   [Stage 1: DB SCRUB]
              │                                              │
            READY                                     (Commit DB Scrub)
              │                                              │
         (7-Day TTL)                                         ▼
              │                                    [Stage 2: FILE CLEANUP]
           EXPIRED                                           │
                                                      (Confirm Unlinks)
                                                             │
                                                             ▼
                                                   [Stage 3: TOMBSTONE]
                                                             │
                                                             ▼ (Day 91+)
                                                   [90-Day Risk Purge]
                                                   (risk_score = NULL,
                                                    risk_band = NULL,
                                                    risk_data_status = PURGED)
                                                             │
                                                             ▼
                                                   [PERMANENT TRANSCRIPT]
```

### Permanent vs. Destroyed Artifacts
* **Permanently Intact:**
  - Official Grade, Final Score, Percentage: PERMANENTLY INTACT
  - `HistoricalResultSummary`: PERMANENTLY INTACT
  - `AssessmentResult` Header Metadata: PERMANENTLY INTACT
  - `RetentionTombstone` (Keyed HMAC-SHA256): PERMANENTLY INTACT
* **Permanently Destroyed:**
  - `AttemptAnswer` text, choices, and code submissions: PERMANENTLY DESTROYED
  - Webcam keyframe JPEGs and biometric evidence: PERMANENTLY UNLINKED
  - Raw `ProctoringEvent` telemetry rows: PERMANENTLY SCRUBBED
  - Proctoring `risk_score` and `risk_band`: NULLED AFTER 90 DAYS

---

## 2. Two-Stage Scrubbing Sequence & Rollback Guarantees

Scrubbing separates authoritative database destruction from physical disk cleanup:

### Stage 1: Authoritative Database Scrub (`transaction.atomic()`)
1. **Global Lock Acquisition:**
   - Lock `Assessment` row `select_for_update()`.
   - Lock `User` (Student row) `select_for_update()`.
   - Lock `TestAttempt` `select_for_update(skip_locked=True)`.
   - Lock `RetentionRecord` `select_for_update()`.
2. **Pre-condition Validation:**
   - Verify terminal attempt status, finalized result, and elapsed retention deadline.
   - Verify zero active `LegalHold` rows across attempt, student, and assessment scopes.
   - Verify zero protected `ExportJob` rows (`SNAPSHOT_PENDING`, `SNAPSHOT_ACQUIRED`, `GENERATING`).
3. **Database Telemetry Deletion:**
   - Delete `AttemptAnswer` records.
   - Delete `CodeSubmission` records.
   - Delete `ProctoringEvent` records.
4. **Queue Disk Deletions:**
   - For every keyframe file in `ProctoringEvidence`, insert a row into `FileCleanupQueue` with `file_bytes` and `status='PENDING'`.
   - Delete `ProctoringEvidence` DB rows.
5. **Mark Ledger Headers:**
   - Update `AssessmentResult.details_purged = True`.
   - Update `HistoricalResultSummary.details_purged = True`.
   - Update `RetentionRecord.purge_state = PurgeState.CLEANING_FILES`.
   - Update `RetentionRecord.database_scrub_status = ScrubStatus.COMPLETED`.
6. **Commit:** DB transaction commits. The detailed data is now authoritatively destroyed from the database.

### Stage 2: Retryable Filesystem Unlinking (Celery Task)
1. Worker queries `FileCleanupQueue.objects.filter(attempt_id=attempt.id, status='PENDING')`.
2. Iterates over file paths, strictly validating `os.path.abspath(f).startswith(MEDIA_ROOT/evidence/)`.
3. Calls `os.remove(f)` safely catching `FileNotFoundError` (already gone) and `OSError` (permissions/I/O).
4. Marks `status='CONFIRMED'`, `confirmed_deleted_at=timezone.now()`.
5. If any file fails, marks `status='RETRYING'` and queues an asynchronous retry task.

### Stage 3: Mint RetentionTombstone
1. Verifies that all `FileCleanupQueue` rows for `attempt_id` have `status='CONFIRMED'`.
2. Computes total confirmed bytes reclaimed via `confirmed_bytes_reclaimed = sum(file_bytes)`.
3. Generates HMAC-SHA256 signature binding `attempt_id`, `student_id`, `assessment_id`, `purged_at`, and `confirmed_bytes_reclaimed` using `settings.SECRET_KEY`.
4. Inserts immutable `RetentionTombstone`.
5. Updates `RetentionRecord.purge_state = PurgeState.PURGED`.
6. Cleans up transient `FileCleanupQueue` rows.

---

## 3. Dedicated DSAR Export Lifecycle, 15-Minute Bounded Lease & 7-Day TTL

```text
[POST /student/privacy/export-request/]
              │
              ▼
    ExportJob Created (status='REQUESTED')
              │
              ▼
    SNAPSHOT_PENDING
    (Stamps lease_expires_at = now() + 15m)
              │
              ├─────────────────────────────────────────────────┐
              ▼ (Active Worker with Valid Lease)                ▼ (Worker Abandoned / Timeout > 15m)
    [DATABASE SERIALIZATION BOUNDARY]                 LEASE EXPIRED (lease_expires_at <= now())
    (Locks Scope Owner ──► Attempt ──►                          │
     RetentionRecord ──► ExportJob)                             ▼
    • Copies allowlisted student responses            [STALE RECOVERY TRANSACTION]
      to JSON staging buffer                          (Locks Scope Owner ──► Attempt ──►
    • Transitions ExportJob to SNAPSHOT_ACQUIRED       RetentionRecord ──► ExportJob)
    • COMMITS (All row locks released)                • Re-verifies lease under lock
              │                                       • Transitions ExportJob to FAILED
              ▼                                       • Clears DEFERRED_EXPORT purge state
    GENERATING (Async Worker - No DB Locks held)      • COMMITS (Row locks released)
    • Derives DEK via HKDF-SHA256 from master key               │
    • Encrypts archive using AES-256-GCM                        ▼
    • Writes payload to media/exports/{job_id}.enc     [Purge Worker Re-evaluates Attempt]
    • Records auth_tag_hex, nonce_hex, key_version
              │
              ▼
    READY (Download Available via Authenticated Streaming)
              │
              ▼ (7 Days After Ready)
    EXPIRED
    • Unlinks media/exports/{job_id}.enc
    • Marks ExportJob.status = 'EXPIRED'
```

### 3.1 Bounded Lease & Heartbeat Protocol
* **Default Timeout:** `DSAR_SNAPSHOT_PENDING_TIMEOUT = 15 minutes` (900 seconds).
* **Protection Scope:** `SNAPSHOT_PENDING` protects an attempt from scheduled purge sweeps ONLY while `lease_expires_at > timezone.now()`.
* **Heartbeat Refresh:** Long-running batch exports update `heartbeat_at = timezone.now()` and advance `lease_expires_at` up to an absolute hard ceiling of 60 minutes from `started_at`.
* **Stale Recovery:** Periodic Celery task `recover_stale_dsar_export_jobs` sweeps expired leases every 5 minutes, acquiring the authoritative `TestAttempt + RetentionRecord` serialization boundary and safely marking abandoned jobs `FAILED`.

