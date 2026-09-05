# CODEGUARD — Codebase File Reference & Inventory

**Document Version:** 1.0.0  
**Status:** Comprehensive Codebase Inventory  
**Scope:** Complete file-by-file documentation of all source, configuration, and test files  

---

## 1. Root Configuration & Project Files

### `.gitignore`
- **Purpose**: Excludes temporary, build, secret, and virtual environment files from version control.
- **Module / Domain**: Repository Governance.
- **Key Responsibilities**: Ignores `.env`, `__pycache__`, `.venv`, `node_modules`, `dist/`, `media/`, `staticfiles/`, and local test caches.
- **Security Considerations**: Ensures production credentials and local sandbox artifacts are never committed.
- **Related Phase**: Global.

### `.env.example`
- **Purpose**: Template of all environment variables required by backend and frontend services.
- **Module / Domain**: Configuration.
- **Key Responsibilities**: Documents database, Redis, Celery, JWT, Judge0, and retention settings with safe defaults.
- **Security Considerations**: Contains zero real production secrets.
- **Related Phase**: Global.

### `docker-compose.yml` & `docker-compose.prod.yml`
- **Purpose**: Multi-container orchestration configurations for local development and production.
- **Module / Domain**: Infrastructure.
- **Key Responsibilities**: Configures MySQL 8, Redis 7, Celery Worker/Beat, Judge0, and Django backend.
- **Security Considerations**: Isolates containers in private Docker bridges; limits exposed host ports.
- **Related Phase**: Global.

### `README.md`
- **Purpose**: Primary documentation and platform overview.
- **Module / Domain**: Documentation.
- **Key Responsibilities**: Explains platform mission, technology stack, architecture, phase status, and setup instructions.
- **Related Phase**: Global.

---

## 2. Backend Core Configuration (`backend/codeguard/`)

### `backend/codeguard/settings/base.py`
- **Purpose**: Foundation Django configuration shared across all environments.
- **Module / Domain**: Core Architecture.
- **Responsibilities**: Registers `INSTALLED_APPS`, middleware, template engines, password validators, and DRF defaults.
- **Security Considerations**: Enforces custom exception handlers and strict cookie-based JWT authentication.
- **Related Phase**: Phase 1.

### `backend/codeguard/settings/development.py`, `production.py`, `test.py`
- **Purpose**: Environment-specific settings overrides.
- **Module / Domain**: Environment Configuration.
- **Responsibilities**: `test.py` configures in-memory SQLite and mock services; `production.py` enforces SSL, HSTS, and secure cookies.
- **Related Phase**: Phase 1.

### `backend/codeguard/urls.py`
- **Purpose**: Primary URL routing router for backend REST APIs.
- **Module / Domain**: API Routing.
- **Responsibilities**: Routes endpoints for `/api/v1/auth/`, `/api/v1/questions/`, `/api/v1/assessments/`, `/api/v1/evaluator/`, `/api/v1/proctoring/`, `/api/v1/results/`, and `/api/v1/retention/`.
- **Related Phase**: Global.

### `backend/codeguard/asgi.py` & `routing.py`
- **Purpose**: ASGI protocol router for HTTP and WebSocket traffic.
- **Module / Domain**: Real-Time Infrastructure.
- **Responsibilities**: Bridges Django Channels and Daphne; maps `ws/attempts/{id}/` to `TestAttemptConsumer`.
- **Related Phase**: Phase 5.

### `backend/codeguard/celery.py`
- **Purpose**: Celery application factory and periodic beat schedule configuration.
- **Module / Domain**: Asynchronous Orchestration.
- **Responsibilities**: Schedules scheduled purge jobs, stale DSAR recovery, and queue monitoring.
- **Related Phase**: Global.

---

## 3. Django App: Core (`backend/apps/core/`)

### `apps/core/models.py`
- **Purpose**: Abstract base models providing universal identity and timestamp tracking.
- **Responsibilities**: Defines `UUIDModel` (UUIDv4 primary keys) and `TimeStampedModel` (`created_at`, `updated_at`).
- **Related Phase**: Phase 1.

### `apps/core/exceptions.py` & `responses.py`
- **Purpose**: Standardized API error and success payload formatting.
- **Responsibilities**: Enforces consistent JSON error structure `{ status, message, errors }`.
- **Related Phase**: Phase 1.

