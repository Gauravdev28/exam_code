# CODEGUARD — Phase 10 Final Architecture Correction & Micro-Hardening Report

**Document Version:** 1.0.0  
**Phase:** 10 — Real-Time Human Proctoring, Live Interventions & Invigilation Engine  
**Status:** PHASE 10 — READY FOR ARCHITECTURE REVIEW 🔒  
**Implementation Status:** NOT STARTED (Architecture Specification Only)  

---

## 1. Issues Found & Addressed

1. **Phase 7 $\to$ Phase 10 Keyframe Handoff Boundary**:
   - *Issue*: Keyframe transport was vaguely described without establishing an internal handoff boundary or clarifying that Phase 10 does not capture raw camera input.
   - *Fix*: Created ADR 10-7 explicitly distinguishing Phase 7 camera capture/evidence from Phase 10 authorized consumption/display. Phase 10 has zero camera capture and zero persistence.
2. **Pause vs Assessment End-Time Semantics**:
   - *Issue*: Pauses could theoretically extend an attempt past `Assessment.end_datetime`, violating Phase 5's hard expiry boundary.
   - *Fix*: Bounded remaining time strictly: $\text{effective\_remaining\_seconds} = \min(\text{duration\_remaining},\ \text{assessment.end\_datetime} - \text{now})$. Added the **Assessment End Boundary Invariant**.
3. **Phase 9 Retention Ownership vs Phase 10 Domain Data**:
   - *Issue*: Retention ownership was blurred between Phase 10 and Phase 9.
   - *Fix*: Explicitly separated responsibilities: Phase 10 owns domain entities (`ProctorAssignment`, `ProctorIntervention`, `ProctorDutySession`, `ProctorChatMessage`), while Phase 9 owns their retention lifecycle, purge eligibility, legal hold freezing, and tombstoning.
4. **`ProctorIntervention` Immutability & Lifecycle Mutation**:
   - *Issue*: Storing `pause_started_at` and updating it later with `pause_ended_at` broke audit record immutability.
   - *Fix*: Transitioned to an append-only event model (`PAUSE_STARTED` and `PAUSE_ENDED` as separate immutable events). Added the **Append-Only Intervention Invariant**.
5. **Unsupported Bandwidth Claims**:
   - *Issue*: Used unverified claims like "100x lighter than continuous WebRTC".
   - *Fix*: Replaced with a documented engineering target: ~250–450 Kbps aggregate for a 25-student mosaic at 0.2 FPS / 10 KB per frame.

---

## 2. Updated Authority Map

```text
Phase 7
  ↓
AI telemetry / risk signals
  ↓
Advisory triage only

Human Proctor
  ↓
Binding intervention decision

Phase 10 (apps.invigilation)
  ↓
Intervention command + immutable audit lineage

Phase 5 (apps.assessments)
  ↓
Authoritative attempt state + timer

Phase 8 (apps.results)
  ↓
Authoritative result finalization + scoring

Phase 9 (apps.retention)
  ↓
Retention + purge + legal hold + DSAR lifecycle
```

---

## 3. ADR 10-7 — Phase 7 → Phase 10 Keyframe Handoff

```text
Student Browser
      │
      ▼
Phase 7 Camera Capture (apps.proctoring client telemetry)
      │
      ▼
Phase 7 Keyframe Ingest (apps.proctoring.views / consumers)
      │
      ▼
Authenticated Transient Keyframe Event
      │
      ▼
Internal Phase 7 → Phase 10 Handoff (Channel Group: proctor_assessment_{id})
      │
      ▼
Authorized Phase 10 Proctor Stream (apps.invigilation.consumers.InvigilationConsumer)
      │
      ▼
Proctor Console (Transient Browser Memory Display)
```

- **Capture Authority**: Phase 7 exclusively captures client webcam frames. Phase 10 has zero camera code.
- **Transport Authority**: Phase 10 subscribes to internal Channels group `proctor_assessment_{id}`.
- **Throttling**: 1 FPS for high-risk (`CRITICAL`, `HIGH`); 0.2 FPS (1 frame per 5s) for normal (`NORMAL`, `LOW`).
- **Zero Persistence in Phase 10**: Display keyframes exist solely in transient memory; evidence persistence belongs strictly to Phase 7.
- **Target Aggregate Bandwidth**: $\approx 250\text{--}450\text{ Kbps}$ for a 25-student mosaic (performance target to be validated in testing).

---

## 4. Final 12 Architectural Invariants

1. **Human Authority Invariant**: Automated AI advises; only human proctors can pause or terminate an attempt.
2. **Timer Authority Invariant**: Phase 5 remains authoritative. Server calculates elapsed wall-clock minus authorized pause intervals.
3. **Assessment End Boundary Invariant**: Authorized pauses may reduce effective elapsed attempt time but **MUST NOT** extend an attempt beyond the authoritative `Assessment.end_datetime` boundary.
4. **Intervention Lineage Invariant**: Every human intervention has immutable proctor, attempt, reason, type, and timestamp lineage in `ProctorIntervention`. Phase 10 MUST NOT modify `HistoricalResultSummary`.
5. **Append-Only Intervention Invariant**: Once a `ProctorIntervention` event is committed, its audit fields are immutable. Lifecycle transitions are represented by additional immutable events (`PAUSE_STARTED`, `PAUSE_ENDED`).
6. **Termination Authority Invariant**: Phase 10 requests termination via Phase 5 (`CANCELLED`); Phase 8 owns result finalization. Phase 10 does not calculate grades or bypass Phase 8.
7. **Keyframe Transport Invariant**: Phase 10 consumes periodic authenticated keyframes from Phase 7 and does not create a competing continuous video pipeline.
8. **Command Authority Invariant**: REST domain transactions are authoritative for interventions; WebSockets provide real-time delivery. If WebSockets fail, REST commands still execute safely.
9. **Single-Pause Invariant**: Only one active pause may exist per attempt, and cumulative authorized pause cannot exceed the configured operational cap (default 15 minutes).
10. **Cross-Student Isolation Invariant**: A proctor cannot access, view keyframes for, or intervene in an unassigned student's attempt.
11. **DSAR Boundary Invariant**: Phase 10 consumes Phase 9 DSAR policies, strictly including student-owned notifications and excluding internal proctor investigation notes.
12. **Retention Ownership Invariant**: Phase 10 owns domain records, while Phase 9 owns their retention lifecycle, purge eligibility, and legal hold freezing.

---

## 5. Architectural Decision Records (ADRs) Summary

- **ADR 10-1**: Decoupled `apps.invigilation` app to preserve Phase 7 freeze.
- **ADR 10-2**: Periodic authenticated keyframes (1 FPS / 0.2 FPS) instead of continuous WebRTC SFU.
- **ADR 10-3**: Phase 5 timer authority preserved with `Assessment.end_datetime` hard boundary.
- **ADR 10-4**: Human authority over advisory AI signals.
- **ADR 10-5**: REST/domain command authority with WebSocket push delivery.
- **ADR 10-6**: Termination lineage recorded in `ProctorIntervention`, leaving `HistoricalResultSummary` untouched.
- **ADR 10-7**: Phase 7 $\to$ Phase 10 keyframe handoff via transient Channel layer publish without Phase 10 persistence.

---

## 6. Readiness Status

```text
PHASE 10 — READY FOR ARCHITECTURE REVIEW 🔒
```
*(Implementation is NOT authorized. Awaiting explicit approval from Software Architect / Product Owner.)*
