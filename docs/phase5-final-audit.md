# CODEGUARD — Phase 5 Final Audit & Freeze Verification Report

## Executive Result
```text
PHASE 5 — APPROVED / READY TO FREEZE
```

Phase 5 (**Assessment Engine & Server-Authoritative State**) has undergone an exhaustive codebase audit across models, database migrations, domain services, serializers, REST endpoints, Channels WebSocket consumers, permissions, frontend architecture, and automated test suites.

---

## 1. Audit Matrix

| Requirement | Result | Evidence / Implementation Details |
| :--- | :--- | :--- |
| **Phase 1–4 Regression Integrity** | **PASS** | 103 total tests passed, 3 warnings (0 skipped, 0 xfailed). Phase 1 (13), Phase 2 (16), Phase 3 (25), Phase 4 (27), Phase 5 (22) intact. |
| **Snapshot Question Binding** | **PASS** | `AttemptAnswer.snapshot_question` directly binds to `AssessmentSnapshotQuestion` (`models.ForeignKey(AssessmentSnapshotQuestion, on_delete=models.PROTECT)`). Decoupled from future QuestionVersion mutations. |
| **Attempt Concurrency** | **PASS** | `AttemptService.start_attempt` utilizes `select_for_update()` with strict database verification of `attempt_limit` and active attempts. |
| **Autosave Race Safety** | **PASS** | `AttemptAnswer.revision` counter rejects stale or out-of-order writes (`client_revision <= answer.revision`). Verified with out-of-order sequence `[13, 12, 14, 11]`. |
| **Submit Race Safety** | **PASS** | `AttemptService.submit_attempt` transitions `IN_PROGRESS -> SUBMITTED` idempotently. Duplicate submissions return the submitted attempt without state corruption. |
| **Expiry Race Safety** | **PASS** | `AttemptTimerService` checks server-side expiration (`now > expires_at`). Expired attempts transition to `EXPIRED` and reject further answer writes. |
| **Hidden Data Protection** | **PASS** | `server_evaluation_bundle` and hidden test cases are isolated server-side and strictly excluded from student serializers and WebSocket frames. |
| **Assignment Revocation** | **PASS** | Unassigned or revoked students are blocked from starting new attempts. Ongoing `IN_PROGRESS` attempts are permitted to complete cleanly without destruction. |
| **Server Timer Authority** | **PASS** | Deadline is computed on server: `expires_at = MIN(started_at + duration, assessment.end_datetime)`. Page refreshes, clock changes, or reconnects cannot extend duration. |
| **REST / WebSocket Consistency** | **PASS** | Both REST views (`StudentAttemptSaveAnswerView`, `StudentAttemptSubmitView`) and WebSocket consumer (`TestAttemptConsumer`) invoke identical `AttemptService` and `AttemptTimerService` methods. |
| **Historical Snapshot Integrity** | **PASS** | `AssessmentSnapshot` captures full self-contained state. Modifying or publishing QuestionVersion V2 leaves existing V1 snapshots 100% untouched. |
| **Student State Protection** | **PASS** | Authoritative fields (`attempt_number`, `started_at`, `expires_at`, `randomization_seed`, `points`, `is_answered`) cannot be overridden via student request payloads. |
| **IDOR Protection** | **PASS** | Attempt access, answer persistence, and submission enforce student ownership (`attempt.student == request.user`). Unauthorized access raises `403 PermissionDenied`. |
| **Database Constraints** | **PASS** | Unique constraints enforced for `AssessmentAssignment (assessment, student)`, `AssessmentQuestion (assessment, question_version / order)`, `TestAttempt (student, assessment, attempt_number)`, `AttemptAnswer (attempt, snapshot_question)`. |
| **Snapshot Immutability** | **PASS** | `AssessmentSnapshot` and `AssessmentSnapshotQuestion` override `save()` and `delete()` to raise `PermissionDenied` on existing instances. |
| **API Lifecycle Rules** | **PASS** | State transitions strictly follow `DRAFT -> PUBLISHED -> ARCHIVED`. Modifications to questions or points on published assessments are rejected. |
| **Backend Regression** | **PASS** | `103 passed, 3 warnings in 0.70s` on `pytest -v`. (Warnings: deprecation warning in dependency auth decorators). |
| **Frontend Build** | **PASS** | `npm run build` completed in `964ms` with 1599 modules transformed and 0 errors. |

---

## 2. Detailed Findings by Audit Category

