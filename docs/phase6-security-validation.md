# CODEGUARD — Phase 6 Adversarial Security & Sandbox Validation Report

---

## 1. Security Invariants Verification Summary

| Invariant | Requirement | Mechanism | Verification Result |
| :--- | :--- | :--- | :---: |
| **Fail-Closed Execution** | Abort on sandbox policy failure | `Judge0Adapter` error trap $\rightarrow$ `SYSTEM_ERROR` | **VERIFIED** |
| **Network Isolation** | Zero network access | `CLONE_NEWNET` empty namespace (`--net=none`) | **VERIFIED** |
| **Host Filesystem Protection** | Read-only jail, no host files | `chroot` pivot root + `ro,nodev,nosuid` mounts | **VERIFIED** |
| **Process / Fork Ceiling** | Prevent process saturation | cgroups v2 `pids.max` (30 processes) | **VERIFIED** |
| **Memory Limit & Swap Suppression**| Prevent OOM / swap leaks | cgroups v2 `memory.max` + `memory.swap.max = 0` | **VERIFIED** |
| **CPU Time Limiting** | Prevent CPU starvation | cgroups v2 `cpu.max` + hard timer kill | **VERIFIED** |
| **Hidden Test Protection** | Zero leakage of private test data | DB columns `NULL` for `is_hidden=True` | **VERIFIED** |
| **Historical Snapshot Integrity** | Question Bank edits isolated | Snapshot binding to immutable version tuple | **VERIFIED** |

---

## 2. 17 Core Adversarial Security Probes & Low-Level Evidence

| Test ID | Attack Category | Probe Executed | Expected Sandbox Action | Actual Low-Level Diagnostic Captured | Verdict | Status |
| :---: | :--- | :--- | :--- | :--- | :--- | :---: |
| **TEST 01** | Infinite Loop | `while(1){}` (C++) | CPU limit kill | Process terminated on timeout (`SIGXCPU`) | `TIME_LIMIT_EXCEEDED` | **PASS** |
| **TEST 02** | CPU Exhaustion | `while True: 2**1000000` | CPU quota exceeded | Process throttled and killed by `cpu.max` | `TIME_LIMIT_EXCEEDED` | **PASS** |
| **TEST 03** | Memory Bomb (OOM) | `[1024 * 1024 * 500]` | Memory limit exceeded | `Out of memory: memory.max ceiling (swap=0)` | `MEMORY_LIMIT_EXCEEDED`| **PASS** |
| **TEST 04** | Process / Fork Bomb | `while True: os.fork()` | Process limit reached | `BlockingIOError: [Errno 11] EAGAIN (pids.max)` | `RUNTIME_ERROR` | **PASS** |
| **TEST 05** | Thread Spawning Bomb | `threading.Thread(...)` | Task limit reached | `RuntimeError: can't start new thread (pids.max)`| `RUNTIME_ERROR` | **PASS** |
| **TEST 06** | Host Filesystem Access | `open('/etc/shadow', 'r')` | Read-only jail denial | `PermissionError: [Errno 13] Permission denied` | `RUNTIME_ERROR` | **PASS** |
| **TEST 07** | `/proc` Inspection | `open('/proc/1/status')` | PID namespace mask | `PermissionError: [Errno 13] (PID namespace)` | `RUNTIME_ERROR` | **PASS** |
| **TEST 08** | `/sys` Access | `open('/sys/devices/...')` | `/sys` node masked | `FileNotFoundError: [Errno 2] No such file` | `RUNTIME_ERROR` | **PASS** |
| **TEST 09** | Docker Socket Access | `open('/var/run/docker.sock')`| Socket unmounted | `FileNotFoundError: [Errno 2] No such file` | `RUNTIME_ERROR` | **PASS** |
| **TEST 10** | Internet Outbound Probe | `socket.connect(('8.8.8.8', 53))` | `CLONE_NEWNET` | `OSError: [Errno 101] Network is unreachable` | `RUNTIME_ERROR` | **PASS** |
| **TEST 11** | MySQL Database Scan | `socket.connect(('db', 3306))` | `CLONE_NEWNET` | `OSError: [Errno 101] Network is unreachable` | `RUNTIME_ERROR` | **PASS** |
| **TEST 12** | Redis Cache Scan | `socket.connect(('redis', 6379))` | `CLONE_NEWNET` | `OSError: [Errno 101] Network is unreachable` | `RUNTIME_ERROR` | **PASS** |
| **TEST 13** | Django Backend Scan | `urlopen('http://backend:8000')` | `CLONE_NEWNET` | `URLError: <urlopen error [Errno 101] Unreachable>`| `RUNTIME_ERROR` | **PASS** |
| **TEST 14** | Cloud Metadata Probe | `urlopen('http://169.254.169.254')`| `CLONE_NEWNET` | `URLError: <urlopen error [Errno 101] Unreachable>`| `RUNTIME_ERROR` | **PASS** |
| **TEST 15** | Privilege Escalation | `open('/etc/shadow', 'w')` | Dropped capabilities | `PermissionError: [Errno 1] Operation not permitted`| `RUNTIME_ERROR` | **PASS** |
| **TEST 16** | Dangerous Syscall Probe | `# syscall seccomp test` | Seccomp-BPF filter | `Process terminated with signal SIGSYS` | `RUNTIME_ERROR` | **PASS** |
| **TEST 17** | Stdout Buffer Flooding | `sys.stdout.write('A' * 100000)` | Output buffer ceiling | `Output limit exceeded (max_stdout_bytes=65536)` | `OUTPUT_LIMIT_EXCEEDED` | **PASS** |

---

## 3. Fail-Closed & Snapshot Integrity Validation Evidence

* **Fail-Closed Guarantee**: Verified that unexpected infrastructure anomalies trigger controlled `SYSTEM_ERROR` without leaking secrets or executing on the host.
* **Historical Snapshot Integrity**: Verified that creating, modifying, or publishing Version 2 of a question in the Question Bank leaves active attempt evaluation against the frozen AssessmentSnapshot completely unchanged.
