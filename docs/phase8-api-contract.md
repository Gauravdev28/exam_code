# CODEGUARD — Phase 8 API Contract Specification (Micro-Hardened)

## Results, Analytics & Reporting REST Endpoints

**Status:** PROPOSED & READY FOR ARCHITECTURAL REVIEW  
**Author:** Senior Software Engineer / Software Architect  

---

## 1. Authentication & Query Policy

All Phase 8 endpoints strictly enforce standard CODEGUARD RBAC and server-side query bounds:
- **`IsAuthenticated`**: Valid JWT access token required for all endpoints.
- **`IsAdmin`**: Required for administrative rosters, cross-student queries, aggregated analytics, and institutional report exports.
- **`IsStudent`**: Permitted to access only personal results where Phase 5 visibility rules evaluate to released.
- **Server-Side Pagination & Anti-Dumping**: All list endpoints enforce mandatory server-side pagination with `default_page_size = 20` and `max_page_size = 100`. Unbounded data dumps are rejected.

---

## 2. Student Endpoints

### 2.1 Get Attempt Result
- **URL**: `GET /api/v1/student/attempts/<attempt_id>/result/`
- **Role**: `STUDENT` (Object ownership verified)
- **Phase 5 Visibility Enforcement**:
  - `IMMEDIATE` & `FINALIZED` $\rightarrow$ Returns HTTP 200.
  - `AFTER_DEADLINE` & `now < Assessment.end_datetime` $\rightarrow$ Returns HTTP 403 (`{"detail": "Results will be available after the assessment deadline."}`).
  - `MANUAL` & `is_released == False` $\rightarrow$ Returns HTTP 403 (`{"detail": "Results have not been released by the administrator."}`).
  - `status in ['PENDING', 'PROCESSING']` $\rightarrow$ Returns HTTP 202 (`{"status": "PROCESSING", "detail": "Result evaluation in progress."}`).
- **Response Format (HTTP 200 OK)**:
```json
{
  "result_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "attempt_id": "4a7c1b5e-9f3a-4a7b-8c1e-2f3a4b5c6d7e",
  "assessment_id": "1a2b3c4d-5e6f-7a8b-9c0d-1e2f3a4b5c6d",
  "assessment_title": "Data Structures & Algorithms Final 2026",
  "status": "FINALIZED",
  "total_score_earned": "85.00",
  "total_possible_score": "100.00",
  "percentage": "85.00",
  "is_passed": true,
  "summary": {
    "total_questions": 5,
    "correct_questions": 4,
    "partially_correct_questions": 0,
    "incorrect_questions": 1,
    "skipped_questions": 0,
    "time_spent_seconds": 3240
  },
  "question_breakdown": [
    {
      "question_id": "q-algo-1",
      "question_type": "MCQ",
      "order": 1,
      "earned_points": "10.00",
      "max_points": "10.00",
      "is_correct": true,
      "is_skipped": false
    },
    {
      "question_id": "q-coding-2",
      "question_type": "CODING",
      "order": 2,
      "earned_points": "20.00",
      "max_points": "20.00",
      "is_correct": true,
      "is_skipped": false,
      "coding_summary": {
        "passed_test_cases": 10,
        "total_test_cases": 10,
        "execution_time_ms": 142,
        "memory_used_kb": 18240
      }
    }
  ],
  "finalized_at": "2026-09-02T14:30:00Z"
}
```

---

### 2.2 List Student Historical Transcripts
- **URL**: `GET /api/v1/student/results/`
- **Role**: `STUDENT`
- **Query Params**: `page=1`, `page_size=20`, `search=Algorithms`
- **Response Format (HTTP 200 OK)**:
```json
{
  "count": 12,
  "next": null,
  "previous": null,
  "results": [
    {
      "result_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
      "assessment_id": "1a2b3c4d-5e6f-7a8b-9c0d-1e2f3a4b5c6d",
      "assessment_title": "Data Structures & Algorithms Final 2026",
      "total_score_earned": "85.00",
      "total_possible_score": "100.00",
      "percentage": "85.00",
      "completed_at": "2026-09-02T14:30:00Z"
    }
  ]
}
```

---

### 2.3 Student Topic Mastery Analytics
- **URL**: `GET /api/v1/student/analytics/topics/`
- **Role**: `STUDENT`
- **Response Format (HTTP 200 OK)**:
```json
{
  "topics": [
    {
      "tag_name": "Dynamic Programming",
      "questions_attempted": 8,
      "accuracy_percentage": 75.0,
      "earned_points": "60.00",
      "max_points": "80.00"
    }
  ]
}
```

---

## 3. Admin Endpoints

