# CODEGUARD — Phase 8 Security Threat Model & Mitigations (Micro-Hardened)

## Results, Analytics & Reporting Security Specification

**Status:** PROPOSED & READY FOR ARCHITECTURAL REVIEW  
**Author:** Senior Software Engineer / Software Architect  

---

## 1. Threat Taxonomy & Attack Vectors

```text
┌────────────────────────────────────────────────────────────────────────┐
│                        Phase 8 Threat Landscape                        │
├───────────────────┬──────────────────┬─────────────────┬───────────────┤
│   Authorization   │   Injection &    │ Data Leakage &  │  Concurrency  │
│   & IDOR Attacks  │  Malicious File  │ Confidentiality │  & Tampering  │
└─────────┬─────────┴────────┬─────────┴────────┬────────┴───────┬───────┘
          │                  │                  │                │
          ▼                  ▼                  ▼                ▼
   Cross-student      CSV / Formula      Hidden test     Race condition
   result snooping;   injection in       case leakage    during submit;
   Unreleased result  XLSX/CSV exports;  to candidates;  Client-side
   visibility bypass  Path traversal     Small-cohort    score tampering
                      on downloads       de-anonymize    attempts
```

---

## 2. Detailed Threat Mitigations

### 2.1 Threat T1: IDOR on Student Results & Cross-Student Querying
- **Mitigation:** Mandatory object ownership check: `attempt.student == request.user`. All student querysets filter by `student=request.user`. Violations return `HTTP 403 Forbidden`.

### 2.2 Threat T2: Premature Result Visibility Bypass
- **Mitigation:** Backend enforcement of Phase 5 `ResultVisibility` (`IMMEDIATE`, `AFTER_DEADLINE`, `MANUAL`). Unreleased attempts return `HTTP 403 Forbidden` regardless of client state.

### 2.3 Threat T3: Hidden Test Case & Sensitive Sandbox Leakage
- **Mitigation:** `QuestionResult.evaluation_details` exposed to students strictly strips hidden test cases (`is_hidden == True`). Candidate summaries expose only public test cases and aggregate counts. Hidden inputs, expected outputs, and raw stderr are quarantined on the server.

### 2.4 Threat T4: CSV / Spreadsheet Formula Injection (CWE-1236)
- **Mitigation:** All exported string cells starting with `=`, `+`, `-`, `@`, `\t`, `\r` are prepended with a single quote (`'`), rendering them as literal text in spreadsheet viewers.

### 2.5 Threat T5: Report Path Traversal & Arbitrary File Streaming
- **Mitigation:** File paths are never built from client input. Downloads look up `ReportJob` by UUID in the database, verify ownership/admin permissions, and stream strictly from the designated `/var/codeguard/reports/` directory with path validation.

### 2.6 Threat T6: Client-Side Score Tampering & Mutation
- **Mitigation:** Client scores are completely ignored. Scoring authority rests solely in Phase 5/6 evaluation engines. Multi-layer immutability ensures `AssessmentResult` and `QuestionResult` cannot be mutated via APIs, serializers, services, or bulk queries.

### 2.7 Threat T7: Finalization Race Conditions
- **Mitigation:** Database row lock with `select_for_update()` and `UniqueConstraint(fields=['attempt'])`. Idempotent finalization logic safely skips duplicate execution.

### 2.8 Threat T8: Small-Cohort Proctoring De-anonymization
- **Mitigation:** Aggregate proctoring risk-vs-score correlations require a minimum cohort threshold of $N \ge 10$ candidates before rendering, preventing student de-anonymization in small groups.

---

## 3. Phase 8 Architectural Invariants Matrix

| Invariant | Enforcement Mechanism |
| :--- | :--- |
| **1. Scoring Authority** | Phase 5 and Phase 6 are the sole authorities for scoring |
| **2. No Secondary Scoring** | Phase 8 never independently re-scores an attempt or reinterprets submissions |
| **3. Multi-Layer Immutability** | No supported application path can mutate a finalized result |
| **4. Historical Stability** | `HistoricalResultSummary` preserves immutable snapshot titles and IDs |
| **5. Proctoring Independence** | Proctoring risk metrics are informational context only and never modify grades |
| **6. Hidden Test Confidentiality** | Hidden test cases are completely excluded from student views |
| **7. Client Untrusted** | Client telemetry, scores, or timestamps are never authoritative |
| **8. Backend Visibility Authority** | Phase 5 result visibility is strictly enforced on the server |
| **9. Retention Compatibility** | Detailed attempt records purge at 30 days; historical summaries persist |
| **10. Analytics Non-Interference** | Analytics consume finalized results and never alter official scores |
| **11. Controlled Export Schema** | CSV/XLSX exports contain only explicitly whitelisted fields |
| **12. Report File Security** | Report downloads enforce object ownership and SHA-256 verification |
| **13. Idempotent Finalization** | Result finalization is safe against duplicate task execution |
| **14. Concurrency Safety** | Row locking prevents race conditions between submit and expiry |
| **15. Domain/Infrastructure Separation** | Celery task failures do not create permanent failed domain states |
| **16. Retention Precedence** | Finalization and summary generation must complete before source purge |
| **17. Privacy Safeguard** | Small-cohort proctoring aggregate distributions ($N < 10$) are withheld |
| **18. Contextual Ranking** | Ranks are contextual query projections, not intrinsic permanent properties |
