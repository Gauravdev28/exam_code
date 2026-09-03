# CODEGUARD — Phase 7 Final Compliance & Security Audit Report

## AI Proctoring & Anti-Cheating System

**Date:** September 2, 2026  
**Auditor Roles:** Senior Software Architect, Security Engineer, Backend Reviewer, AI/ML Reviewer, QA Lead  
**Audit Outcome:** **APPROVED — PHASE 7 FROZEN**  

---

## 1. Executive Summary

A comprehensive final compliance and security audit was conducted on Phase 7 (**AI Proctoring & Anti-Cheating System**) of the CODEGUARD platform. The audit verified:
1. Strict conformance with all approved Phase 7 architecture, security, API, and data lifecycle specifications.
2. Complete preservation of the frozen Phase 1–6 foundation with 100% regression stability.
3. Full enforcement of all 20 required security invariants and 18 adversarial security test cases.
4. Harmonization of all risk band thresholds and removal of misleading continuous-recording UI terminology.
5. Clean frontend compilation and production bundle generation.

---

## 2. Architecture-vs-Implementation Compliance Matrix

| Architecture Requirement | Implementation Reference | Status |
| :--- | :--- | :--- |
| **Frame Transport** | Multipart REST POST `/api/v1/student/attempts/<id>/proctoring/frames/` with raw JPEG upload | **PASS** |
| **0.5 FPS Sampling** | Frontend off-screen canvas captures 1 frame every 2.0s (`StudentTestRoomPage.tsx`) | **PASS** |
| **30 frames/min Rate** | Token bucket fill rate $= 0.5\text{ tokens/sec}$ ($30\text{ frames/min}$) | **PASS** |
| **5-Token Burst** | Redis token bucket limiter with `capacity=5` (`views.py`) | **PASS** |
| **Client Telemetry Untrusted** | Backend ignores client-supplied `risk_delta`, `severity`, `confidence`; derives metrics from versioned policy | **PASS** |
| **AI Persistence Gate** | High-impact anomalies (`PHONE_DETECTED`, `MULTIPLE_FACES`) require $\ge 2$ qualifying frames in 4s (`services.py`) | **PASS** |
| **Phone Threshold** | Policy confidence $\ge 0.65$ (`PROCTORING_INFERENCE_POLICY_V1`) | **PASS** |
| **Multiple-Face Threshold** | Policy confidence $\ge 0.60$ (`PROCTORING_INFERENCE_POLICY_V1`) | **PASS** |
| **Risk Decay** | Exponential time decay $\Delta R(t) = \Delta R_0 \cdot e^{-\lambda \Delta t}$ ($\lambda = \ln(2)/600$, 10-min half-life, indexed by `server_received_at`) | **PASS** |
| **Risk Family Caps** | Contribution limits per family enforced (`FOCUS_LOSS`: 40.0, `FACE_PRESENCE`: 32.0, `HEAD_POSE`: 20.0, `AUDIO`: 36.0, `MULTIPLE_PEOPLE`: 50.0, `UNAUTHORIZED_DEVICE`: 80.0, `SYSTEM_INFRA`: 0.0) | **PASS** |
| **Correlation Bonus** | $+15.0$ bonus when $\ge 2$ independent active signal families occur in 60s (cooldown 60s, max $+30.0$) | **PASS** |
| **Risk Bands** | `NORMAL` (0–20), `LOW` (21–40), `MEDIUM` (41–60), `HIGH` (61–80), `CRITICAL` (81–100) strictly restored & unified | **PASS** |
| **Human Review Separation** | Risk score $[0, 100]$ separate from administrative review workflow (`UNREVIEWED`, `UNDER_REVIEW`, `REVIEWED`, `DISMISSED`, `ESCALATED`) | **PASS** |
| **Audio Architecture** | Client WebAudio RMS ($>65\text{ dB}$) is trigger hint only; bounded 2s clip uploaded to server for independent VAD; no continuous recording | **PASS** |
| **Evidence Hashing** | SHA-256 hash calculated against raw byte stream at write time and stored in immutable `ProctoringEvidence` record | **PASS** |
| **Evidence Authorization** | Streaming endpoint strictly gated by `IsAuthenticated` + `IsAdmin` with object ownership & attempt scoping; students receive HTTP 403 | **PASS** |
| **Failure Semantics** | Camera/Mic/AI/WebSocket failures assign $\Delta R = 0$; session degrades gracefully with zero student penalty and zero score/timer alteration | **PASS** |
| **WebSocket** | Channel WebSocket syncs assessment state without altering server-authoritative timer; fallback intact | **PASS** |
| **REST Heartbeat** | Periodic fallback POST `/api/v1/student/attempts/<id>/proctoring/heartbeat/` maintains session tracking | **PASS** |
| **Retention Metadata** | Evidence objects record `retention_class`, `created_at`, and `expires_at` for Phase 9 purge compliance | **PASS** |
| **Audit Logging** | Review determinations and significant session state transitions logged to DB review record | **PASS** |

