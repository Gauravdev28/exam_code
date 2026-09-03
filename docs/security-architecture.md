# CODEGUARD — Security Architecture Specification

**Document Version:** 1.0.0  
**Status:** Comprehensive Security Baseline  
**Scope:** Phases 1–9 Implemented & Phase 10 Invariants  

---

## 1. Authentication & Session Security

1. **Token Transport**: Short-lived JWT access tokens (60-minute expiry) and refresh tokens (7-day expiry) delivered strictly via `HttpOnly`, `SameSite=Lax`, `Secure` cookies. Browser JavaScript has zero programmatic access to authentication tokens, neutralizing Cross-Site Scripting (XSS) token theft.
2. **Password Hashing**: Cryptographic password hashing utilizing Argon2id and Django's PBKDF2 with SHA-256 (600,000 iterations).
3. **Session Revocation & Blocklist**: Refresh tokens and revoked sessions are tracked in Redis. Password changes or administrative lockouts immediately invalidate active sessions.

---

## 2. Role-Based Access Control (RBAC) & Object-Level Authorization (IDOR Defense)

CODEGUARD enforces strict dual-layer authorization:
- **System Roles**: `ADMIN`, `INSTRUCTOR`, `PROCTOR`, `STUDENT`.
- **Object-Level Scoping**:
  - `Student`: Can only access their own assigned assessments, own active attempts, own submission results, and own DSAR export archives.
  - `Proctor`: Can only view telemetry, keyframes, and intervention actions for assessments they are explicitly assigned to via `ProctorAssignment`.
  - `Admin`: Global management scope subject to strict audit logging.
- **IDOR Defense**: All database queries resolve objects via foreign key ownership (e.g. `TestAttempt.objects.filter(id=attempt_id, student=request.user)`). Knowledge of another candidate's UUID yields `404 Not Found` or `403 Forbidden`.

---

## 3. Sandboxed Code Execution Security (Judge0 CE)

To protect host infrastructure from malicious student code submissions (e.g. fork bombs, disk fill attacks, reverse shells, memory exhaustion):
1. **Linux Kernel Sandboxing**: Submissions run inside containerized Linux `isolate` sandboxes with strict `cgroups` enforcement.
2. **Resource Quotas**:
   - Max CPU Time: 2.0 seconds per test case.
   - Max Memory: 256 MB per execution.
   - Max Disk Output: 10 MB limit.
   - Process Limits: Max 30 processes (blocks `fork()` bombs).
3. **Zero Network Egress**: Sandbox containers have network interfaces dropped (`--net=none`), preventing SSRF attacks, crypto-mining connections, or data exfiltration.
4. **Non-Root Execution**: Code runs as an unprivileged ephemeral user (`judge0`).

---

## 4. Academic Integrity & Test Leakage Defense

1. **Hidden Test Case Protection**: Test cases flagged as `is_hidden=True` are graded server-side. Their inputs, expected outputs, and execution details are strictly filtered out of API responses. Candidates only receive high-level status (`PASSED` or `FAILED`).
2. **Assessment Snapshotting**: When an assessment is published, questions and test cases are copied into an immutable `AssessmentSnapshot`. Modifications to the master question bank cannot alter ongoing or completed exams.
3. **Full-Screen & Tab-Switch Telemetry**: The student test room detects blur events, tab switches, and full-screen exits, streaming telemetry events to Phase 7 for risk scoring.

---

## 5. Vision AI Telemetry & Keyframe Security

1. **Ephemeral Keyframe Transport**: Periodic webcam keyframes are captured locally via Canvas API, transmitted over authenticated WebSocket/REST to Phase 7 ingest, and evaluated in transient memory.
2. **Evidence Isolation**: Unflagged normal keyframes are discarded. Flagged violation keyframes are saved to a restricted directory outside public web roots and accessed via time-limited authenticated view endpoints.
3. **Cross-Assessment Isolation**: Invigilation Channels groups are strictly partitioned (`proctor_assessment_{assessment_id}`). Proctors cannot listen to keyframes from unassigned assessments.

---

## 6. Data Retention, Legal Holds & DSAR Cryptography (Phase 9)

1. **Authoritative Purge Pipeline**:
   - Stage 1: Destructive database scrub under canonical row locks (`select_for_update()`). Detailed code, answers, proctoring events, and telemetry rows are irreversibly wiped.
   - Stage 2: Database transaction commits $\to$ unlinking jobs queued in `FileCleanupQueue`.
   - Stage 3: Asynchronous Celery worker unlinks disk files (webcam frames, exports) with path traversal defense (`os.path.realpath` checks).
   - Stage 4: 100% of required files confirmed deleted $\to$ immutable `RetentionTombstone` minted.
2. **Cryptographic Tombstones**:
   - `RetentionTombstone` proves compliance without retaining student PII.
   - Bound by a keyed **HMAC-SHA256** integrity proof computed over `{attempt_id}:{student_euid}:{assessment_id}:{purged_at}:{bytes_reclaimed}` using server-side `settings.SECRET_KEY`.
   - Any attempt to update or delete a tombstone raises `PermissionDenied`.
3. **Legal Hold Freezing**:
   - Legal holds (`ATTEMPT`, `STUDENT`, `ASSESSMENT`) block database scrubbing and file unlinking. Distinct scopes may overlap, while duplicate active holds on the same target are forbidden.
4. **DSAR Encryption**:
   - Self-service student DSAR export archives are encrypted using **AES-256-GCM** with a 96-bit random nonce and 16-byte authentication tag.
   - Derives ephemeral encryption keys via **HKDF-SHA256** using `settings.SECRET_KEY` and the `export_job_id` bytes as salt.
   - Archives auto-expire and are permanently deleted after 7 days.
5. **Server-Side DSAR Allowlist**:
   - Includes: Student profile, own answers, own submitted code, visible questions, scorecard, summarized anomaly timeline, own webcam keyframes.
   - Strictly Excludes: Hidden test cases, expected outputs, compiler flags, peer data, internal proctor notes, staff user IDs.

---

## 7. Injection & Export Security

1. **SQL Injection Defense**: 100% of database access is handled through Django ORM parameterized queries. Raw string concatenation in SQL queries is prohibited.
2. **Formula Injection (CSV / XLSX Sanitization)**: All student-supplied text exported into grade reports or CSVs is sanitized to neutralize spreadsheet formula injection (stripping or prepending single quotes to fields starting with `=`, `+`, `-`, `@`, `\t`, `\r`).
3. **Path Traversal Defense**: All file unlinking and archive streaming operations strictly assert `target_path.startswith(settings.MEDIA_ROOT)`.
