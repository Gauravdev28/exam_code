# CODEGUARD — Phase 9 Architecture Design (Micro-Hardened)

## Automated Data Retention, Privacy Compliance & Legal Hold Engine

**Document Version:** 1.1.0  
**Status:** MICRO-HARDENED — READY FOR REVIEW  
**Author:** Senior Software Architect + Security Architect  
**Baseline Frozen Systems:** Phase 1–8 Frozen (197 / 197 Backend Tests Passing)  

---

## 1. Executive Summary

CODEGUARD is an enterprise-grade technical assessment platform for higher education institutions. Over Phases 1 through 8, the platform established:
- Secure authentication and role-based access control (Phase 1 & 2)
- Student management and deterministic EUID generation (Phase 3)
- Version-controlled question banking with hidden test case protection (Phase 4)
- Assessment engine with immutable snapshots, server timers, and autosave (Phase 5)
- Sandboxed code execution with partial scoring (Phase 6)
- AI-assisted proctoring capturing telemetry, face tracking, and keyframe evidence (Phase 7)
- Authoritative evaluation ledger, cohort analytics, and reporting (Phase 8)

Phase 7 and Phase 8 introduced intensive data generation:
- Webcam keyframe screenshots and telemetry recorded every 10–30 seconds
- Code submissions with source code and execution logs
- Detailed candidate responses across all question types
- Generated PDF, XLSX, and CSV reports

Without an automated retention, privacy compliance, and archival subsystem, CODEGUARD faces significant operational risks:
1. **Infrastructure Storage Exhaustion:** In an institution with thousands of students taking weekly exams, raw telemetry and keyframe screenshots consume gigabytes of disk space and millions of database rows, degrading query performance and causing storage exhaustion.
2. **Data Governance & Policy Compliance:** CODEGUARD implements a configurable institutional retention policy with a default 30-day detailed-data retention period. The 30-day value is an operational and privacy-policy configuration and is not represented as a universal statutory retention period. Actual institutional retention requirements must be determined by the applicable institution, jurisdiction, and legal policy.

Phase 9 implements the **Automated Data Retention, Privacy Compliance & Legal Hold Engine (`apps.retention`)**. It provides an automated, race-safe, and cryptographically verified data lifecycle manager that scrubs detailed telemetry and responses at the deterministic expiration boundary while permanently preserving immutable academic transcripts, audit logs, and compliance tombstones.

---

## 2. Priority Analysis & Candidate Evaluation

To determine the exact scope of Phase 9, five candidate subsystems were evaluated across six architectural dimensions:

| Candidate Phase Scope | User Value | Architectural Impact | Security Risk | Complexity | Dependency on Existing Phases | Priority |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **A. Automated Retention, Privacy Compliance & Legal Hold Engine** | **VERY HIGH** | **VERY HIGH** | **HIGH** | **MEDIUM** | **Phase 5, 6, 7, 8 (Direct)** | **RANK 1 (RECOMMENDED)** |
| **B. Institutional Academic Structure & Cohort Management** | HIGH | MEDIUM | LOW | MEDIUM | Phase 3, 5 | RANK 2 |
| **C. Unified Notification, Alert & Broadcast System** | MEDIUM | MEDIUM | LOW | LOW | Phase 1, 5, 8 | RANK 3 |
| **D. Live Proctoring Two-Way Intervention & Streaming** | MEDIUM | HIGH | HIGH | HIGH | Phase 7 | RANK 4 |
| **E. AI-Assisted Question Authoring & Assessment Intelligence** | LOW | LOW | MEDIUM | MEDIUM | Phase 4 | RANK 5 |

### Justification for Recommending Scope A (Retention, Compliance & Legal Hold)
1. **Urgency & Storage Safety:** As assessments run in production, proctoring evidence (keyframe JPEGs) and telemetry tables grow linearly without bound. Phase 9 must establish the automated purge pipeline before production volume leads to disk starvation.
2. **Pre-Engineered Contract Fulfillment:** Phase 7 (`RetentionClass`) and Phase 8 (`RetentionService.is_eligible_for_purge`, `HistoricalResultSummary.details_purged`) explicitly stubbed and scheduled Phase 9 as the operational purge and legal hold executor. The route `path('api/v1/retention/', ...)` is already reserved in `backend/codeguard/urls.py`.
3. **Institutional Privacy Policy Enforcement:** Enables institutions to enforce data minimization policies to purge sensitive biometric and keyframe data following the standard 30-day appeal window.
4. **Clean Decoupling:** Phase 9 does not alter exam taking, timer authority, or grading. It operates exclusively on completed, post-finalization artifacts.
5. **Prerequisite for Subsequent Phases:** Advanced cohort management and notification features will generate further telemetry; the lifecycle and retention framework must be operational first.

