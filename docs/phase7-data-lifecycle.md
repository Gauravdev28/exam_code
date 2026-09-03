# CODEGUARD — Phase 7 Data Retention & Lifecycle Contract: AI Proctoring

---

## 1. Executive Summary & Privacy Principles

The Phase 7 AI Proctoring subsystem enforces a **strict data minimization paradigm**:
1. Continuous raw video and audio streams are **never stored permanently**.
2. Normal baseline frames (where no high-severity anomaly is confirmed) are processed strictly in process RAM and **discarded immediately post-inference**.
3. High/Critical anomaly evidence (e.g. `PHONE_DETECTED`, `MULTIPLE_FACES`) generates bounded, cryptographically hashed keyframe snapshots (`.jpg`) or 2-second audio clips (`.webm`) tied to explicit expiration policies.
4. Cryptographic hashing (`SHA256(raw_bytes)`) is employed strictly for **tamper-evident integrity verification**, while confidentiality is guaranteed via strict RBAC access controls, private volume mounts, and secure transport.

---

## 2. Phase 7 Final Architecture Decisions (Data Lifecycle)

1. **Transient RAM Processing**: Unflagged raw webcam frames have a retention lifespan of $0\text{ seconds}$ and are evicted from Celery process memory immediately after OpenCV/MediaPipe/YOLO inference completes.
2. **Anomaly Keyframe Gating**: Media files are written to disk **only** when an AI or hybrid signal passes both the confidence threshold ($\ge 0.65$) and the multi-frame persistence window ($\ge 2$ frames over 4s).
3. **Structured Retention Attributes**: Every evidence artifact and event ledger row contains `created_at`, `expires_at`, and `retention_class` for zero-friction integration with the Phase 9 regulatory retention purge worker.

---

## 3. Data Classification & Lifecycle Policy Matrix

| Data Classification | Specific Entity / Field | Storage Location | Sensitivity | Default Retention Class | Default Expiration ($T_{\text{expire}}$) | Automated Purge Action |
| :--- | :--- | :--- | :---: | :---: | :---: | :--- |
| **Transient In-Memory Frames** | Decoded JPEG buffer in Celery task | Process RAM | High | `EPHEMERAL_BUFFER` | $0\text{ seconds}$ | Immediate in-memory garbage collection post-inference |
| **Normal Keyframes (No Anomaly)**| Unflagged baseline snapshots | Discarded | High | `EPHEMERAL_BUFFER` | $0\text{ seconds}$ | Never committed to disk storage |
| **Flagged Evidence Images** | `ProctoringEvidence` (`.jpg` file) | Local Media Volume | High | `TEMPORARY_EVIDENCE` | 30 days after assessment end datetime | Automated disk file unlink + record metadata archiving |
| **Bounded Audio Snippets** | Flagged 2s audio (`.webm` file) | Local Media Volume | High | `TEMPORARY_EVIDENCE` | 30 days after assessment end datetime | Automated disk file unlink + record metadata archiving |
| **Proctoring Event Ledger** | `ProctoringEvent` DB rows | MySQL DB | Medium | `OPERATIONAL_AUDIT` | 90 days after assessment end datetime | Cascaded SQL purge with `TestAttempt` |
| **Risk Summary & Review Record**| `ProctoringSession`, `ProctoringReview`| MySQL DB | Low | `PERMANENT_RECORD` | Permanent with Academic Record | Retained alongside student assessment transcript |

---

## 4. Phase 9 Integration Contract

The Phase 7 database models provide the following fields for Phase 9 retention services:
```python
# Model fields contract for Phase 9 Retention Engine
created_at = models.DateTimeField(auto_now_add=True)
expires_at = models.DateTimeField(null=True, blank=True, db_index=True)
retention_class = models.CharField(
    max_length=32,
    choices=[
        ('EPHEMERAL_BUFFER', 'Ephemeral Buffer (0s)'),
        ('TEMPORARY_EVIDENCE', 'Temporary Flagged Evidence (30d)'),
        ('OPERATIONAL_AUDIT', 'Operational Audit Ledger (90d)'),
        ('PERMANENT_RECORD', 'Permanent Academic Summary'),
    ],
    default='TEMPORARY_EVIDENCE',
    db_index=True
)
```
When Phase 9 runs its scheduled retention purge job:
$$\text{SELECT } * \text{ FROM proctoring\_evidence WHERE expires\_at } \le \text{NOW}() \text{ AND retention\_class } = \text{'TEMPORARY\_EVIDENCE'}$$
All matching media files on disk are unlinked, and corresponding database entries are marked `PURGED`.
