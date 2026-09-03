# CODEGUARD — Phase 6 Threat Model & Security Capability Specification

---

## 1. Threat Matrix & Defense Capabilities

| Threat Scenario | Vector / Attack Mechanism | Mitigation Mechanism | Sandbox Control |
| :--- | :--- | :--- | :--- |
| **Denial of Service (CPU)** | Infinite loops (`while(1){}`) / algorithmic complexity attacks | CPU quota + hard wall timer | cgroups v2 `cpu.max` + `SIGXCPU` timer |
| **Denial of Service (RAM)** | Memory allocation bombs (`[1024*1024*500]`) | Hard memory limits without swap | cgroups v2 `memory.max` + `memory.swap.max = 0` |
| **Process Fork Bomb** | Uncontrolled process spawning (`while True: os.fork()`) | Strict process tree ceiling | cgroups v2 `pids.max = 30` (`EAGAIN`) |
| **Thread Spawning Bomb** | Rapid thread allocation (`threading.Thread`) | PID quota ceiling (Linux counts tasks/threads) | cgroups v2 `pids.max` (`RuntimeError`) |
| **Sensitive File Access** | Reading `/etc/shadow`, `/etc/passwd`, host configs | Pivot root into read-only minimal jail | `chroot` / `ro,nosuid,nodev` mounts |
| **Host Process Snooping** | Inspecting `/proc` or `/sys` of host containers | Unshared PID namespace + masked `/proc` | `CLONE_NEWPID` / isolated PID namespace |
| **Docker Socket Hijack** | Accessing `/var/run/docker.sock` to escape container | Socket unmounted and inaccessible | Filesystem jail isolation |
| **Outbound Internet Egress** | Connecting to external C2 servers (`8.8.8.8`) | Empty network namespace without interface | `CLONE_NEWNET` (`ENETUNREACH`) |
| **Lateral Movement (DB/Redis)**| Port scanning internal services (`db:3306`, `redis:6379`) | Network namespace isolation | `CLONE_NEWNET` (`ENETUNREACH`) |
| **Backend API Spoofing** | Reaching `backend:8000` to spoof exam state | Network namespace isolation | `CLONE_NEWNET` (`ENETUNREACH`) |
| **Cloud Metadata Theft** | Querying AWS/GCP metadata (`169.254.169.254`) | Network namespace isolation | `CLONE_NEWNET` (`ENETUNREACH`) |
| **Privilege Escalation** | `setuid(0)` or writing to system dirs | Dropped Linux capabilities + non-root UID | `cap_drop=ALL`, `setuid=unprivileged` |
| **Dangerous Syscalls** | Raw socket creation, ptrace, reboot | Seccomp-BPF strict syscall filtering | Seccomp profile (`SIGSYS`) |
| **Stdout Buffer Flooding** | Exfiltrating MBs of spam data via stdout | Kernel buffer ceiling + capture truncation | 64 KB truncation ceiling (`OUTPUT_LIMIT_EXCEEDED`) |
| **Test Case Data Exfiltration**| Attempting to leak hidden test inputs/outputs | Zero transmission of hidden tests to frontend | Database `NULL` values for hidden inputs/outputs |
| **Question Bank Manipulation** | Modifying published question during exam | Historical snapshot immutability | Isolated frozen `AssessmentSnapshot` binding |

---

## 2. Low-Level Verification Taxonomy

The evaluation subsystem clearly distinguishes:
1. **Student Program Failure**: Logical errors (`WRONG_ANSWER`), syntax errors (`COMPILATION_ERROR`), unhandled exceptions (`RUNTIME_ERROR` with stack trace).
2. **Sandbox Security Enforcement**: Resource starvation (`TIME_LIMIT_EXCEEDED`, `MEMORY_LIMIT_EXCEEDED`, `OUTPUT_LIMIT_EXCEEDED`), OS permission blocks (`EACCES`, `EPERM`), networking denials (`ENETUNREACH`), syscall denials (`SIGSYS`).
3. **Infrastructure / Engine Failure**: Sandbox connection timeout, policy absence, or execution crash $\rightarrow$ triggers transactional retry (max 3) or fail-closed `SYSTEM_ERROR`.
