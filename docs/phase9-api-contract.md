# CODEGUARD — Phase 9 API Contract Specification (Micro-Hardened)

**Document Version:** 1.1.0  
**Base URL:** `/api/v1/`  
**Authentication:** JWT Bearer (`Authorization: Bearer <token>`)  
**Authorization:** RBAC via `IsAdmin` / `IsStudent`  

---

## 1. Summary of Endpoints

| Method | Endpoint | Role | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/admin/retention/policies/` | Admin | List active retention policies and configurations |
| `POST`| `/admin/retention/policies/` | Admin | Create or update retention policy override |
| `GET` | `/admin/retention/metrics/` | Admin | Retention overview (confirmed reclaimed space, upcoming purges) |
| `GET` | `/admin/retention/purge-runs/` | Admin | History of automated and manual purge cycles |
| `POST`| `/admin/retention/purge/preview/` | Admin | Dry-run preview returning eligible items and signed `preview_token` |
| `POST`| `/admin/retention/purge/execute/` | Admin | Execute purge requiring valid `preview_token` & re-evaluating state |
| `GET` | `/admin/legal-holds/` | Admin | List all legal holds with status filter |
| `POST`| `/admin/legal-holds/` | Admin | Place a new legal hold with strict target scope |
| `POST`| `/admin/legal-holds/{id}/release/` | Admin | Release an active legal hold with justification reason |
| `GET` | `/admin/tombstones/` | Admin | Search and inspect cryptographic purge tombstones |
| `GET` | `/student/privacy/lifecycle/` | Student | View data retention lifecycle & countdown timers for attempts |
| `POST`| `/student/privacy/export-request/` | Student | Initiate a DSAR pre-purge data export archive (allowlist filtered) |
| `GET` | `/student/privacy/exports/{job_id}/` | Student | Check status & download personal data archive |

---

## 2. Admin Endpoint Specifications

### 2.1 `GET /api/v1/admin/retention/metrics/`
- **Authentication:** Required (`Role.ADMIN`)
- **Response `200 OK`:**
```json
{
  "status": "success",
  "data": {
    "storage_summary": {
      "total_confirmed_bytes_reclaimed": 1458923000,
      "total_database_records_scrubbed": 84210,
      "total_tombstones_count": 342,
      "active_detailed_attempts_count": 89,
      "purged_attempts_count": 342,
      "pending_file_cleanups_count": 0
    },
    "upcoming_purges_forecast": {
      "expiring_in_7_days": 14,
      "expiring_in_14_days": 38,
      "expiring_in_30_days": 89
    },
    "legal_holds_summary": {
      "active_holds_count": 3,
      "held_attempts_count": 5
    },
    "last_purge_run": {
      "completed_at": "2026-09-03T02:00:15Z",
      "status": "COMPLETED",
      "purged_count": 12,
      "confirmed_bytes_reclaimed": 52428800
    }
  }
}
```

### 2.2 `POST /api/v1/admin/retention/purge/preview/`
- **Authentication:** Required (`Role.ADMIN`)
- **Input Payload:**
```json
{
  "assessment_id": "optional-uuid",
  "older_than_days": 30
}
```
- **Response `200 OK`:**
```json
{
  "status": "success",
  "data": {
    "preview_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "preview_token_expires_in_seconds": 300,
    "eligible_count": 15,
    "blocked_by_legal_hold_count": 2,
    "blocked_by_unfinalized_count": 1,
    "estimated_bytes_to_reclaim": 73400320,
    "preview_items": [
      {
        "attempt_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
        "student_euid": "EUID-STU-001",
        "assessment_title": "DSA Final Exam",
        "submitted_at": "2026-08-01T10:00:00Z",
        "days_elapsed": 33,
        "is_held": false
      }
    ]
  }
}
```

### 2.3 `POST /api/v1/admin/retention/purge/execute/`
- **Authentication:** Required (`Role.ADMIN`)
- **Input Payload:**
```json
{
  "preview_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "confirmed_scope": "ASSESSMENT",
  "assessment_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "confirmation_phrase": "I CONFIRM PERMANENT IRREVERSIBLE DESTRUCTION"
}
```
- **Execution Safeguards:**
  1. Validates `preview_token` HMAC signature and 5-minute expiry.
  2. Verifies `confirmation_phrase` exact match.
  3. Re-evaluates `is_eligible_for_purge()` and `LegalHold` state under `select_for_update` row locks.
  4. Automatically skips any attempt that became held or unfinalized between preview and execution.
- **Response `202 Accepted`:**
```json
{
  "status": "success",
  "message": "Manual purge execution task accepted.",
  "data": {
    "job_run_id": "55c4d001-c88f-4f2a-89aa-6178a9c3b112",
    "status": "RUNNING",
    "evaluated_count": 15,
    "eligible_for_execution_count": 15
  }
}
```

### 2.4 `POST /api/v1/admin/legal-holds/`
- **Authentication:** Required (`Role.ADMIN`)
- **Input Payload:**
```json
{
  "title": "Academic Honor Council Review - Case #2026-089",
  "case_reference": "HONOR-2026-089",
  "scope": "ATTEMPT",
  "attempt_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "reason": "Preserve webcam keyframes and answer details pending grievance hearing."
}
```
- **Validation:** Mutual exclusivity of scope targets; attempt must not already be in `details_purged = True` state.
- **Response `201 Created`:**
```json
{
  "status": "success",
  "data": {
    "id": "4a72d001-c88f-4f2a-89aa-6178a9c3b889",
    "status": "ACTIVE",
    "scope": "ATTEMPT",
    "case_reference": "HONOR-2026-089",
    "placed_by": "admin@codeguard.test",
    "created_at": "2026-09-03T11:00:00Z"
  }
}
```

### 2.5 `POST /api/v1/admin/legal-holds/{id}/release/`
- **Authentication:** Required (`Role.ADMIN`)
- **Input Payload:**
```json
{
  "release_reason": "Grievance concluded. Disciplinary sanction recorded."
}
```
- **Response `200 OK`:**
```json
{
  "status": "success",
  "message": "Legal hold successfully released. Associated attempts resume normal retention lifecycle.",
  "data": {
    "id": "4a72d001-c88f-4f2a-89aa-6178a9c3b889",
    "status": "RELEASED",
    "released_at": "2026-09-03T11:15:00Z"
  }
}
```

### 2.6 `GET /api/v1/admin/tombstones/`
- **Authentication:** Required (`Role.ADMIN`)
- **Query Params:** `search`, `assessment_id`, `page`, `page_size`.
- **Response `200 OK`:**
```json
{
  "count": 1,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": "f8a12340-9988-4433-2211-556677889900",
      "attempt_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
      "student_euid": "EUID-STU-001",
      "assessment_id": "11223344-5566-7788-99aa-bbccddeeff00",
      "assessment_title_snapshot": "DSA Final Exam",
      "purged_at": "2026-09-03T02:01:00Z",
      "answers_scrubbed_count": 25,
      "code_submissions_scrubbed_count": 4,
      "proctoring_events_scrubbed_count": 312,
      "evidence_files_deleted_count": 18,
      "confirmed_bytes_reclaimed": 14500200,
      "sha256_audit_proof": "a3f5b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7"
    }
  ]
}
```

---

## 3. Student Endpoint Specifications

### 3.1 `GET /api/v1/student/privacy/lifecycle/`
- **Authentication:** Required (`Role.STUDENT`)
- **Response `200 OK`:**
```json
{
  "status": "success",
  "data": {
    "student_euid": "EUID-BOB-001",
    "retention_policy_summary": "Detailed responses and proctoring telemetry are stored for 30 days after exam completion, after which they are permanently and irreversibly destroyed. Your official grade, score, and transcript remain permanent.",
    "attempts": [
      {
        "attempt_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
        "assessment_title": "Database Systems Exam",
        "completed_at": "2026-08-25T14:30:00Z",
        "details_purged": false,
        "detailed_data_expires_at": "2026-09-24T14:30:00Z",
        "days_remaining": 21,
        "export_status": "AVAILABLE_FULL_TELEMETRY"
      },
      {
        "attempt_id": "3c8290fa-1122-3344-5566-778899aabbcc",
        "assessment_title": "Programming in Python",
        "completed_at": "2026-07-01T10:00:00Z",
        "details_purged": true,
        "detailed_data_expires_at": "2026-07-31T10:00:00Z",
        "days_remaining": 0,
        "export_status": "AVAILABLE_PARTIAL_ARCHIVE"
      }
    ]
  }
}
```

### 3.2 `POST /api/v1/student/privacy/export-request/`
- **Authentication:** Required (`Role.STUDENT`)
- **Rate Limit:** 3 req/day
- **Input Payload:**
```json
{
  "attempt_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d"
}
```
- **Allowlist Filter Applied:**
  - Includes: Student profile, own submitted code/answers, earned score, pass/fail status, public question descriptions, own webcam keyframes.
  - Redacts: Hidden test cases, sandbox commands, evaluator secrets, another student's data, administrative notes.
- **Response `202 Accepted`:**
```json
{
  "status": "success",
  "message": "Data export request queued. Snapshot is being acquired.",
  "data": {
    "job_id": "e9871234-abcd-ef01-2345-6789abcdef01",
    "status": "SNAPSHOT_PENDING",
    "protection_boundary": "Protects attempt from retention purge once SNAPSHOT_ACQUIRED is reached",
    "expires_at": "2026-09-10T11:00:00Z"
  }
}
```

### 3.3 `GET /api/v1/student/privacy/exports/{job_id}/`
- **Authentication:** Required (`Role.STUDENT`)
- **Response `200 OK` (when ready):**
```json
{
  "status": "success",
  "data": {
    "job_id": "e9871234-abcd-ef01-2345-6789abcdef01",
    "status": "READY",
    "archive_type": "FULL_PRE_PURGE_TELEMETRY",
    "encryption_metadata": {
      "algorithm": "AES-256-GCM",
      "key_version": "v1"
    },
    "download_url": "/api/v1/student/privacy/exports/e9871234-abcd-ef01-2345-6789abcdef01/download/",
    "sha256_hash": "c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6",
    "expires_at": "2026-09-10T11:00:00Z"
  }
}
```
*(If attempt was already purged prior to export, `archive_type` reports `AVAILABLE_PARTIAL_ARCHIVE` containing the permanent transcript and tombstone certificate).*

