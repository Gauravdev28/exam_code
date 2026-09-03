# CODEGUARD — Phase 8 Architecture Specification

## Results, Analytics & Reporting System (Micro-Hardened)

**Status:** PROPOSED & READY FOR ARCHITECTURAL REVIEW  
**Author:** Senior Software Engineer / Software Architect  
**Scope:** Phase 8 Architecture Specification  
**Baseline Status:** Phase 1–7 Frozen (170/170 Backend Tests PASS, 20/20 Security Invariants PASS)  

---

## 1. Executive Summary

Phase 8 introduces the **Results, Analytics & Reporting Engine** for CODEGUARD. Its primary mandate is to project finalized assessment evaluation states into immutable result records (`AssessmentResult`, `QuestionResult`), compute multi-dimensional analytics (question difficulty/discrimination, coding performance, student topic mastery, cohort distributions, time consumption, and proctoring-risk correlations), and orchestrate asynchronous generation of cryptographically verified, sanitized PDF, XLSX, and CSV reports.

### Core Architectural Principle
**There is exactly one authoritative scoring and evaluation path: the Phase 5 Assessment Engine and Phase 6 Evaluation Engine.** Results and Analytics MUST NOT become a secondary scoring engine. Analytics and Reporting strictly consume authoritative finalized result data.

```text
┌────────────────────────────────────────┐
│     Phase 5 Assessment Engine          │ (Immutable Snapshot + Authoritative Timer)
│                 +                      │
│     Phase 6 Evaluation Engine          │ (Isolated Execution + Authoritative Coding Verdicts)
└──────────────────┬─────────────────────┘
                   │ Attempt State: SUBMITTED / EXPIRED
                   ▼
┌────────────────────────────────────────┐
│     Authoritative Evaluation State     │ (Phase 5/6 Authoritative Scoring Contract)
└──────────────────┬─────────────────────┘
                   │
                   ▼
┌────────────────────────────────────────┐
│   Phase 8 Result Projection / Ledger   │ (Immutable AssessmentResult & QuestionResult)
└─────────┬────────────────────┬─────────┘
          │                    │
          ▼                    ▼
┌──────────────────┐  ┌──────────────────┐
│ Analytics Engine │  │ Reporting Engine │
│ (Indexed DB &    │  │ (Async Celery,   │
│  Precomputed)    │  │ PDF, XLSX, CSV)  │
└──────────────────┘  └──────────────────┘
```

---

## 2. Existing-System Dependencies & Boundaries

Phase 8 builds upon and strictly preserves the frozen contracts of Phases 1–7:
- **Phase 1 (Core Foundation):** Uses `UUIDModel`, `TimeStampedModel`, append-only `AuditLog`, custom exception handlers.
- **Phase 2 (Auth & RBAC):** Strict separation between `ADMIN` and `STUDENT` roles.
- **Phase 3 (Student Management):** Links results to deterministic EUID, roll numbers, and student profiles.
- **Phase 4 (Question Bank & Versioning):** Consumes frozen `QuestionVersion`, `Tag`, and question type definitions (`MCQ`, `MULTI_SELECT`, `TRUE_FALSE`, `SHORT_ANSWER`, `CODING`, `SQL`).
- **Phase 5 (Assessment Engine):** Consumes `Assessment`, `AssessmentSnapshot`, `AssessmentSnapshotQuestion`, `TestAttempt` (`SUBMITTED` / `EXPIRED`), and `AttemptAnswer`. Respects `ResultVisibility` (`IMMEDIATE`, `AFTER_DEADLINE`, `MANUAL`).
- **Phase 6 (Secure Code Execution):** Consumes authoritative `CodeSubmission` and `CodeTestCaseResult` records produced by the frozen Phase 6 execution contract. Respects hidden test-case confidentiality.
- **Phase 7 (AI Proctoring):** Reads proctoring summary metrics (`risk_score`, `risk_band`) as non-disciplinary context only. **Proctoring never modifies exam marks or attempt validity.**

---

## 3. Goals & Non-Goals

