# CODEGUARD — Phase 11 Native Linux Judge0 Validation Readiness & Checklist

## 1. Context & Purpose

The CODEGUARD platform features sandboxed execution infrastructure for both algorithmic coding (via Judge0 CE and `isolate`) and database queries (via isolated ephemeral MySQL sandboxes).

All deterministic components, unit tests, integration tests, and security boundaries have been fully verified:
* **594 / 594** baseline regression tests passed
* **71 / 71** Phase 11 deterministic tests passed
* **665 / 665** total deterministic tests passed (0 failures, 0 errors)
* SQL sandbox physical database separation, unprivileged candidate user isolation, and zero-leakage cleanup verified
* Frontend typecheck and production build passed with 0 errors
* Docker Compose development and production specifications verified

However, **live isolate execution through Judge0 workers cannot execute on macOS Docker Desktop** due to Docker Desktop's LinuxKit kernel utilizing a pure cgroups v2 hierarchy (`cgroup2fs`). The bundled `isolate 1.8.1` binary strictly requires Linux kernel cgroups v1.

Therefore, live Judge0 execution tests are cleanly skipped on macOS. **Final operational validation of real sandboxed execution must take place on a supported native Linux environment.**

---

## 2. Linux Validation Environment Specifications

The following technical requirements have been confirmed directly from the installed Judge0 v1.13.1 stack:

| Parameter | Confirmed Requirement | Technical Reason |
| :--- | :--- | :--- |
| **Judge0 Version** | `1.13.1` (`judge0/judge0:1.13.1`) | Pinned in `docker-compose.yml` and `docker-compose.prod.yml`. |
| **Isolate Version** | `1.8.1` (Git commit `v1.8.1-8-gad39cc4`) | Bundled inside the Judge0 worker container image. |
| **Operating System** | Native Linux (e.g. Ubuntu 22.04 LTS, Ubuntu 20.04 LTS, Debian 11/12) | Must be a bare-metal or full hypervisor Linux kernel (not macOS Docker Desktop / LinuxKit). |
| **Kernel cgroups** | **cgroup v1** (`systemd.unified_cgroup_hierarchy=0`) | `isolate 1.8.1` requires legacy controller directories (`/sys/fs/cgroup/memory`, `/sys/fs/cgroup/cpu,cpuacct`). On Ubuntu 22.04+, append `systemd.unified_cgroup_hierarchy=0` to `GRUB_CMDLINE_LINUX_DEFAULT` in `/etc/default/grub` and run `sudo update-grub && sudo reboot`. |
| **CPU Architecture** | `x86_64` (AMD64) | Native compilation and execution of isolate; Rosetta translation on ARM64 cannot mount chroot namespaces. |
| **Container Engine** | Docker Engine 20.10+ | Native Linux daemon running directly on host kernel. |
| **Compose Tool** | Docker Compose v2+ (`docker compose`) | Orchestrates `judge0_db`, `judge0_redis`, `judge0`, and `judge0_workers`. |
| **Container Privileges** | `privileged: true` on `judge0` and `judge0_workers` | Required by `isolate` to manage chroot, mount points, and cgroup resource limits. |

---

## 3. Pre-Validation Environment Verification Commands

Before running the test suite on the Linux host, execute and inspect:

```bash
# 1. Verify CPU architecture (must be x86_64)
uname -m

# 2. Verify kernel and OS release
uname -a
cat /etc/os-release

# 3. Verify cgroups hierarchy (must NOT be pure cgroup2fs)
stat -fc %T /sys/fs/cgroup
mount | grep cgroup

# 4. Verify cgroup v1 controller directories exist
ls -la /sys/fs/cgroup/memory
ls -la /sys/fs/cgroup/cpu
```

If `stat -fc %T /sys/fs/cgroup` returns `cgroup2fs` without legacy controllers, configure GRUB:
```bash
sudo sed -i 's/GRUB_CMDLINE_LINUX_DEFAULT="\(.*\)"/GRUB_CMDLINE_LINUX_DEFAULT="\1 systemd.unified_cgroup_hierarchy=0"/' /etc/default/grub
sudo update-grub
sudo reboot
```

---

## 4. Operational Validation Checklist

This checklist tracks the operational milestones that must be verified on the native Linux host:

```text
Phase 11 Linux Validation Checklist

[ ] Native Linux host verified (x86_64)
[ ] Docker Engine and Compose available
[ ] Linux kernel cgroups v1 available (/sys/fs/cgroup/memory present)
[ ] Docker Compose services started (docker compose up -d)
[ ] Judge0 API healthy (HTTP 200 from http://127.0.0.1:2358/system_info)
[ ] Judge0 workers available (active Resque worker processes confirmed)
[ ] Execution probe passes (Judge0Adapter.check_health_detailed()["execution_operational"] == True)
[ ] Python live execution test passes (test_live_python_accepted_execution)
[ ] C++ live execution test passes (test_live_cpp_execution)
[ ] Java live execution test passes (test_live_java_execution)
[ ] Live timeout test passes (test_live_python_timeout -> TIME_LIMIT_EXCEEDED)
[ ] Live resource-limit test passes (memory / output boundary truncation)
[ ] Live failure handling passes (network / 500 error / malformed code fail closed)
[ ] Concurrent execution passes (multiple simultaneous submissions isolated)
[ ] SQL sandbox execution passes (dedicated mysql_sandbox on codeguard_prod_network)
[ ] SQL cleanup passes (zero orphan cg_sb_% databases, zero orphan users)
[ ] Complete 594 regression tests pass
[ ] Complete 71 Phase 11 deterministic tests pass
[ ] Frontend typecheck passes (npm run typecheck)
[ ] Frontend production build passes (npm run build)
[ ] Final production Compose config validates (docker compose -f docker-compose.prod.yml config)
```

---

## 5. Running the Validation Commands on Linux

Once the Linux environment meets all prerequisites, execute:

```bash
# 1. Start the stack
docker compose up -d

# 2. Force live Judge0 tests to execute (disabling skip)
export JUDGE0_LIVE_TEST=true
pytest backend/tests/test_judge0_live_and_integration.py -v

# 3. Run the full backend suite
pytest backend/tests/ -v

# 4. Run frontend verification
cd frontend && npm run typecheck && npm run build
```
