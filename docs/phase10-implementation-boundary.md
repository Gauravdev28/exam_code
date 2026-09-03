# CODEGUARD — Phase 10 Implementation Boundary Specification

**Document Version:** 1.0.0  
**Phase:** 10 — Real-Time Human Proctoring, Live Interventions & Invigilation Engine  
**Status:** IMPLEMENTATION BOUNDARY CONTRACT 🔒  

---

## 1. What Phase 10 May Own

The `apps.invigilation` domain owns the following discrete responsibilities, models, and interfaces:

1. **Domain App**:
   - `backend/apps/invigilation/` (models, services, serializers, REST views, Channels consumers).
2. **Domain Data Models**:
   - `ProctorAssignment`: Maps proctor users to assessment cohorts and candidate rosters.
   - `ProctorIntervention`: Immutable, append-only audit ledger of proctor interventions (`WARNING_ISSUED`, `WARNING_ACKNOWLEDGED`, `PAUSE_STARTED`, `PAUSE_ENDED`, `ROOM_SCAN_REQUESTED`, `ROOM_SCAN_COMPLETED`, `TERMINATION_REQUESTED`).
   - `ProctorDutySession`: Heartbeat and telemetry tracking proctor active monitoring.
   - `ProctorChatMessage`: Ephemeral student-facing bilateral messages.
3. **Domain Services**:
   - `ProctorRosterService`: Manages cohort assignments and enforces object-level IDOR access controls.
   - `LiveInterventionService`: Executes transactional interventions under canonical row locks.
   - `ProctorTriageQueueService`: Aggregates active attempts sorted dynamically by Phase 7 AI risk bands.
   - `InvigilationAuditService`: Records immutable intervention entries and delivers proctor shift audit reports.
4. **Transport & User Interfaces**:
   - `InvigilationConsumer` on `ws/proctor/assessments/<id>/`: Live keyframe mosaic feed.
   - Ephemeral bilateral chat WebSocket on `ws/proctor/attempts/<id>/chat/`.
   - `ProctorLiveConsolePage.tsx`: Live proctor mosaic grid, triage banner, and intervention bar.
   - Candidate intervention modals, frosted pause overlay, and room scan guide in `StudentTestRoomPage.tsx`.

---

## 2. What Phase 10 May Consume

Phase 10 is an authorized consumer of authoritative outputs produced by frozen upstream phases:

1. **Phase 1 (Authentication & RBAC)**:
   - Consumes `Role.PROCTOR` and `Role.ADMIN` claims.
   - Enforces user session authentication via `IsAuthenticated` and `IsActiveUser`.
2. **Phase 5 (Assessment Engine)**:
   - Consumes `TestAttempt` status (`IN_PROGRESS`, `SUBMITTED`, `EXPIRED`, `CANCELLED`).
   - Consumes `AttemptTimerService` calculations (`get_remaining_seconds()`).
   - Dispatches attempt state transitions to `AttemptStatus.CANCELLED` via Phase 5 domain services.
3. **Phase 7 (AI Proctoring & Vision Telemetry)**:
   - Consumes advisory `risk_score` and `RiskBand` from `ProctoringSession` to order the proctor triage queue.
   - Consumes transient periodic keyframes from internal Channels group `proctor_assessment_{id}`.
   - Consumes flagged `ProctoringEvidence` references for violation audits.
4. **Phase 8 (Results & Analytics)**:
   - Consumes finalized `AssessmentResult` status to verify whether an attempt is already terminal.
5. **Phase 9 (Data Retention & Privacy)**:
   - Governed by Phase 9 `RetentionPolicy` for data expiration (operational audit window: 90 days; chat: 30 days).
   - Protected from purge when an active `LegalHold` is present.
   - Consumed by Phase 9 DSAR export engine for candidate-visible notifications.

---

## 3. What Phase 10 Must Never Own

To preserve the absolute freeze of Phases 1–9 and avoid architectural corruption, Phase 10 **MUST NEVER OWN OR MODIFY**:

1. **Assessment Timer Authority**:
   - Phase 10 must never independently compute, store, or alter the core attempt countdown timer.
   - Phase 5 remains the sole timer authority.
2. **Attempt Lifecycle Authority**:
   - Phase 10 must never create or directly modify `TestAttempt` lifecycle logic outside of authorized Phase 5 service calls.
3. **Code Execution & Grading**:
   - Phase 10 has zero code execution, compiler, or Judge0 sandbox responsibilities (owned by Phase 6).
4. **Scoring & Finalization Authority**:
   - Phase 10 must never calculate grades, alter points earned, or finalize `AssessmentResult` records (owned by Phase 8).
   - Phase 10 must never invent an artificial zero-score rule for cancelled attempts.
5. **Historical Ledger Schema**:
   - Phase 10 must **NEVER modify `HistoricalResultSummary`** schema, fields, or records. Termination lineage lives exclusively in `ProctorIntervention`.
6. **Camera Capture & Evidence Storage**:
   - Phase 10 must never capture raw webcam frames directly from the browser or build a second camera ingestion pipeline (owned by Phase 7).
   - Phase 10 must never build a continuous WebRTC SFU/MCU server.
   - Phase 10 must never persist display keyframes to disk.
7. **Retention Engine & Cryptographic Purge**:
   - Phase 10 must never build an independent retention, purge, or tombstone engine (owned by Phase 9).
8. **Autonomous Disqualification**:
   - AI models must never autonomously terminate or penalize student attempts. Only authenticated human proctors or admins can execute binding interventions.
