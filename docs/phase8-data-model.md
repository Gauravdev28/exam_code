# CODEGUARD — Phase 8 Data Model Specification (Micro-Hardened)

## Results, Analytics & Reporting Data Models

**Status:** PROPOSED & READY FOR ARCHITECTURAL REVIEW  
**Author:** Senior Software Engineer / Software Architect  

---

## 1. Schema Overview

Phase 8 introduces 5 discrete database models within a dedicated Django app (`apps.results` / `apps.analytics`) to manage result projection, question breakdowns, precomputed assessment analytics, permanent historical summaries, and asynchronous report export jobs.

```text
┌─────────────────────────┐
│       TestAttempt       │ (Phase 5 Model)
└────────────┬────────────┘
             │ 1:1
             ▼
┌─────────────────────────┐       1:N       ┌─────────────────────────┐
│    AssessmentResult     ├────────────────►│     QuestionResult      │
└────────────┬────────────┘                 └─────────────────────────┘
             │ 1:1
             ▼
┌─────────────────────────┐
│ HistoricalResultSummary │ (Permanent Lightweight Retention)
└─────────────────────────┘

┌─────────────────────────┐                 ┌─────────────────────────┐
│AssessmentAnalyticsSnapshot                │        ReportJob        │
│ (Optional Precomputed)  │                 │ (Async Export Tracking) │
└─────────────────────────┘                 └─────────────────────────┘
```

---

## 2. Model Definitions

### 2.1 `AssessmentResult`
**Table Name:** `assessment_results`  
**Purpose:** Authoritative immutable ledger recording the projected final score, percentage, passing verdict, and completion metrics of an attempt.

| Field | Type | Modifiers / Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUIDField` | Primary Key, default `uuid4` | Unique result identifier |
| `attempt` | `OneToOneField(TestAttempt)` | `on_delete=models.PROTECT`, related_name=`result` | Link to student test attempt |
| `student` | `ForeignKey(User)` | `on_delete=models.PROTECT`, related_name=`assessment_results` | Denormalized student link |
| `assessment` | `ForeignKey(Assessment)` | `on_delete=models.PROTECT`, related_name=`results` | Assessment reference |
| `assessment_snapshot` | `ForeignKey(AssessmentSnapshot)` | `on_delete=models.PROTECT` | Frozen snapshot used for evaluation |
| `status` | `CharField(20)` | choices: `PENDING`, `PROCESSING`, `FINALIZED`, default `PENDING` | Domain result projection status |
| `total_score_earned` | `DecimalField(8, 2)` | default `0.00` | Authoritative earned marks (quantized to 0.01) |
| `total_possible_score` | `DecimalField(8, 2)` | default `0.00` | Max possible points for the exam |
| `percentage` | `DecimalField(5, 2)` | default `0.00` | Earned score percentage |
| `is_passed` | `BooleanField` | null `True`, blank `True` | Passing status (if passing threshold configured) |
| `total_questions` | `PositiveIntegerField` | default `0` | Total questions in assessment snapshot |
| `answered_questions` | `PositiveIntegerField` | default `0` | Answered question count |
| `correct_questions` | `PositiveIntegerField` | default `0` | Fully correct question count |
| `partially_correct_questions` | `PositiveIntegerField` | default `0` | Partially correct question count |
| `incorrect_questions` | `PositiveIntegerField` | default `0` | Incorrect question count |
| `skipped_questions` | `PositiveIntegerField` | default `0` | Unanswered question count |
| `time_spent_seconds` | `PositiveIntegerField` | default `0` | Duration between started_at and submitted_at |
| `is_released` | `BooleanField` | default `False`, db_index=`True` | Manual release visibility flag |
| `finalized_at` | `DateTimeField` | null `True`, blank `True` | Timestamp when scoring completed |
| `retention_class` | `CharField(32)` | default `DETAILED_RESULT_30D` | Retention policy identifier |
| `created_at` | `DateTimeField` | auto_now_add=`True` | Record creation timestamp |
| `updated_at` | `DateTimeField` | auto_now=`True` | Record update timestamp |

**Indexes & Constraints:**
- `UniqueConstraint(fields=['attempt'], name='unique_attempt_assessment_result')`
- `Index(fields=['assessment', 'status', '-total_score_earned'], name='idx_res_assmt_score')`
- `Index(fields=['student', '-created_at'], name='idx_res_student_created')`

---

### 2.2 `QuestionResult`
**Table Name:** `question_results`  
**Purpose:** Per-question scoring breakdown, test case summary, and evaluation details.

| Field | Type | Modifiers / Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUIDField` | Primary Key, default `uuid4` | Unique record ID |
| `assessment_result` | `ForeignKey(AssessmentResult)` | `on_delete=models.CASCADE`, related_name=`question_results` | Parent assessment result |
| `snapshot_question` | `ForeignKey(AssessmentSnapshotQuestion)` | `on_delete=models.PROTECT` | Frozen question definition |
| `question_id` | `CharField(64)` | db_index=`True` | Snapshot question identifier |
| `question_type` | `CharField(32)` | choices: `MCQ`, `MULTI_SELECT`, `TRUE_FALSE`, `SHORT_ANSWER`, `CODING`, `SQL` | Question type |
| `earned_points` | `DecimalField(6, 2)` | default `0.00` | Points awarded |
| `max_points` | `DecimalField(6, 2)` | default `0.00` | Maximum points allocated |
| `is_correct` | `BooleanField` | default `False` | Full correctness flag |
| `is_partially_correct` | `BooleanField` | default `False` | Partial correctness flag |
| `is_skipped` | `BooleanField` | default `False` | Skipped flag |
| `evaluation_details` | `JSONField` | default `dict` | Student-safe scoring metadata |
| `time_spent_seconds` | `PositiveIntegerField` | default `0` | Time spent on question |
| `created_at` | `DateTimeField` | auto_now_add=`True` | Record timestamp |

