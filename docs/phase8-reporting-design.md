# CODEGUARD — Phase 8 Report Generation Architecture (Micro-Hardened)

## PDF, XLSX & Controlled CSV Export Engine

**Status:** PROPOSED & READY FOR ARCHITECTURAL REVIEW  
**Author:** Senior Software Engineer / Software Architect  

---

## 1. Engine Architecture & Technology Choices

Report generation is handled by dedicated worker libraries executed asynchronously via Celery:
- **PDF Generation:** `ReportLab` (vector document layout, institutional headers, charts, and candidate scorecards).
- **XLSX Generation:** `openpyxl` (multi-sheet workbooks with **deterministic precomputed cell values calculated on the backend**). Formulas are minimized to only explicitly required presentation needs.
- **CSV Generation:** `pandas` (bulk text serialization adhering strictly to the **Controlled Export Schema**).

```text
┌────────────────────────────────────────────────────────────────────────┐
│                   Controlled Report Generation Pipeline                │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │ POST /api/v1/admin/reports/
                                   ▼
                        ┌─────────────────────┐
                        │ Create ReportJob DB │ (Status: QUEUED)
                        └──────────┬──────────┘
                                   │ Enqueue Celery Task
                                   ▼
                        ┌─────────────────────┐
                        │   Celery Worker     │
                        └──────────┬──────────┘
                                   │
         ┌─────────────────────────┼─────────────────────────┐
         ▼                         ▼                         ▼
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│ PDF (ReportLab) │       │ XLSX (openpyxl) │       │ CSV (Controlled)│
└────────┬────────┘       └────────┬────────┘       └────────┬────────┘
         │                         │                         │
         └─────────────────────────┼─────────────────────────┘
                                   │
                                   ▼
               ┌───────────────────────────────────────┐
               │ 1. Apply Formula Injection Escaping   │
               │ 2. Compute SHA-256 Checksum           │
               │ 3. Write to /var/codeguard/reports/   │
               │ 4. Update ReportJob (Status: COMPLETE)│
               └───────────────────────────────────────┘
```

---

## 2. Controlled Export Schemas & Report Templates

### 2.1 Individual Student Candidate Scorecard (PDF)
- **Header:** Institutional Title, Assessment Title, Assessment Snapshot Date.
- **Candidate Metadata:** Full Name, Email, Roll Number, EUID, Attempt Number.
- **Score Breakdown:** Total Marks Earned, Maximum Possible Marks, Percentage, Passing Verdict.
- **Question Summary Table:** Question Order, Question Title, Topic/Tag, Points Earned / Max Points, Correctness Status.
- **Coding Performance Summary:** Public Test Cases Passed / Total, Execution Time (ms), Peak Memory (KB). **No hidden test case inputs or expected outputs exposed.**

### 2.2 Assessment Master Gradebook (XLSX)
- **Sheet 1 (Executive Summary):** Cohort Size, Mean Score, Median, Pass Rate, Highest/Lowest Marks (deterministic precomputed values).
- **Sheet 2 (Student Roster):** EUID, Roll Number, Candidate Name, Email, Score Earned, Percentage, Passing Status, Time Spent (s), Submission Timestamp.
- **Sheet 3 (Question Item Analysis):** Question Order, Title, Type, Tag, Difficulty Index ($P$), Discrimination Index ($D$).

### 2.3 Assessment Controlled CSV Export Schema
The export layer **never dumps raw database tables**. The CSV schema is strictly restricted to the following whitelisted columns:
```csv
euid,roll_number,student_name,student_email,assessment_id,assessment_title,total_score_earned,total_possible_score,percentage,is_passed,started_at,submitted_at,time_spent_seconds
```

---

## 3. Storage, Sanitization & Security Policies

1. **Formula Injection Neutralization (CWE-1236):**
   - Any cell string in CSV or XLSX exports starting with `=`, `+`, `-`, `@`, `\t`, `\r` is escaped by prefixing a single quote (`'`), rendering it as safe literal text in spreadsheet viewers.
2. **Storage Isolation:**
   - Reports are stored in private backend storage (`/var/codeguard/reports/<job_id>.<ext>`) with restricted permissions (0600).
   - Nginx does not serve the report directory directly; downloads stream through authenticated DRF endpoints using Django's `FileResponse` / `X-Accel-Redirect`.
3. **Time-To-Live (7-Day TTL):**
   - Generated report binaries expire after 7 days. A daily maintenance task unlinks expired files and updates `ReportJob.status = EXPIRED`.
4. **SHA-256 Integrity Verification:**
   - The SHA-256 digest calculated upon generation is verified prior to download streaming to detect any filesystem-level tampering or corruption.
