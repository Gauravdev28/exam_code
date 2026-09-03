# CODEGUARD — System Architecture Specification

**Document Version:** 1.0.0  
**Status:** Comprehensive Baseline Architecture  
**Platform:** CODEGUARD — Online Coding & Technical Assessment Platform  

---

## 1. System Overview

CODEGUARD is an enterprise-grade technical examination and coding assessment platform engineered for universities, academic institutions, and technical recruitment. It couples sandboxed multi-language code execution, automated real-time AI invigilation, mathematical scoring and certificate generation, and strict GDPR/FERPA-compliant automated data retention with legal hold management.

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                       CLIENT TIER (React + TypeScript)                      │
│   Candidate Test Room  │  Admin Question Bank  │  Proctor Live Console (P10)│
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ HTTPS / WSS
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          API GATEWAY & REVERSE PROXY                        │
│                                (Nginx / ASGI)                               │
└──────────────────┬───────────────────────────────────────────┬──────────────┘
                   │ HTTP / REST                               │ WebSocket
                   ▼                                           ▼
┌──────────────────────────────────────┐    ┌─────────────────────────────────┐
│           DJANGO REST CORE           │    │         DJANGO CHANNELS         │
│          (Gunicorn / WSGI)           │    │             (Daphne)            │
└──────────────────┬───────────────────┘    └─────────────────┬───────────────┘
                   │                                          │
                   ├───────────────────┬──────────────────────┘
                   ▼                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              DOMAIN SERVICES                                │
│   Auth & RBAC (P1-3)  │  Question Engine (P4)  │  Attempt & Timers (P5)     │
│   Judge0 Client (P6)  │  AI Proctoring (P7)    │  Result Ledger (P8)        │
│   Retention Engine(P9)│  Human Invigilation(P10 - Planned)                 │
└──────────┬───────────────────┬───────────────────┬──────────────────┬───────┘
           │                   │                   │                  │
           ▼                   ▼                   ▼                  ▼
┌────────────────────┐ ┌───────────────┐ ┌───────────────────┐ ┌──────────────┐
│   MySQL 8 ENGINE   │ │ REDIS CLUSTER │ │ CELERY ASYNC POOL │ │   JUDGE0 CE  │
│  Authoritative Rel │ │ Cache, Layer  │ │  Async Grading,   │ │   Sandboxed  │
│   Data & Ledger    │ │  & Brokers    │ │  Purge, Reports   │ │  Code Exec   │
└────────────────────┘ └───────────────┘ └───────────────────┘ └──────────────┘
```

---

## 2. Authoritative Phase Boundaries

The CODEGUARD architecture is organized into frozen, authoritative domain layers. No phase may usurp the responsibility of another:

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                           AUTHORITATIVE BOUNDARIES                          │
├───────────────┬─────────────────────────────────────────────────────────────┤
│ Phase 1–3     │ Authentication, Authorization, RBAC, User Profiles & Cohorts│
│ Phase 4       │ Question Bank, Immutable Question Versioning & Test Cases   │
│ Phase 5 🔒    │ Assessment Engine, Snapshot Locking, Attempt State & Timers │
│ Phase 6 🔒    │ Code Execution Authority, Judge0 Sandbox & Automated Grading│
│ Phase 7 🔒    │ Camera Capture, Real-Time AI Telemetry & Risk Scoring       │
│ Phase 8 🔒    │ Authoritative Result Calculation, Grade Ledger & PDF Reports│
│ Phase 9 🔒    │ Data Retention Lifecycle, DSAR Bundles, Purges & Legal Holds│
│ Phase 10 🎯   │ Human-in-the-Loop Invigilation & Interventions (Arch Review)│
└───────────────┴─────────────────────────────────────────────────────────────┘
```

### Detailed Boundary Contracts:
1. **Phase 5 (Attempt & Timer Authority)**:
   - `TestAttempt` is the single source of truth for attempt state (`NOT_STARTED`, `IN_PROGRESS`, `SUBMITTED`, `EXPIRED`, `CANCELLED`).
   - `AttemptTimerService` is the sole authority for countdown calculation.
   - Hard boundary: No attempt may exceed `Assessment.end_datetime`.
2. **Phase 6 (Code Execution Authority)**:
   - Code submissions run exclusively in isolated Judge0 sandboxes.
   - Evaluator grades code against hidden and visible test cases.
3. **Phase 7 (AI Proctoring Authority)**:
   - Captures webcam keyframes via client telemetry.
   - Executes computer vision inference (face presence, multi-face, gaze direction, mobile devices).
   - Computes advisory `risk_score` (0–100) and assigns `RiskBand`.
   - AI is advisory: it never terminates or penalizes attempts autonomously.
4. **Phase 8 (Result & Scoring Authority)**:
   - Result calculation and `HistoricalResultSummary` minting occur strictly post-finalization.
   - Passing criteria, percentile rankings, and certificates are authoritative and immutable.
5. **Phase 9 (Retention & Privacy Authority)**:
   - Determines policy-based retention deadlines (`detailed_data_expires_at`).
   - Executes authoritative two-stage purges (DB scrub $\to$ async file unlinking $\to$ HMAC-SHA256 tombstones).
   - Manages `LegalHold` to freeze records against destruction.
   - Assembles encrypted AES-256-GCM DSAR export archives.
6. **Phase 10 (Future Human Invigilation)**:
   - Supervisory layer consuming Phase 7 keyframes and Phase 5 attempt states.
   - Issues binding human interventions (`WARNING`, `PAUSE`, `RESUME`, `TERMINATE`) recorded in append-only audit records.

---

## 3. Technology Stack

### Backend Infrastructure
- **Framework**: Python 3.14 + Django 5.1.15 + Django REST Framework 3.15.2.
- **Asynchronous & Real-Time**: Django Channels 4.1.0 + Daphne 4.1.0 + Redis Channel Layer.
- **Task Orchestration**: Celery 5.4.0 + Redis 7 broker.
- **Relational Storage**: MySQL 8.0 with InnoDB row-level locking.
- **Execution Sandbox**: Judge0 Community Edition (Dockerized isolate sandbox).
- **Vision & AI Telemetry**: OpenCV (headless), MediaPipe, PyTorch / YOLO.
- **Report & Export Engines**: ReportLab (cryptographically stamped PDFs), pandas, openpyxl.

### Frontend Client
- **Architecture**: React 18 + TypeScript + Vite 5 + Tailwind CSS.
- **Code Editing**: Monaco Editor (`@monaco-editor/react`).
- **Telemetry & Visuals**: Recharts (retention & scoring metrics), Lucide React.
- **Networking**: Axios + WebSocket multiplexing.

### Infrastructure & Deployment
- Docker & Docker Compose (development & production orchestration).
- Nginx reverse proxy (SSL termination, rate limiting, static asset offloading).