**Indexes & Constraints:**
- `UniqueConstraint(fields=['assessment_result', 'question_id'], name='unique_res_question')`
- `Index(fields=['question_id', 'is_correct'], name='idx_q_res_correctness')`

---

### 2.3 `HistoricalResultSummary`
**Table Name:** `historical_result_summaries`  
**Purpose:** Permanent lightweight academic transcript designed to survive 30-day retention purges.

| Field | Type | Modifiers / Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUIDField` | Primary Key, default `uuid4` | Unique summary identifier |
| `student` | `ForeignKey(User)` | `on_delete=models.PROTECT`, related_name=`historical_summaries` | Student user |
| `student_euid` | `CharField(64)` | db_index=`True` | Student deterministic EUID |
| `student_roll_number` | `CharField(64)` | db_index=`True` | Student roll number |
| `assessment_id` | `UUIDField` | db_index=`True` | Assessment UUID |
| `assessment_snapshot_id` | `UUIDField` | db_index=`True` | Immutable snapshot UUID |
| `assessment_title_snapshot` | `CharField(255)` | Snapshot assessment title (stable against future edits) |
| `total_score_earned` | `DecimalField(8, 2)` | Authoritative score earned |
| `total_possible_score` | `DecimalField(8, 2)` | Max assessment score |
| `percentage` | `DecimalField(5, 2)` | Earned score percentage |
| `completion_status` | `CharField(32)` | choices: `SUBMITTED`, `EXPIRED`, `CANCELLED` | Attempt status |
| `started_at` | `DateTimeField` | Exam start timestamp |
| `completed_at` | `DateTimeField` | Exam submission timestamp |
| `retention_class` | `CharField(32)` | default `PERMANENT_SUMMARY` | Permanent retention classification |
| `created_at` | `DateTimeField` | auto_now_add=`True` | Summary creation timestamp |

**Indexes & Constraints:**
- `UniqueConstraint(fields=['student', 'assessment_id'], name='unique_student_assessment_summary')`
- `Index(fields=['student', '-completed_at'], name='idx_hist_student_completed')`

---

### 2.4 `AssessmentAnalyticsSnapshot`
**Table Name:** `assessment_analytics_snapshots`  
**Purpose:** Precomputed statistical aggregates across an entire assessment cohort when scale justifies caching.

| Field | Type | Modifiers / Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUIDField` | Primary Key, default `uuid4` | Unique analytics snapshot ID |
| `assessment` | `ForeignKey(Assessment)` | `on_delete=models.CASCADE`, related_name=`analytics_snapshots` | Target assessment |
| `total_assigned` | `PositiveIntegerField` | default `0` | Count of assigned candidates |
| `total_started` | `PositiveIntegerField` | default `0` | Count of candidates who started |
| `total_completed` | `PositiveIntegerField` | default `0` | Count of completed submissions |
| `total_expired` | `PositiveIntegerField` | default `0` | Count of expired attempts |
| `mean_score` | `DecimalField(8, 2)` | default `0.00` | Arithmetic mean score |
| `median_score` | `DecimalField(8, 2)` | default `0.00` | Median score (p50) |
| `highest_score` | `DecimalField(8, 2)` | default `0.00` | Top score achieved |
| `lowest_score` | `DecimalField(8, 2)` | default `0.00` | Minimum score achieved |
| `standard_deviation` | `DecimalField(8, 2)` | default `0.00` | Score standard deviation ($\sigma$) |
| `score_distribution` | `JSONField` | default `dict` | Bucket counts (0-10, 11-20, ..., 91-100) |
| `question_performance` | `JSONField` | default `dict` | Precomputed success rate & discrimination per question |
| `tag_performance` | `JSONField` | default `dict` | Precomputed tag/topic performance aggregates |
| `generated_at` | `DateTimeField` | auto_now=`True` | Snapshot compute timestamp |

