# CODEGUARD — Phase 9 Architecture Handoff & Implementation Guide (Concurrently & Cryptographically Hardened)

**Document Version:** 1.5.0  
**Phase:** 9 — Automated Data Retention, Privacy Compliance & Legal Hold Engine  
**Current Status:** FULLY HARDENED & READY FOR IMPLEMENTATION AUTHORIZATION 🔒  
**Implementation Status:** NOT STARTED (Awaiting Authorization Gate)  
**Target Test Suite:** 251 Tests (197 Regression + 54 Phase 9)  

---

## 1. Architectural Blueprint Overview

Phase 9 fulfills the lifecycle contracts established during Phase 7 (AI Proctoring) and Phase 8 (Results & Ledger):
1. **Target Django App:** `apps.retention` (URL root `/api/v1/admin/retention/`, `/api/v1/admin/legal-holds/`, and `/api/v1/student/privacy/`).
2. **Key Models:** `RetentionRecord`, `RetentionPolicy`, `LegalHold`, `FileCleanupQueue`, `RetentionTombstone`, `ExportJob`, `PurgeJobRun`.
3. **Core Services:**
   - `RetentionPolicyEngine`: Resolves applicable TTL policies, stamps deterministic deadlines (`detailed_data_expires_at`), and tracks policy versions.
   - `ScrubbingPipelineService`: Executes two-stage purge (Authoritative DB scrub -> Celery retryable file cleanup -> HMAC tombstone minting).
   - `LegalHoldManagerService`: Manages hold placement, scope serialization, and release according to `docs/phase9-transaction-concurrency.md`.
   - `StudentDataExportService`: Manages self-service DSAR export archives filtered by strict allowlist, bounded by 15-minute snapshot leases, and encrypted with AES-256-GCM.
4. **Celery Tasks:**
   - `retention_scheduled_daily_purge`: Scheduled beat task running at 02:00 UTC daily (`CHUNK_SIZE = 100`, `skip_locked=True`).
   - `recover_stale_dsar_export_jobs`: Periodic beat task (every 5m) recovering abandoned `SNAPSHOT_PENDING` exports whose 15-minute lease expired.
   - `process_file_cleanup_queue`: Dedicated queue task retrying disk unlinks.
   - `generate_student_dsar_archive`: Async compilation and encryption of student pre-purge export.
   - `cleanup_expired_dsar_archives`: Daily beat task unlinking archives older than 7 days.
5. **Frontend Modules:**
   - Admin: Retention Dashboard (Storage charts, Legal Hold Manager, Tombstones Table, 5-stage double-confirmation manual purge modal).
   - Student: Privacy & Data Retention Tab (Purge countdown, DSAR export download).

---

## 2. Prioritized Implementation Sequence

When implementation is authorized by the Software Architect, follow this exact sequence:

```text
 1. Implement Authoritative Lock Protocol (Global order: Assessment -> User -> Attempt -> RetentionRecord -> LegalHold -> ExportJob)
 2. Implement DSAR Snapshot Serialization (TestAttempt + RetentionRecord authoritative serialization boundary)
 3. Implement Stale Snapshot Lease/Recovery (15m DSAR_SNAPSHOT_PENDING_TIMEOUT, lease re-verification, No False Failure rule)
 4. Implement Purge Serialization (Eligibility, LegalHold check, bounded DSAR check, DB scrub, commit)
 5. Implement Concurrency Tests (DSAR vs purge, snapshot rollback, stale recovery races, deadlock prevention)
 6. Implement Encryption & Key-Version Handling (AES-256-GCM, HKDF-SHA256, key rotation v1/v2, 7-day archive TTL)
 7. Implement Filesystem Cleanup Pipeline (FileCleanupQueue, decoupled async unlinking, No-I/O-under-lock rule)
 8. Implement Retention Models (RetentionRecord, RetentionPolicy, LegalHold, RetentionTombstone, ExportJob, PurgeJobRun)
 9. Implement Policy Versioning & Deterministic Deadlines (Fixed detailed_data_expires_at at finalization)
10. Implement Tombstone Minting (Keyed HMAC-SHA256 integrity proof)
11. Implement Manual Purge Workflow (5-stage double-confirmation with signed preview_token)
12. Implement REST APIs (Admin retention, legal holds, student privacy lifecycle)
13. Implement Admin UI (Dashboard, storage metrics, hold manager, tombstones table)
14. Implement Student Privacy UI (Retention countdown, encrypted DSAR download)
15. Implement Complete Test Suite (All 54 tests across unit, integration, and security modules)
16. Execute Security & Concurrency Audit (STRIDE, 48-threat verification, path traversal checks)
17. Execute Regression Verification (197 / 197 frozen baseline verified)
18. Conduct Final Freeze Review (Audit report and Phase 9 freeze declaration)
```

---

## 3. Strict Prohibitions

- DO NOT alter Phase 5 scoring bundles or timers.
- DO NOT alter Phase 6 Judge0 sandboxed execution or submission score records.
- DO NOT alter Phase 7 proctoring risk calculations or live WebSocket streams.
- DO NOT alter Phase 8 authoritative evaluation projection or passing percentage freeze.
- DO NOT allow deletion of `HistoricalResultSummary` or `AssessmentResult` headers.
- DO NOT treat `ExportJob` as the sole concurrency guard; all destructive decisions MUST acquire row locks on `TestAttempt + RetentionRecord`.
- DO NOT perform filesystem unlinking while holding database row locks (`No-I/O-under-lock` rule).
- DO NOT implement Phase 9 code until architecture is explicitly approved.
