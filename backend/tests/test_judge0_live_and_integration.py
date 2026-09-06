"""
Unit, integration, and live execution tests for Judge0Adapter and execution infrastructure.
"""
import pytest
import requests
from rest_framework.exceptions import ValidationError as DRFValidationError

from apps.evaluator.services import Judge0Adapter
from apps.evaluator.models import CodeVerdict


# ==============================================================================
# 1. Judge0 Health Check Unit Tests
# ==============================================================================

class TestJudge0HealthCheck:

    def test_health_check_success(self, monkeypatch):
        class MockResponse:
            status_code = 200
            def json(self):
                return {"version": "1.13.1", "status": "operational"}

        monkeypatch.setattr(requests, "get", lambda url, **kwargs: MockResponse())
        assert Judge0Adapter.check_health(timeout=1.0) is True

    def test_health_check_connection_error_fails_safely(self, monkeypatch):
        def _mock_err(url, **kwargs):
            raise requests.exceptions.ConnectionError("Connection refused")

        monkeypatch.setattr(requests, "get", _mock_err)
        assert Judge0Adapter.check_health(timeout=1.0) is False

    def test_health_check_timeout_fails_safely(self, monkeypatch):
        def _mock_timeout(url, **kwargs):
            raise requests.exceptions.Timeout("Request timed out")

        monkeypatch.setattr(requests, "get", _mock_timeout)
        assert Judge0Adapter.check_health(timeout=1.0) is False

    def test_health_check_http_500_fails_safely(self, monkeypatch):
        class Mock500Response:
            status_code = 500
            def json(self):
                return {"error": "Internal Server Error"}

        monkeypatch.setattr(requests, "get", lambda url, **kwargs: Mock500Response())
        assert Judge0Adapter.check_health(timeout=1.0) is False

    def test_health_check_malformed_response_fails_safely(self, monkeypatch):
        class MockMalformedResponse:
            status_code = 200
            def json(self):
                raise ValueError("Malformed JSON payload")

        monkeypatch.setattr(requests, "get", lambda url, **kwargs: MockMalformedResponse())
        assert Judge0Adapter.check_health(timeout=1.0) is False

    def test_check_health_detailed_success(self, monkeypatch):
        def _mock_get(url, **kwargs):
            class MockResp:
                status_code = 200
                def json(self):
                    if "/workers" in url:
                        return [{"queue": "default", "available": True}]
                    return {"version": "1.13.1", "workers": 2}
            return MockResp()

        def _mock_post(url, **kwargs):
            class MockPostResp:
                status_code = 201
                def json(self):
                    return {"status": {"id": 3, "description": "Accepted"}}
            return MockPostResp()

        monkeypatch.setattr(requests, "get", _mock_get)
        monkeypatch.setattr(requests, "post", _mock_post)
        detailed = Judge0Adapter.check_health_detailed(timeout=2.0)
        assert detailed["healthy"] is True
        assert detailed["api_reachable"] is True
        assert detailed["worker_operational"] is True
        assert detailed["execution_operational"] is True
        assert "version" in detailed["system_info"]

    def test_check_health_detailed_unreachable(self, monkeypatch):
        def _mock_err(url, **kwargs):
            raise requests.exceptions.ConnectionError("Connection refused")

        monkeypatch.setattr(requests, "get", _mock_err)
        detailed = Judge0Adapter.check_health_detailed(timeout=1.0)
        assert detailed["healthy"] is False
        assert detailed["api_reachable"] is False
        assert detailed["worker_operational"] is False


# ==============================================================================
# 2. Judge0 Adapter Unit & Fail-Closed Tests
# ==============================================================================

