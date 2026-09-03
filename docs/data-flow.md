# CODEGUARD — End-to-End Data Flow Specification

**Document Version:** 1.0.0  
**Status:** Baseline System Data Flow  
**Scope:** Lifecycle from Student Onboarding to Cryptographic Purge  

---

## 1. High-Level Lifecycle Diagram

```text
┌────────────────────────┐
│ 1. Student Onboarding  │ Student account registered / imported with immutable EUID
└───────────┬────────────┘
            │
            ▼
┌────────────────────────┐
│ 2. Assessment Assigned │ Assessment published with frozen Question Snapshot
└───────────┬────────────┘
            │
            ▼
┌────────────────────────┐
│ 3. Attempt Start       │ TestAttempt created (IN_PROGRESS), server countdown starts
└───────────┬────────────┘
            │
            ├─────────────────────────────────────────┐
            ▼                                         ▼
┌────────────────────────┐               ┌────────────────────────┐
│ 4. Code / Answer Exec  │               │ 5. AI Telemetry & CV   │
│ Code submitted to      │               │ Periodic keyframes,    │
│ Judge0 sandbox;        │               │ face/gaze/object ML,   │
│ test cases evaluated   │               │ advisory risk scoring  │
└───────────┬────────────┘               └───────────┬────────────┘
            │                                         │
            │           ┌─────────────────────────────┤
            │           ▼ (Planned Phase 10)          │
            │   ┌───────────────────────────┐         │
            │   │ Live Human Invigilation   │         │
            │   │ Proctor triage grid,      │         │
            │   │ warnings, pause, term     │         │
            │   └─────────────┬─────────────┘         │
            │                 │                       │
            ├─────────────────┴───────────────────────┘
            ▼
┌────────────────────────┐
│ 6. Attempt Submission  │ Candidate submits or timer expires (terminal state)
└───────────┬────────────┘
            │
            ▼
┌────────────────────────┐
│ 7. Result Finalization │ Phase 8 computes scores, grade band, scorecard PDF,
│                        │ and mints immutable HistoricalResultSummary
└───────────┬────────────┘
            │
            ▼
┌────────────────────────┐
│ 8. Retention Stamping  │ Phase 9 policy stamps detailed_data_expires_at
└───────────┬────────────┘
            │
            ├─────────────────────────────────────────┐
            ▼                                         ▼
┌────────────────────────┐               ┌────────────────────────┐
│ 9a. DSAR Export        │               │ 9b. Automated Purge    │
│ Student requests       │               │ Deadline reached:      │
│ AES-256-GCM archive    │               │ DB scrub committed     │
│ within 7-day TTL       │               │ Files unlinked via Celery
└────────────────────────┘               │ HMAC tombstone minted  │
                                         └────────────────────────┘
```

---

## 2. Detailed Stage Walkthrough

### Stage 1: Student Onboarding & Authentication
1. Admin imports students via CSV or creates individual student profiles.
2. System assigns an immutable `EUID` (Enterprise Unique Identifier) and roll number.
3. Student logs in via `/api/v1/auth/token/`; server validates credentials and sets `HttpOnly` JWT cookies.

### Stage 2: Assessment Scheduling & Snapshotting
1. Instructor/Admin authors questions in the question bank (`MCQ`, `CODING`, `SQL`).
2. Assessment is created with start datetime, end datetime, and duration.
3. Upon publishing, `AssessmentSnapshotService` freezes questions and test cases into an `AssessmentSnapshot`. Future edits to the question bank do not touch active exams.

### Stage 3: Attempt Initiation & Runtime Synchronization
1. Student enters exam room at `/student/assessments/{id}/room/`.
2. Client calls `POST /api/v1/student/attempts/start/`.
3. Server creates `TestAttempt` with status `IN_PROGRESS` under database row lock.
4. Client connects to WebSocket `ws/attempts/{attempt_id}/` (`TestAttemptConsumer`). Server syncs authoritative remaining seconds.

### Stage 4: Code Execution & Grading (Phase 6)
1. Candidate writes code in Monaco Editor and clicks "Run Code" or "Submit".
2. Backend validates rate limits and sends source code, compiler options, and test cases to Judge0 CE via internal HTTP.
3. Judge0 executes code in an unprivileged, network-isolated sandbox with CPU and memory quotas.
4. Execution results (exit code, stdout, stderr, execution time) return to backend.
5. Visible test case results return to candidate; hidden test case results are concealed.

### Stage 5: AI Proctoring & Telemetry Stream (Phase 7)
1. Student browser captures webcam keyframes periodically using HTML5 Canvas.
2. Keyframes and telemetry events (tab switches, full-screen exits) are sent to `/api/v1/proctoring/events/`.
3. OpenCV and MediaPipe models evaluate face presence, multi-face presence, gaze direction, and device detection.
4. `ProctoringSession` recalculates the cumulative mathematical `risk_score` (0–100) and assigns a `RiskBand` (`NORMAL`, `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`).
5. Real-time alerts stream over WebSocket to the admin dashboard.

### Stage 6: Future Human Invigilation Loop (Planned Phase 10)
1. Assigned proctor monitors up to 25 students in the `ProctorLiveConsolePage`.
2. Phase 7 keyframes and risk bands stream into the proctor's mosaic grid.
3. If suspicious activity occurs, proctor issues a binding intervention via REST:
   - Warning $\to$ candidate receives non-dismissible modal.
   - Pause $\to$ attempt timer halts on server; candidate editor is frozen.
   - Disqualification $\to$ attempt is terminated with cause.

### Stage 7: Attempt Finalization & Scoring (Phase 8)
1. Candidate submits or timer reaches 0 $\to$ attempt transitions to `SUBMITTED`, `EXPIRED`, or `CANCELLED`.
2. `ResultFinalizationService.finalize_attempt()` executes:
   - Grades all submitted answers and code executions.
   - Computes weighted section scores, overall score, and grade band.
   - Mints `AssessmentResult` and immutable `HistoricalResultSummary`.
   - Generates tamper-proof scorecard PDF with SHA-256 verification hash.

### Stage 8: Retention Governance & Cryptographic Purge (Phase 9)
1. Immediately following finalization, `RetentionPolicyEngine` resolves applicable retention policy and stamps `RetentionRecord.detailed_data_expires_at`.
2. **DSAR Self-Service**: Student can request an encrypted AES-256-GCM ZIP archive containing their own exam submissions, scorecard, and webcam frames.
3. **Automated Purge**:
   - Nightly Celery task detects expired records.
   - `AuthoritativeScrubbingService` acquires `TestAttempt` row lock.
   - Verifies no active `LegalHold` exists.
   - DB Scrub: Destructively wipes answers, code submissions, telemetry, and keyframe metadata $\to$ Commits transaction.
   - File Cleanup: Queues files in `FileCleanupQueue`; Celery worker unlinks disk files asynchronously.
   - Tombstone: When 100% of files are confirmed deleted, mints a permanent `RetentionTombstone` with an HMAC-SHA256 proof.
