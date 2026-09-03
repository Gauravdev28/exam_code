# CODEGUARD — Phase 9 Transaction & Concurrency Specification

**Document Version:** 1.2.0  
**Phase:** 9 — Automated Data Retention, Privacy Compliance & Legal Hold Engine  
**Status:** AUTHORITATIVE SPECIFICATION — CONCURRENCY, LOCKING & SERIALIZATION  
**ORM Contract:** Django 5.x / PostgreSQL & MySQL Row-Level Locking via `select_for_update()`  

---

## 1. Global Lock Order Hierarchy

To prevent lock-order deadlocks among concurrent Phase 9 operations, any transaction requiring multiple shared or overlapping resources MUST acquire row locks strictly according to this global hierarchy:

```text
1. Assessment (apps.assessments.models.Assessment)
        ↓
2. User / Student (apps.accounts.models.User)
        ↓
3. TestAttempt (apps.assessments.models.TestAttempt)
        ↓
4. RetentionRecord (apps.retention.models.RetentionRecord)
        ↓
5. LegalHold (apps.retention.models.LegalHold)
        ↓
6. ExportJob (apps.retention.models.ExportJob)
```

### Universal Rule of Minimal Lock Sets
A transaction acquires **only the minimum subset of resources** required for its specific scope. When multiple resources are required, they MUST be acquired strictly in downward order matching the global hierarchy.

* **Valid Orderings:**
  - `Assessment` ──► `TestAttempt` ──► `RetentionRecord`
  - `User` ──► `TestAttempt` ──► `RetentionRecord`
  - `TestAttempt` ──► `RetentionRecord` ──► `LegalHold`
  - `TestAttempt` ──► `RetentionRecord` ──► `ExportJob`
  - `Assessment` ──► `User` ──► `TestAttempt` ──► `RetentionRecord` ──► `ExportJob`
* **Forbidden Orderings (Deadlock Hazards):**
  - ❌ `ExportJob` then `TestAttempt` (Violates order)
  - ❌ `ExportJob` then `RetentionRecord` (Violates order)
  - ❌ `RetentionRecord` then `TestAttempt` (Violates order)
  - ❌ `TestAttempt` then `Assessment` (Violates order)
  - ❌ `LegalHold` then `User` (Violates order)

---

## 2. Authoritative Serialization Boundary vs. Subordinate Metadata

### 2.1 The Authoritative Boundary: `TestAttempt + RetentionRecord`
`TestAttempt` and its associated `RetentionRecord` constitute the **authoritative database serialization boundary** for destructive retention operations, legal-hold checks, and DSAR snapshot acquisitions concerning that attempt.
* **Core Rule:** Any operation that destructively scrubs telemetry or materializes a protected snapshot MUST acquire exclusive row locks on BOTH `TestAttempt` and `RetentionRecord` `FOR UPDATE`.

### 2.2 Subordinate Responsibility of `ExportJob`
`ExportJob` represents **subordinate state and metadata**. 
* **The ExportJob Subordination Invariant:** An `ExportJob` status such as `SNAPSHOT_PENDING`, `SNAPSHOT_ACQUIRED`, or `GENERATING` does not independently guarantee concurrency safety. Concurrency safety derives entirely from the row locks held on `TestAttempt` and `RetentionRecord`.
* **Prohibition:** Implementations MUST NOT perform uncoordinated checks (e.g. `if ExportJob.status == SNAPSHOT_PENDING: assume_protected()`) without first acquiring the required `TestAttempt` and `RetentionRecord` locks.

---

## 3. Lock Set Specifications per Operation