### `apps/core/pagination.py`
- **Purpose**: Standard pagination class for list views.
- **Responsibilities**: Limits page sizes, provides cursor/page-number metadata.
- **Related Phase**: Phase 1.

---

## 4. Django App: Accounts & Students (`backend/apps/accounts/`)

### `apps/accounts/models.py`
- **Purpose**: User identity, role management, and student profile models.
- **Responsibilities**: Defines custom `User` model (`Role.ADMIN`, `Role.INSTRUCTOR`, `Role.PROCTOR`, `Role.STUDENT`) and `StudentProfile` (`euid`, `roll_number`, `branch`, `batch`).
- **Security**: Strict uniqueness on email and EUID; role-based access constraints.
- **Related Phase**: Phase 1–3.

### `apps/accounts/services.py`
- **Purpose**: Domain operations for user registration, bulk CSV student import, and profile management.
- **Responsibilities**: Parses bulk student CSVs, validates format, hashes initial passwords, handles cohort assignment.
- **Related Phase**: Phase 2–3.

### `apps/accounts/views.py` & `serializers.py`
- **Purpose**: REST views and serialization for authentication and student management.
- **Responsibilities**: Cookie-based login/logout, token refresh, password reset, admin student CRUD.
- **Related Phase**: Phase 1–3.

---

## 5. Django App: Question Bank (`backend/apps/questions/`)

### `apps/questions/models.py`
- **Purpose**: Question authoring, tagging, and versioning data models.
- **Responsibilities**: `Question` (`MCQ`, `CODING`, `SQL`), `QuestionVersion` (immutable version tracking), `TestCase` (visible & hidden test cases).
- **Security**: Hidden test cases strictly flagged and excluded from candidate visibility.
- **Related Phase**: Phase 4.

### `apps/questions/services.py`
- **Purpose**: Question versioning and lifecycle domain operations.
- **Responsibilities**: Manages question cloning, tag filtering, version increments, and validation.
- **Related Phase**: Phase 4.

### `apps/questions/views.py` & `serializers.py`
- **Purpose**: REST endpoints for instructor and admin question management.
- **Related Phase**: Phase 4.

---

## 6. Django App: Assessment Engine (`backend/apps/assessments/`)

### `apps/assessments/models.py`
- **Purpose**: Assessment scheduling, immutable snapshotting, and runtime attempts.
- **Responsibilities**: `Assessment`, `AssessmentSnapshot` (frozen questions at publish time), `TestAttempt` (attempt status, timer tracking), `AttemptAnswer`.
- **Related Phase**: Phase 5 🔒.

### `apps/assessments/services.py`
- **Purpose**: Authoritative attempt lifecycle and timer operations.
- **Responsibilities**: `AttemptService` (starts attempts, validates limits, submits), `AttemptTimerService` (authoritative countdown, auto-expiry).
- **Security**: Row locking via `select_for_update()`, server-authoritative clock.
- **Related Phase**: Phase 5 🔒.

### `apps/assessments/consumers.py`
- **Purpose**: Real-Time WebSocket consumer (`TestAttemptConsumer`).
- **Responsibilities**: Broadcasts remaining seconds, autosaves answer drafts, handles auto-submission on timer expiry.
- **Related Phase**: Phase 5 🔒.

---

## 7. Django App: Evaluator & Sandboxing (`backend/apps/evaluator/`)

### `apps/evaluator/models.py`
- **Purpose**: Submission records and code test case execution results.
- **Responsibilities**: `CodeSubmission` (source code, language, status, execution metrics), `TestCaseResult`.
- **Related Phase**: Phase 6 🔒.

### `apps/evaluator/services.py`
- **Purpose**: Judge0 client integration and automated grading orchestrator.
- **Responsibilities**: Dispatches code to Judge0, polls status, compares outputs, assigns scores.
- **Security**: Strips hidden test case details before emitting client events.
- **Related Phase**: Phase 6 🔒.

---

## 8. Django App: Real-Time AI Proctoring (`backend/apps/proctoring/`)

### `apps/proctoring/models.py`
- **Purpose**: Telemetry events, webcam evidence, and risk score tracking.
- **Responsibilities**: `ProctoringSession` (aggregate risk score, band), `ProctoringEvent` (event type, severity, confidence), `ProctoringEvidence` (flagged frame paths).
- **Related Phase**: Phase 7 🔒.

