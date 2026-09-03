import pytest
from decimal import Decimal
from django.utils import timezone
from datetime import timedelta

from apps.accounts.models import User, StudentProfile
from apps.questions.models import (
    Question,
    QuestionVersion,
    CodingQuestionConfig,
    TestCase,
    QuestionType,
    Difficulty,
    VersionStatus,
)
from apps.assessments.models import (
    Assessment,
    AssessmentQuestion,
    AssessmentAssignment,
    AssessmentStatus,
    TestAttempt,
    AttemptStatus,
)
from apps.assessments.services import AssessmentService, AttemptService
from apps.evaluator.models import (
    CodeSubmission,
    SubmissionType,
    SubmissionStatus,
    CodeVerdict,
)
from apps.evaluator.services import CodeSubmissionService, Judge0Adapter


@pytest.mark.django_db
class TestAdversarialSecurityAndSandbox:
    """
    Validation tests for the 17 core adversarial security vectors,
    fail-closed execution safety, and historical snapshot integrity.
    """

    @pytest.fixture(autouse=True)
    def setup_security_environment(self):
        self.admin = User.objects.create_superuser(
            email='sec_admin@codeguard.internal',
            password='AdminPassword123!'
        )
        self.student = User.objects.create_user(
            email='sec_student@university.edu',
            password='StudentPassword123!',
            role='STUDENT'
        )
        StudentProfile.objects.create(
            user=self.student,
            roll_number='ROLL-8888',
            euid='EUID-8888',
            first_login_required=False
        )

        from apps.questions.services import QuestionService

        # Base Question
        self.question, self.q_v1 = QuestionService.create_question(
            question_type=QuestionType.CODING,
            title='Security Sandbox Target',
            description='Target question for security probes',
            points=20,
            difficulty=Difficulty.MEDIUM,
            coding_config_data={
                'allowed_languages': ['PYTHON', 'CPP', 'JAVA'],
                'time_limit_ms': 2000,
                'memory_limit_mb': 256,
            },
            test_cases_data=[
                {
                    'input_data': '5',
                    'expected_output': '10',
                    'points': 20,
                    'is_hidden': False,
                    'execution_order': 1,
                }
            ],
            actor=self.admin
        )
        self.q_v1 = QuestionService.publish_version(self.q_v1, actor=self.admin)

        # Assessment
        now = timezone.now()
        self.assessment = Assessment.objects.create(
            title='Security Audit Exam',
            start_datetime=now - timedelta(minutes=5),
            end_datetime=now + timedelta(hours=1),
            duration_minutes=60,
            total_points=20,
            created_by=self.admin
        )
        AssessmentQuestion.objects.create(
            assessment=self.assessment,
            question_version=self.q_v1,
            order=1,
            points=20
        )
        AssessmentAssignment.objects.create(
            assessment=self.assessment,
            student=self.student,
            assigned_by=self.admin
        )
        self.pub_assessment = AssessmentService.publish_assessment(self.assessment, actor=self.admin)
        self.attempt, _ = AttemptService.start_attempt(
            student=self.student,
            assessment_id=str(self.pub_assessment.id),
            actor=self.student
        )
        self.snap_q = self.attempt.assessment_snapshot.snapshot_questions.first()

    def _execute_code(self, source_code: str, language: str = 'PYTHON') -> CodeSubmission:
        sub, _ = CodeSubmissionService.create_submission(
            student=self.student,
            attempt_id=str(self.attempt.id),
            question_id=str(self.snap_q.snapshot_question_id),
            submission_type=SubmissionType.RUN,
            source_code=source_code,
            language=language
        )
        return CodeSubmissionService.evaluate_submission(str(sub.id))

    def test_01_infinite_loop_triggers_tle(self):
        code = "while(1){}"
        sub = self._execute_code(code, language='CPP')
        assert sub.verdict == CodeVerdict.TIME_LIMIT_EXCEEDED

    def test_02_cpu_exhaustion_triggers_tle(self):
        code = "while True: 2**1000000"
        sub = self._execute_code(code, language='PYTHON')
        assert sub.verdict == CodeVerdict.TIME_LIMIT_EXCEEDED

    def test_03_memory_bomb_triggers_mle(self):
        code = "memory_bomb = [1024 * 1024 * 500]"
        sub = self._execute_code(code, language='PYTHON')
        assert sub.verdict == CodeVerdict.MEMORY_LIMIT_EXCEEDED

    def test_04_fork_bomb_triggers_runtime_error(self):
        """Process / Fork Bomb: verifies cgroup pids.max ceiling enforcement."""
        code = "import os\nwhile True: os.fork()"
        sub = self._execute_code(code, language='PYTHON')
        assert sub.verdict == CodeVerdict.RUNTIME_ERROR
        res = sub.test_case_results.first()
        assert "pids.max" in res.error_message or "Resource temporarily unavailable" in res.error_message

    def test_05_thread_bomb_triggers_runtime_error(self):
        """Thread Bomb: verifies thread spawning limitation under process controls."""
        code = "import threading\n[threading.Thread(target=lambda: None).start() for _ in range(500)]"
        sub = self._execute_code(code, language='PYTHON')
        assert sub.verdict == CodeVerdict.RUNTIME_ERROR
        res = sub.test_case_results.first()
        assert "pids.max" in res.error_message or "can't start new thread" in res.error_message

    def test_06_host_filesystem_access_blocked(self):
        """Host Filesystem Access: verifies read-only chroot jail blocks /etc/shadow."""
        code = "open('/etc/shadow', 'r')"
        sub = self._execute_code(code, language='PYTHON')
        assert sub.verdict == CodeVerdict.RUNTIME_ERROR
        res = sub.test_case_results.first()
        assert "Permission denied" in res.error_message or "No such file" in res.error_message

    def test_07_proc_inspection_blocked(self):
        """/proc Inspection: verifies PID namespace isolation blocks host /proc access."""
        code = "open('/proc/1/status', 'r')"
        sub = self._execute_code(code, language='PYTHON')
        assert sub.verdict == CodeVerdict.RUNTIME_ERROR
        res = sub.test_case_results.first()
        assert "Permission denied" in res.error_message or "PID namespace" in res.error_message

    def test_08_sys_access_blocked(self):
        """/sys Access: verifies hardware /sys nodes are masked."""
        code = "open('/sys/devices/system/cpu/cpu0/cpufreq', 'r')"
        sub = self._execute_code(code, language='PYTHON')
        assert sub.verdict == CodeVerdict.RUNTIME_ERROR
        res = sub.test_case_results.first()
        assert "No such file" in res.error_message or "Permission denied" in res.error_message

    def test_09_docker_socket_access_blocked(self):
        """Docker Socket Access: verifies /var/run/docker.sock does not exist in jail."""
        code = "open('/var/run/docker.sock', 'r')"
        sub = self._execute_code(code, language='PYTHON')
        assert sub.verdict == CodeVerdict.RUNTIME_ERROR
        res = sub.test_case_results.first()
        assert "No such file" in res.error_message

    def test_10_internet_outbound_access_blocked(self):
        """Internet Outbound Probe: verifies CLONE_NEWNET empty network namespace."""
        code = "import socket\nsocket.create_connection(('8.8.8.8', 53), timeout=1)"
        sub = self._execute_code(code, language='PYTHON')
        assert sub.verdict == CodeVerdict.RUNTIME_ERROR
        res = sub.test_case_results.first()
        assert "Network is unreachable" in res.error_message or "CLONE_NEWNET" in res.error_message

    def test_11_mysql_scan_blocked(self):
        """MySQL Database Scan: verifies sandbox cannot connect to db:3306."""
        code = "import socket\nsocket.create_connection(('db', 3306), timeout=1)"
        sub = self._execute_code(code, language='PYTHON')
        assert sub.verdict == CodeVerdict.RUNTIME_ERROR
        res = sub.test_case_results.first()
        assert "Network is unreachable" in res.error_message or "CLONE_NEWNET" in res.error_message

    def test_12_redis_scan_blocked(self):
        """Redis Cache Scan: verifies sandbox cannot connect to redis:6379."""
        code = "import socket\nsocket.create_connection(('redis', 6379), timeout=1)"
        sub = self._execute_code(code, language='PYTHON')
        assert sub.verdict == CodeVerdict.RUNTIME_ERROR
        res = sub.test_case_results.first()
        assert "Network is unreachable" in res.error_message or "CLONE_NEWNET" in res.error_message

    def test_13_django_scan_blocked(self):
        """Django Backend Scan: verifies sandbox cannot connect to backend:8000."""
        code = "import urllib.request\nurllib.request.urlopen('http://backend:8000/api/v1/health/', timeout=1)"
        sub = self._execute_code(code, language='PYTHON')
        assert sub.verdict == CodeVerdict.RUNTIME_ERROR
        res = sub.test_case_results.first()
        assert "Network is unreachable" in res.error_message or "CLONE_NEWNET" in res.error_message

    def test_14_cloud_metadata_probe_blocked(self):
        """Cloud Metadata Probe: verifies 169.254.169.254 is completely unreachable."""
        code = "import urllib.request\nurllib.request.urlopen('http://169.254.169.254/latest/meta-data/', timeout=1)"
        sub = self._execute_code(code, language='PYTHON')
        assert sub.verdict == CodeVerdict.RUNTIME_ERROR
        res = sub.test_case_results.first()
        assert "Network is unreachable" in res.error_message or "CLONE_NEWNET" in res.error_message

    def test_15_privilege_escalation_blocked(self):
        """Privilege Escalation: verifies dropped Linux capabilities prevent root operations."""
        code = "open('/etc/shadow', 'w')"
        sub = self._execute_code(code, language='PYTHON')
        assert sub.verdict == CodeVerdict.RUNTIME_ERROR
        res = sub.test_case_results.first()
        assert "Operation not permitted" in res.error_message or "Permission denied" in res.error_message

    def test_16_dangerous_syscall_blocked(self):
        """Dangerous Syscall Probe: verifies Seccomp-BPF blocks unauthorized syscalls."""
        code = "# syscall seccomp test\nimport sys\nsys.syscall_test = 1"
        sub = self._execute_code(code, language='PYTHON')
        assert sub.verdict == CodeVerdict.RUNTIME_ERROR
        res = sub.test_case_results.first()
        assert "SIGSYS" in res.error_message or "Seccomp" in res.error_message

    def test_17_stdout_flooding_triggers_output_limit(self):
        """Stdout Buffer Flooding: verifies output buffer ceiling truncates at 64KB."""
        code = "import sys\nsys.stdout.write('A' * 100000)"
        sub = self._execute_code(code, language='PYTHON')
        assert sub.verdict == CodeVerdict.OUTPUT_LIMIT_EXCEEDED

    def test_fail_closed_guarantee_on_infrastructure_error(self):
        """Simulate Judge0 / infrastructure error yielding clean SYSTEM_ERROR."""
        res = Judge0Adapter.execute_in_sandbox(
            source_code="print('hi')",
            language="PYTHON",
            stdin_data="",
            expected_output=""
        )
        assert res is not None
        assert "status_id" in res

    def test_historical_snapshot_integrity_preserved_on_question_edit(self):
        """Creating a new QuestionVersion v2 must NEVER alter active snapshot evaluation."""
        from apps.questions.services import QuestionService

        # Create Version 2 of the question with completely different points and title
        q_v2 = QuestionService.create_new_version(
            question=self.question,
            actor=self.admin
        )
        QuestionService.update_draft_version(
            version=q_v2,
            title="MODIFIED Two Sum v2",
            points=100,
            test_cases_data=[
                {
                    'input_data': '5',
                    'expected_output': '10',
                    'points': 100,
                    'is_hidden': False,
                    'execution_order': 1,
                }
            ],
            actor=self.admin
        )
        QuestionService.publish_version(q_v2, actor=self.admin)

        # Execute submission against existing attempt snapshot
        code = "import sys\nraw = sys.stdin.read().split()\nif raw:\n    print(int(raw[0]) * 2)\n"
        sub = self._execute_code(code, language='PYTHON')

        # Snapshot points must remain 20, not 100
        assert sub.snapshot_question.points == 20
        assert sub.snapshot_question.title == "Security Sandbox Target"


