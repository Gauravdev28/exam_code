# CODEGUARD — Phase 8 Reporting & Export Guide

## Overview

CODEGUARD Phase 8 provides asynchronous, cryptographically verified report generation across PDF, XLSX, and Controlled CSV formats.

---

## 1. Supported Report Formats

### A. PDF Vector Documents (`ReportLab`)
- **Student Scorecard**: Official student transcript containing assessment title, duration, points earned, percentage score, pass/fail status, and question-level performance summaries.
- **Assessment Executive Summary**: Admin-level executive report containing cohort participation metrics, score distribution charts, item difficulties, and summary performance KPIs.

### B. Excel Workbooks (`openpyxl`)
- Precomputed, deterministic cell values.
- Styled header rows with frozen panes and formatted numeric cells.
- Candidate roster including EUID, roll number, student email, total score, percentage, and submission timestamps.

### C. Controlled CSV Exports (`pandas`)
- Strict whitelist schema containing only approved analytical fields:
  ```csv
  euid,roll_number,student_name,student_email,assessment_id,assessment_title,total_score_earned,total_possible_score,percentage,is_passed,started_at,submitted_at,time_spent_seconds
  ```
- Excludes sensitive internal tokens, password hashes, and hidden test cases.

---

## 2. Security & Anti-Abuse Measures

### A. Formula Injection Sanitization
All text fields are sanitized prior to export. Any field commencing with `=`, `+`, `-`, `@`, `\t`, or `\r` is escaped with a leading single quote (`'`), neutralizing dynamic formula execution in spreadsheet applications.

### B. SHA-256 Digest Verification
Every generated report file has its SHA-256 hash computed upon generation and stored on the `ReportJob`. Prior to delivering the file to the client, the backend recalculates the SHA-256 checksum of the file on disk. Any discrepancy results in immediate download rejection (HTTP 403 Forbidden).

### C. Lifecycle & Expiry (7-Day TTL)
Generated report files are stored in `media/reports/` and are assigned a 7-day expiration (`expires_at`). The periodic Celery task `cleanup_expired_reports_task` automatically unlinks expired files and marks records as `EXPIRED`. Attempts to download expired reports return HTTP 410 Gone.
