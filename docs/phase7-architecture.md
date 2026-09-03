# CODEGUARD — Phase 7 Architecture Specification: AI Proctoring & Anti-Cheating

---

## 1. Executive Summary

Phase 7 designs the **AI Proctoring & Anti-Cheating Subsystem** for CODEGUARD. The subsystem captures multi-modal environmental, visual, and acoustic telemetry during active exam sessions, extracts probabilistic risk signals through client heuristics and asynchronous computer vision (CV) pipelines, computes deterministic attempt risk scores, and surfaces objective event timelines for human administrative review.

### Non-Negotiable Core Principle
> **Proctoring signals are probabilistic indicators and suspicious-event evidence, NOT proof of cheating.**
>
> AI-generated events require human contextual interpretation. The assessment engine remains completely decoupled: proctoring events, warnings, or risk scores **NEVER directly mutate student scores, timer countdowns, question states, attempt statuses, or code evaluation verdicts**. Human review remains strictly authoritative for any disciplinary decisions.

---

## 2. Phase 7 Final Architecture Decisions

| # | Architecture Dimension | Final Locked Decision | Rationale |
| :---: | :--- | :--- | :--- |
| **1** | **Frame Transport** | REST multipart snapshot upload (`POST /proctoring/frames/`) | Eliminates binary streaming complexity, enables fine-grained backpressure and standard HTTP rate limiting. |
| **2** | **Sampling & Rate Limit** | Target 0.5 FPS, sustained $\le 30$ frames/min, bounded burst capacity of 5 tokens | Absorbs network latency and browser timer jitter without false 429 rejections; burst is a tolerance mechanism, not high-frequency capture. |
| **3** | **Client Telemetry Trust** | Client signals $\ne$ authoritative facts (`server_received_at` authoritative) | Prevents DOM event spoofing, timestamp manipulation, and client-dictated risk scoring. |
| **4** | **AI Confidence & Persistence Gate** | Multi-frame persistence gate ($\ge 2$ frames over 4s) + confidence thresholds (Phone: $\ge 0.65$, Faces: $\ge 0.60$) | Eliminates transient optical noise and single-frame false positives from triggering persistent alerts. |
| **5** | **Risk Score Inflation Protection** | Per-event-family caps, deduplication windows, mathematical decay, overall clamp $[0, 100]$ | Prevents event flooding from artificially inflating risk scores to critical levels. |
| **6** | **Deterministic Time Decay Clock** | Decay uses $\Delta t = \text{now}_{\text{server}} - e.\text{server\_received\_at}$ with $\lambda = \ln(2)/600$ | Authoritative server clock prevents client or worker completion timestamps from altering decay determinism. |
| **7** | **Exact Multi-Signal Correlation** | Bounded $+15.0$ bonus (cooldown 60s, cap $30.0$) across $\ge 2$ independent active signal families in 60s window | Same-family duplicates cannot trigger bonus; surfaces multi-modal context without implying guilt. |
| **8** | **Risk Expiration $\ne$ Data Deletion** | 3600s active evaluation window $\rightarrow \Delta R(t) = 0$; metadata retained per Phase 9 retention | Explicitly separates active scoring contributions from historical audit log retention. |
| **9** | **Evidence Hashing & Security** | `SHA256(raw_bytes)` for integrity verification; RBAC + Object Authorization for confidentiality | Hashing verifies non-tampering; authorization and ACLs prevent unauthorized access. |
| **10**| **Audio Architecture** | Client WebAudio RMS trigger hint $\rightarrow$ 2s bounded audio upload $\rightarrow$ Server VAD | Client RMS is an untrusted trigger hint; server VAD independently validates speech presence. |
| **11**| **REST Heartbeat Fallback** | Dedicated `POST /proctoring/heartbeat/` maintains session health on WS disconnect | Maintains proctoring session health without affecting server-authoritative timer. |
| **12**| **Versioned Policy Contracts** | Centralized `ProctoringInferencePolicy` & `ProctoringAudioPolicy` configuration | Eliminates scattered hardcoded constants; guarantees historical reproducibility. |
| **13**| **Fault Tolerance & Degraded Mode** | Infrastructure/AI failure $\rightarrow$ `PROCTORING_DEGRADED` (Zero Student-Penalization System Failures) | Technical failures produce zero cheating risk ($\Delta R = 0$) and never penalize students. |
| **14**| **Human Review Authority** | AI $\rightarrow$ Risk Indicators $\rightarrow$ Evidence $\rightarrow$ Admin Review $\rightarrow$ Human Decision | Ensures no student is ever automatically disqualified or penalized by AI algorithms. |

