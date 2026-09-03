# CODEGUARD — Phase 7 API & WebSocket Contract: AI Proctoring & Anti-Cheating

---

## 1. Phase 7 Final Architecture Decisions (API)

1. **REST Multipart Snapshot Ingestion**: Frame telemetry uses `POST /api/v1/student/attempts/<attempt_id>/proctoring/frames/` (multipart/form-data) at target rate 0.5 FPS (sustained $\le 30$ frames/min with bounded burst allowance of 5 tokens).
2. **REST Heartbeat Fallback**: Dedicated endpoint `POST /api/v1/student/attempts/<attempt_id>/proctoring/heartbeat/` maintains proctoring session communication and health if WebSockets disconnect, without interfering with the server-authoritative assessment timer.
3. **Untrusted Client Ingestion**: Client cannot provide `risk_delta`, `severity`, `confidence`, or `student_id` in request payloads. The server derives and validates all metrics.
4. **Dedicated Audio Spike Endpoint**: Client WebAudio uploads bounded 2-second audio clips via `POST /api/v1/student/attempts/<attempt_id>/proctoring/audio/` only when client RMS energy exceeds threshold ($> 65\text{ dB}$ hint).
5. **WebSocket Channel Scoping**: Channels WebSockets transmit real-time warnings to students (`proctoring_student_<attempt_id>`) and real-time risk alerts to administrators (`proctoring_admin_<assessment_id>`), but do not carry continuous video streams.
6. **Evidence Object Authorization**: Evidence retrieval enforces authenticated session, Admin role, object existence, and institutional authorization scope.

---

## 2. Student REST Endpoints

### 2.1 Start Proctoring Session
* **Method & URI**: `POST /api/v1/student/attempts/<attempt_id>/proctoring/start/`
* **Authorization**: Active Student owning the attempt (`request.user == attempt.student`).
* **Response (HTTP 200 OK)**:
```json
{
  "session_id": "27c3e445-6671-460d-a773-1004ea74681f",
  "status": "ACTIVE",
  "frame_sampling_interval_seconds": 2.0,
  "heartbeat_interval_seconds": 15.0,
  "created_at": "2026-09-02T23:10:00Z"
}
```

### 2.2 Proctoring Heartbeat Fallback
* **Method & URI**: `POST /api/v1/student/attempts/<attempt_id>/proctoring/heartbeat/`
* **Authorization**: Active Student owning the attempt.
* **Purpose**: Maintains proctoring session communication health when WebSocket is disconnected. (Does NOT alter server timer authority).
* **Response (HTTP 200 OK)**:
```json
{
  "status": "HEALTHY",
  "session_status": "ACTIVE",
  "server_time": "2026-09-02T23:15:15Z"
}
```

### 2.3 Ingest Client Heuristic Event
* **Method & URI**: `POST /api/v1/student/attempts/<attempt_id>/proctoring/events/`
* **Authorization**: Active Student owning the attempt.
* **Request Payload**:
```json
{
  "event_type": "FULLSCREEN_EXIT",
  "client_detected_at": "2026-09-02T23:15:10Z",
  "metadata": {
    "viewport_width": 1280,
    "viewport_height": 720
  }
}
```
* **Response (HTTP 202 Accepted)**:
```json
{
  "event_id": "f516a2b3-96b2-4d2b-b62e-855f4621d10e",
  "status": "RECORDED",
  "source": "BROWSER",
  "server_received_at": "2026-09-02T23:15:11Z",
  "warning_issued": true,
  "warning": {
    "id": "8b512e0e-4b63-424a-9774-601e3b68019a",
    "warning_type": "FULLSCREEN",
    "message": "Full-screen mode was exited. Please re-enter full-screen to continue your assessment."
  }
}
```

### 2.4 Upload Sampled Frame
* **Method & URI**: `POST /api/v1/student/attempts/<attempt_id>/proctoring/frames/`
* **Content-Type**: `multipart/form-data`
* **Form Fields**: `frame` (binary JPEG image, $\le 300\text{ KB}$), `sequence_number` (int).
* **Rate Limits**: Target 0.5 FPS, sustained $\le 30\text{ frames/min}$, burst capacity 5 tokens.
* **Response (HTTP 202 Accepted)**:
```json
{
  "status": "QUEUED_FOR_INFERENCE",
  "sequence_number": 42
}
```
* **Rate Limit Exceeded (HTTP 429 Too Many Requests)**:
```json
{
  "detail": "Frame submission rate limit exceeded. Please maintain normal sampling intervals."
}
```

### 2.5 Upload Bounded Audio Trigger Clip
* **Method & URI**: `POST /api/v1/student/attempts/<attempt_id>/proctoring/audio/`
* **Content-Type**: `multipart/form-data`
* **Form Fields**: `audio` (binary Opus WebM, $\le 2.0\text{s}$, $\le 100\text{ KB}$), `rms_db` (float).
* **Rate Limits**: Maximum 6 uploads per minute, burst capacity 2.
* **Response (HTTP 202 Accepted)**:
```json
{
  "status": "QUEUED_FOR_VAD_ANALYSIS"
}
```

