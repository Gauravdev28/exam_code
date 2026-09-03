# CODEGUARD — Phase 8 Retention & Historical Data Architecture (Micro-Hardened)

## 30-Day Retention Compatibility & Data Lifecycle Design

**Status:** PROPOSED & READY FOR ARCHITECTURAL REVIEW  
**Author:** Senior Software Engineer / Software Architect  

---

## 1. Retention Classification & Synchronization Model

In compliance with institutional privacy policies and GDPR/FERPA guidelines, CODEGUARD enforces a strict **30-day retention window** on detailed candidate attempt data while permanently retaining lightweight academic transcripts.

```text
┌─────────────────────────────────────────────────────────────────────────┐
│                    Data Classification & Retention                      │
├────────────────────────────────────┬────────────────────────────────────┤
│       Detailed Attempt Data        │     Permanent Academic Summary     │
│       (30-Day Lifecycle TTL)       │       (Permanent Retention)        │
├────────────────────────────────────┼────────────────────────────────────┤
│ • AttemptAnswer text/code/options  │ • Student User, EUID, Roll Number  │
│ • CodeSubmission source & outputs  │ • Snapshot Title & Snapshot ID     │
│ • CodeTestCaseResult execution logs│ • Authoritative Final Score        │
│ • ProctoringEvent raw telemetry    │ • Percentage & Passing Status      │
│ • ProctoringEvidence keyframes     │ • Exam Started & Submitted Times   │
│ • Temporary Report Export Files    │ • Immutable AuditLog entries       │
└────────────────────────────────────┴────────────────────────────────────┘
```

---

## 2. Retention / Finalization Synchronization Invariant

```text
Attempt reaches terminal state (SUBMITTED / EXPIRED)
        ↓
Result finalization executes (AssessmentResult + QuestionResult)
        ↓
HistoricalResultSummary created synchronously in the same transaction
        ↓
30-Day Retention Purge Worker (Phase 9) verifies finalization is complete before scrubbing
```

### Core Invariant:
**A terminal attempt MUST complete result finalization and generate its `HistoricalResultSummary` before detailed source data is eligible for 30-day retention purging.**

If an attempt is submitted but finalization is deferred or in progress, the automated 30-day purge worker defers scrubbing the attempt's answers and submissions until finalization completes.

---

## 3. Historical Result Identity & Context-Free Rank Removal

1. **Immutable Snapshot References:**
   `HistoricalResultSummary` preserves `assessment_id`, `assessment_snapshot_id`, and `assessment_title_snapshot`. Even if an administrator later modifies the mutable live assessment title or archives the assessment, the historical transcript remains unchanged.
2. **Removal of Context-Free Rank:**
   Rank is a cohort-dependent metric that shifts if cohort boundaries change. Context-free `rank` is explicitly excluded from the permanent summary. Summaries preserve intrinsic student performance (score, percentage, completion status, completion timestamp).

---

## 4. Handling Retention Edge Cases

### Case A: Detailed Data Reaches 30 Days
- **Behavior:** The daily purge task scrubs detailed answers (`AttemptAnswer`), code submissions (`CodeSubmission`), and question-level breakdowns (`QuestionResult`), while leaving the `AssessmentResult` metadata header and `HistoricalResultSummary` intact.
- **API Impact:** `GET /api/v1/student/results/<id>/` returns score and percentage with `"details_purged": true`.

### Case B: Admin Requests Report for Expired Assessment
- **Behavior:** The report generator checks if detailed records exist. If purged, it automatically generates a **Transcript Summary Report** based on `HistoricalResultSummary`.

### Case C: Active Retention Hold Exists
- **Behavior:** If an attempt or student has `retention_hold = True` (e.g., active academic inquiry), the automated purge worker skips the attempt until the hold is lifted.

### Case D: Report Job Running During Purge
- **Behavior:** The purge task runs with `SKIP LOCKED` and ignores attempts referenced by active in-flight `ReportJob` tasks (`status == PROCESSING`).