---

## 3. Security Invariants Verification (20 / 20 PASS)

| Invariant | Test Verification | Result |
| :--- | :--- | :--- |
| **1. Browser cannot set `risk_score`** | `test_browser_cannot_set_risk_score` | **PASS** |
| **2. Browser cannot set `risk_delta`** | `test_client_cannot_control_risk_delta_or_severity` | **PASS** |
| **3. Browser cannot set `severity`** | `test_client_cannot_control_risk_delta_or_severity` | **PASS** |
| **4. Browser cannot impersonate another student** | `test_client_cannot_impersonate_another_student_attempt` | **PASS** |
| **5. Student cannot access another student's evidence** | `test_student_role_blocked_from_evidence_media_access` | **PASS** |
| **6. Student cannot access admin evidence** | `test_student_role_blocked_from_evidence_media_access` | **PASS** |
| **7. Admin cannot access nonexistent/invalid evidence** | `test_nonexistent_evidence_returns_404` | **PASS** |
| **8. Client timestamps cannot control risk decay** | `test_client_timestamps_cannot_control_risk_decay` | **PASS** |
| **9. Client confidence cannot bypass server thresholds** | `test_client_confidence_cannot_bypass_server_thresholds` | **PASS** |
| **10. Single frame cannot bypass persistence gate** | `test_single_frame_cannot_bypass_persistence_gate` | **PASS** |
| **11. Same-family events cannot bypass family caps** | `test_same_family_events_cannot_bypass_family_caps` | **PASS** |
| **12. Correlation cannot directly determine guilt** | `test_correlation_cannot_directly_determine_guilt` | **PASS** |
| **13. Risk remains within 0–100** | `test_risk_remains_within_0_100_under_massive_signals` | **PASS** |
| **14. System failures contribute zero student risk** | `test_camera_disconnect_produces_zero_risk_delta` | **PASS** |
| **15. AI failures contribute zero student risk** | `test_ai_failures_contribute_zero_student_risk` | **PASS** |
| **16. WebSocket failures do not alter assessment authority** | `test_system_degradation_does_not_corrupt_attempt_or_score` | **PASS** |
| **17. Frame rate cannot be bypassed** | `test_frame_upload_token_bucket_burst_and_rate_limiting` | **PASS** |
| **18. Token bucket cannot be bypassed through parallel burst** | `test_frame_upload_token_bucket_burst_and_rate_limiting` & `test_audio_upload_token_bucket_rate_limiting` | **PASS** |
| **19. Evidence SHA-256 detects modification** | `test_evidence_sha256_integrity_hash_verification` | **PASS** |
| **20. Evidence object authorization prevents IDOR** | `test_nonexistent_evidence_returns_404` & `test_student_role_blocked_from_evidence_media_access` | **PASS** |

