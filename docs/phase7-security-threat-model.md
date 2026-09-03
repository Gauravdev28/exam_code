# CODEGUARD — Phase 7 Security Threat Model & Capability Matrix

---

## 1. Executive Security Summary & Trust Boundaries

The Phase 7 AI Proctoring subsystem processes multi-modal environmental and visual signals to detect anomalies during exams. The security boundary establishes that **client telemetry is untrusted**, **server timestamps and calculations are authoritative**, and **stored evidence is cryptographically verified for integrity and protected by strict RBAC access controls**.

---

## 2. Phase 7 Final Architecture Decisions (Security)

1. **Untrusted Client Signals**: Client-originated DOM events (`TAB_SWITCH`, `FULLSCREEN_EXIT`) are categorized as untrusted telemetry (`source=BROWSER`). The server independently validates attempt state, records `server_received_at`, and derives severity/risk deltas.
2. **Untrusted Audio Trigger**: Client WebAudio RMS amplitude ($>65\text{ dB}$) is strictly an unauthenticated activity hint. Server VAD independently evaluates voice presence.
3. **SHA-256 Evidence Integrity**: SHA-256 hashing is explicitly designated as an **integrity verification mechanism** (`SHA256(raw_bytes)` to prove non-tampering). Evidence confidentiality is enforced through Django RBAC, local media volume permission masks (`chmod 0600`), and HTTPS transport security.
4. **Multi-Frame Persistence Gating**: Raw AI inferences must meet confidence thresholds (Phone: $\ge 0.65$, Faces: $\ge 0.60$) and persist across $\ge 2$ sampled frames in a 4-second window before generating high-impact events (`PHONE_DETECTED`, `MULTIPLE_FACES`), eliminating single-frame adversarial optical noise.
5. **Anti-Inflation Risk Caps & Multi-Signal Correlation**: Per-event-family maximum contribution caps, exponential time decay ($\lambda = \ln(2)/600$), and bounded correlation rules ($+15.0$ bonus, cap $30.0$) prevent automated score inflation from event flooding.
6. **IDOR & Object Authorization Shields**: Evidence access enforces four checks: (1) Authenticated session, (2) Authorized Admin role, (3) Valid evidence object, and (4) Permitted institutional scope for that assessment/attempt. Direct filesystem paths are never exposed.
7. **Zero Student-Penalization Guarantee**: System outages, camera disconnects, or worker crashes emit `SYSTEM` events with $\Delta R = 0$ and transition session to `DEGRADED` without penalizing students.

---

## 3. Threat Actors & Attack Vectors

### 3.1 Threat Actors
* **Student Candidate**: Motivated to hide unauthorized devices, tamper with browser event listeners, replay static webcam frames, or flood endpoints.
* **Malicious Network Snoop**: Attempting to intercept or tamper with webcam snapshots or audio snippets in transit.
* **Unauthorized Peer / Student**: Attempting to view or manipulate another student's proctoring timeline or evidence via IDOR.

---

## 4. Threat Analysis & Mitigation Matrix

| Threat Category | Specific Attack Vector | Mitigation Mechanism | Verification Method |
| :--- | :--- | :--- | :--- |
| **DOM Event Tampering** | Overriding `document.addEventListener` to suppress fullscreen/tab events | Server heartbeat frequency checks + AI face tracking + Window focus loss heuristics | Automated probe simulating event suppression |
| **Timestamp Forgery** | Submitting delayed events with backdated `detected_at` values | Server indexes events strictly by immutable `server_received_at` timestamp | Ingestion test with historical timestamp |
| **Frame Replay Attack** | Replaying identical "clean" JPEG frames in a loop | Token bucket + frame sequence validation + multi-signal correlation | Replay probe verifying deduplication |
| **Rate Limit / DoS Flooding** | Submitting 1,000 frame uploads/min to exhaust worker CPU | Redis token bucket rate limiter (Target 0.5 FPS, sustained $\le 30$ frames/min, burst 5) | Flooding test verifying HTTP 429 rejection |
| **Evidence IDOR & Access** | Student requesting `/api/v1/admin/proctoring/evidence/<id>/` | Strict Django permission checks: Student role $\rightarrow$ HTTP 403 Forbidden | RBAC integration test |
| **Evidence Path Traversal** | Requesting `../../etc/passwd` or arbitrary filenames | UUID lookup against database entity; no user-supplied filenames used on disk | Path traversal probe verifying HTTP 404 |
| **Media File Modification** | Tampering with stored `.jpg` keyframes on disk | SHA-256 hash verified upon access against `ProctoringEvidence.sha256_hash` | Hash mismatch test triggering audit alert |
| **False Accusation Risk** | Single noisy frame misclassifies background object as phone | Confidence threshold ($\ge 0.65$) + multi-frame persistence ($\ge 2$ frames over 4s) | Synthetic noisy frame test |
| **Worker DoS via Bad Data** | Uploading malformed/corrupt JPEG images | Secure image decoding in worker with error traps; rejected frames logged as errors | Corrupted byte stream upload test |

---

## 5. Failure Security & Zero Student-Penalization

If an AI worker or webcam stream becomes unavailable:
* The assessment engine **does NOT corrupt or abort the active attempt**.
* The proctoring session transitions to `status = DEGRADED`.
* Score, timer, answers, and submission integrity remain 100% authoritative and protected.
* Disciplinary penalties are never automatically assigned due to technical or infrastructure failures.
