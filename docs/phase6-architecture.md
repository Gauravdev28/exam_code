# CODEGUARD — Phase 6 Architecture Specification: Secure Code Execution & Evaluation

---

## 1. System Topology & Execution Boundary

```text
[ React Test Room / Monaco Editor ]
                │
         HTTPS / WSS (REST / Channels)
                │
                ▼
[ CODEGUARD Django Application ] ─── (Timer, Auth, Idempotency, Snapshot Policy, Scoring)
                │
                ▼ (Celery Async Task: acks_late=True, exponential backoff)
[ Redis Task Broker ]
                │
                ▼
[ Celery Execution Worker ]
                │
                ▼ (HTTP POST /submissions / Judge0Adapter)
[ Judge0 CE Execution Gateway ] (v1.13.1 production target / hermetic dev adapter)
                │
                ▼ (isolate / cgroups v2 / namespaces)
┌─────────────────────────────────────────────────────────────┐
│              ISOLATED SANDBOX EXECUTION JAIL                │
│  - CLONE_NEWNET (Empty network namespace / No egress)       │
│  - CLONE_NEWPID (Isolated process tree)                     │
│  - Read-Only Root Filesystem + tmpfs scratchpad             │
│  - cgroups v2 (cpu.max, memory.max, pids.max = 30)         │
│  - Seccomp-BPF Syscall Whitelist & Dropped Capabilities     │
│  - 64 KB Stdout/Stderr buffer truncation                    │
│  - Ephemeral unprivileged UID execution                     │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Core Responsibilities & System Boundaries

### 2.1 CODEGUARD Backend
* **Authentication & Role Authorization**: Validates active student session and ensures attempt belongs to requesting student.
* **Server-Authoritative Timer**: Validates `now < attempt.expires_at` using server time. Rejects expired submissions.
* **Snapshot Configuration Resolution**: Extracts `coding_config` and `server_coding_eval` strictly from frozen `AssessmentSnapshot`.
* **Idempotency & Concurrency Quotas**:
  - SHA-256 idempotency key prevents duplicate execution jobs.
  - Concurrency ceiling: Maximum 1 active execution job, maximum 2 queued execution jobs per attempt (rejects with HTTP 429).
  - Rate limiting: 6 Runs/minute, 3 Submits/minute.
* **Scoring & Negative Marking**: Deterministic partial scoring ($\sum_{tc \in \text{Passed}} tc.\text{points}$) and negative marking penalty deduction on $0/N$ passed tests (floored at 0.00).
* **Hidden Test Redaction**: Ensures hidden test cases are never transmitted to students via REST, WebSocket, or logs.

### 2.2 Execution Engine & Sandbox
* **Process & Thread Sandboxing**: Enforces `pids.max = 30` to prevent fork/thread exhaustion attacks.
* **Memory Constraints**: Strict `memory.max` allocation with swap disabled (`memory.swap.max = 0`).
* **Time Limiting**: Wall clock + CPU time limits with `SIGXCPU` and hard kill timeouts.
* **Output Truncation**: Stdout and Stderr capped at 64 KB to eliminate buffer overflow / memory flooding.
* **Network Isolation**: `CLONE_NEWNET` empty namespace prevents outbound Internet, MySQL, Redis, Django, and cloud metadata access.
* **Filesystem Jail**: Chroot jail with read-only root and isolated unshared temporary workspace.