| Operation | Resources Locked | Lock Mode | Rationale |
| :--- | :--- | :--- | :--- |
| **Create DSAR Request** | `ExportJob` (Insert) | `INSERT` (No row lock) | Inserts job record in `REQUESTED` status without locking attempt rows. |
| **DSAR Snapshot Acquisition** | Scope Owner (`Assessment` ──► `User`) ──► `TestAttempt` ──► `RetentionRecord` ──► `ExportJob` | `select_for_update()` | Synchronizes against concurrent purge while materializing allowed student responses into snapshot buffer. |
| **Stale DSAR Job Recovery** | Scope Owner (`Assessment` ──► `User`) ──► `TestAttempt` ──► `RetentionRecord` ──► `ExportJob` | `select_for_update()` | Safely breaks stale leases and transitions abandoned jobs to `FAILED` without racing against active workers. |
| **Export Generation (Async)** | `ExportJob` (State update only) | `select_for_update()` | Once snapshot is acquired, DB locks are released. Encryption occurs without holding attempt/retention locks (`No-I/O-under-lock`). |
| **Export Failure / Expiry** | `ExportJob` | `select_for_update()` | Updates status to `FAILED` or `EXPIRED` without touching attempt tables. |
| **Attempt Hold Creation** | `TestAttempt` | `select_for_update()` | Serializes hold against attempt-level purge. |
| **Student Hold Creation** | `User` (Student row) | `select_for_update()` | Serializes hold against any purge of that student's attempts without locking thousands of attempt rows. |
| **Assessment Hold Creation**| `Assessment` | `select_for_update()` | Serializes hold against any purge of that assessment's attempts without table-wide locking. |
| **Hold Release** | Scope Owner (`Assessment`, `User`, or `Attempt`) + `LegalHold` | `select_for_update()` | Prevents stale reads or concurrent state transitions during release. |
| **Purge Eligibility & DB Scrub** | `Assessment` ──► `User` ──► `TestAttempt` ──► `RetentionRecord` (Per-attempt) | `select_for_update()` | Serializes purge against parent-scope holds, attempt holds, and in-flight DSAR snapshot acquisition. |
| **Manual Purge (Batch)** | `Assessment` ──► `User` ──► `TestAttempt` ──► `RetentionRecord` (Per-attempt loop) | `select_for_update()` | Evaluates and scrubs each eligible attempt sequentially in chunks (`CHUNK_SIZE = 100`). |
| **RetentionRecord Creation**| `TestAttempt` ──► `RetentionRecord` (Insert) | `select_for_update()` | Serializes 1:1 binding at result finalization time. |

---

## 4. Transaction Boundary Specifications

### 4.1 Attempt-Scoped Legal Hold Creation
```text
BEGIN TRANSACTION
    attempt = TestAttempt.objects.select_for_update().get(id=attempt_id)
    retention_record = RetentionRecord.objects.filter(attempt=attempt).first()
    IF retention_record AND retention_record.purge_state == PurgeState.PURGED:
        RETURN scope_warning ("Hold applies only to surviving permanent transcripts and audit tombstones")
    VALIDATE authorization and reason
    CREATE LegalHold (scope='ATTEMPT', attempt=attempt, status='ACTIVE')
COMMIT
```

### 4.2 Student-Scoped Legal Hold Creation
```text
BEGIN TRANSACTION
    student = User.objects.select_for_update().get(id=student_id)
    VALIDATE authorization and case_reference
    CREATE LegalHold (scope='STUDENT', student=student, status='ACTIVE')
COMMIT
```
*Note: Locks only the single `User` row, scaling to cohorts of any size without touching attempt rows.*

### 4.3 Assessment-Scoped Legal Hold Creation
```text
BEGIN TRANSACTION
    assessment = Assessment.objects.select_for_update().get(id=assessment_id)
    VALIDATE authorization and case_reference
    CREATE LegalHold (scope='ASSESSMENT', assessment=assessment, status='ACTIVE')
COMMIT
```
*Note: Locks only the single `Assessment` row, scaling to thousands of attempts without lock contention.*

