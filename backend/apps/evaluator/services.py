import base64
import hashlib
import json
import logging
import math
import re
import time
import requests
from decimal import Decimal
from typing import Dict, List, Optional, Tuple, Any

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from rest_framework.exceptions import ValidationError as DRFValidationError
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from apps.assessments.models import (
    TestAttempt,
    AttemptStatus,
    AssessmentSnapshotQuestion,
    AttemptAnswer,
)
from apps.assessments.services import AttemptTimerService
from apps.evaluator.models import (
    CodeSubmission,
    CodeTestCaseResult,
    SubmissionType,
    SubmissionStatus,
    CodeVerdict,
    TestCaseVerdict,
)

logger = logging.getLogger('codeguard.evaluator')


# ==============================================================================
# 1. Output Comparison Service
# ==============================================================================

class OutputComparisonService:
    """
    Deterministic output comparison algorithms.
    Supported modes: EXACT_STRIPPED, FLOAT_TOLERANT, TOKEN_MATCH.
    """

    @classmethod
    def compare_exact_stripped(
        cls,
        actual: str,
        expected: str,
        ignore_trailing_whitespace: bool = True,
        ignore_trailing_empty_lines: bool = True,
        case_sensitive: bool = True
    ) -> bool:
        if actual is None:
            actual = ""
        if expected is None:
            expected = ""

        # 1. Normalize newlines (CRLF and CR -> LF)
        norm_actual = actual.replace('\r\n', '\n').replace('\r', '\n')
        norm_expected = expected.replace('\r\n', '\n').replace('\r', '\n')

        # 2. Case sensitivity
        if not case_sensitive:
            norm_actual = norm_actual.lower()
            norm_expected = norm_expected.lower()

        # 3. Line-by-line processing
        actual_lines = norm_actual.split('\n')
        expected_lines = norm_expected.split('\n')

        if ignore_trailing_whitespace:
            actual_lines = [line.rstrip(' \t') for line in actual_lines]
            expected_lines = [line.rstrip(' \t') for line in expected_lines]

        if ignore_trailing_empty_lines:
            while actual_lines and actual_lines[-1] == '':
                actual_lines.pop()
            while expected_lines and expected_lines[-1] == '':
                expected_lines.pop()

        return actual_lines == expected_lines

    @classmethod
    def compare_float_tolerant(
        cls,
        actual: str,
        expected: str,
        epsilon: float = 1e-6
    ) -> bool:
        if actual is None:
            actual = ""
        if expected is None:
            expected = ""

        actual_tokens = actual.split()
        expected_tokens = expected.split()

        if len(actual_tokens) != len(expected_tokens):
            return False

        for a_tok, e_tok in zip(actual_tokens, expected_tokens):
            try:
                a_val = float(a_tok)
                e_val = float(e_tok)
                tol = max(epsilon, epsilon * abs(e_val))
                if not math.isclose(a_val, e_val, abs_tol=tol, rel_tol=epsilon):
                    return False
            except ValueError:
                # Fallback to string equality if not convertible to float
                if a_tok != e_tok:
                    return False
        return True

    @classmethod
    def compare_token_match(cls, actual: str, expected: str, case_sensitive: bool = True) -> bool:
        if actual is None:
            actual = ""
        if expected is None:
            expected = ""

        if not case_sensitive:
            actual = actual.lower()
            expected = expected.lower()

        return actual.split() == expected.split()

    @classmethod
    def compare(cls, actual: str, expected: str, policy: Optional[Dict[str, Any]] = None) -> bool:
        if not policy:
            policy = {}

        mode = policy.get('mode', 'EXACT_STRIPPED')
        case_sensitive = policy.get('case_sensitive', True)
        ignore_trailing_ws = policy.get('ignore_trailing_whitespace', True)
        ignore_trailing_nl = policy.get('ignore_trailing_empty_lines', True)
        epsilon = float(policy.get('float_tolerance_epsilon', 1e-6))

        if mode == 'FLOAT_TOLERANT':
            return cls.compare_float_tolerant(actual, expected, epsilon=epsilon)
        elif mode == 'TOKEN_MATCH':
            return cls.compare_token_match(actual, expected, case_sensitive=case_sensitive)
        else:
            return cls.compare_exact_stripped(
                actual,
                expected,
                ignore_trailing_whitespace=ignore_trailing_ws,
                ignore_trailing_empty_lines=ignore_trailing_nl,
                case_sensitive=case_sensitive
            )