---

## 3. Source-Based Trust Matrix

| Source | Example Telemetry | Trust Level | Authority & Server Validation |
| :--- | :--- | :--- | :--- |
| **`BROWSER`** | `TAB_SWITCH`, `FULLSCREEN_EXIT`, `WINDOW_BLUR` | **Untrusted Client Telemetry** | Server validates attempt ownership, checks active attempt status, records `server_received_at`, and enforces rate limits. |
| **`BROWSER`** | Audio RMS Energy Spike ($>65\text{ dB}$ hint) | **Untrusted Activity Hint** | Server receives 2s clip and performs authoritative Voice Activity Detection (VAD). |
| **`AI`** | `PHONE_DETECTED`, `MULTIPLE_FACES`, `HEAD_TURN` | **Probabilistic Model Signal** | Derived asynchronously on server Celery workers; filtered by confidence thresholds and persistence gates. |
| **`SERVER`** | Session heartbeat, attempt status, timer expiry | **Authoritative Server State** | Generated directly by Django core; client has zero write access. |
| **`SYSTEM`** | `PROCTORING_DEGRADED`, worker timeout | **Authoritative System Telemetry** | Generated by infrastructure watchdogs; contributes zero risk ($\Delta R = 0$). |
| **`RISK_ENGINE`**| `risk_score`, `risk_band`, `risk_delta` | **Authoritative Derived Metric** | Deterministically calculated by server domain services; client inputs strictly ignored. |

---

## 4. Versioned Policy & Configuration Contracts

All threshold parameters and inference policies are defined as versioned configuration contracts rather than scattered code constants. Initial configurable policy values can change only through a newly registered policy version.

### 4.1 `ProctoringInferencePolicy` (Contract)
```python
# Versioned Proctoring Inference Configuration Contract
PROCTORING_INFERENCE_POLICY_V1 = {
    "policy_version": "CG-INFERENCE-POL-V1",
    "model_name": "YOLOv8n-MediaPipeFaceMesh",
    "model_version": "CG-MODELS-2026.1",
    "threshold_version": "CG-THRESHOLDS-V1",
    "phone_confidence_threshold": 0.65,              # Initial authoritative policy
    "multiple_face_confidence_threshold": 0.60,       # Initial authoritative policy
    "face_missing_duration_seconds": 5.0,
    "required_persistent_frames": 2,                  # Required persistent sampled frames
    "persistence_window_seconds": 4.0,                # Sliding window duration
    "head_turn_yaw_threshold_degrees": 30.0,
    "head_tilt_pitch_threshold_degrees": 25.0,
    "gaze_deviation_duration_seconds": 4.0,
    "target_frame_sampling_rate_fps": 0.5,
    "decay_lambda_parameter": 0.001155,               # Half-life = 600 seconds (10 minutes)
    "decay_evaluation_window_seconds": 3600,          # 1 hour active evaluation window
    "correlation_window_seconds": 60,                 # Multi-signal correlation window
    "minimum_independent_families": 2,                # Minimum distinct active signal families
    "correlation_bonus": 15.0,                        # Correlation bonus for qualifying condition
    "correlation_cooldown_seconds": 60,               # Cooldown preventing repeated bonus spam
    "maximum_correlation_contribution": 30.0,         # Maximum correlation contribution ceiling
}
```

### 4.2 `ProctoringAudioPolicy` (Contract)
```python
# Versioned Proctoring Audio Configuration Contract
PROCTORING_AUDIO_POLICY_V1 = {
    "audio_policy_version": "CG-AUDIO-POL-V1",
    "client_trigger_threshold_db": 65.0,              # Client activity hint threshold only
    "clip_duration_seconds": 2.0,                     # Bounded Opus snippet
    "maximum_clip_size_bytes": 102400,                # 100 KB max Opus WebM
    "vad_model_version": "WebRTC-VAD-V1",
    "vad_speech_confidence_threshold": 0.70,          # Server-side VAD validation gate
    "audio_cooldown_seconds": 30,
    "audio_rate_limit_per_minute": 6,
}
```

