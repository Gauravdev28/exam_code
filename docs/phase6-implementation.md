# CODEGUARD — Phase 6 Implementation Report: Secure Code Execution & Evaluation

---

## 1. Executive Summary

Phase 6 implements the **Secure Code Execution & Evaluation Engine** for CODEGUARD. It enables students to execute untrusted code in a sandboxed execution boundary (`RUN`), submit solutions for authoritative partial scoring (`SUBMIT`), and receive real-time execution feedback via Django Channels WebSockets while preserving complete historical snapshot immutability.

---

## 2. Architecture & Subsystems Implemented

### 2.1 Evaluator Django App (`apps.evaluator`)
* **`CodeSubmission`**: Represents an execution or evaluation job, linked to `TestAttempt` and `AssessmentSnapshotQuestion`. Retains frozen environment version (`CG-ENV-PY311-V1`, `CG-ENV-CPP13-V1`, `CG-ENV-JAVA17-V1`), execution policy version, comparison policy version, execution time, memory usage, score awarded, and compilation error diagnostics.
* **`CodeTestCaseResult`**: Represents per-test-case execution metrics and verdicts (`PASSED`, `FAILED`, `TIME_LIMIT_EXCEEDED`, `MEMORY_LIMIT_EXCEEDED`, `RUNTIME_ERROR`). Strictly ensures `public_input`, `expected_output`, and `actual_output` are `NULL` for hidden test cases.

### 2.2 Authoritative Domain Services (`apps.evaluator.services`)
* **`OutputComparisonService`**: Implements deterministic output comparison policies:
  - `EXACT_STRIPPED`: Normalizes CRLF $\rightarrow$ LF, strips line trailing whitespace, strips EOF newlines, preserves internal whitespace, case-sensitive.
  - `FLOAT_TOLERANT`: Tokenizes floating point values with relative/absolute error tolerance ($\epsilon = 10^{-6}$).
  - `TOKEN_MATCH`: Compares sequence of whitespace-delimited tokens.
* **`ScoringService`**: Evaluates partial credit $\sum_{tc \in \text{Passed}} tc.\text{points}$. Enforces negative marking penalties ($0/N$ passed $\rightarrow$ deduct `negative_points`, floored at 0.00).
* **`Judge0Adapter`**: Maps supported runtime languages (`PYTHON`, `CPP`, `JAVA`), prepares batch execution payloads, and handles sandboxed execution results.
* **`CodeSubmissionService`**: Enforces attempt ownership, server-authoritative timer checks (`now < expires_at`), rate limiting (6/min for Run, 3/min for Submit), concurrency limits (max 1 active, max 2 queued), idempotency key deduplication, Celery task dispatch, and WebSocket push broadcasting.

### 2.3 Celery Execution Pipeline (`apps.evaluator.tasks`)
* **`evaluate_code_submission_task`**: Executes asynchronously with `acks_late=True`, exponential backoff retry for infrastructure errors (max 3 retries), and transactional answer updates for `SUBMIT`.

### 2.4 REST & WebSocket APIs
* `POST /api/v1/student/attempts/<attempt_id>/questions/<question_id>/run/`
* `POST /api/v1/student/attempts/<attempt_id>/questions/<question_id>/submit/`
* `GET /api/v1/student/submissions/<submission_id>/`
* `GET /api/v1/admin/assessments/<assessment_id>/submissions/`
* `GET /api/v1/admin/submissions/<submission_id>/`
* WebSocket `attempt_event` consumer pushing `CODE_SUBMISSION_QUEUED`, `CODE_SUBMISSION_PROCESSING`, and `CODE_SUBMISSION_COMPLETED` events.

### 2.5 Frontend Monaco Test Room Integration (`frontend/src/`)
* Added Run Code (Public Tests) and Submit Solution buttons to `StudentTestRoomPage.tsx`.
* Added real-time execution results console with verdict badges, pass counts, scores, execution times, memory usage, compilation error output box, and per-test-case tabs with hidden test case protection.