### 2.6 Acknowledge Warning
* **Method & URI**: `POST /api/v1/student/attempts/<attempt_id>/proctoring/warnings/<warning_id>/ack/`
* **Response (HTTP 200 OK)**:
```json
{
  "status": "ACKNOWLEDGED",
  "acknowledged_at": "2026-09-02T23:15:25Z"
}
```

---

## 3. Admin REST Endpoints

### 3.1 List Assessment Proctoring Sessions
* **Method & URI**: `GET /api/v1/admin/assessments/<assessment_id>/proctoring/sessions/`
* **Authorization**: Admin role required.
* **Query Params**: `risk_band=HIGH,CRITICAL`, `review_status=UNREVIEWED`, `search=Alice`
* **Response (HTTP 200 OK)**:
```json
{
  "count": 1,
  "results": [
    {
      "session_id": "27c3e445-6671-460d-a773-1004ea74681f",
      "attempt_id": "f516a2b3-96b2-4d2b-b62e-855f4621d10e",
      "student": {
        "id": "u1",
        "email": "alice@example.com",
        "euid": "STU260001",
        "full_name": "Alice Johnson"
      },
      "status": "ACTIVE",
      "risk_score": "75.00",
      "risk_band": "HIGH",
      "total_events_count": 4,
      "total_warnings_count": 2,
      "review_status": "UNREVIEWED",
      "created_at": "2026-09-02T23:10:00Z"
    }
  ]
}
```

### 3.2 Get Attempt Proctoring Detail & Timeline
* **Method & URI**: `GET /api/v1/admin/proctoring/sessions/<session_id>/`
* **Authorization**: Admin role required.
* **Response (HTTP 200 OK)**:
```json
{
  "session_id": "27c3e445-6671-460d-a773-1004ea74681f",
  "risk_score": "75.00",
  "risk_band": "HIGH",
  "events": [
    {
      "id": "e1",
      "event_type": "PHONE_DETECTED",
      "source": "AI",
      "severity": "CRITICAL",
      "confidence": 0.88,
      "server_received_at": "2026-09-02T23:15:13Z",
      "model_name": "YOLOv8n",
      "model_version": "CG-YOLO-PHONE-V1",
      "threshold_version": "CG-PHONE-THRESHOLD-V1",
      "inference_policy_version": "CG-PROCTORING-POLICY-V1",
      "risk_delta": "40.00",
      "evidence_id": "3bb8cf65-1d48-43d9-9520-22c6b443597d"
    }
  ],
  "review": null
}
```

### 3.3 Retrieve Evidence Media (Secure Stream)
* **Method & URI**: `GET /api/v1/admin/proctoring/evidence/<evidence_id>/`
* **Authorization**: Admin role + institutional attempt authorization required (Students receive `HTTP 403 Forbidden`).
* **Response (HTTP 200 OK)**: Binary `image/jpeg` with `Content-Disposition: inline`.

### 3.4 Update Review Decision
* **Method & URI**: `PATCH /api/v1/admin/proctoring/sessions/<session_id>/review/`
* **Authorization**: Admin role required.
* **Request Payload**:
```json
{
  "decision": "REVIEWED_CLEAN",
  "notes": "Student adjusted eyeglasses; no secondary phone device present upon manual inspection."
}
```
* **Response (HTTP 200 OK)**:
```json
{
  "review_id": "9a12c4e5-a342-43bb-a1b9-1234567890ab",
  "decision": "REVIEWED_CLEAN",
  "reviewed_by": "admin@example.com",
  "reviewed_at": "2026-09-02T23:25:00Z"
}
```

---

## 4. WebSocket Real-Time Event Protocol

### 4.1 Student Group: `proctoring_student_<attempt_id>`
* **Event**: `PROCTORING_WARNING`
```json
{
  "type": "proctoring_warning",
  "payload": {
    "warning_id": "8b512e0e-4b63-424a-9774-601e3b68019a",
    "warning_type": "FULLSCREEN",
    "message": "Full-screen mode was exited. Please re-enter full-screen to continue your assessment.",
    "timestamp": "2026-09-02T23:15:11Z"
  }
}
```

### 4.2 Admin Group: `proctoring_admin_<assessment_id>`
* **Event**: `PROCTORING_ALERT`
```json
{
  "type": "proctoring_alert",
  "payload": {
    "session_id": "27c3e445-6671-460d-a773-1004ea74681f",
    "student_euid": "STU260001",
    "event_type": "PHONE_DETECTED",
    "source": "AI",
    "severity": "CRITICAL",
    "risk_score": "75.00",
    "risk_band": "HIGH",
    "timestamp": "2026-09-02T23:15:13Z"
  }
}
```