### 4.4 Legal Hold Release Transaction
```text
BEGIN TRANSACTION
    hold = LegalHold.objects.get(id=hold_id)
    IF hold.status == LegalHoldStatus.RELEASED:
        RAISE ValidationError ("Hold is already released")
        
    # Lock scope owner according to global order:
    IF hold.scope == 'ASSESSMENT':
        Assessment.objects.select_for_update().get(id=hold.assessment_id)
    ELIF hold.scope == 'STUDENT':
        User.objects.select_for_update().get(id=hold.student_id)
    ELIF hold.scope == 'ATTEMPT':
        TestAttempt.objects.select_for_update().get(id=hold.attempt_id)
        
    # Lock hold row:
    hold = LegalHold.objects.select_for_update().get(id=hold_id)
    hold.status = LegalHoldStatus.RELEASED
    hold.released_at = timezone.now()
    hold.released_by = current_user
    hold.release_reason = release_reason
    hold.save()
    
    APPEND AuditLog (action="LEGAL_HOLD_RELEASED", target_id=hold.id)
COMMIT
```

### 4.5 Purge Eligibility & Authoritative Database Scrub Transaction
```text
BEGIN TRANSACTION
    # 1. Acquire parent scope owner locks in global order:
    assessment = Assessment.objects.select_for_update().get(id=attempt.assessment_id)
    student = User.objects.select_for_update().get(id=attempt.student_id)
    
    # 2. Acquire attempt & retention record locks (AUTHORITATIVE SERIALIZATION BOUNDARY):
    attempt = TestAttempt.objects.select_for_update(skip_locked=True).filter(id=attempt_id).first()
    IF NOT attempt:
        ROLLBACK / YIELD (ALREADY_LOCKED_OR_PURGED)
        
    retention_record = RetentionRecord.objects.select_for_update().get(attempt=attempt)
    
    # 3. Verification Pre-conditions:
    IF attempt.status NOT IN [AttemptStatus.SUBMITTED, AttemptStatus.EXPIRED, AttemptStatus.CANCELLED]:
        ROLLBACK / YIELD (INELIGIBLE_ACTIVE_STATUS)
    IF NOT attempt.result OR attempt.result.status != ResultStatus.FINALIZED:
        ROLLBACK / YIELD (INELIGIBLE_UNFINALIZED)
    IF retention_record.detailed_data_expires_at > timezone.now():
        ROLLBACK / YIELD (INELIGIBLE_TTL_NOT_ELAPSED)
    IF retention_record.purge_state == PurgeState.PURGED:
        ROLLBACK / YIELD (ALREADY_PURGED)
        
    # 4. Check for active legal holds (Parent scopes locked, guarantees no hold is in-flight):
    active_holds = LegalHold.objects.filter(
        Q(scope='ATTEMPT', attempt=attempt) |
        Q(scope='STUDENT', student=student) |
        Q(scope='ASSESSMENT', assessment=assessment),
        status=LegalHoldStatus.ACTIVE
    )
    IF active_holds.exists():
        retention_record.purge_state = PurgeState.DEFERRED_HOLD
        retention_record.save()
        COMMIT / YIELD (SKIPPED_ACTIVE_HOLD)
        
    # 5. Check for actively protected DSAR exports (Bounded by active lease):
    active_dsar = ExportJob.objects.filter(
        attempt=attempt,
        status__in=[ExportStatus.SNAPSHOT_PENDING, ExportStatus.SNAPSHOT_ACQUIRED, ExportStatus.GENERATING]
    )
    # Check bounded lease: SNAPSHOT_PENDING only protects if lease_expires_at > now()
    truly_protected = False
    FOR job IN active_dsar:
        IF job.status in [ExportStatus.SNAPSHOT_ACQUIRED, ExportStatus.GENERATING]:
            truly_protected = True
            BREAK
        ELIF job.status == ExportStatus.SNAPSHOT_PENDING AND job.lease_expires_at > timezone.now():
            truly_protected = True
            BREAK
            
    IF truly_protected:
        retention_record.purge_state = PurgeState.DEFERRED_EXPORT
        retention_record.save()
        COMMIT / YIELD (SKIPPED_IN_FLIGHT_DSAR)
        
    # 6. Authoritative Database Scrubbing:
    retention_record.purge_state = PurgeState.SCRUBBING_DB
    retention_record.save()
    
    scrubbed_answers = attempt.answers.all().delete()[0]
    scrubbed_submissions = CodeSubmission.objects.filter(attempt=attempt).delete()[0]
    scrubbed_events = ProctoringEvent.objects.filter(session__attempt=attempt).delete()[0]
    
    # Queue filesystem files for retryable asynchronous cleanup:
    evidence_qs = ProctoringEvidence.objects.filter(session__attempt=attempt)
    FOR ev IN evidence_qs:
        FileCleanupQueue.objects.create(
            attempt_id=attempt.id,
            file_path=ev.file_path,
            file_bytes=ev.file_size_bytes or 0,
            status=FileCleanupStatus.PENDING
        )
    evidence_qs.delete()
    
    # Update permanent summaries & headers:
    HistoricalResultSummary.objects.filter(student=attempt.student, assessment_id=attempt.assessment_id).update(details_purged=True)
    AssessmentResult.objects.filter(attempt=attempt).update(details_purged=True)
    
    retention_record.purge_state = PurgeState.CLEANING_FILES
    retention_record.database_scrub_status = ScrubStatus.COMPLETED
    retention_record.save()
COMMIT
```

