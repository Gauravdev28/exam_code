# CODEGUARD — Phase 9 Testing & Quality Assurance Strategy (Concurrently & Cryptographically Hardened)

**Document Version:** 1.4.0  
**Baseline Test Count:** 197 / 197 PASS (Phases 1–8)  
**Target Additional Test Count:** 54 New Test Cases  
**Target Total Suite:** 251 Tests  

---

## 1. Test Domain Architecture

Phase 9 test coverage is organized into three targeted modules under `backend/tests/`:

1. `tests/test_retention_unit.py` (15 Tests): Domain rules, deadline calculations, policy versioning, tombstone PII minimization, HMAC verification, RetentionRecord 1:1 binding, risk state separation, key version selection.
2. `tests/test_retention_integration.py` (18 Tests): Scheduled Celery tasks, two-stage scrubbing, retryable file cleanup queue, legal hold lifecycle, DSAR export allowlist, manual purge multi-stage confirmation, key rotation, key retirement, expired archive cleanup, stale pending snapshot recovery.
3. `tests/test_retention_security.py` (21 Tests): Legal-hold race conditions, DSAR-purge races, snapshot acquisition serialization, snapshot rollback false-protection prevention, lock-order compliance, deadlock prevention, path traversal, score immutability, active session isolation, RBAC enforcement, stale recovery concurrency races.

---

## 2. Complete Planned Test Inventory (Exactly 54 Tests)

### 2.1 Unit Tests (`test_retention_unit.py` - 15 Tests)
1. `test_retention_policy_creation_and_validation`: Validates TTL defaults (30d), range limits (1–3650 days), and scope consistency.
2. `test_retention_policy_versioning_increment`: Asserts policy edits bump `version` integer to preserve audit lineage.
3. `test_retention_record_creation_on_finalization`: Asserts `RetentionRecord` is created 1:1 with `TestAttempt` at finalization.
4. `test_retention_record_deterministic_deadline_stamped`: Asserts `detailed_data_expires_at` is fixed at creation based on policy.
5. `test_retention_policy_change_existing_record`: Proves altering policy TTL does not retroactively shorten existing attempt deadlines.
6. `test_retention_policy_extension_existing_record`: Proves lengthening policy TTL does not shift existing stamped deadlines.
7. `test_purge_eligibility_unfinalized_attempt_rejected`: Confirms `is_eligible_for_purge` returns `False` for in-progress or unfinalized attempts.
8. `test_purge_eligibility_active_legal_hold_blocks_purge`: Confirms active hold on attempt, student, or assessment blocks eligibility.
9. `test_purge_eligibility_released_legal_hold_allows_purge`: Confirms that once a hold is released, purge eligibility is restored.
10. `test_tombstone_hmac_sha256_proof_computation`: Validates mathematical correctness and key-sensitivity of HMAC integrity proof.
11. `test_tombstone_immutability_save_and_delete_blocked`: Verifies that `RetentionTombstone` raises `PermissionDenied` on edit or delete.
12. `test_tombstone_data_minimization`: Asserts that `RetentionTombstone` contains EUID and UUIDs, and does NOT store roll numbers.
13. `test_legal_hold_scope_validation`: Ensures attempt, student, and assessment references strictly match the declared `scope`.
14. `test_proctoring_risk_operational_window_expiry`: Asserts that after 90 days, `risk_score = NULL`, `risk_band = NULL`, and `risk_data_status = 'PURGED'`.
15. `test_key_version_selection`: Validates that newly queued `ExportJob` instances select the currently active master key version (e.g. `v1`).

### 2.2 Integration Tests (`test_retention_integration.py` - 18 Tests)
16. `test_end_to_end_30_day_purge_workflow`: Verifies full sweep: DB answers wiped, files queued and unlinked, tombstone created, summary marked `details_purged`.
17. `test_decoupled_file_cleanup_queue`: Confirms that `FileCleanupQueue` tracks pending file unlinks independently from DB transactions.
18. `test_partial_filesystem_cleanup`: Verifies behavior when a subset of files unlink successfully; asserts tombstone is withheld until remaining files delete.
19. `test_filesystem_failure_after_db_commit`: Asserts DB scrub remains committed even if OS unlink fails, and failure is queued for retry.
20. `test_filesystem_cleanup_retry_idempotency`: Verifies Celery retry task safely ignores already unlinked files.
21. `test_admin_retention_metrics_calculation`: Verifies accurate reporting of confirmed bytes reclaimed, upcoming purge counts, and active holds.
22. `test_admin_dry_run_purge_preview`: Verifies preview endpoint generates a valid `preview_token` and predicts eligible items without mutating data.
23. `test_manual_purge_stale_preview_rejected`: Proves that presenting an expired or tampered `preview_token` aborts execution.
24. `test_manual_purge_final_eligibility_recheck`: Asserts that an attempt receiving a legal hold after preview is skipped during manual execution.
25. `test_legal_hold_placement_and_release_workflow`: Verifies hold lifecycle, audit logging, and attempt immunity enforcement.
26. `test_student_dsar_export_job_generation`: Verifies async compilation of personal attempt data into downloadable encrypted archive.
27. `test_dsar_after_detailed_purge`: Asserts that requesting export post-purge returns `AVAILABLE_PARTIAL_ARCHIVE` with permanent transcripts.
28. `test_student_retention_lifecycle_view`: Verifies countdown timer of days remaining before scheduled purge.
29. `test_celery_beat_purge_batch_task`: Verifies chunking (`CHUNK_SIZE = 100`), batch limits, and completion logging of the daily scheduled task.
30. `test_key_rotation_while_old_archive_valid`: Verifies that rotating master key from `v1` to `v2` leaves existing unexpired `v1` archives decryptable.
31. `test_old_key_unavailable_fails_safely`: Verifies safe failure (logged error and clean HTTP response) if an expired or missing key version is requested.
32. `test_expired_archive_no_longer_requires_old_key`: Proves that once a 7-day archive expires and is unlinked, the old key version is permanently decommissioned without error.
33. `test_stale_snapshot_pending_recovery`: Verifies that an abandoned `SNAPSHOT_PENDING` export whose 15-minute lease has expired is automatically transitioned to `FAILED` and unblocks scheduled purge.