class TestJudge0AdapterExecutionUnit:

    def test_unsupported_language_raises_validation_error(self):
        with pytest.raises(DRFValidationError, match="Unsupported execution language"):
            Judge0Adapter.get_language_id("RUST")

    def test_supported_language_ids(self):
        assert Judge0Adapter.get_language_id("PYTHON") == 71
        assert Judge0Adapter.get_language_id("CPP") == 54
        assert Judge0Adapter.get_language_id("JAVA") == 62

    def test_fail_closed_on_network_error(self, monkeypatch):
        def _mock_post(url, **kwargs):
            raise requests.exceptions.ConnectionError("Connection refused by Judge0 broker")

        monkeypatch.setattr(requests, "post", _mock_post)
        res = Judge0Adapter.execute_in_sandbox(
            source_code="print('test')",
            language="PYTHON",
            stdin_data="",
            expected_output="test"
        )
        assert res["status_id"] == 13
        assert res["status_description"] == "Sandbox Unavailable"
        assert "FAIL_CLOSED" in res["stderr"]

    def test_fail_closed_on_http_error(self, monkeypatch):
        class MockHttpError:
            status_code = 502
            text = "Bad Gateway"
            def json(self):
                return {}

        monkeypatch.setattr(requests, "post", lambda url, **kwargs: MockHttpError())
        res = Judge0Adapter.execute_in_sandbox(
            source_code="print('test')",
            language="PYTHON",
            stdin_data="",
            expected_output="test"
        )
        assert res["status_id"] == 13
        assert res["status_description"] == "Sandbox Unavailable"
        assert "FAIL_CLOSED" in res["stderr"]


# ==============================================================================
# 3. Live Execution Tests (Executed against real Judge0 when available)
# ==============================================================================

@pytest.mark.live_judge0
class TestJudge0LiveExecution:

    def test_live_python_accepted_execution(self, require_live_judge0):
        res = Judge0Adapter.execute_in_sandbox(
            source_code="print('Hello CODEGUARD')",
            language="PYTHON",
            stdin_data="",
            expected_output="Hello CODEGUARD\n",
            cpu_time_limit_ms=3000,
            memory_limit_mb=256
        )
        assert res["status_id"] == 3  # Accepted in Judge0
        assert res["stdout"].strip() == "Hello CODEGUARD"

    def test_live_python_runtime_error(self, require_live_judge0):
        res = Judge0Adapter.execute_in_sandbox(
            source_code="x = 1 / 0",
            language="PYTHON",
            stdin_data="",
            expected_output="",
            cpu_time_limit_ms=2000,
            memory_limit_mb=256
        )
        assert res["status_id"] != 3  # Not accepted
        assert "ZeroDivisionError" in (res.get("stderr") or "")

    def test_live_python_timeout(self, require_live_judge0):
        res = Judge0Adapter.execute_in_sandbox(
            source_code="while True: pass",
            language="PYTHON",
            stdin_data="",
            expected_output="",
            cpu_time_limit_ms=1000,
            memory_limit_mb=128
        )
        assert res["status_id"] == 5  # Time Limit Exceeded

    def test_live_cpp_execution(self, require_live_judge0):
        code = """
        #include <iostream>
        int main() {
            std::cout << "Hello C++" << std::endl;
            return 0;
        }
        """
        res = Judge0Adapter.execute_in_sandbox(
            source_code=code,
            language="CPP",
            stdin_data="",
            expected_output="Hello C++\n",
            cpu_time_limit_ms=4000,
            memory_limit_mb=256
        )
        assert res["status_id"] == 3
        assert res["stdout"].strip() == "Hello C++"

    def test_live_java_execution(self, require_live_judge0):
        code = """
        public class Main {
            public static void main(String[] args) {
                System.out.println("Hello Java");
            }
        }
        """
        res = Judge0Adapter.execute_in_sandbox(
            source_code=code,
            language="JAVA",
            stdin_data="",
            expected_output="Hello Java\n",
            cpu_time_limit_ms=5000,
            memory_limit_mb=512
        )
        assert res["status_id"] == 3
        assert res["stdout"].strip() == "Hello Java"