### `apps/proctoring/services.py`
- **Purpose**: Computer vision inference pipelines and risk calculation algorithms.
- **Responsibilities**: Face presence detection, multi-face counting, gaze direction, mobile phone inference, weighted risk score calculation.
- **Related Phase**: Phase 7 🔒.

---

## 9. Django App: Results & Analytics (`backend/apps/results/`)

### `apps/results/models.py`
- **Purpose**: Finalized scores, grade ledger, and immutable historical summaries.
- **Responsibilities**: `AssessmentResult` (final score, percentage, grade band), `HistoricalResultSummary` (permanent immutable grade ledger).
- **Related Phase**: Phase 8 🔒.

### `apps/results/services.py`
- **Purpose**: Finalization authority, score calculations, and PDF/Excel generation.
- **Responsibilities**: `ResultFinalizationService` (grades attempts, calculates percentiles), `ScorecardPDFService` (tamper-proof PDF generation), `ReportExportService` (Excel generation with CSV formula injection sanitization).
- **Related Phase**: Phase 8 🔒.

---

## 10. Django App: Retention, Privacy & DSAR (`backend/apps/retention/`)

### `apps/retention/models.py`
- **Purpose**: Retention policies, legal holds, audit tombstones, and DSAR export jobs.
- **Responsibilities**: `RetentionPolicy`, `RetentionRecord` (`detailed_data_expires_at`), `LegalHold`, `RetentionTombstone` (HMAC-SHA256 sealed proof), `ExportJob`, `FileCleanupQueue`.
- **Related Phase**: Phase 9 🔒.

### `apps/retention/services/`
- `policy_engine.py`: Stamps deterministic retention deadlines at finalization.
- `scrubbing.py`: Authoritative two-stage database scrubbing under row locks.
- `legal_holds.py`: Scoped hold management (`STUDENT`, `ASSESSMENT`, `ATTEMPT`).
- `tombstone.py`: Mints immutable HMAC-SHA256 audit proofs after 100% file deletion.
- `dsar.py`: AES-256-GCM encrypted self-service student export pipeline with HKDF key derivation.
- `filesystem.py`: Celery worker unlinking disk files with path traversal checks.
- `metrics.py`: Calculates physical disk vs logical DB cleanup statistics.
- **Related Phase**: Phase 9 🔒.

---

## 11. Frontend Application Inventory (`frontend/src/`)

### Core Entry & Routing
- `src/App.tsx`: Top-level application component configuring React Router, AuthProvider, and route guards.
- `src/main.tsx`: React DOM mount entrypoint.
- `src/index.css`: Global Tailwind CSS utility and animation definitions.

### API Integration (`src/api/`)
- `client.ts`: Axios client configured with `withCredentials: true`, CSRF extraction, and global error interceptors.
- `auth.ts`, `students.ts`, `questions.ts`, `assessments.ts`, `evaluator.ts`, `proctoring.ts`, `results.ts`, `retention.ts`: Type-safe REST client modules matching backend endpoints.

### State & Hooks
- `src/context/AuthContext.tsx`: Manages active user authentication state, role claims, and logout.
- `src/hooks/useAuth.ts`: Custom hook exposing auth state and permissions.

### Common Components (`src/components/common/`, `src/components/layout/`)
- `Button.tsx`, `Card.tsx`, `Badge.tsx`: Reusable design system tokens.
- `ProtectedRoute.tsx`: Route wrapper checking authentication and role authorization (`ADMIN`, `STUDENT`).
- `Navbar.tsx`: Responsive navigation bar displaying active user identity, role, and logout.

### Admin Pages & Modals (`src/pages/admin/`, `src/components/admin/`)
- `AdminStudentsPage.tsx` & `AddStudentModal.tsx`, `BulkImportModal.tsx`: Student directory and batch CSV import.
- `AdminQuestionsPage.tsx` & `QuestionEditorPage.tsx`: Question authoring and testcase configuration.
- `AdminAssessmentsPage.tsx` & `AssessmentEditorPage.tsx`: Assessment scheduling, question selection, and publication.
- `AdminProctoringDashboardPage.tsx`: Real-time AI proctoring telemetry monitor and risk alerts.
- `AdminAssessmentResultsPage.tsx`: Gradebook, score distributions, and PDF/Excel export controls.
- `AdminRetentionDashboardPage.tsx`: Storage metrics, legal hold manager, tombstones table, and manual purge modal.