### Goals
1. **Authoritative Result Projection:** Idempotent, transactional projection of Phase 5/6 evaluation states into finalized `AssessmentResult` and `QuestionResult` ledger entities.
2. **Multi-Layer Result Immutability:** Finalized result records cannot be mutated through APIs, serializers, domain services, or bulk operations.
3. **Multi-Dimensional Analytics:** Deep statistical aggregation across questions, coding test cases, students, cohorts, tags, and proctoring risk (with small-cohort privacy safeguards).
4. **Controlled Asynchronous Report Exports:** Celery-driven generation of PDF (ReportLab), XLSX (openpyxl), and CSV (pandas) exports adhering to strict Controlled Export Schemas and formula injection escaping.
5. **30-Day Retention Compatibility:** Clear lifecycle separation between detailed attempt data (eligible for deletion at 30 days) and permanent `HistoricalResultSummary` records.

### Non-Goals
1. Re-scoring attempts independently or creating a secondary grading engine in Phase 8.
2. Reinterpreting or selecting coding submissions independently from Phase 6 contracts.
3. Altering Phase 5 assessment timers, attempt state machines, or result visibility semantics.
4. Altering Phase 6 Judge0 / sandbox execution policies or compiler environments.
5. Implementing active regrading execution (regrading is architecturally reserved, implementation deferred).
6. Auto-penalizing students based on Phase 7 proctoring risk scores.

---

## 4. Result Finalization Lifecycle & Concurrency Model

### 4.1 State Machine

```text
TestAttempt: IN_PROGRESS
       │
       ├─────────────────────────────────┐
       │ Student Manual "Submit"         │ Server Timer Exceeds Deadline
       ▼                                 ▼
TestAttempt: SUBMITTED            TestAttempt: EXPIRED
       │                                 │
       └────────────────┬────────────────┘
                        │
                        ▼
           AssessmentResult: PENDING
                        │
                        ▼ (Celery Task: finalize_assessment_result_task)
           AssessmentResult: PROCESSING
                        │
                        ▼ (Consumes Authoritative Phase 5/6 Evaluation State)
           AssessmentResult: FINALIZED
```

### 4.2 Separation of Domain State vs. Infrastructure Task State
- **Domain Result States:** `AssessmentResult.status` is strictly limited to:
  - `PENDING`: Finalization job queued.
  - `PROCESSING`: Finalization in progress.
  - `FINALIZED`: Authoritative scoring projected and ledger locked.
- **Celery Infrastructure States:** Celery manages transient infrastructure retries, exponential backoff, worker timeouts, and connection retries. Transient task retries **never create a permanent failed domain state**. If Celery encounters an unrecoverable system exception after all retries are exhausted, the domain state remains `PENDING` or `PROCESSING` to be swept by a periodic maintenance job.

### 4.3 Idempotency & Double-Finalization Prevention
1. `AssessmentResult` enforces a database `UniqueConstraint(fields=['attempt'])`.
2. Database row-level locking via `select_for_update()` on the `AssessmentResult` row ensures concurrent workers cannot finalize the same attempt simultaneously.
3. All result projections and the creation of `HistoricalResultSummary` execute inside a single atomic database transaction (`@transaction.atomic`).

---

## 5. Score Authority & Coding Evaluation Contract

### 5.1 Single Scoring Authority
**There is exactly one authoritative scoring and evaluation path.**
- Phase 8 does not independently evaluate candidate responses or calculate scoring formulas.
- Phase 8 invokes/consumes the authoritative Phase 5 evaluation logic for objective questions (`MCQ`, `MULTI_SELECT`, `TRUE_FALSE`, `SHORT_ANSWER`, `SQL`) against the frozen `AssessmentSnapshot.server_evaluation_bundle`.
- For coding questions (`CODING`), **Phase 8 consumes the authoritative coding evaluation produced by the frozen Phase 6 execution/evaluation contract and does not reinterpret or select submissions independently.**

### 5.2 Decimal Quantization & Aggregation Invariants
All scores use `Decimal` arithmetic quantized to 2 decimal places (`Decimal('0.01')`):
$$\text{Earned Points} = \max\left(0.00, \sum_{q \in \text{Questions}} \text{QuestionResult.earned\_points}_q\right)$$
$$\text{Percentage} = \left(\frac{\text{Earned Points}}{\text{Total Possible Points}} \times 100\right)$$

**Key Invariants:**
1. $\text{Earned Points} \le \text{Total Possible Points}$.
2. Total assessment score is non-negative (floored at $0.00$).
3. $\sum \text{QuestionResult.earned\_points} \equiv \text{AssessmentResult.total\_score\_earned}$.