---

## 5. Sampling Rate, Burst Allowance & Token Bucket Specification

```text
[ Browser Webcam Capture ] (Canvas Snapshot @ Target 0.5 FPS = 1 frame / 2.0s)
            │
            ▼ (HTTPS POST /api/v1/student/attempts/<id>/proctoring/frames/)
┌─────────────────────────────────────────────────────────────┐
│                 REDIS TOKEN BUCKET FILTER                   │
│                                                             │
│  - Target Sampling Rate: 0.5 FPS (1 request every 2.0s)     │
│  - Sustained Average: ≤ 30 frames / minute                  │
│  - Bucket Capacity (Burst Allowance): 5 tokens              │
│  - Refill Rate: 0.5 tokens / second                         │
│                                                             │
│  Token Available?                                           │
│  ├── YES ──> Deduct 1 token & accept frame (HTTP 202)       │
│  └── NO  ──> Reject with HTTP 429 Too Many Requests         │
└─────────────────────────────────────────────────────────────┘
```
* **Burst Allowance Purpose**: The 5-token burst is strictly a tolerance mechanism to accommodate network jitter and browser timer drift, not permission for high-frequency continuous capture.

---

## 6. AI Confidence & Multi-Frame Persistence Gate

```text
Raw Frame (JPEG)
       │
       ▼
[ Asynchronous Celery AI Worker (MediaPipe / YOLOv8n) ]
       │
       ▼
Confidence Threshold Check (confidence >= policy.confidence_threshold)
  ├── NO  ──> Discard (Normal / Ephemeral RAM eviction)
  └── YES ──>
       │
       ▼
Persistence Window Gate (Detected in ≥ policy.required_persistent_frames within window)
  ├── NO  ──> Buffer state in Redis ephemeral cache (No event created)
  └── YES ──>
       │
       ▼
Deduplication & Cooldown Check (e.g. Cooldown active for event family?)
  ├── YES ──> Extend existing event duration (Update ended_at; zero risk delta)
  └── NO  ──> Create immutable ProctoringEvent & Calculate bounded Risk Delta
```

---

## 7. Deterministic Risk Scoring, Time Decay & Multi-Signal Correlation

### 7.1 Risk Score Protection Architecture
```text
Raw Signal ──> Validated Event ──> Deduplication ──> Risk Delta ──> Family Cap Check ──> Multi-Signal Correlation ──> Deterministic Time Decay ──> Score Clamp [0, 100] ──> Risk Band
```

### 7.2 Event Family Caps & Severity Matrix

| Event Family | Event Types Included | Base $\Delta R$ | Cooldown | Max Family Contribution Cap |
| :--- | :--- | :---: | :---: | :---: |
| **`FOCUS_LOSS`** | `WINDOW_BLUR`, `TAB_SWITCH`, `FULLSCREEN_EXIT` | $+4.0$ to $+10.0$ | 15s | **$40.0$** |
| **`FACE_PRESENCE`**| `FACE_MISSING`, `FACE_PARTIALLY_OCCLUDED` | $+8.0$ | 20s | **$32.0$** |
| **`HEAD_POSE`** | `HEAD_TURN_PROLONGED`, `GAZE_DEVIATION` | $+5.0$ | 20s | **$20.0$** |
| **`AUDIO`** | `AUDIO_ACTIVITY` (Server VAD Confirmed) | $+12.0$ | 30s | **$36.0$** |
| **`MULTIPLE_PEOPLE`**| `MULTIPLE_FACES`, `MULTIPLE_VOICE_ACTIVITY`| $+25.0$ | 30s | **$50.0$** |
| **`UNAUTHORIZED_DEVICE`**| `PHONE_DETECTED`, `BOOK_NOTES_DETECTED` | $+40.0$ | 30s | **$80.0$** |
| **`SYSTEM_INFRA`** | `PROCTORING_DEGRADED`, `CAMERA_UNAVAILABLE` | **$0.0$** | 0s | **$0.0$** |