### 3.1 List Assessment Results Roster (Advanced Querying)
- **URL**: `GET /api/v1/admin/assessments/<assessment_id>/results/`
- **Role**: `ADMIN`
- **Query Parameters**:
  - **Searching**: `search=EUID-A1B2` (searches EUID, email, roll number, name)
  - **Filtering**:
    - `status=FINALIZED` (`PENDING`, `PROCESSING`, `FINALIZED`)
    - `is_passed=true` (`true`, `false`)
    - `is_released=true` (`true`, `false`)
    - `min_score=50.00`, `max_score=100.00`
    - `completed_after=2026-09-01T00:00:00Z`, `completed_before=2026-09-02T23:59:59Z`
    - `risk_band=HIGH,CRITICAL` (Informational proctoring filter)
  - **Sorting**: `ordering=-total_score_earned` (`total_score_earned`, `-total_score_earned`, `percentage`, `-percentage`, `time_spent_seconds`, `-time_spent_seconds`, `completed_at`, `-completed_at`, `student_euid`, `-student_euid`)
  - **Pagination**: `page=1`, `page_size=50` (Enforces `max_page_size=100`)
- **Response Format (HTTP 200 OK)**:
```json
{
  "count": 120,
  "next": null,
  "previous": null,
  "results": [
    {
      "result_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
      "attempt_id": "4a7c1b5e-9f3a-4a7b-8c1e-2f3a4b5c6d7e",
      "student": {
        "id": "u-student-1",
        "email": "alice@university.edu",
        "full_name": "Alice Johnson",
        "roll_number": "CS2026-001",
        "euid": "EUID-A1B2-C3D4"
      },
      "status": "FINALIZED",
      "total_score_earned": "92.00",
      "total_possible_score": "100.00",
      "percentage": "92.00",
      "is_passed": true,
      "time_spent_seconds": 2980,
      "finalized_at": "2026-09-02T14:30:00Z",
      "is_released": true,
      "proctoring_summary": {
        "risk_score": "12.50",
        "risk_band": "NORMAL"
      }
    }
  ]
}
```

---

### 3.2 Get Assessment Analytics Summary
- **URL**: `GET /api/v1/admin/assessments/<assessment_id>/analytics/`
- **Role**: `ADMIN`
- **Response Format (HTTP 200 OK)**:
```json
{
  "assessment_id": "1a2b3c4d-5e6f-7a8b-9c0d-1e2f3a4b5c6d",
  "assessment_title": "Data Structures & Algorithms Final 2026",
  "cohort_metrics": {
    "total_assigned": 120,
    "total_started": 115,
    "total_completed": 110,
    "total_expired": 5,
    "completion_rate_percentage": 95.65,
    "pass_rate_percentage": 82.50
  },
  "score_statistics": {
    "mean_score": "74.50",
    "median_score": "78.00",
    "highest_score": "98.00",
    "lowest_score": "32.00",
    "standard_deviation": "12.40",
    "quartiles": {
      "q1": "65.00",
      "q2": "78.00",
      "q3": "86.00"
    }
  },
  "score_distribution": [
    {"bucket": "0-10", "count": 0},
    {"bucket": "11-20", "count": 0},
    {"bucket": "21-30", "count": 1},
    {"bucket": "31-40", "count": 4},
    {"bucket": "41-50", "count": 8},
    {"bucket": "51-60", "count": 12},
    {"bucket": "61-70", "count": 20},
    {"bucket": "71-80", "count": 35},
    {"bucket": "81-90", "count": 22},
    {"bucket": "91-100", "count": 8}
  ],
  "proctoring_risk_correlation": {
    "is_available": true,
    "min_cohort_threshold_met": true,
    "distribution": {
      "NORMAL": {"count": 88, "average_score": "75.20"},
      "LOW": {"count": 15, "average_score": "73.10"},
      "MEDIUM": {"count": 5, "average_score": "70.50"},
      "HIGH": {"count": 2, "average_score": "78.00"},
      "CRITICAL": {"count": 0, "average_score": "0.00"}
    }
  }
}
```

*Note: If cohort $N < 10$, `proctoring_risk_correlation` returns `"is_available": false, "reason": "Cohort size below privacy threshold (N < 10)"`.*

---

### 3.3 Request Controlled Report Export
- **URL**: `POST /api/v1/admin/reports/`
- **Role**: `ADMIN`
- **Request Payload**:
```json
{
  "report_type": "ASSESSMENT_ROSTER",
  "format": "XLSX",
  "assessment_id": "1a2b3c4d-5e6f-7a8b-9c0d-1e2f3a4b5c6d"
}
```
- **Response Format (HTTP 202 ACCEPTED)**:
```json
{
  "job_id": "7f8e9d0c-1b2a-3c4d-5e6f-7a8b9c0d1e2f",
  "status": "QUEUED",
  "created_at": "2026-09-02T15:00:00Z"
}
```

---

### 3.4 Check Report Job Status & Download
- **URL**: `GET /api/v1/admin/reports/<job_id>/`
- **Role**: `ADMIN`
- **Response Format (HTTP 200 OK)**:
```json
{
  "job_id": "7f8e9d0c-1b2a-3c4d-5e6f-7a8b9c0d1e2f",
  "status": "COMPLETED",
  "file_size_bytes": 142850,
  "sha256_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "download_url": "/api/v1/admin/reports/7f8e9d0c-1b2a-3c4d-5e6f-7a8b9c0d1e2f/download/",
  "expires_at": "2026-09-09T15:00:00Z"
}
```