### 4.6 DSAR Snapshot Acquisition Transaction
```text
BEGIN TRANSACTION
    # 1. Acquire parent scope owners in global order:
    assessment = Assessment.objects.select_for_update().get(id=attempt.assessment_id)
    student = User.objects.select_for_update().get(id=attempt.student_id)
    
    # 2. Acquire attempt & retention record locks (AUTHORITATIVE SERIALIZATION BOUNDARY):
    attempt = TestAttempt.objects.select_for_update().get(id=attempt_id)
    retention_record = RetentionRecord.objects.select_for_update().get(attempt=attempt)
    
    # 3. Acquire export job lock:
    export_job = ExportJob.objects.select_for_update().get(id=export_job_id)
    
    # 4. Check attempt purge state under lock:
    IF retention_record.purge_state IN [PurgeState.SCRUBBING_DB, PurgeState.CLEANING_FILES, PurgeState.PURGED]:
        # Data already purged: transition to partial archive without detailed answers
        export_job.archive_type = ArchiveType.AVAILABLE_PARTIAL_ARCHIVE
        export_job.status = ExportStatus.SNAPSHOT_ACQUIRED
        export_job.save()
        COMMIT
    ELSE:
        # 5. Materialize complete allowlisted data into export staging buffer:
        allowed_snapshot_payload = MaterializeAllowedDsarPayload(attempt)
        export_job.snapshot_payload = allowed_snapshot_payload
        export_job.archive_type = ArchiveType.FULL_PRE_PURGE_TELEMETRY
        export_job.status = ExportStatus.SNAPSHOT_ACQUIRED
        export_job.save()
        COMMIT
        
    # NOTE: At this point, COMMIT releases all Assessment, User, Attempt, and RetentionRecord row locks!
    # Celery worker transitions to GENERATING and performs AES-256-GCM encryption WITHOUT holding DB locks.
```

### 4.7 Stale `SNAPSHOT_PENDING` Recovery Transaction
```text
# Invoked by periodic Celery sweep (e.g. every 5 minutes):
BEGIN TRANSACTION
    # 1. Acquire parent scope owners in global order:
    assessment = Assessment.objects.select_for_update().get(id=attempt.assessment_id)
    student = User.objects.select_for_update().get(id=attempt.student_id)
    
    # 2. Acquire attempt & retention record locks:
    attempt = TestAttempt.objects.select_for_update().get(id=attempt_id)
    retention_record = RetentionRecord.objects.select_for_update().get(attempt=attempt)
    export_job = ExportJob.objects.select_for_update().get(id=export_job_id)
    
    # 3. Re-verify lease expiry under exclusive locks:
    IF export_job.status == ExportStatus.SNAPSHOT_PENDING AND export_job.lease_expires_at <= timezone.now():
        export_job.status = ExportStatus.FAILED
        export_job.error_message = "Snapshot acquisition lease expired after 15 minutes without worker progress."
        export_job.save()
        
        # Remove purge deferral if attempt was deferred:
        IF retention_record.purge_state == PurgeState.DEFERRED_EXPORT:
            retention_record.purge_state = PurgeState.SCHEDULED
            retention_record.save()
            
        APPEND AuditLog (action="DSAR_STALE_JOB_TIMED_OUT", target_id=export_job.id)
COMMIT
```