---

### 2.5 `ReportJob`
**Table Name:** `report_jobs`  
**Purpose:** Asynchronous export task state tracker, authorization boundary, and download gate.

| Field | Type | Modifiers / Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUIDField` | Primary Key, default `uuid4` | Random UUID identifier |
| `requested_by` | `ForeignKey(User)` | `on_delete=models.PROTECT`, related_name=`requested_reports` | Admin or student requester |
| `report_type` | `CharField(32)` | choices: `STUDENT_SCORECARD`, `ASSESSMENT_SUMMARY`, `ASSESSMENT_ROSTER` | Scope of report |
| `format` | `CharField(16)` | choices: `PDF`, `XLSX`, `CSV` | Export format |
| `status` | `CharField(20)` | choices: `QUEUED`, `PROCESSING`, `COMPLETED`, `FAILED` | Job lifecycle status |
| `assessment` | `ForeignKey(Assessment)` | null `True`, blank `True`, `on_delete=models.CASCADE` | Target assessment scope |
| `student` | `ForeignKey(User)` | null `True`, blank `True`, `on_delete=models.SET_NULL` | Target student scope |
| `file_path` | `CharField(512)` | null `True`, blank `True` | Private filesystem path (`/var/codeguard/reports/<uuid>.<ext>`) |
| `file_size_bytes` | `BigIntegerField` | default `0` | Size of generated file in bytes |
| `sha256_hash` | `CharField(64)` | null `True`, blank `True` | Cryptographic SHA-256 integrity digest |
| `error_message` | `TextField` | blank `True`, default `""` | Sanitized error log if generation failed |
| `expires_at` | `DateTimeField` | db_index=`True` | File expiration date (7-day TTL) |
| `created_at` | `DateTimeField` | auto_now_add=`True` | Job queue timestamp |
| `completed_at` | `DateTimeField` | null `True`, blank `True` | Generation completion timestamp |

**Indexes & Constraints:**
- `Index(fields=['requested_by', '-created_at'], name='idx_report_user_created')`
- `Index(fields=['status', 'expires_at'], name='idx_report_status_expiry')`