### Student Pages (`src/pages/student/`)
- `StudentAssessmentsPage.tsx`: Candidate dashboard listing available, upcoming, and completed exams.
- `StudentTestRoomPage.tsx`: Live exam environment integrating Monaco Editor, question viewer, countdown timer, and AI proctoring monitor.
- `StudentResultPage.tsx`: Detailed score report and PDF scorecard download.
- `StudentPrivacyPage.tsx`: Data retention countdown, policy notice, and encrypted DSAR download.

---

## 12. Automated Test Suite (`backend/tests/`)

- `conftest.py`: Fixtures for users, assessments, attempts, questions, and authenticated API clients.
- `test_auth.py` & `test_student_management.py`: Authentication, RBAC, and CSV import tests.
- `test_question_bank.py`: Question versioning, tagging, and hidden testcase tests.
- `test_assessments.py`: Attempt lifecycle, snapshotting, and timer synchronization tests.
- `test_evaluator.py` & `test_evaluator_security.py`: Sandboxed code execution, grading, and security limits.
- `test_proctoring_unit.py`, `integration.py`, `security.py`: AI vision telemetry, risk scoring, and alert tests.
- `test_results_unit.py`, `integration.py`, `security.py`: Scoring math, report generation, and Excel formula injection protection.
- `test_retention_unit.py`, `integration.py`, `security.py`: Data retention deadlines, legal holds, database scrubbing, HMAC tombstones, and DSAR encryption.
- `test_invigilation_unit.py`: Phase 10 unit tests for proctor assignments, interventions, pause cumulative cap, duty sessions, bilateral chat, and idempotency (32 tests).
- `test_invigilation_integration.py`: Phase 10 integration tests for proctor live roster, warnings, pause/resume, room scans, termination with Phase 8 finalization, and Channels WebSockets (13 tests).
- `test_invigilation_security.py`: Phase 10 security tests for RBAC, unassigned proctor isolation, candidate chat scoping, and blank input validation (17 tests).
- `test_invigilation_concurrency.py`: Phase 10 concurrency tests for duplicate pauses, simultaneous termination, race conditions, and assessment end boundary clamping (8 tests).
- **Total Verified Tests**: **327 / 327 PASS** (257 Phase 1–9 regression tests + 70 Phase 10 invigilation tests).

---

## 13. Phase 10 Human Invigilation & Live Intervention Files

### Backend (`backend/apps/invigilation/`)
- `models.py`: `InterventionType`, `ProctorAssignment`, `ProctorIntervention` (immutable append-only audit ledger), `ProctorDutySession`, `ProctorChatMessage`.
- `permissions.py`: `IsProctorOrAdmin`, `HasAssignedAssessmentAccess`, `HasAttemptInvigilationAccess`.
- `services.py`: `ProctorRosterService`, `LiveInterventionService` (warning, pause, resume, room scan, terminate), `ProctorTriageQueueService`, `ProctorChatService`.
- `serializers.py`: DRF serializers with student DSAR sanitization (masking internal notes and proctor IDs).
- `views.py`: Proctor console REST APIs and student intervention endpoints.
- `urls.py`: URL patterns for proctor endpoints and student intervention responses.
- `consumers.py`: `InvigilationConsumer` (`ws/proctor/assessments/<id>/`) and `ProctorChatConsumer` (`ws/proctor/attempts/<id>/chat/`).
- `admin.py`: Django admin site registration with immutable audit ledger protection.
- `migrations/0001_initial.py`: Migration creating Phase 10 tables with zero ALTER operations on Phase 1–9 tables.

### Frontend (`frontend/src/`)
- `types/invigilation.ts`: TypeScript interfaces for assignments, interventions, triage candidates, and chat messages.
- `api/invigilation.ts`: API service functions for live roster, warnings, pause/resume, room scans, termination, and chat.
- `pages/admin/ProctorLiveConsolePage.tsx`: Real-time proctoring console featuring candidate triage by risk band, transient keyframe mosaic, intervention controls, and bilateral chat.
- `pages/student/StudentTestRoomPage.tsx`: Integrated candidate test room featuring frosted pause overlay, warning acknowledgement modal, and room scan prompt.