### 4.8 RetentionRecord Creation Transaction
```text
# Invoked strictly upon Phase 8 Result Finalization:
BEGIN TRANSACTION
    attempt = TestAttempt.objects.select_for_update().get(id=attempt_id)
    IF NOT hasattr(attempt, 'retention_record'):
        policy = RetentionPolicyResolver.resolve_for_assessment(attempt.assessment)
        RetentionRecord.objects.create(
            attempt=attempt,
            retention_policy=policy,
            policy_version=policy.version,
            detailed_data_expires_at=attempt.submitted_at + timedelta(days=policy.detailed_data_ttl_days),
            proctoring_evidence_expires_at=attempt.submitted_at + timedelta(days=policy.proctoring_evidence_ttl_days),
            purge_state=PurgeState.SCHEDULED
        )
COMMIT
```

---

## 5. Bounded `SNAPSHOT_PENDING` Lease & Recovery Semantics

### 5.1 The 15-Minute Bounded Lease (`DSAR_SNAPSHOT_PENDING_TIMEOUT`)
* **Configuration:** `DSAR_SNAPSHOT_PENDING_TIMEOUT = 900` (15 minutes).
* **Rationale:** In CODEGUARD's local-first architecture, extracting and staging an attempt's allowlisted responses takes < 5 seconds. A 15-minute lease provides ample tolerance for Celery queue latency and worker retries while ensuring that an abandoned or crashed worker cannot permanently block retention scrubbing.
* **Lease Stamping:** Upon entering `SNAPSHOT_PENDING`, `ExportJob` stamps:
  `lease_expires_at = timezone.now() + timedelta(minutes=15)`
* **Active Heartbeat:** Active snapshot workers executing multi-attempt batch exports may refresh `heartbeat_at = timezone.now()` and extend `lease_expires_at` up to a maximum hard ceiling of 60 minutes.

### 5.2 Stale Recovery Synchronization Guarantee
```text
Recovery Worker ──► Evaluates lease_expires_at <= now()
                          │
                          ▼
            [AUTHORITATIVE SERIALIZATION LOCK]
            (Locks Attempt, RetentionRecord, ExportJob)
                          │
                          ▼
            Re-verifies lease status under lock
            ├── Valid active worker unblocked? ──► Aborts recovery cleanly
            └── Still expired and pending?    ──► Marks FAILED & clears DEFERRED_EXPORT
```
* **No False Failure Invariant:** A legitimate active snapshot worker MUST NOT be marked stale solely because another worker observed an outdated state. By re-verifying `lease_expires_at` under exclusive row locks, race conditions between recovery and active workers are mathematically eliminated.

---

## 6. DSAR Snapshot ↔ Purge Race Outcomes

Because both the DSAR snapshot acquisition and purge eligibility evaluation acquire the exact same `TestAttempt` and `RetentionRecord` locks in the same global hierarchy, they strictly serialize.

### Case A — DSAR Wins the Race
1. DSAR worker acquires `TestAttempt` and `RetentionRecord` locks.
2. Purge worker attempts to evaluate the attempt, but blocks waiting for the `TestAttempt` lock.
3. DSAR worker materializes the allowlisted snapshot, marks `ExportJob.status = SNAPSHOT_ACQUIRED`, and commits.
4. Purge worker unblocks and acquires locks.
5. Purge worker queries `ExportJob` for active exports on this attempt.
6. Purge worker detects `ExportJob` in `SNAPSHOT_ACQUIRED` status.
7. Purge worker sets `retention_record.purge_state = DEFERRED_EXPORT`, commits, and cleanly skips the attempt.
* **Result:** DSAR snapshot is completely preserved; purge is safely deferred.

