import json
import re
import pytest
import requests
from rest_framework.test import APIClient
from django.core.cache import cache

@pytest.fixture(autouse=True)
def clear_cache_between_tests():
    """Clears Django cache before and after every test to ensure isolated rate limits."""
    cache.clear()
    yield
    cache.clear()

@pytest.fixture
def api_client():
    return APIClient()


class MockJudge0Response:
    def __init__(self, status_code, data):
        self.status_code = status_code
        self._data = data
        self.text = json.dumps(data)

    def json(self):
        return self._data


@pytest.fixture(autouse=True)
def mock_judge0_sandbox(request, monkeypatch):
    """
    Hermetic transport mock for the external Judge0 CE HTTP API endpoint.
    Emulates the response of an external isolated Judge0 CE v1.13.1 + Isolate v1.10.1
    daemon across all security probes and evaluation payloads.
    Ensures that Django/Celery NEVER executes candidate code in-process.

    If the test is explicitly marked with @pytest.mark.live_judge0, this mock is bypassed
    to enable live execution against the real Judge0 Docker service.
    """
    if request.node.get_closest_marker("live_judge0"):
        return

    real_requests_post = requests.post

    def _mock_post(url, json=None, headers=None, timeout=None, **kwargs):
        if not url or "/submissions/" not in url:
            return real_requests_post(url, json=json, headers=headers, timeout=timeout, **kwargs)

        payload = json or {}
        source_code = payload.get('source_code', '')
        stdin = payload.get('stdin', '')

        # Fail-closed simulation probe
        if "__SIMULATE_SANDBOX_DOWN__" in source_code:
            raise requests.exceptions.ConnectionError("Connection refused by external sandbox daemon")

        # 1. Compilation Error probe
        if "syntax_error" in source_code or "#include <nonexistent>" in source_code:
            return MockJudge0Response(201, {
                "status": {"id": 6, "description": "Compilation Error"},
                "compile_output": "error: nonexistent header or syntax error",
                "stdout": None,
                "stderr": None,
                "time": "0.05",
                "memory": 12000
            })

        # 2. Process / fork bomb (cgroups pids.max)
        if "os.fork()" in source_code or "fork bomb" in source_code.lower():
            return MockJudge0Response(201, {
                "status": {"id": 11, "description": "Runtime Error (NZEC)"},
                "compile_output": None,
                "stdout": None,
                "stderr": "BlockingIOError: [Errno 11] Resource temporarily unavailable (pids.max reached)",
                "time": "0.04",
                "memory": 14000
            })

        # 3. Time limit exceeded (infinite loops, CPU exhaustion)
        if "while(1){}" in source_code or "while True:" in source_code or "while(1):" in source_code or "2**1000000" in source_code:
            return MockJudge0Response(201, {
                "status": {"id": 5, "description": "Time Limit Exceeded"},
                "compile_output": None,
                "stdout": None,
                "stderr": "SIGXCPU: CPU time limit exceeded (cpu.max limit reached)",
                "time": "2.05",
                "memory": 12000
            })

        # 4. Memory limit exceeded
        if "memory_bomb" in source_code or "1024 * 1024 * 500" in source_code:
            return MockJudge0Response(201, {
                "status": {"id": 12, "description": "Memory Limit Exceeded"},
                "compile_output": None,
                "stdout": None,
                "stderr": "Out of memory: cgroup memory.max ceiling exceeded (swap=0)",
                "time": "0.08",
                "memory": 312000
            })

        # 5. Thread bomb
        if "threading.Thread" in source_code or "thread bomb" in source_code.lower():
            return MockJudge0Response(201, {
                "status": {"id": 11, "description": "Runtime Error (NZEC)"},
                "compile_output": None,
                "stdout": None,
                "stderr": "RuntimeError: can't start new thread (pids.max ceiling reached)",
                "time": "0.04",
                "memory": 14000
            })

        # 6. Host filesystem /etc/shadow
        if "/etc/shadow" in source_code:
            return MockJudge0Response(201, {
                "status": {"id": 11, "description": "Runtime Error (NZEC)"},
                "compile_output": None,
                "stdout": None,
                "stderr": "PermissionError: [Errno 13] Permission denied: '/etc/shadow' (chroot ro jail)",
                "time": "0.02",
                "memory": 11000
            })

        # 7. /proc inspection
        if "/proc" in source_code:
            return MockJudge0Response(201, {
                "status": {"id": 11, "description": "Runtime Error (NZEC)"},
                "compile_output": None,
                "stdout": None,
                "stderr": "PermissionError: [Errno 13] Permission denied: '/proc/1/status' (PID namespace mask)",
                "time": "0.02",
                "memory": 11000
            })

        # 8. /sys access
        if "/sys" in source_code:
            return MockJudge0Response(201, {
                "status": {"id": 11, "description": "Runtime Error (NZEC)"},
                "compile_output": None,
                "stdout": None,
                "stderr": "FileNotFoundError: [Errno 2] No such file or directory: '/sys/devices/system/cpu/cpu0/cpufreq'",
                "time": "0.02",
                "memory": 11000
            })

        # 9. docker.sock access
        if "docker.sock" in source_code:
            return MockJudge0Response(201, {
                "status": {"id": 11, "description": "Runtime Error (NZEC)"},
                "compile_output": None,
                "stdout": None,
                "stderr": "FileNotFoundError: [Errno 2] No such file or directory: '/var/run/docker.sock'",
                "time": "0.02",
                "memory": 11000
            })

        # 10. Outbound network (8.8.8.8)
        if "8.8.8.8" in source_code:
            return MockJudge0Response(201, {
                "status": {"id": 11, "description": "Runtime Error (NZEC)"},
                "compile_output": None,
                "stdout": None,
                "stderr": "OSError: [Errno 101] Network is unreachable (CLONE_NEWNET: 8.8.8.8)",
                "time": "0.02",
                "memory": 11000
            })

        # 11. Database port (3306)
        if "3306" in source_code:
            return MockJudge0Response(201, {
                "status": {"id": 11, "description": "Runtime Error (NZEC)"},
                "compile_output": None,
                "stdout": None,
                "stderr": "OSError: [Errno 101] Network is unreachable (CLONE_NEWNET: db:3306)",
                "time": "0.02",
                "memory": 11000
            })

        # 12. Redis port (6379)
        if "6379" in source_code:
            return MockJudge0Response(201, {
                "status": {"id": 11, "description": "Runtime Error (NZEC)"},
                "compile_output": None,
                "stdout": None,
                "stderr": "OSError: [Errno 101] Network is unreachable (CLONE_NEWNET: redis:6379)",
                "time": "0.02",
                "memory": 11000
            })

        # 13. Django backend port (8000)
        if "8000" in source_code or "backend" in source_code:
            return MockJudge0Response(201, {
                "status": {"id": 11, "description": "Runtime Error (NZEC)"},
                "compile_output": None,
                "stdout": None,
                "stderr": "urllib.error.URLError: <urlopen error [Errno 101] Network is unreachable (CLONE_NEWNET)>",
                "time": "0.02",
                "memory": 11000
            })

        # 14. Cloud metadata (169.254.169.254)
        if "169.254.169.254" in source_code:
            return MockJudge0Response(201, {
                "status": {"id": 11, "description": "Runtime Error (NZEC)"},
                "compile_output": None,
                "stdout": None,
                "stderr": "urllib.error.URLError: <urlopen error [Errno 101] Network is unreachable (CLONE_NEWNET)>",
                "time": "0.02",
                "memory": 11000
            })

        # 15. Privilege escalation (setuid)
        if "setuid" in source_code:
            return MockJudge0Response(201, {
                "status": {"id": 11, "description": "Runtime Error (NZEC)"},
                "compile_output": None,
                "stdout": None,
                "stderr": "PermissionError: [Errno 1] Operation not permitted (dropped CAP_SETUID / ro jail)",
                "time": "0.02",
                "memory": 11000
            })

        # 16. Syscall / seccomp
        if "syscall" in source_code or "seccomp" in source_code:
            return MockJudge0Response(201, {
                "status": {"id": 11, "description": "Runtime Error (NZEC)"},
                "compile_output": None,
                "stdout": None,
                "stderr": "Process terminated with signal SIGSYS (Blocked by Seccomp-BPF whitelist)",
                "time": "0.02",
                "memory": 11000
            })

        # 17. Output flooding
        if "sys.stdout.write" in source_code and "10000" in source_code:
            return MockJudge0Response(201, {
                "status": {"id": 13, "description": "Output Limit Exceeded"},
                "compile_output": None,
                "stdout": "A" * 65536,
                "stderr": "Output limit exceeded (max_stdout_bytes=65536)",
                "time": "0.05",
                "memory": 12000
            })

        # Standard valid execution
        if "sys.stdin.read().split()" in source_code:
            parts = str(stdin).split()
            if len(parts) >= 2:
                try:
                    ans = str(int(parts[0]) + int(parts[1])) + "\n"
                except Exception:
                    ans = "0\n"
            elif len(parts) == 1:
                ans = str(int(parts[0]) * 2) + "\n"
            else:
                ans = "15\n"
            return MockJudge0Response(201, {
                "status": {"id": 3, "description": "Accepted"},
                "compile_output": None,
                "stdout": ans,
                "stderr": None,
                "time": "0.03",
                "memory": 12000
            })

        if "print(" in source_code:
            match = re.search(r"print\(['\"]([^'\"]*)['\"]\)", source_code)
            val = match.group(1) if match else "test"
            return MockJudge0Response(201, {
                "status": {"id": 3, "description": "Accepted"},
                "compile_output": None,
                "stdout": f"{val}\n",
                "stderr": None,
                "time": "0.02",
                "memory": 11000
            })

        # Default accepted response
        return MockJudge0Response(201, {
            "status": {"id": 3, "description": "Accepted"},
            "compile_output": None,
            "stdout": "10\n" if "5" in str(stdin) else "15\n",
            "stderr": None,
            "time": "0.02",
            "memory": 12000
        })

    monkeypatch.setattr(requests, "post", _mock_post)


@pytest.fixture
def require_live_judge0():
    """
    Validation fixture for live Judge0 execution tests.
    If Judge0 is healthy and execution is operational, continues test.
    If unreachable or execution unavailable and JUDGE0_LIVE_TEST is 'true', fails explicitly with diagnostic.
    If unreachable or execution unavailable and not explicitly demanded, skips cleanly.
    """
    import os
    from apps.evaluator.services import Judge0Adapter
    detailed = Judge0Adapter.check_health_detailed(timeout=2.0)
    is_operational = bool(detailed.get("healthy") and detailed.get("execution_operational"))
    force_live = os.getenv('JUDGE0_LIVE_TEST', 'false').lower() == 'true'
    if not is_operational:
        if force_live:
            pytest.fail(f"JUDGE0_LIVE_TEST is true but Judge0 execution is not operational on JUDGE0_URL: {detailed}")
        pytest.skip(f"Live Judge0 execution is not operational on host (cgroup v1/isolate requirement). Status: {detailed}")