### 7.3 Authoritative Time Decay Reference Clock
The risk engine applies time decay strictly referenced against the authoritative `server_received_at` timestamp:
$$\Delta t = \text{current authoritative server evaluation timestamp} - e.\text{server\_received\_at}$$
$$\Delta R_e(t) = \begin{cases} 
\Delta R_{e, \text{initial}} \cdot e^{-\lambda \cdot \Delta t} & \text{if } \Delta t \le \text{decay\_evaluation\_window\_seconds} (3600\text{s}) \\
0.00 & \text{if } \Delta t > 3600\text{s} \text{ (Active risk expired)}
\end{cases}$$
where:
* $\lambda = \text{decay\_lambda\_parameter} = 0.001155 \text{ s}^{-1}$ (half-life $T_{1/2} = 600\text{ seconds} = 10\text{ minutes}$).
* `client_detected_at`, browser clocks, or AI inference completion timestamps **NEVER control the decay clock**.
* **Risk Expiration $\ne$ Data Deletion**: After 3600 seconds, an event's active risk contribution $\Delta R_e(t)$ becomes $0.00$, but its historical metadata remains stored in the database according to the Phase 7 / Phase 9 data retention policy.

### 7.4 Exact Multi-Signal Correlation Policy
* **Definition of Active Signal Family**: A signal family $f$ is defined as *active* if and only if it contains at least one qualifying, non-expired event ($e \in f$) with $\Delta t \le \text{correlation\_window\_seconds} (60\text{s})$ and $\Delta R_e(t) > 0$.
* **Independence Rule**: Multiple events belonging to the **same** family (e.g. 3 consecutive `TAB_SWITCH` events in `FOCUS_LOSS`) count as **1 active family**, not 3.
* **Qualifying Correlation Condition**: Occurs when $\ge 2$ **distinct, independent** signal families are simultaneously active within the 60-second correlation window (e.g., `FOCUS_LOSS` + `UNAUTHORIZED_DEVICE`).
* **Deterministic Correlation Rule**:
  $$\text{If } |\{f_{\text{active}}\}| \ge \text{minimum\_independent\_families } (2) \text{ and correlation cooldown has elapsed:}$$
  $$\text{Correlation Bonus } R_{\text{corr}} = \min(\text{maximum\_correlation\_contribution } (30.0), R_{\text{corr, current}} + \text{correlation\_bonus } (15.0))$$
  $$\text{Otherwise: } R_{\text{corr}} = R_{\text{corr, current}}$$
* **Correlation Cooldown & Cap**: `correlation_cooldown_seconds = 60` prevents duplicate bonuses for the same continuous anomaly condition. Maximum total correlation bonus is clamped at $+30.0$.
* **Non-Accusatory Invariant**: Correlation is strictly a mathematical risk aggregator; it **does NOT constitute proof of cheating** and cannot trigger automated guilt or disciplinary penalties.

### 7.5 Cumulative Risk Score Clamping
$$\text{Risk Score} = \min\left(100.00, \max\left(0.00, \sum_{f} \min\left(\text{Cap}_f, \sum_{e \in f} \Delta R_e(t)\right) + R_{\text{corr}}\right)\right)$$

### 7.6 Risk Bands vs. Disciplinary Review States
* **Proctoring Risk Bands** (AI & Mathematical Metric):
  - `NORMAL` ($0.00 - 20.00$)
  - `LOW` ($20.01 - 40.00$)
  - `MEDIUM` ($40.01 - 60.00$)
  - `HIGH` ($60.01 - 80.00$)
  - `CRITICAL` ($80.01 - 100.00$)
* **Human Review States** (Authoritative Administrative Workflow):
  - `UNREVIEWED` (Default initial state)
  - `UNDER_REVIEW` (Administrator investigating attempt timeline)
  - `REVIEWED` (Validated as acceptable / normal)
  - `DISMISSED` (Flagged as false positive)
  - `ESCALATED` (Forwarded for institutional inquiry)

---

## 8. Database Entities & Schemas