### Case B — Purge Wins the Race
1. Purge worker acquires `TestAttempt` and `RetentionRecord` locks.
2. DSAR snapshot worker attempts to acquire locks, but blocks waiting for the `TestAttempt` lock.
3. Purge worker checks for protected DSAR states; finds none.
4. Purge worker scrubs detailed answers and code, sets `retention_record.purge_state = CLEANING_FILES`, and commits.
5. DSAR snapshot worker unblocks and acquires locks.
6. DSAR worker observes `retention_record.purge_state == CLEANING_FILES` (or `PURGED`).
7. DSAR worker recognizes that detailed data was already purged; sets `export_job.archive_type = AVAILABLE_PARTIAL_ARCHIVE`, captures surviving permanent transcripts and tombstones, and commits.
* **Result:** Purge completes authoritatively; DSAR safely compiles a partial archive without attempting to reconstruct deleted data.

### Forbidden Intermediate State
```text
FORBIDDEN SEQUENCE:
DSAR reads source data ──► PURGE destroys source data ──► DSAR marks SNAPSHOT_ACQUIRED
```
**Architectural Invariant:** Under no circumstances can a DSAR export mark `SNAPSHOT_ACQUIRED` on data that was destroyed during reading. Because the entire read and status transition is executed inside the atomic transaction while holding `TestAttempt` and `RetentionRecord` locks `FOR UPDATE`, this sequence is impossible.

---

## 7. Precise Semantic Definition of `SNAPSHOT_ACQUIRED`

> **Authoritative Definition:**  
> `SNAPSHOT_ACQUIRED` means the complete allowlisted DSAR payload for the requested scope has been materialized into the protected export snapshot buffer under the defined database serialization boundary, and the transition has committed successfully.

* It is NOT an asynchronous or external database read replica.
* It represents an immutable, in-memory or staging JSON document containing all allowed candidate answers, code submissions, timestamps, and scores.

---

## 8. DSAR Archive TTL & Cryptographic Key Retention

### 8.1 Independent 7-Day Archive TTL
* DSAR export archives have an independent, policy-defined time-to-live:
  ```text
  DSAR_ARCHIVE_TTL_DAYS = 7
  ```
* At `expires_at = ready_at + timedelta(days=7)`, a scheduled cleanup task unlinks the encrypted `.enc` file from `media/exports/` and transitions `ExportJob.status = EXPIRED`.

### 8.2 Key Retention vs. Archive Lifetime Invariant
* **Rule:** An encryption key version MUST remain available for decryption for at least the maximum remaining lifetime of every non-expired archive encrypted with that key version.
* **Example:**
  - Key `v1` is active.
  - Export A expires Sept 10.
  - Export B expires Sept 13.
  - Key `v2` is rotated in on Sept 14 (becomes active for new exports).
  - Export C (encrypted with `v1`) expires Sept 20.
  - **Key `v1` CANNOT be retired until Sept 20 23:59:59 UTC**, after which 100% of `v1` archives are confirmed expired and deleted.

### 8.3 Key Rotation Procedure
1. Infrastructure injects new master key `v2` via secret manager or Docker secret.
2. Configuration updates `ACTIVE_DSAR_KEY_VERSION = "v2"`.
3. All new export jobs derive DEKs using `v2`.
4. Existing unexpired archives continue resolving their tagged `encryption_key_version = "v1"`.
5. Once all archives with `key_version == "v1"` reach `status == EXPIRED`, `v1` secret is retired.
6. **No Bulk Re-Encryption:** Archives are short-lived (7 days); bulk re-encryption of ephemeral archives is prohibited.

---

## 9. Deadlock Prevention & Qualification

> **Engineering Declaration:**  
> All Phase 9 transactions that access overlapping retention resources MUST acquire locks according to the documented global lock order (`Assessment -> User -> TestAttempt -> RetentionRecord -> LegalHold -> ExportJob`). This prevents lock-order deadlocks among compliant Phase 9 transactions.

### Assumptions and Limitations:
1. **Compliance Boundary:** Any external transaction or unreviewed raw SQL query that touches these tables without honoring the global lock order is outside this guarantee and may trigger deadlocks.
2. **Transaction Minimization:** Database transactions must only encompass query validation and record mutation.
3. **No-I/O-under-lock Rule:** Filesystem deletion, network requests, and cryptographic export packaging MUST NEVER occur while holding database row locks.