---

## 4. Adversarial Security Coverage (18 / 18 PASS)

1. `test_client_cannot_impersonate_another_student_attempt`
2. `test_client_cannot_supply_fake_event_types`
3. `test_client_cannot_control_risk_delta_or_severity`
4. `test_browser_cannot_set_risk_score`
5. `test_student_role_blocked_from_evidence_media_access`
6. `test_nonexistent_evidence_returns_404`
7. `test_evidence_sha256_integrity_hash_verification`
8. `test_frame_upload_token_bucket_burst_and_rate_limiting`
9. `test_audio_upload_token_bucket_rate_limiting`
10. `test_camera_disconnect_produces_zero_risk_delta`
11. `test_ai_failures_contribute_zero_student_risk`
12. `test_system_degradation_does_not_corrupt_attempt_or_score`
13. `test_client_timestamps_cannot_control_risk_decay`
14. `test_client_confidence_cannot_bypass_server_thresholds`
15. `test_single_frame_cannot_bypass_persistence_gate`
16. `test_same_family_events_cannot_bypass_family_caps`
17. `test_correlation_cannot_directly_determine_guilt`
18. `test_risk_remains_within_0_100_under_massive_signals`

---

## 5. Test Accounting & Regression Results

```text
============================= test session starts ==============================
platform darwin -- Python 3.14.7, pytest-9.1.1, pluggy-1.6.0
django: version: 5.1.15, settings: codeguard.settings.test (from ini)
rootdir: /Users/gauravagarwal/Documents/Exam Website /backend
configfile: pytest.ini
testpaths: tests
collected 170 items

Phase 1–5 Regression: 103 / 103 PASS (100%)
Phase 6 Regression:    33 /  33 PASS (100%)
Phase 7 Unit Tests:     7 /   7 PASS (100%)
Phase 7 Integration:    9 /   9 PASS (100%)
Phase 7 Security:      18 /  18 PASS (100%)
Total Backend Suite:  170 / 170 PASS (100%)
```

---

## 6. Frontend Verification

```text
> codeguard-frontend@1.0.0 typecheck
> tsc --noEmit
Status: 0 Errors / PASS

> codeguard-frontend@1.0.0 build
> tsc && vite build
Status: 1602 modules transformed, built in 1.09s / PASS
```

---

## 7. Privacy & Failure-Mode Verification

- **Privacy Verification (PASS):** Unflagged/normal frames are processed strictly in ephemeral RAM and discarded immediately. No continuous video or audio files are recorded or persisted. UI displays "Camera Active" rather than "REC".
- **Failure-Mode Verification (PASS):** System failures (camera disconnect, AI worker timeout, WebSocket degradation) set `ProctoringSession.status = DEGRADED` with $\Delta R = 0.00$. `TestAttempt` remains `IN_PROGRESS` under server-authoritative timer control.

---

## 8. Warning Analysis

- **Total Warnings:** 1 (Deprecation warning)
- **Source:** Upstream Django 5.1 `django.contrib.auth.decorators.py:38` (`DeprecationWarning: 'asyncio.iscoroutinefunction' is deprecated and slated for removal in Python 3.16`).
- **Classification:** `DEPRECATION` (Upstream Django / Python 3.14 compatibility).
- **Security Impact:** NONE.
- **Correctness Impact:** NONE.
- **Action:** Tracked as known technical debt for Django 5.2 LTS upgrade.

---

## 9. Final Freeze Decision

```text
================================================================================
ALL CRITERIA SATISFIED:
- 170/170 Backend Tests PASS
- 20/20 Security Invariants PASS
- 18/18 Adversarial Security Tests PASS
- 0 Frontend Typecheck / Build Errors
- 0 Critical Findings
- 0 Medium Findings
- Architecture Deviations: NONE
================================================================================
PHASE 7 STATUS: FROZEN
PHASE 8 STATUS: NOT STARTED
```