### 8.1 `ProctoringSession`
* `id` (UUID PK)
* `attempt` (OneToOneField $\rightarrow$ `TestAttempt`, `on_delete=CASCADE`)
* `status` (`ACTIVE`, `PAUSED`, `TERMINATED`, `DEGRADED`)
* `risk_score` (`DecimalField(max_digits=5, decimal_places=2)`, default `0.00`)
* `risk_band` (`NORMAL`, `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`)
* `total_events_count` (`PositiveIntegerField`, default 0)
* `total_warnings_count` (`PositiveIntegerField`, default 0)
* `review_status` (`UNREVIEWED`, `UNDER_REVIEW`, `REVIEWED`, `DISMISSED`, `ESCALATED`)
* `created_at`, `updated_at`

### 8.2 `ProctoringEvent` (Append-Only Immutable Ledger)
* `id` (UUID PK)
* `session` (ForeignKey $\rightarrow$ `ProctoringSession`, related_name='events')
* `event_type` (`CharField(max_length=64)`, db_index=True)
* `source` (`CharField(choices=['BROWSER', 'AI', 'SERVER', 'SYSTEM'])`)
* `severity` (`CharField(choices=['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'])`)
* `confidence` (`FloatField`, default 1.0)
* `started_at` (`DateTimeField`)
* `ended_at` (`DateTimeField`, null=True)
* `duration_ms` (`PositiveIntegerField`, default 0)
* `client_detected_at` (`DateTimeField`, null=True)  *(Informational telemetry only)*
* `server_received_at` (`DateTimeField`, auto_now_add=True)  *(Authoritative index for time decay)*
* `model_name` (`CharField(max_length=64)`, blank=True)
* `model_version` (`CharField(max_length=32)`, blank=True)
* `threshold_version` (`CharField(max_length=32)`, default='V1')
* `inference_policy_version` (`CharField(max_length=32)`, default='V1')
* `risk_delta` (`DecimalField(max_digits=5, decimal_places=2)`, default 0.00)
* `metadata` (`JSONField`, default=dict)
* `evidence` (ForeignKey $\rightarrow$ `ProctoringEvidence`, null=True, on_delete=SET_NULL)

### 8.3 `ProctoringEvidence`
* `id` (UUID PK)
* `session` (ForeignKey $\rightarrow$ `ProctoringSession`)
* `media_type` (`IMAGE_JPEG`, `AUDIO_WEBM`)
* `storage_path` (`CharField(max_length=512)`)
* `sha256_hash` (`CharField(max_length=64)`)  *(Integrity verification: `SHA256(raw_bytes)`)*
* `file_size_bytes` (`PositiveIntegerField`)
* `created_at` (`DateTimeField`, auto_now_add=True)
* `expires_at` (`DateTimeField`, null=True)
* `retention_class` (`TEMPORARY_EVIDENCE`, `ARCHIVED_FLAGGED`)

### 8.4 `ProctoringWarning`
* `id` (UUID PK)
* `session` (ForeignKey $\rightarrow$ `ProctoringSession`, related_name='warnings')
* `warning_type` (`FULLSCREEN`, `FACE_VISIBILITY`, `AUDIO`, `DEVICE`)
* `message` (`CharField(max_length=255)`)
* `issued_at` (`DateTimeField`, auto_now_add=True)
* `acknowledged_at` (`DateTimeField`, null=True)

### 8.5 `ProctoringReview`
* `id` (UUID PK)
* `session` (OneToOneField $\rightarrow$ `ProctoringSession`, related_name='review')
* `reviewer` (ForeignKey $\rightarrow$ `User`, on_delete=PROTECT)
* `decision` (`REVIEWED_CLEAN`, `SUSPICIOUS_CONFIRMED`, `DISMISSED_FALSE_POSITIVE`, `REQUIRES_FURTHER_INSPECTION`)
* `notes` (`TextField`, blank=True)
* `reviewed_at` (`DateTimeField`, auto_now_add=True)

---

## 9. Audio Proctoring Architecture