---

## 3. Product Requirements

### 3.1 Primary User Roles
* **System Administrator / Compliance Officer (`Role.ADMIN`):**
  - Configures retention policy rules and inspects system storage metrics.
  - Places, manages, and releases **Legal Holds** on students, assessments, or specific attempts.
  - Inspects the **Tombstone Registry** and audits cryptographic proofs of data scrubbing.
  - Triggers manual or emergency compliance purges with mandatory double-confirmation.
* **Student (`Role.STUDENT`):**
  - Views data retention status and upcoming purge dates on past attempts.
  - Exercises **Data Subject Access Rights (DSAR)** by downloading a self-service encrypted archive of their personal assessment data prior to 30-day purge.
  - Inspects permanent transcripts that survive data scrubbing.

### 3.2 Functional Requirements
1. **Multi-Tier Automated Retention Worker:**
   - Daily scheduled Celery beat task scanning attempts past their deterministic `detailed_data_expires_at`.
   - Verifies the **Retention / Finalization Synchronization Invariant**: No attempt may be scrubbed unless `AssessmentResult` is `FINALIZED` and `HistoricalResultSummary` exists.
   - Batch scrubbing (`CHUNK_SIZE = 100`) using `select_for_update(skip_locked=True)` to prevent table contention with active test sessions.
2. **Data Scrubbing Hierarchy:**
   - **Scrubbed Detailed Data (Deterministic TTL, Default 30 Days):**
     - `AttemptAnswer`: `text_response`, `selected_options`, `code_response` cleared.
     - `CodeSubmission`: `source_code`, `compilation_error` wiped.
     - `CodeTestCaseResult`: `actual_output`, `error_message` wiped.
     - `ProctoringEvent`: Raw event telemetry rows unlinked and deleted.
     - `ProctoringEvidence`: Keyframe JPEG files unlinked via retryable `FileCleanupQueue`.
     - `QuestionResult`: `evaluation_details` scrubbed of itemized response internals.
   - **Operational Risk Purge (90-Day Window):**
     - `ProctoringSession`: `risk_score` set to NULL, `risk_band` set to `'PURGED'`. Non-scoring risk data is never permanently retained.
   - **Retained Permanent Data (Indefinite):**
     - `HistoricalResultSummary`: Student EUID, Snapshot Title, Score, Percentage, Pass/Fail, Timestamps.
     - `AssessmentResult`: Header metadata with `details_purged = True`.
     - `Assessment` & `AssessmentSnapshot`: Immutable historical configurations.
     - `AuditLog`: Immutable, append-only compliance trail.
3. **Legal Hold Subsystem & Serialization:**
   - Prevents automated or manual purging of all records linked to an attempt, student, or assessment under active inquiry.
   - Supports states: `ACTIVE`, `RELEASED`.
   - Participates in the same row-lock serialization boundary as purge execution.
4. **Cryptographic Proof of Scrubbing (Tombstone Registry):**
   - Minted ONLY when both database scrub and all associated filesystem unlinks are confirmed.
   - Contains: `attempt_id`, `student_id`, `student_euid`, `assessment_id`, `assessment_title_snapshot`, timestamp, scrubbed counts, confirmed reclaimed bytes, and HMAC-SHA256 keyed integrity proof.
5. **Student Data Export (DSAR Allowlist):**
   - Student can request a downloadable, structured JSON archive of their personal exam telemetry before the 30-day purge deadline, strictly filtered via an allowlist that redacts hidden test cases, answer keys, and evaluator internals.

### 3.3 Explicit Non-Goals
Phase 9 will **NOT** implement:
- Automated academic regrading or result alteration.
- Multi-college SaaS tenancy or cloud bucket replication (local-first storage architecture preserved).
- Live video streaming or remote proctor takeover.
- Custom institution department / batch hierarchy (reserved for Phase 10).
- Outbound email / SMS notification delivery (reserved for Phase 11).

---

## 4. Architectural Integration & System Flow

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                            Existing Frozen Platform                         │
│   Phase 5 (Attempts)  │  Phase 6 (Code)  │  Phase 7 (Proctor)  │ Phase 8 (Ledger)│
└─────────────┬───────────────────┬──────────────────┬───────────────────┬─────┘
              │                   │                  │                   │
              ▼                   ▼                  ▼                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                   Phase 9 Retention & Compliance Engine                     │