---

## 6. Multi-Layer Result Immutability & Regrading Scope

### 6.1 Multi-Layer Immutability
Finalized result records are immutable across all system layers:
1. **API / Serializer Layer:** No REST endpoints support `PUT`, `PATCH`, or `DELETE` on finalized results.
2. **Domain Service Layer:** Service methods reject any modification requests targeting records with `status == FINALIZED`.
3. **Model Layer:** `AssessmentResult.save()` and `QuestionResult.save()` raise `PermissionDenied` if invoked on existing finalized records.
4. **Data Access Layer:** Direct `QuerySet.update()` or bulk update calls are strictly prohibited on result tables.

### 6.2 Regrading Scope
```text
REGRADING:
ARCHITECTURALLY RESERVED
IMPLEMENTATION DEFERRED
```
Finalized results remain permanently immutable in Phase 8. Full regrading (which involves complex cascading recalculations, cohort rank shifts, historical summary updates, and audit trails) is architecturally reserved for a dedicated future module.

---

## 7. Result Visibility Authority (Phase 5 Contract Preservation)

Phase 8 strictly consumes the established Phase 5 `ResultVisibility` domain contract:
- `IMMEDIATE`: Student can query their result immediately upon finalization.
- `AFTER_DEADLINE`: Student receives `HTTP 403 Forbidden` until `now >= Assessment.end_datetime`.
- `MANUAL`: Student receives `HTTP 403 Forbidden` until `AssessmentResult.is_released == True` (toggled by Admin).

Backend authorization is authoritative. Frontend visibility logic is purely presentational.

---

## 8. Analytics Engine Architecture

The Analytics Engine generates insights across multiple dimensions without recomputing authoritative scores.

```text
┌─────────────────────────────────────────────────────────────────────────┐
│                           Analytics Service                             │
├──────────────────┬──────────────────┬─────────────────┬─────────────────┤
│    Assessment    │     Question     │     Student     │      Batch      │
│    Analytics     │    Analytics     │    Analytics    │    Analytics    │
└────────┬─────────┴────────┬─────────┴────────┬────────┴────────┬────────┘
         │                  │                  │                 │
         ▼                  ▼                  ▼                 ▼
  Score Distribution, Discrimination,  Topic Radar,      Cohort Quartiles,
  Mean, Median, StdDev, Success Rate,  Velocity Trend,   Comparative Mean,
  Pass Rate, Quartiles  Time Consumed  Accuracy Rate     Drop-off Rates
```

### 8.1 Question-Level Analytics
- **Difficulty Index ($P$):** Proportion of candidates answering correctly ($P = \frac{N_{\text{correct}}}{N_{\text{total}}}$).
- **Discrimination Index ($D$):** $D = P_{\text{upper 27\%}} - P_{\text{lower 27\%}}$.
- **Time Consumption:** Mean and median time spent per question.
- **Coding Error Breakdown:** Distribution of `ACCEPTED`, `WRONG_ANSWER`, `TIME_LIMIT_EXCEEDED`, `COMPILATION_ERROR`, and `RUNTIME_ERROR`.

### 8.2 Coding Performance Analytics
- Aggregate test case pass rates across candidate submissions.
- Percentile distribution (p50, p90, p99) of CPU runtime and memory consumption.
- **Confidentiality Invariant:** Public test case results are visible; hidden test case inputs, expected outputs, and raw stdout/stderr are **strictly excluded from student views**.

### 8.3 Topic & Tag Analytics
- Aggregate accuracy and points earned per tag.
- **No Double-Counting Invariant:** Topic aggregations are analytical summaries; official assessment totals are strictly summed by question.

### 8.4 Proctoring-Risk Analytics & Privacy Safeguards
- Correlates risk bands (`NORMAL`, `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`) with score quartiles for administrative review.
- **Separation Invariant:** Proctoring risk is non-disciplinary context and **never modifies marks or attempt validity**.
- **Small-Cohort Privacy Safeguard:** Aggregate proctoring-vs-score correlations require a minimum cohort threshold of $N \ge 10$ candidates to prevent individual student de-anonymization.