```text
[ Browser WebAudio API ] (AnalyserNode monitors ambient RMS amplitude @ 10 Hz)
            │
      Is RMS Amplitude > Threshold (e.g. > 65 dB hint)?
            ├── NO  ──> Discard (Zero Audio Sent)
            └── YES ──>
                 │
                 ▼ (Capture 2.0-second Opus WebM snippet)
[ HTTPS POST /api/v1/student/attempts/<id>/proctoring/audio/ ] (Rate limit: max 6 / min)
                 │
                 ▼
[ Celery Voice Activity Detection (VAD) ]
  ├── Energy confirmed as speech spectrum (300 Hz - 3400 Hz) with VAD confidence >= 0.70?
  │     ├── NO  ──> Discard snippet (Ambient transient / Keyboard click)
  │     └── YES ──> Emit AUDIO_ACTIVITY Event (+12.0 Risk Delta)
  └── Discard audio snippet from memory unless multi-voice overlap detected
```

---

## 10. Failure Semantics & Zero Student-Penalization Guarantee

| Failure Scenario | Proctoring Subsystem Response | Assessment Engine Impact | Student UI Impact | Admin Dashboard Impact |
| :--- | :--- | :--- | :--- | :--- |
| **Webcam Hardware Disconnect** | Emits `CAMERA_UNAVAILABLE` ($\Delta R = 0$) | Zero impact (Timer/answers preserved) | Non-accusatory modal prompt to reconnect | Flagged as `DEVICE_DISCONNECTED` |
| **Microphone Disconnect** | Logs `MICROPHONE_UNAVAILABLE` ($\Delta R = 0$) | Zero impact | Optional advisory banner | Annotated in timeline |
| **AI Worker Crash / Queue Backlog**| Ingestion saves state; marks `PROCTORING_DEGRADED` | Zero impact (Exam continues normally) | None (Transparent) | Session badge: `DEGRADED (AI Offline)` |
| **Redis Queue Outage** | Ingestion gateway drops frame inference; logs degradation | Zero impact | None | Session badge: `DEGRADED (Queue Offline)` |
| **WebSocket Disconnection** | Client falls back to REST heartbeat `POST /proctoring/heartbeat/` | Zero impact (Answers save via REST) | Reconnection toast indicator | Live status shows `REST Fallback` |
| **Inference Timeout ($>5\text{s}$)**| Task aborted; worker claims next item | Zero impact | None | Diagnostic log recorded |

---

## 11. Performance & Scaling Contract

1. **Non-Blocking Guarantee**: Proctoring telemetry, frame uploads, and AI inference execute strictly out-of-band and **NEVER block editor typing, question navigation, answer autosave, or code compilation/execution**.
2. **Resource Ceilings**:
   - Single frame inference duration: $\le 60\text{ ms}$ on standard CPU (MediaPipe: $\approx 18\text{ ms}$, YOLOv8n ONNX: $\approx 38\text{ ms}$).
   - Memory allocation per worker process: $\le 350\text{ MB}$.
3. **Queue Backpressure**: If Redis task queue depth exceeds 100 frames, intermediate unflagged baseline frames are dropped with FIFO eviction to ensure real-time latency remains bounded.

---

## 12. Security Test Matrix

* **Client Spoofing Probes**: Injecting forged `TAB_SWITCH`, manipulated `detected_at` timestamps, or client-provided `risk_delta` $\rightarrow$ Server overrides with `server_received_at` and computes risk delta independently.
* **Identity & IDOR Probes**: Uploading frames or events under another student's `attempt_id` $\rightarrow$ Rejected with `HTTP 403 Forbidden`.
* **Replay Attacks**: Re-submitting identical frame payloads $\rightarrow$ Deduplicated and rejected without extra risk contribution.
* **Flooding Attacks**: Submitting $>30$ frames/min or $>20$ events/min $\rightarrow$ Rejected with `HTTP 429 Too Many Requests`.
* **Evidence Protection**: Querying `/api/v1/admin/proctoring/evidence/<id>/` with Student credentials $\rightarrow$ Rejected with `HTTP 403 Forbidden`. Path traversal attempts (`../../etc/shadow`) $\rightarrow$ Rejected with `HTTP 404`.
* **AI Model Integrity**: Submitting corrupted JPEG or invalid model version tags $\rightarrow$ Handled gracefully without worker termination.
* **Degraded Mode Verification**: Killing Celery AI worker during active exam $\rightarrow$ `TestAttempt` completes cleanly; `ProctoringSession` marks `status = DEGRADED`.
* **Phase 1–6 Regression**: All 136 backend tests must pass with 0 errors.