# ==============================================================================
# 2. Scoring Service
# ==============================================================================

class ScoringService:
    """
    Deterministic partial scoring calculation for coding questions.
    """

    @classmethod
    def calculate_score(
        cls,
        test_case_results: List[Dict[str, Any]],
        total_question_points: int,
        negative_marking_enabled: bool = False,
        negative_points: int = 0
    ) -> Tuple[Decimal, int, int]:
        total_count = len(test_case_results)
        if total_count == 0:
            return Decimal('0.00'), 0, 0

        passed_count = sum(1 for r in test_case_results if r['verdict'] == TestCaseVerdict.PASSED)
        earned_points = sum(Decimal(str(r.get('points_awarded', 0))) for r in test_case_results if r['verdict'] == TestCaseVerdict.PASSED)

        if passed_count == total_count:
            # Full pass
            score = Decimal(str(total_question_points))
        elif passed_count == 0 and negative_marking_enabled:
            # 0 tests passed with negative marking active -> penalty floored at 0
            score = max(Decimal('0.00'), Decimal(str(-negative_points)))
        else:
            # Partial pass -> earned points
            score = earned_points

        return score, passed_count, total_count


# ==============================================================================
# 3. Judge0 / Sandbox Execution Adapter
# ==============================================================================

class Judge0Adapter:
    """
    Adapter interfacing with the sandboxed Judge0 CE execution broker.
    Maps language tags to runtime IDs and enforces execution/output limits.
    """

    LANGUAGE_IDS = {
        'PYTHON': 71,   # Python 3.11/3.12
        'CPP': 54,      # C++ (GCC 13 / C++20)
        'JAVA': 62,     # Java (OpenJDK 17)
    }

    @classmethod
    def get_language_id(cls, language: str) -> int:
        lang_upper = (language or '').upper()
        if lang_upper in cls.LANGUAGE_IDS:
            return cls.LANGUAGE_IDS[lang_upper]
        raise DRFValidationError({"language": f"Unsupported execution language: {language}"})

    @classmethod
    def execute_in_sandbox(
        cls,
        source_code: str,
        language: str,
        stdin_data: str,
        expected_output: str,
        cpu_time_limit_ms: int = 2000,
        memory_limit_mb: int = 256,
        max_stdout_bytes: int = 65536
    ) -> Dict[str, Any]:
        """
        Executes code strictly within the external isolated Judge0 CE sandbox via HTTP API.
        The Django/Celery application process NEVER executes candidate code.
        If the external sandbox is unavailable or returns an infrastructure failure,
        execution fails closed with an internal error and NEVER falls back to host execution.
        """
        judge0_url = getattr(settings, 'JUDGE0_URL', 'http://127.0.0.1:2358').rstrip('/')
        api_key = getattr(settings, 'JUDGE0_API_KEY', '')
        timeout = getattr(settings, 'JUDGE0_TIMEOUT_SECONDS', 10)
        lang_id = cls.get_language_id(language)

        payload = {
            "source_code": source_code,
            "language_id": lang_id,
            "stdin": stdin_data or "",
            "expected_output": expected_output or "",
            "cpu_time_limit": max(0.1, cpu_time_limit_ms / 1000.0),
            "memory_limit": memory_limit_mb * 1024,
            "max_file_size": max_stdout_bytes,
        }

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if api_key:
            headers["X-Auth-Token"] = api_key
            headers["X-RapidAPI-Key"] = api_key

        endpoint = f"{judge0_url}/submissions/?base64_encoded=false&wait=true"

        try:
            response = requests.post(endpoint, json=payload, headers=headers, timeout=timeout)
            if response.status_code not in (200, 201):
                logger.error(f"Judge0 external sandbox HTTP error {response.status_code}: {response.text}")
                return cls._fail_closed_response(
                    f"External sandbox returned error HTTP {response.status_code}"
                )

            data = response.json()
            status_obj = data.get('status') or {}
            status_id = status_obj.get('id', 13)
            status_desc = status_obj.get('description', 'Internal Error')

            raw_time = data.get('time')
            try:
                exec_time_sec = float(raw_time) if raw_time is not None else 0.0
            except (ValueError, TypeError):
                exec_time_sec = 0.0

            raw_mem = data.get('memory')
            try:
                mem_kb = int(raw_mem) if raw_mem is not None else 0
            except (ValueError, TypeError):
                mem_kb = 0

            return {
                "status_id": status_id,
                "status_description": status_desc,
                "compile_output": data.get('compile_output'),
                "stdout": data.get('stdout'),
                "stderr": data.get('stderr'),
                "time": max(0.01, round(exec_time_sec, 3)),
                "memory": mem_kb
            }
        except requests.exceptions.RequestException as e:
            logger.error(f"Judge0 external sandbox connection error: {e}")
            return cls._fail_closed_response(f"Sandbox unavailable: {e}")
        except Exception as e:
            logger.error(f"Unexpected error interfacing with external sandbox: {e}")
            return cls._fail_closed_response(f"Execution interface error: {e}")

    @classmethod
    def _fail_closed_response(cls, reason: str) -> Dict[str, Any]:
        """
        Controlled fail-closed execution error response.
        NEVER falls back to host execution or in-process execution.
        """
        return {
            "status_id": 13,  # Internal Error in Judge0 / Fail-Closed
            "status_description": "Sandbox Unavailable",
            "compile_output": None,
            "stdout": None,
            "stderr": f"FAIL_CLOSED: {reason}",
            "time": 0.0,
            "memory": 0
        }


