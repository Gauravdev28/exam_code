# CODEGUARD — Phase 6 API & WebSocket Contract

---

## 1. REST Endpoints

### 1.1 Student: Run Code (Public Tests Only)
* **Method & URI**: `POST /api/v1/student/attempts/<attempt_id>/questions/<question_id>/run/`
* **Authorization**: Active Student session owning the attempt.
* **Request Payload**:
```json
{
  "source_code": "def two_sum(nums, target):\n    ...",
  "language": "PYTHON",
  "idempotency_key": "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"
}
```
* **Response (HTTP 202 Accepted)**:
```json
{
  "submission_id": "13ab3090-62c4-42ad-b680-f8d55d754b40",
  "status": "QUEUED",
  "submission_type": "RUN",
  "created_at": "2026-09-02T22:30:00Z"
}
```

### 1.2 Student: Submit Solution (Authoritative Evaluation)
* **Method & URI**: `POST /api/v1/student/attempts/<attempt_id>/questions/<question_id>/submit/`
* **Authorization**: Active Student session owning the attempt.
* **Request Payload**: Same as Run.
* **Response (HTTP 202 Accepted)**: Same as Run (with `submission_type: "SUBMIT"`).

### 1.3 Student: Get Submission Status & Results
* **Method & URI**: `GET /api/v1/student/submissions/<submission_id>/`
* **Response (HTTP 200 OK)**:
```json
{
  "id": "13ab3090-62c4-42ad-b680-f8d55d754b40",
  "status": "COMPLETED",
  "verdict": "ACCEPTED",
  "submission_type": "SUBMIT",
  "language": "PYTHON",
  "score_awarded": "20.00",
  "passed_test_cases": 2,
  "total_test_cases": 2,
  "execution_time_ms": 15,
  "memory_used_kb": 12500,
  "compile_output": null,
  "test_case_results": [
    {
      "index": 1,
      "is_hidden": false,
      "verdict": "PASSED",
      "points_awarded": "10.00",
      "max_points": "10.00",
      "execution_time_ms": 10,
      "memory_used_kb": 12000,
      "input": "2 3",
      "expected_output": "5",
      "actual_output": "5\n",
      "error_message": null
    },
    {
      "index": 2,
      "is_hidden": true,
      "verdict": "PASSED",
      "points_awarded": "10.00",
      "max_points": "10.00",
      "execution_time_ms": 12,
      "memory_used_kb": 12500,
      "input": null,
      "expected_output": null,
      "actual_output": null,
      "error_message": null
    }
  ]
}
```

---

## 2. WebSocket Real-Time Event Contract

When a submission progresses through the asynchronous pipeline, the consumer sends messages to group `attempt_<attempt_id>`:

```json
{
  "type": "attempt_event",
  "event": "CODE_SUBMISSION_COMPLETED",
  "payload": {
    "submission_id": "13ab3090-62c4-42ad-b680-f8d55d754b40",
    "question_id": "q1",
    "submission_type": "SUBMIT",
    "status": "COMPLETED",
    "verdict": "ACCEPTED",
    "score_awarded": "20.00",
    "passed_test_cases": 2,
    "total_test_cases": 2,
    "compile_output": null
  }
}
```