### 8.5 Analytics Execution Strategy
- **Primary Strategy:** Indexed database aggregation queries over authoritative `AssessmentResult` and `QuestionResult` tables.
- **Precomputed Snapshots (`AssessmentAnalyticsSnapshot`):** Generated asynchronously when cohort scale and query cost justify caching, determined via performance benchmarking rather than arbitrary student count thresholds.

---

## 9. 30-Day Retention Compatibility & Historical Summaries

### 9.1 Retention / Finalization Synchronization Invariant
**Core Invariant:** A terminal attempt MUST complete result finalization and generate its `HistoricalResultSummary` before detailed source data is eligible for 30-day retention purging.

```text
Attempt reaches SUBMITTED / EXPIRED
        ↓
Result finalization executes (AssessmentResult + QuestionResult)
        ↓
HistoricalResultSummary created synchronously in same transaction
        ↓
30-Day Retention Purge Worker (Phase 9) verifies finalization is complete before scrubbing
```

### 9.2 Historical Result Identity & Context-Free Rank Removal
- `HistoricalResultSummary` stores immutable snapshot fields: `assessment_id`, `assessment_snapshot_id`, `assessment_title_snapshot`, `student_euid`, `total_score_earned`, `total_possible_score`, `percentage`, `completion_status`, `completed_at`.
- **Rank Removal:** Context-free `rank` is removed from `HistoricalResultSummary` because ranking is inherently cohort-dependent. Historical summaries preserve intrinsic student performance.
- **Historical Stability:** Summaries remain historically stable even if mutable assessment titles change later.

---

## 10. Report Generation & Controlled Export Engine

### 10.1 Asynchronous Pipeline
- **PDF Export:** `ReportLab` renders student scorecards and assessment executive summaries.
- **XLSX Export:** `openpyxl` builds multi-sheet workbooks containing deterministic precomputed values calculated authoritatively on the backend. **Formulas are minimized to only explicitly justified presentation needs.**
- **CSV Export:** `pandas` generates exports adhering strictly to the **Controlled Export Schema** (no raw database dumps; only explicitly approved fields exported).

### 10.2 Report Security & Sanitization
1. **Formula Injection Neutralization (CWE-1236):** Prepends single quote (`'`) to any cell string starting with `=`, `+`, `-`, `@`, `\t`, `\r`.
2. **Path Traversal Shield:** Files are saved using random UUIDs in private backend storage (`/var/codeguard/reports/<job_id>.<ext>`); downloads stream via authorized database lookups.
3. **Role & Object Authorization:** Students can only export their own released scorecards; admin rosters require `IsAdmin`.

---

## 11. Phase 8 Architectural Invariants

1. **Scoring Authority:** Phase 5 and Phase 6 are the sole authorities for assessment scoring.
2. **No Secondary Scoring:** Phase 8 never independently re-scores an attempt or reinterprets submissions.
3. **Multi-Layer Immutability:** Finalized result records have no supported mutation path across APIs, services, or models.
4. **Historical Stability:** `HistoricalResultSummary` is immutable and independent of future metadata edits.
5. **Proctoring Independence:** Proctoring risk metrics are informational context and never modify marks or attempt validity.
6. **Hidden Test Confidentiality:** Hidden test cases, inputs, and expected outputs are strictly excluded from student views and exports.
7. **Client Untrusted:** Client telemetry, scores, or timestamps are never authoritative.
8. **Backend Visibility Authority:** Result visibility is strictly enforced by backend authorization.
9. **Retention Compatibility:** Detailed attempt records purge cleanly at 30 days while historical summaries persist permanently.
10. **Analytics Non-Interference:** Analytics consume finalized results and never alter official scores.
11. **Controlled Export Schema:** Reports and CSVs contain only explicitly approved, whitelisted fields.
12. **Report File Security:** Report jobs and downloads enforce strict object-level authorization and SHA-256 integrity verification.
13. **Idempotent Finalization:** Result finalization is safe against duplicate task execution.
14. **Concurrency Safety:** Row locking prevents race conditions between manual submit and auto-expiry.
15. **Domain/Infrastructure Separation:** Celery task failures do not create permanent failed domain states.
16. **Retention Precedence:** Finalization and historical summary generation must complete before detailed source data can be purged.
17. **Privacy Safeguard:** Small-cohort proctoring aggregate distributions ($N < 10$) are withheld to prevent de-anonymization.
18. **Contextual Ranking:** Ranks are contextual query projections, not intrinsic permanent result properties.