│                                                                             │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                      RetentionPolicyEngine                          │   │
│   │  • Deterministic deadlines: detailed_data_expires_at                │   │
│   │  • Policy versioning & audit lineage                                │   │
│   │  • Evaluates LegalHold under row-lock serialization boundary        │   │
│   └──────────────────────────────────┬──────────────────────────────────┘   │
│                                      │                                      │
│                                      ▼                                      │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                      ScrubbingPipelineService                       │   │
│   │  • Stage 1: Authoritative Database Scrub (Atomic DB transaction)    │   │
│   │  • Stage 2: Asynchronous Filesystem Cleanup via FileCleanupQueue    │   │
│   │  • Stage 3: Mint RetentionTombstone with HMAC-SHA256 integrity      │   │
│   └──────────────────────────────────┬──────────────────────────────────┘   │
│                                      │                                      │
│                                      ▼                                      │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                      LegalHoldManagerService                        │   │
│   │  • Places / Releases holds on attempts, students, assessments       │   │
│   │  • Serialization against concurrent purge execution                 │   │
│   └──────────────────────────────────┬──────────────────────────────────┘   │
│                                      │                                      │
│                                      ▼                                      │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                      StudentDataExportService                       │   │
│   │  • Strict allowlist: Student answers, code, scores, own telemetry   │   │
│   │  • Redacts hidden test cases, answer keys, and other students       │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            REST API Layer (/api/v1/)                        │
│   • Admin: /admin/retention/policies/       • Admin: /admin/legal-holds/    │
│   • Admin: /admin/retention/metrics/        • Admin: /admin/tombstones/     │
│   • Admin: /admin/retention/purge/preview/  • Student: /student/privacy/    │
└──────────────────────────────────────┬──────────────────────────────────────┘
```

---

## 5. Frozen-Phase Compatibility

| Frozen Phase | Dependency Type | Strict Operational Boundary |
| :--- | :--- | :--- |
| **Phase 1 (Auth & RBAC)** | `READ ONLY` | Uses `User`, `Role.ADMIN`, `Role.STUDENT`. No changes to authentication. |
| **Phase 2 (User Foundation)** | `READ ONLY` | Respects `is_active` and password security rules. |
| **Phase 3 (Student Profiles)**| `READ ONLY` | Preserves deterministic EUID and roll numbers. |
| **Phase 4 (Question Bank)** | `READ ONLY` | Question versions, difficulty, and tags are permanently preserved. |
| **Phase 5 (Assessment Engine)**| `READ ONLY` | `TestAttempt` schema remains 100% frozen. Phase 9 introduces a separate `RetentionRecord` model (1:1 with `TestAttempt`) to govern retention lifecycles without schema changes to Phase 5 tables. |
| **Phase 6 (Code Execution)** | `READ ONLY / EXTENSION`| Purges `CodeSubmission.source_code` and testcase output logs. Scores and verdicts remain in Phase 8 ledger. |
| **Phase 7 (AI Proctoring)** | `READ ONLY / EXTENSION`| Unlinks keyframe JPEG images from disk and deletes raw `ProctoringEvent` rows. `risk_score` nulled after 90 days. |
| **Phase 8 (Results & Ledger)**| `READ ONLY / EXTENSION`| Consumes `RetentionService`. `AssessmentResult` header and `HistoricalResultSummary` are never deleted. `details_purged = True` is updated. |

---

## 6. Comprehensive Architectural Invariants

1. **The Frozen Baseline Invariant:** Phase 1–8 remain permanently frozen; `TestAttempt`, `Assessment`, and `AssessmentResult` schemas are not altered by Phase 9.
2. **The RetentionRecord Ownership Invariant:** `RetentionRecord` (1:1 with `TestAttempt`) exclusively owns retention deadlines, purge states, and policy versions.
3. **The Synchronization Invariant:** An attempt's detailed data MUST NEVER be purged while its `AssessmentResult` is in `PENDING` or `PROCESSING` status.
4. **The Legal Hold Immunity Invariant:** Any record associated with an `ACTIVE` `LegalHold` (whether scoped by attempt, student, or assessment) is strictly immune to scrubbing.
5. **The Universal Lock Order Invariant:** All concurrent transactions acquire locks strictly in order: `Assessment` -> `User (Student)` -> `TestAttempt` -> `RetentionRecord` -> `LegalHold` -> `ExportJob`.
6. **The Scope Lock Serialization Invariant:** Legal-hold creation, legal-hold release, and purge eligibility for the same scope MUST serialize through the same scope-owner lock.
7. **The Scalable Hold Invariant:** Scope-level holds lock their respective scope parent (`Assessment` or `User`), preventing thousands of attempt row locks.
8. **The Post-Purge Hold Invariant:** A legal hold placed after DB scrubbing applies strictly to surviving permanent metadata; it cannot restore destroyed data.
9. **The Permanent Transcript Invariant:** `HistoricalResultSummary` and `AssessmentResult` metadata headers are PERMANENT and MUST NEVER be deleted by retention scrubbing.
10. **The Non-Scoring Invariant:** Retention operations MUST NEVER alter earned points, total points, percentages, or pass/fail verdicts.
11. **The Deterministic Deadline Invariant:** Retention deadlines (`detailed_data_expires_at`) are stamped at finalization; subsequent policy changes do not silently alter existing deadlines.
12. **The Decoupled Cleanup Invariant:** Database scrubbing is authoritative; filesystem file unlinking is a separate, retryable operation that never rolls back an authoritative DB scrub.
13. **The No-I/O-under-lock Invariant:** Filesystem deletion, network I/O, and long-running export generation MUST NOT occur while critical database row locks are held.
14. **The Tombstone Integrity Invariant:** `RetentionTombstone` is minted ONLY when the full destruction contract (DB + filesystem) is confirmed, and is sealed with an HMAC-SHA256 keyed integrity proof.
15. **The Tombstone Immutability Invariant:** Tombstone records are append-only; updates and deletions raise `PermissionDenied`.
16. **The PII Minimization Invariant:** Tombstones store internal UUIDs and necessary audit IDs; redundant PII (roll numbers, full prompts) is excluded.
17. **The DSAR Allowlist Invariant:** Student exports are strictly allowlist-filtered; hidden tests, answer keys, compiler flags, and other students' data are never exported.
18. **The DSAR Post-Purge Invariant:** Requests following data scrubbing return partial archives containing permanent transcripts and tombstone certificates; deleted data is never reconstructed.
19. **The DSAR/Purge Serialization Invariant:** DSAR snapshot acquisition and destructive purge for the same attempt MUST serialize through the defined database locking boundary. Neither operation may make a contradictory protection decision concurrently.
20. **The Snapshot Commit Invariant:** `SNAPSHOT_ACQUIRED` may be committed only after the complete allowlisted snapshot has been successfully materialized.
21. **The No False Protection Invariant:** A failed or rolled-back DSAR snapshot acquisition MUST NOT leave the export in a state that blocks purge.
22. **The Export Lock Ordering Invariant:** `ExportJob` MUST always be acquired after `RetentionRecord` whenever both resources are locked by the same transaction.
23. **The DSAR Authenticated Encryption Invariant:** DSAR archives are encrypted at rest using AES-256-GCM with unique 96-bit nonces and derived DEKs.
24. **The Key Retention vs. Archive Lifetime Invariant:** An encryption key version MUST remain available for decryption for at least the maximum remaining lifetime of every non-expired archive encrypted with that key version.
25. **The Double-Confirmation Invariant:** Manual purge requires a signed 5-minute preview token and re-validates legal holds and eligibility at execution time.
26. **The Purge Idempotency Invariant:** Redundant purge executions on an already purged attempt yield zero changes and create zero duplicate tombstones.
27. **The Accurate Storage Invariant:** Reclaimed storage metrics reflect confirmed filesystem bytes freed, not synthetic estimates.
28. **The Active Session Safety Invariant:** Attempts in `NOT_STARTED` or `IN_PROGRESS` status are structurally excluded from purge queries.
29. **The Informational Risk Invariant:** Proctoring risk scores are non-scoring operational telemetry with a 90-day retention window; they are never converted into automatic disciplinary judgments.
30. **The Separate Risk Lifecycle Invariant:** Proctoring `risk_band` values are strictly evaluation classifications; purge states are tracked separately via `risk_data_status`.
31. **The Append-Only Audit Invariant:** All policy modifications, hold placements, releases, and purge operations append to `AuditLog`.
32. **The Authoritative Serialization Invariant:** `TestAttempt` and its associated `RetentionRecord` constitute the authoritative database serialization boundary for destructive retention operations and DSAR snapshot acquisition concerning that attempt.
33. **The ExportJob Subordination Invariant:** `ExportJob` state MUST NOT be treated as the sole concurrency guard for destructive retention; safety derives strictly from row locks on `TestAttempt` and `RetentionRecord`.
34. **The Bounded Pending Invariant:** A DSAR job in `SNAPSHOT_PENDING` cannot indefinitely block purge without an active valid lease/heartbeat (`lease_expires_at > now()`).
35. **The Stale Recovery Serialization Invariant:** Stale DSAR recovery MUST serialize through the same `TestAttempt + RetentionRecord` boundary used by snapshot acquisition and purge.
36. **The No False Failure Invariant:** A legitimate active snapshot worker MUST NOT be marked stale solely because another worker observed an outdated state; recovery re-verifies lease status under exclusive row locks.

