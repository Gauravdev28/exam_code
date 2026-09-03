# CODEGUARD — Phase 10 Implementation Readiness Matrix

**Document Version:** 1.0.0  
**Phase:** 10 — Real-Time Human Proctoring, Live Interventions & Invigilation Engine  
**Status:** IMPLEMENTATION READINESS AUDIT COMPLETE  
**Readiness Verdict:** READY FOR EXPLICIT AUTHORIZATION 🔒  

---

## 1. Dependency Compatibility Matrix

| Dependency | Actual Existing Interface | Phase 10 Compatibility Analysis | Frozen Code Changes Required | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Phase 5 Attempt Lifecycle** | `TestAttempt` model in `apps.assessments.models` (Lines 328–401), `clean()` state validation, `AttemptStatus.CANCELLED`. | Fully compatible. `clean()` allows transition from `IN_PROGRESS` $\to$ `CANCELLED`. Row locks via `select_for_update()` fully supported. | **NONE** | **PASS** |
| **Phase 5 Timer Engine** | `AttemptTimerService` in `apps.assessments.services` (Lines 57–100): `compute_expiry()`, `get_remaining_seconds()`, `is_expired()`. | Fully compatible. `effective_remaining_seconds` respects `Assessment.end_datetime` hard ceiling. Pause intervals tracked without altering Phase 5 schema. | **NONE** | **PASS** |
| **Phase 5 Cancellation** | `AttemptStatus.CANCELLED` in `AttemptStatus.choices` (Line 28), handled as terminal in `submit_attempt()` (Line 880). | Fully compatible. Phase 10 commands transition to `CANCELLED` under `TestAttempt` row lock. | **NONE** | **PASS** |
| **Phase 7 AI Keyframes** | `StudentProctoringFrameUploadView` in `apps.proctoring.views` (Line 159), `process_proctoring_frame_task` in `tasks.py`. | Fully compatible. Phase 7 captures frames and handles CV inference/evidence; Phase 10 consumes transient handoff via Channels group `proctor_assessment_{id}` with zero Phase 10 persistence. | **NONE** | **PASS** |
| **Phase 8 Result Finalization** | `ResultFinalizationService.finalize_attempt()` in `apps.results.services` (Lines 110–400). | Fully compatible. Line 119 explicitly accepts `AttemptStatus.CANCELLED`. Phase 8 calculates existing earned points and records `completion_status='CANCELLED'`. `HistoricalResultSummary` requires zero schema changes. | **NONE** | **PASS** |
| **Phase 8 Historical Ledger** | `HistoricalResultSummary` model in `apps.results.models` (Lines 80–135). | Fully compatible. Lineage (proctor ID, reason) lives in `ProctorIntervention`. `HistoricalResultSummary` remains 100% frozen. | **NONE** | **PASS** |
| **Phase 9 Retention Engine** | `AuthoritativeScrubbingService` in `apps.retention.services.scrubbing` (Lines 80–180), `RetentionRecord`, `LegalHold`. | Fully compatible. Phase 9 owns retention lifecycle, deadlines, and legal holds. Phase 10 records are scrubbed pursuant to Phase 9 policies. | **NONE** | **PASS** |
| **Phase 9 DSAR Engine** | `DsarExportService` in `apps.retention.services.dsar` (Lines 80–280), allowlist filtering. | Fully compatible. Candidate DSAR export includes candidate-facing warnings and chat, while internal proctor notes and staff identities are strictly excluded. | **NONE** | **PASS** |
| **Django Channels** | `backend/codeguard/routing.py`, `backend/codeguard/asgi.py`, `AsyncJsonWebsocketConsumer`. | Fully compatible. Phase 10 registers `ws/proctor/assessments/<id>/` cleanly alongside existing `ws/attempts/<id>/`. | **NONE** | **PASS** |
| **Redis Infrastructure** | Redis 7 Channel Layer (`redis://127.0.0.1:6379/0`), token buckets in `apps.proctoring.views` (Line 170). | Fully compatible. Fallback to 5-second REST polling if Redis is unavailable. | **NONE** | **PASS** |

---

## 2. Interface Audit Summary

### Phase 5 Compatibility Verdict:
- **Timer Compatibility:** `COMPATIBLE WITHOUT PHASE 5 CHANGES`.
- **Attempt Cancellation:** Existing `TestAttempt` model and `AttemptStatus.CANCELLED` support proctor-commanded cancellation directly under row locks.
- **Assessment End Boundary:** Enforced mathematically:
  $$\text{effective\_remaining\_seconds} = \max\Big(0, \min\big(\text{duration\_remaining},\ \text{assessment.end\_datetime} - \text{now}\big)\Big)$$

### Phase 8 Compatibility Verdict:
- **Result Finalization:** `finalize_attempt()` in `apps/results/services.py` already permits terminal status `AttemptStatus.CANCELLED` (Line 119).
- **Scoring Behavior:** Evaluates submitted answers pursuant to existing Phase 8 rules without inventing an artificial zero-score mechanism.
- **`HistoricalResultSummary` Freeze:** Confirmed **zero schema changes** and **zero field additions** required.

### Phase 7 Keyframe Handoff Verdict:
- **Camera Capture:** Owned exclusively by Phase 7 (`apps.proctoring`). Phase 10 has zero camera ingestion code.
- **Keyframe Transport:** Delivered via transient Channel Layer events to `proctor_assessment_{id}`.
- **Persistence:** Display keyframes held in transient browser memory; evidence persistence owned strictly by Phase 7.

### Phase 9 Retention Ownership Verdict:
- Phase 10 owns domain entities (`ProctorAssignment`, `ProctorIntervention`, `ProctorDutySession`, `ProctorChatMessage`).
- Phase 9 owns the retention lifecycle, deadlines, legal hold freezing, and physical purge. Phase 10 does not build an independent retention engine.