### Audit #1: Phase 1–4 Regression Integrity
- **Phase 1 Foundation (13 tests)**: Health checks, UUIDs, timestamps, Channels ping, Celery tasks, exception handling.
- **Phase 2 Authentication & RBAC (16 tests)**: Superuser/student login, session invalidation, role elevation protection, password hashing, brute-force rate limiting, WebSocket auth.
- **Phase 3 Student Management & EUID (25 tests)**: Deterministic EUID generation (`CG-{NORMALIZED_ROLL_NUMBER}`), collision rejection without numeric suffixing, bulk CSV/XLSX preview/confirm, student profile protection.
- **Phase 4 Question Bank & Versioning (27 tests)**: 6 question types, point sum scoring invariants, sequential versioning, version immutability on publish, historical snapshot readiness.
- **Phase 5 Assessment Engine (22 tests)**: Assessment drafting, points invariant enforcement (`SUM(points) == total_points`), snapshot immutability, assignments, seeded randomization, server timer deadlines, answer revisions, and Channels sync.

### Audit #2: AttemptAnswer Snapshot Binding
- `AttemptAnswer.snapshot_question` is a direct `ForeignKey` to `AssessmentSnapshotQuestion` with `on_delete=models.PROTECT`.
- When an attempt starts, empty `AttemptAnswer` rows are created pointing directly to the snapshot's immutable question records.
- Creating and publishing new Question Bank versions (`QuestionVersion V2`, `V3`) has zero impact on `AttemptAnswer.snapshot_question`.

### Audit #3: Concurrency & Race Safety
- **Attempt Limit Race**: `start_attempt` uses `Assessment.objects.select_for_update()` and checks existing attempt count before creation, preventing parallel double-start exploits.
- **Revision Control**: `save_answer` compares `client_revision <= answer.revision`. Stale updates return `STALE_REVISION` and do not overwrite the server state. Verified with test `test_concurrency_multi_revision_ordering_race`.
- **Submit Idempotency**: `submit_attempt` transitions the status to `SUBMITTED` atomically; re-submissions return the submitted attempt without state corruption.
- **State Locking**: Once an attempt reaches `SUBMITTED` or `EXPIRED`, all subsequent `save_answer` requests are blocked.

### Audit #4: Hidden Evaluation Data Protection
- `AssessmentSnapshot` cleanly bifurcates data into:
  1. `snapshot_data`: Public metadata, question statements, instructions, options, and public example test cases.
  2. `server_evaluation_bundle`: Hidden/private test cases, SQL expected result queries, and secret evaluation rules.
- Student serializers (`StudentAssessmentListSerializer`, `StudentAttemptAnswerSerializer`, `StudentAttemptDetailView`) and WebSocket messages strictly source from `snapshot_data` and never query or expose `server_evaluation_bundle`.

### Audit #5: Assignment Revocation Semantics
- Tested via `test_assignment_revocation_allows_in_progress_attempt_to_finish_but_blocks_new_attempts`:
  - When an admin revokes an assignment for a student who has an active `IN_PROGRESS` attempt, that existing attempt is allowed to finish and submit normally.
  - The student is permanently blocked from starting any new attempts (`start_attempt` raises `PermissionDenied`).

### Audit #6: Server-Authoritative Timer & Deadlines
- `AttemptTimerService` calculates `expires_at = MIN(started_at + duration_minutes, assessment.end_datetime)`.
- Client clock manipulation or page reloads have zero influence on remaining time, which is computed dynamically from `expires_at - server_now`.

### Audit #7: REST & WebSocket Domain Service Consistency
- Both `StudentAttemptSaveAnswerView` and `TestAttemptConsumer` call `AttemptService.save_answer()`.
- Both `StudentAttemptSubmitView` and `TestAttemptConsumer` call `AttemptService.submit_attempt()`.
- Both REST and WebSocket endpoints call `AttemptTimerService.check_and_expire_attempt_if_needed()`.

### Audit #8: Database Constraints & Immutability
- All key models enforce database-level `UniqueConstraint` and `models.PROTECT` deletion guards.
- `AssessmentSnapshot` and `AssessmentSnapshotQuestion` override `save()` and `delete()` to raise `PermissionDenied`, guaranteeing absolute historical permanence.

---

## 3. Final Decision & Phase 6 Readiness

Phase 5 has met all architectural criteria, passed all verification tests, and contains zero critical or high-severity defects.

```text
STATUS: PHASE 5 IS FROZEN AND OFFICIALLY CLOSED.
ARCHITECTURALLY READY FOR PHASE 6 (Sandboxed Coding Evaluation & Judge0).
```
