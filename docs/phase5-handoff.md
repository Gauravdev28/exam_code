# CODEGUARD — Phase 5 Handoff & Phase 6 Integration Specification

## 1. Phase 5 Status
```text
STATUS: APPROVED
STATUS: FROZEN
STATUS: READY FOR PHASE 6 DESIGN & PLANNING
```

The Phase 5 foundation (Assessment Engine, Immutable Snapshots, Server-Authoritative State, Deterministic Randomization, Race-Safe Answer Autosave, and Student Test Room) is completed, verified with 103/103 tests, and permanently frozen.

---

## 2. Frozen Phase 5 Architectural Contracts

Phase 6 and all subsequent phases must build upon and respect the frozen Phase 5 contracts:

```text
QuestionVersion
      ↓
Assessment (DRAFT -> PUBLISHED -> ARCHIVED)
      ↓
AssessmentSnapshot (Self-contained, permanently immutable)
      ↓
AssessmentAssignment (Student access authorization)
      ↓
TestAttempt (Server-authoritative timer, seed, order, state)
      ↓
AttemptAnswer (Bound to AssessmentSnapshotQuestion, revision-controlled)
```

### 2.1 Entity Models & Invariants
1. **`Assessment`**: Container for scheduled exams (`start_datetime`, `end_datetime`, `duration_minutes`, `total_points`, `attempt_limit`, `randomize_questions`, `randomize_options`). Enforces `SUM(AssessmentQuestion.points) == Assessment.total_points` on publication.
2. **`AssessmentQuestion`**: Ordered links between `Assessment` and immutable published `QuestionVersion` records.
3. **`AssessmentAssignment`**: Student authorization record with `UniqueConstraint(fields=['assessment', 'student'])`.
4. **`AssessmentSnapshot` & `AssessmentSnapshotQuestion`**: Permanently immutable frozen definition of the exam created at publish time. Model-level `save()` and `delete()` methods raise `PermissionDenied`.
5. **`TestAttempt`**: Student runtime attempt (`started_at`, `expires_at = MIN(start + duration, assessment.end_datetime)`, `randomization_seed`, `status`).
6. **`AttemptAnswer`**: Student response storage linked to `snapshot_question` with integer `revision` preventing stale overwrite races.

### 2.2 Server-Authoritative Guarantees
* **Server Timer Authority**: Remaining seconds are calculated dynamically on the server from `expires_at - now`. Browser clock changes or page refreshes cannot extend the attempt.
* **Hidden Data Redaction**: Secret/hidden test cases and `server_evaluation_bundle` are stored in `AssessmentSnapshot` and strictly redacted from student serializers, REST responses, and WebSocket frames.
* **Draft Storage Only**: In Phase 5, student coding (`code_response`, `code_language`) and SQL (`sql_response`) answers are persisted safely as drafts. Phase 5 performs **no code compilation or execution**.

---

## 3. Phase 6 Input Contract

Phase 6 (**Sandboxed Coding Evaluation & Judge0 Integration**) will consume the following frozen data structures:

```text
AssessmentSnapshot
      ↓
AssessmentSnapshotQuestion (question_type = 'CODING')
      ↓
TestAttempt
      ↓
AttemptAnswer (code_response, code_language)
```

### Required Evaluation Inputs Available for Phase 6:
* **Student Code**: `AttemptAnswer.code_response` (string source code).
* **Language**: `AttemptAnswer.code_language` (`PYTHON`, `CPP`, `JAVA`).
* **Constraints**: `AssessmentSnapshotQuestion.coding_config` (`time_limit_ms`, `memory_limit_mb`).
* **Public Examples**: `AssessmentSnapshotQuestion.coding_config['public_test_cases']`.
* **Complete Evaluation Suite**: `AssessmentSnapshot.server_evaluation_bundle[snapshot_question_id]['all_test_cases']` (accessed strictly by trusted server evaluation services).
* **Scoring Rules**: `AssessmentSnapshotQuestion.points`, `negative_marking_enabled`, `negative_points`.

> **CRITICAL SECURITY INVARIANT**:
> Hidden test cases and `server_evaluation_bundle` must remain exclusively server-side. Phase 6 evaluation workers will read evaluation bundles directly from backend models/services, never through student-facing APIs.

---

## 4. Planned Phase 6 Scope (Document Only)

```text
Judge0 / Isolated Execution Engine
               ↓
     Secure Worker Sandbox
               ↓
    Compilation & Validation
               ↓
    Isolated Execution (Limits)
               ↓
     Test Case Verification
               ↓
       Partial Scoring
               ↓
     Persisted Evaluation Run
```

### Supported Initial Languages:
1. **Python** (3.11+)
2. **C++** (GCC / Clang C++17/20)
3. **Java** (OpenJDK 17/21)

### Planned Capabilities for Phase 6:
* **Sandboxed Execution**: Isolated container/cgroup environment for running untrusted student code.
* **Strict Resource Limits**: Enforcement of CPU time limits (`time_limit_ms`) and memory ceilings (`memory_limit_mb`).
* **Security Containment**: Process isolation, network isolation (no outbound socket access), and read-only filesystem environments.
* **Execution Statuses**: Handlers for `ACCEPTED`, `WRONG_ANSWER`, `TIME_LIMIT_EXCEEDED`, `MEMORY_LIMIT_EXCEEDED`, `COMPILATION_ERROR`, `RUNTIME_ERROR`.
* **Deterministic Partial Scoring**: Automated scoring based on weighted test case points.

---

## 5. Phase 6 Security & Isolation Design Gate

> [!CAUTION]
> **UNTRUSTED CODE EXECUTION MANDATE**:
> Phase 6 must **NEVER** execute arbitrary student code inside Django, Celery, Redis, MySQL, Nginx, or the main application container.
> Untrusted student code must be executed inside dedicated, sandboxed execution runners (e.g., Judge0 in isolated containers with drop-capabilities, seccomp filters, and disabled networking).

Before any Phase 6 implementation begins, the sandbox and execution architecture must undergo a formal **Architecture Design & Review**.

---

## 6. Verification Baseline

* **Backend Tests**: 103 passed, 3 warnings in 0.70s (`pytest -v`).
* **Frontend Build**: 1599 modules, 0 build errors in 964ms (`tsc && vite build`).
* **Regressions**: 0 regressions across Phase 1, Phase 2, Phase 3, Phase 4, Phase 5.