### 2.3 Security, Concurrency & Cryptographic Tests (`test_retention_security.py` - 21 Tests)
34. `test_legal_hold_vs_purge_race`: Simulates simultaneous purge worker lock and admin hold creation; verifies hold immunity takes precedence.
35. `test_student_hold_vs_purge_race`: Verifies student-level hold placed concurrently blocks attempt-scoped purge.
36. `test_assessment_hold_vs_purge_race`: Verifies assessment-level hold placed concurrently blocks attempt-scoped purge.
37. `test_global_lock_order_deadlock_prevention`: Exercises concurrent hold creation and purge workers under stress; verifies zero lock-order deadlocks.
38. `test_export_job_lock_order_compliance`: Verifies `ExportJob` row lock is acquired strictly after `TestAttempt` and `RetentionRecord`.
39. `test_dsar_vs_purge_race`: Simulates in-flight DSAR export while purge worker runs; verifies purge is safely deferred.
40. `test_dsar_snapshot_acquisition_vs_purge_race`: Exercises `SNAPSHOT_PENDING` vs purge eligibility vs `SNAPSHOT_ACQUIRED`; proves purge cannot destroy source data during snapshot acquisition.
41. `test_dsar_snapshot_acquisition_rollback`: Simulates failure/rollback during snapshot acquisition; asserts `ExportJob` does not commit `SNAPSHOT_ACQUIRED` and leaves no false purge block.
42. `test_purge_vs_snapshot_pending`: Verifies purge worker defers when an export is in `SNAPSHOT_PENDING` with a valid lease.
43. `test_purge_vs_snapshot_acquired`: Verifies purge worker defers when an export is in `SNAPSHOT_ACQUIRED`.
44. `test_stale_recovery_vs_snapshot_acquisition_race`: Simulates simultaneous recovery sweep and active snapshot worker; verifies active worker with valid lease is never marked failed.
45. `test_stale_recovery_vs_purge_race`: Simulates recovery worker clearing a stale job while purge worker evaluates the attempt; verifies safe serialization through `TestAttempt + RetentionRecord`.
46. `test_dsar_hidden_test_protection`: Asserts hidden test inputs and expected outputs are strictly redacted from student DSAR exports.
47. `test_dsar_cross_student_protection`: Verifies student cannot export another student's responses (IDOR prevention).
48. `test_dsar_aes_256_gcm_encryption_and_key_versioning`: Verifies export archive is encrypted using AES-256-GCM with a 96-bit unique nonce and records `encryption_key_version`.
49. `test_student_cannot_access_admin_retention_endpoints`: Verifies 403 Forbidden across all `/api/v1/admin/retention/` and `/admin/legal-holds/`.
50. `test_path_traversal_on_evidence_cleanup_blocked`: Proves that malicious file paths in `ProctoringEvidence` cannot delete files outside `media/evidence/`.
51. `test_path_traversal_on_dsar_export_download_blocked`: Proves that DSAR file download cannot traverse outside `media/exports/`.
52. `test_purge_worker_never_modifies_official_scores`: Asserts that `AssessmentResult.total_score_earned` and `is_passed` are strictly unchanged after purge.
53. `test_duplicate_tombstone_prevention`: Asserts DB unique constraint and service check reject creating duplicate tombstones.
54. `test_in_progress_attempt_never_purged`: Proves active or in-progress attempts are strictly excluded from purge querysets.

---

## 3. Regression Assurance (197 / 197 Baseline)

Before declaring Phase 9 implementation complete, the entire regression suite must pass:
```text
Phase 1–5: 103 / 103 PASS
Phase 6:    33 / 33 PASS
Phase 7:    34 / 34 PASS
Phase 8:    27 / 27 PASS
Phase 9:    54 / 54 PASS
Total:     251 / 251 PASS
```
