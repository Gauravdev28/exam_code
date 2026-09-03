# CODEGUARD — Phase 7 Freeze Record

## Status

**PHASE 7 — FROZEN**

---

## Verification

- **Architecture compliance:** 21/21 (100%)
- **Security invariants:** 20/20 (100%)
- **Adversarial security tests:** 18/18 (100%)
- **Phase 1–5 regression:** 103/103 (100%)
- **Phase 6 regression:** 33/33 (100%)
- **Phase 7 tests:** 34/34 (100%)
- **Complete backend suite:** 170/170 (100%)
- **Frontend typecheck:** PASS (0 Errors)
- **Frontend build:** PASS (1602 modules, 1.09s)
- **Privacy audit:** PASS
- **Failure-mode audit:** PASS
- **Documentation consistency:** PASS

---

## Core Security Guarantees

- **Client telemetry is untrusted:** Server ignores client-supplied `risk_delta`, `severity`, or `confidence`.
- **Client cannot control authoritative risk:** All risk increments are calculated on the backend from versioned policies.
- **Client cannot impersonate another student:** IDOR protected by strict attempt student ownership verification.
- **Risk calculation is server authoritative:** Clock decay $\Delta R(t) = \Delta R_0 \cdot e^{-\lambda \Delta t}$ uses `server_received_at`.
- **AI confidence thresholds are policy controlled:** `PROCTORING_INFERENCE_POLICY_V1` and `PROCTORING_AUDIO_POLICY_V1` govern anomaly qualification.
- **High-impact signals require persistence:** `PHONE_DETECTED` and `MULTIPLE_FACES` require $\ge 2$ qualifying frames in 4 seconds.
- **Risk contribution is bounded:** Signal families are capped (`FOCUS_LOSS`: 40.0, `FACE_PRESENCE`: 32.0, `HEAD_POSE`: 20.0, `AUDIO`: 36.0, `MULTIPLE_PEOPLE`: 50.0, `UNAUTHORIZED_DEVICE`: 80.0, `SYSTEM_INFRA`: 0.0).
- **Risk score is deterministic:** Identical telemetry inputs produce identical risk scores.
- **Risk score is clamped to 0–100:** Hard bounds $[0.00, 100.00]$ enforced with discrete risk bands (`NORMAL` 0–20, `LOW` 21–40, `MEDIUM` 41–60, `HIGH` 61–80, `CRITICAL` 81–100).
- **Risk bands are separated from administrative review:** Risk bands are mathematical indicators; institutional administrators maintain exclusive authority over disciplinary decisions (`UNREVIEWED`, `UNDER_REVIEW`, `REVIEWED`, `DISMISSED`, `ESCALATED`).
- **Correlation cannot determine guilt:** $+15.0$ multi-signal correlation bonus acts purely as risk score contribution; it never triggers automated penalties.
- **System failures contribute zero student risk:** Camera/Mic disconnects, AI worker crashes, or timeouts assign $\Delta R = 0.00$.
- **AI failures contribute zero student risk:** Inference exceptions degrade proctoring session without penalizing student score or timer.
- **Assessment timer remains server authoritative:** Proctoring session state transitions (`DEGRADED`) never alter `TestAttempt.status`, points, answers, or submission timers.
- **Normal webcam frames are transient:** Baseline unflagged frames are decoded in ephemeral RAM and discarded immediately with zero persistent storage.
- **Continuous audio/video recording is not implemented:** Only isolated snapshot frames and bounded 2s audio clips on acoustic trigger hints are processed.
- **Evidence access uses authorization and object scoping:** Streaming endpoints require authenticated session with `IsAdmin` role and attempt scoping; student requests are rejected with HTTP 403.
- **Evidence integrity uses SHA-256:** SHA-256 digest is calculated at write time and stored immutably to detect media tampering.
- **Evidence retention metadata supports future cleanup:** Evidence records include `retention_class`, `created_at`, and `expires_at` for Phase 9 automated lifecycle purge.

---

## Frozen Contracts

Phase 7 contracts are frozen.

Future phases must not silently modify:

- proctoring event semantics
- risk engine behavior
- risk bands (`NORMAL` 0–20, `LOW` 21–40, `MEDIUM` 41–60, `HIGH` 61–80, `CRITICAL` 81–100)
- confidence thresholds (`PHONE_DETECTED >= 0.65`, `MULTIPLE_FACES >= 0.60`)
- persistence rules ($\ge 2$ qualifying frames within 4 seconds)
- correlation behavior ($\ge 2$ distinct active families within 60s $\rightarrow +15.0$, max $+30.0$)
- evidence authorization (Admin-only RBAC)
- failure semantics (Zero student risk $\Delta R = 0.00$, non-penalizing graceful degradation)
- assessment authority boundaries (`TestAttempt` timer and submission pipeline strictly independent)
- API contracts (REST telemetry ingestion, token-bucket frame upload, warning ack, and review patch endpoints)

Any required change requires explicit architecture review.

---

## Known Warnings

### Warning 1: Upstream Django Decorator Asyncio Deprecation
```text
warning: DeprecationWarning: 'asyncio.iscoroutinefunction' is deprecated and slated for removal in Python 3.16; use inspect.iscoroutinefunction() instead
source: django.contrib.auth.decorators.py:38
test/file: tests/test_proctoring_integration.py, tests/test_proctoring_security.py
severity: LOW / INFORMATIONAL
classification: DEPRECATION
security_impact: NONE
correctness_impact: NONE
requires_immediate_remediation: NO
action: Tracked as known technical debt for upstream Django 5.2 / Python 3.16 LTS release cycle.
```

---

## Future Integration Validation

The following remain deployment/integration validation concerns and do not invalidate the Phase 7 application architecture:

- real AI model accuracy evaluation
- production-like MediaPipe/YOLO/VAD validation
- model artifact integrity verification
- AI runtime dependency security review
- production container/runtime isolation validation
- malicious media decoder testing
- production infrastructure hardening

These are future environment/integration validation tasks, not unresolved Phase 7 architecture blockers.

---

## Phase 8

Phase 8 has **NOT STARTED**.