# ==============================================================================
# 4. Code Submission & Evaluation Domain Service
# ==============================================================================

class CodeSubmissionService:
    """
    Authoritative domain service orchestrating code submission, deduplication,
    rate limiting, concurrency caps, sandbox execution, and scoring.
    """

    @classmethod
    def create_submission(
        cls,
        student,
        attempt_id: str,
        question_id: str,
        submission_type: str,
        source_code: str,
        language: str,
        client_nonce: Optional[str] = None,
        custom_input: Optional[str] = None
    ) -> Tuple[CodeSubmission, bool]:
        """
        Creates an asynchronous CodeSubmission record in QUEUED status.
        Validates attempt ownership, server timer, question snapshot binding, and quotas.
        """
        # 1. Fetch attempt and enforce ownership
        try:
            attempt = TestAttempt.objects.select_related('assessment', 'assessment_snapshot').get(id=attempt_id)
        except TestAttempt.DoesNotExist:
            raise DRFValidationError({"attempt": "Test attempt does not exist."})

        if attempt.student != student:
            raise PermissionDenied("You do not have permission to submit code for this attempt.")

        # 2. Enforce Attempt Status & Server Expiration
        if attempt.status != AttemptStatus.IN_PROGRESS:
            raise DRFValidationError({"attempt": f"Cannot execute code on attempt in {attempt.status} status."})

        if AttemptTimerService.check_and_expire_attempt_if_needed(attempt):
            raise DRFValidationError({"timer": "Test attempt has expired. Submissions are no longer accepted."})

        # 3. Resolve Snapshot Question
        snapshot = attempt.assessment_snapshot
        try:
            snap_q = snapshot.snapshot_questions.get(snapshot_question_id=str(question_id))
        except AssessmentSnapshotQuestion.DoesNotExist:
            raise DRFValidationError({"question_id": "Question is not part of this assessment attempt snapshot."})

        if snap_q.question_type != 'CODING':
            raise DRFValidationError({"question_id": "Code execution is only supported for CODING questions."})

        # 4. Validate Language
        allowed_langs = snap_q.coding_config.get('allowed_languages', ['PYTHON', 'CPP', 'JAVA'])
        lang_upper = (language or '').upper()
        if lang_upper not in allowed_langs:
            raise DRFValidationError({"language": f"Language '{language}' is not permitted. Allowed: {allowed_langs}"})

        # 5. Validate Source Code Size (Max 64KB)
        if not source_code or len(source_code.strip()) == 0:
            raise DRFValidationError({"source_code": "Source code cannot be empty."})
        if len(source_code) > 65536:
            raise DRFValidationError({"source_code": "Source code exceeds maximum limit of 64KB."})

        # 6. Sliding Window Rate Limiting (Run: 6/min, Submit: 3/min)
        rate_key = f"rl:code:{student.id}:{attempt_id}:{snap_q.id}:{submission_type}"
        limit = 6 if submission_type == SubmissionType.RUN else 3
        current_count = cache.get(rate_key, 0)
        if current_count >= limit:
            raise DRFValidationError({
                "rate_limit": f"Rate limit exceeded for {submission_type}. Maximum {limit} requests per minute."
            })
        cache.set(rate_key, current_count + 1, timeout=60)

        # 7. Concurrency Quotas
        active_jobs = CodeSubmission.objects.filter(
            attempt=attempt,
            status__in=[SubmissionStatus.PROCESSING, SubmissionStatus.COMPILING, SubmissionStatus.RUNNING]
        ).count()
        if active_jobs >= 1:
            raise DRFValidationError({
                "concurrency": "You already have an active execution job in progress. Please wait for it to complete."
            })

        queued_jobs = CodeSubmission.objects.filter(
            attempt=attempt,
            status=SubmissionStatus.QUEUED
        ).count()
        if queued_jobs >= 2:
            raise DRFValidationError({
                "concurrency": "Execution queue backlog limit reached (max 2 queued jobs). Please wait."
            })

        # 8. Idempotency Hashing
        code_hash = hashlib.sha256(source_code.encode('utf-8')).hexdigest()
        idemp_raw = f"{student.id}:{attempt_id}:{snap_q.id}:{submission_type}:{client_nonce or ''}:{code_hash}"
        idemp_key = hashlib.sha256(idemp_raw.encode('utf-8')).hexdigest()

        existing = CodeSubmission.objects.filter(idempotency_key=idemp_key).first()
        if existing:
            # Reusing same key with same payload -> return existing
            if existing.source_code == source_code:
                return existing, False
            else:
                raise DRFValidationError({
                    "idempotency": "Idempotency key reused with different request payload."
                })

        # 9. Extract Execution Policy & Environment Versions
        exec_policy = snap_q.coding_config.get('execution_policy', {})
        env_ver = exec_policy.get('environment_version', f"CG-ENV-{lang_upper}-V1")
        exec_ver = exec_policy.get('execution_policy_version', 'CG-EXEC-V1')
        cmp_ver = exec_policy.get('comparison_policy_version', 'CG-CMP-V1')

        submission = CodeSubmission.objects.create(
            attempt=attempt,
            snapshot_question=snap_q,
            submission_type=submission_type,
            source_code=source_code,
            language=lang_upper,
            environment_version=env_ver,
            execution_policy_version=exec_ver,
            comparison_policy_version=cmp_ver,
            status=SubmissionStatus.QUEUED,
            idempotency_key=idemp_key,
            max_score=snap_q.points if submission_type == SubmissionType.SUBMIT else 0
        )

        # 10. Dispatch Celery Task Asynchronously
        from apps.evaluator.tasks import evaluate_code_submission_task
        evaluate_code_submission_task.delay(str(submission.id))

        # 11. Publish WebSocket Event
        cls._broadcast_ws_event(submission, "CODE_SUBMISSION_QUEUED")

        return submission, True

    @classmethod
    def evaluate_submission(cls, submission_id: str) -> CodeSubmission:
        """
        Authoritative evaluation handler invoked by Celery worker.
        Executes test cases, normalizes output, evaluates scores, and persists results.
        """
        with transaction.atomic():
            try:
                submission = CodeSubmission.objects.select_for_update().select_related(
                    'attempt', 'snapshot_question', 'snapshot_question__snapshot'
                ).get(id=submission_id)
            except CodeSubmission.DoesNotExist:
                logger.error(f"CodeSubmission {submission_id} does not exist.")
                return None

            # Prevent re-evaluation of terminal state
            if submission.status in [SubmissionStatus.COMPLETED, SubmissionStatus.FAILED, SubmissionStatus.CANCELLED]:
                return submission

            submission.status = SubmissionStatus.PROCESSING
            submission.started_at = timezone.now()
            submission.save(update_fields=['status', 'started_at'])

        cls._broadcast_ws_event(submission, "CODE_SUBMISSION_PROCESSING")

        attempt = submission.attempt
        snap_q = submission.snapshot_question
        snapshot = snap_q.snapshot
        exec_policy = snap_q.coding_config.get('execution_policy', {})
        cmp_policy = exec_policy.get('comparison_policy', {'mode': 'EXACT_STRIPPED'})

        cpu_limit_ms = exec_policy.get('cpu_time_limit_ms', snap_q.coding_config.get('time_limit_ms', 2000))
        mem_limit_mb = exec_policy.get('memory_limit_mb', snap_q.coding_config.get('memory_limit_mb', 256))
        max_stdout = exec_policy.get('max_stdout_bytes', 65536)

        # Resolve Test Cases
        test_cases_to_run = []
        if submission.submission_type == SubmissionType.RUN:
            # RUN: Public test cases only
            public_tcs = snap_q.coding_config.get('public_test_cases', [])
            test_cases_to_run = [
                {
                    "index": i + 1,
                    "input": tc.get('input_data', ''),
                    "expected_output": tc.get('expected_output', ''),
                    "points": tc.get('points', 0),
                    "is_hidden": False
                }
                for i, tc in enumerate(public_tcs)
            ]
        else:
            # SUBMIT: All test cases from server_evaluation_bundle
            questions_eval = snapshot.server_evaluation_bundle.get('questions_eval', {})
            q_eval = questions_eval.get(snap_q.snapshot_question_id, {})
            server_coding_eval = q_eval.get('server_coding_eval', {})
            all_tcs = server_coding_eval.get('all_test_cases', [])
            if not all_tcs:
                all_tcs = snapshot.server_evaluation_bundle.get(snap_q.snapshot_question_id, {}).get('all_test_cases', [])
            if not all_tcs:
                # Fallback to public test cases if none in bundle
                all_tcs = snap_q.coding_config.get('public_test_cases', [])

            test_cases_to_run = [
                {
                    "index": i + 1,
                    "input": tc.get('input_data', ''),
                    "expected_output": tc.get('expected_output', ''),
                    "points": tc.get('points', 1),
                    "is_hidden": tc.get('is_hidden', False)
                }
                for i, tc in enumerate(all_tcs)
            ]

        # Execute Test Cases via Judge0
        tc_results_data = []
        max_time_ms = 0
        max_mem_kb = 0
        overall_verdict = CodeVerdict.ACCEPTED
        compilation_error_log = ""

        for tc in test_cases_to_run:
            res = Judge0Adapter.execute_in_sandbox(
                source_code=submission.source_code,
                language=submission.language,
                stdin_data=tc['input'],
                expected_output=tc['expected_output'],
                cpu_time_limit_ms=cpu_limit_ms,
                memory_limit_mb=mem_limit_mb,
                max_stdout_bytes=max_stdout
            )

            status_id = res.get('status_id', 3)
            actual_out = res.get('stdout', '') or ''
            stderr_out = res.get('stderr', '')
            compile_out = res.get('compile_output', '')
            exec_time_ms = int(res.get('time', 0) * 1000)
            mem_kb = int(res.get('memory', 0))

            max_time_ms = max(max_time_ms, exec_time_ms)
            max_mem_kb = max(max_mem_kb, mem_kb)

            tc_verdict = TestCaseVerdict.PASSED

            if res.get('status_description') == 'Sandbox Unavailable' or (stderr_out and 'FAIL_CLOSED' in stderr_out):
                tc_verdict = TestCaseVerdict.RUNTIME_ERROR
                overall_verdict = CodeVerdict.SYSTEM_ERROR
                tc_results_data.append({
                    "test_case_index": tc['index'],
                    "is_hidden": tc['is_hidden'],
                    "verdict": tc_verdict,
                    "points_awarded": Decimal('0.00'),
                    "max_points": Decimal(str(tc['points'])),
                    "execution_time_ms": exec_time_ms,
                    "memory_used_kb": mem_kb,
                    "public_input": tc['input'] if not tc['is_hidden'] else None,
                    "expected_output": tc['expected_output'] if not tc['is_hidden'] else None,
                    "actual_output": None,
                    "error_message": stderr_out if not tc['is_hidden'] else "Sandbox execution failure",
                })
                break
            elif status_id == 6:  # Compilation Error
                overall_verdict = CodeVerdict.COMPILATION_ERROR
                compilation_error_log = compile_out or "Compilation failed."
                tc_verdict = TestCaseVerdict.FAILED
                break
            elif status_id == 5:  # Time Limit Exceeded
                tc_verdict = TestCaseVerdict.TIME_LIMIT_EXCEEDED
                if overall_verdict == CodeVerdict.ACCEPTED:
                    overall_verdict = CodeVerdict.TIME_LIMIT_EXCEEDED
            elif status_id == 12:  # Memory Limit Exceeded
                tc_verdict = TestCaseVerdict.MEMORY_LIMIT_EXCEEDED
                if overall_verdict == CodeVerdict.ACCEPTED:
                    overall_verdict = CodeVerdict.MEMORY_LIMIT_EXCEEDED
            elif status_id == 13:  # Output Limit Exceeded
                tc_verdict = TestCaseVerdict.FAILED
                if overall_verdict == CodeVerdict.ACCEPTED:
                    overall_verdict = CodeVerdict.OUTPUT_LIMIT_EXCEEDED
            elif status_id not in [3]:  # Runtime Error
                tc_verdict = TestCaseVerdict.RUNTIME_ERROR
                if overall_verdict == CodeVerdict.ACCEPTED:
                    overall_verdict = CodeVerdict.RUNTIME_ERROR
            else:
                # Compare output
                matched = OutputComparisonService.compare(actual_out, tc['expected_output'], cmp_policy)
                if matched:
                    tc_verdict = TestCaseVerdict.PASSED
                else:
                    tc_verdict = TestCaseVerdict.FAILED
                    if overall_verdict == CodeVerdict.ACCEPTED:
                        overall_verdict = CodeVerdict.WRONG_ANSWER

            pts_awarded = Decimal(str(tc['points'])) if tc_verdict == TestCaseVerdict.PASSED else Decimal('0.00')

            tc_results_data.append({
                "test_case_index": tc['index'],
                "is_hidden": tc['is_hidden'],
                "verdict": tc_verdict,
                "points_awarded": pts_awarded,
                "max_points": Decimal(str(tc['points'])),
                "execution_time_ms": exec_time_ms,
                "memory_used_kb": mem_kb,
                # Public-only fields; strictly NULL for hidden
                "public_input": tc['input'] if not tc['is_hidden'] else None,
                "expected_output": tc['expected_output'] if not tc['is_hidden'] else None,
                "actual_output": actual_out if not tc['is_hidden'] else None,
                "error_message": stderr_out if not tc['is_hidden'] else None,
            })

        # Calculate Score
        with transaction.atomic():
            submission = CodeSubmission.objects.select_for_update().get(id=submission_id)

            if overall_verdict == CodeVerdict.COMPILATION_ERROR:
                final_score = Decimal('0.00')
                passed_count = 0
            else:
                final_score, passed_count, _ = ScoringService.calculate_score(
                    test_case_results=tc_results_data,
                    total_question_points=snap_q.points,
                    negative_marking_enabled=snap_q.negative_marking_enabled,
                    negative_points=snap_q.negative_points
                )

            # Persist CodeTestCaseResults
            submission.test_case_results.all().delete()
            for r in tc_results_data:
                CodeTestCaseResult.objects.create(
                    submission=submission,
                    test_case_index=r['test_case_index'],
                    is_hidden=r['is_hidden'],
                    verdict=r['verdict'],
                    points_awarded=r['points_awarded'],
                    max_points=r['max_points'],
                    execution_time_ms=r['execution_time_ms'],
                    memory_used_kb=r['memory_used_kb'],
                    public_input=r['public_input'],
                    expected_output=r['expected_output'],
                    actual_output=r['actual_output'],
                    error_message=r['error_message']
                )

            # Update CodeSubmission
            if overall_verdict == CodeVerdict.SYSTEM_ERROR:
                submission.status = SubmissionStatus.FAILED
            else:
                submission.status = SubmissionStatus.COMPLETED
            submission.verdict = overall_verdict
            submission.total_test_cases = len(test_cases_to_run)
            submission.passed_test_cases = passed_count
            submission.score_awarded = final_score if submission.submission_type == SubmissionType.SUBMIT else Decimal('0.00')
            submission.execution_time_ms = max_time_ms
            submission.memory_used_kb = max_mem_kb
            submission.compilation_error = compilation_error_log
            submission.completed_at = timezone.now()
            submission.save()

            # If SUBMIT: Update AttemptAnswer
            if submission.submission_type == SubmissionType.SUBMIT:
                ans, _ = AttemptAnswer.objects.get_or_create(
                    attempt=attempt,
                    snapshot_question=snap_q,
                    defaults={
                        'question_id': snap_q.snapshot_question_id,
                        'question_type': 'CODING',
                        'revision': 1
                    }
                )
                ans.code_response = submission.source_code
                ans.code_language = submission.language
                ans.is_answered = True
                ans.revision = F('revision') + 1
                ans.save()

        # Broadcast completed WebSocket event
        cls._broadcast_ws_event(submission, "CODE_SUBMISSION_COMPLETED")

        return submission

    @classmethod
    def _broadcast_ws_event(cls, submission: CodeSubmission, event_type: str):
        """
        Publishes real-time push event to Django Channels attempt group.
        """
        try:
            channel_layer = get_channel_layer()
            group_name = f"attempt_{submission.attempt_id}"
            payload = {
                "type": "attempt.event",
                "message": {
                    "type": event_type,
                    "data": {
                        "submission_id": str(submission.id),
                        "question_id": submission.snapshot_question.snapshot_question_id,
                        "submission_type": submission.submission_type,
                        "status": submission.status,
                        "verdict": submission.verdict,
                        "passed_test_cases": submission.passed_test_cases,
                        "total_test_cases": submission.total_test_cases,
                        "score_awarded": str(submission.score_awarded),
                        "max_score": submission.max_score,
                        "execution_time_ms": submission.execution_time_ms,
                        "memory_used_kb": submission.memory_used_kb,
                    }
                }
            }
            async_to_sync(channel_layer.group_send)(group_name, payload)
        except Exception as e:
            logger.warning(f"Failed to broadcast WebSocket event {event_type}: {e}")
