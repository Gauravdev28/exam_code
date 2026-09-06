"""
CODEGUARD — Production-Grade Isolated MySQL SQL Sandbox & Evaluation Engine

Executes candidate SQL queries strictly against isolated, ephemeral MySQL schemas.
Target Compatibility: MySQL 8.0+ (and forward-compatible with MySQL 8.4 LTS / 9.x).
Candidate queries are untrusted input:
- Strict single-statement SELECT / WITH validation via sqlparse token/parse-tree inspection
- Enforced read-only user permissions on disposable sandbox schemas
- Zero access to application databases, tables, or host filesystem
- Server-side statement execution timeouts and row count limits
- Deterministic structured tabular comparison (columns, rows, types, NULLs, duplicate multisets, ordering)
"""
import os
import re
import time
import uuid
import logging
from collections import Counter
from decimal import Decimal
import datetime
from typing import Any, Dict, List, Optional, Tuple

import pymysql
import sqlparse
from sqlparse.sql import Statement, Token, TokenList, Where, Identifier
from sqlparse.tokens import Keyword, DML, DDL, Punctuation, Name

from django.conf import settings
from django.utils import timezone
from django.db import transaction

from apps.evaluator.models import (
    CodeSubmission,
    CodeTestCaseResult,
    CodeVerdict,
    TestCaseVerdict,
    SubmissionStatus,
    SubmissionType,
)

logger = logging.getLogger(__name__)


# ==============================================================================
# 1. SQL Parser & Token-Level Security Validation
# ==============================================================================

class SQLValidationException(Exception):
    """Raised when candidate SQL query violates security, read-only, or structural rules."""
    pass


class SQLValidator:
    """
    Defense-in-depth static SQL validator:
    - Enforces single-statement structure
    - Permits ONLY read-only queries (SELECT or WITH ... SELECT)
    - Rejects DDL, DML, administrative commands, dangerous builtins, and system table probes
    """

    MAX_QUERY_LENGTH = 65536

    FORBIDDEN_KEYWORDS = {
        # DDL / Schema changes
        'DROP', 'ALTER', 'CREATE', 'TRUNCATE', 'RENAME',
        # DML write operations
        'INSERT', 'UPDATE', 'DELETE', 'REPLACE',
        # Access control & Admin
        'GRANT', 'REVOKE', 'SHUTDOWN', 'RELOAD', 'KILL',
        'LOCK', 'UNLOCK', 'SET', 'FLUSH', 'RESET',
        # Execution & Procedures
        'CALL', 'DO', 'HANDLER', 'EXECUTE', 'PREPARE', 'DEALLOCATE',
        # File I/O
        'LOAD', 'OUTFILE', 'DUMPFILE',
    }

    FORBIDDEN_FUNCTIONS = {
        'SLEEP', 'BENCHMARK', 'GET_LOCK', 'RELEASE_LOCK',
        'LOAD_FILE', 'SYS_EVAL', 'SYS_EXEC',
    }

    FORBIDDEN_IDENTIFIERS = {
        # MySQL internal databases
        'mysql', 'information_schema', 'performance_schema', 'sys',
        # CODEGUARD application tables
        'auth_user', 'auth_group', 'auth_permission',
        'accounts_user', 'accounts_adminprofile', 'accounts_studentprofile',
        'accounts_section', 'accounts_auditlog',
        'assessments_assessment', 'assessments_assessmentquestion',
        'assessments_assessmentsnapshot', 'assessments_assessmentsnapshotquestion',
        'assessments_testattempt', 'assessments_attemptanswer',
        'questions_question', 'questions_questionversion',
        'questions_tag', 'questions_testcase',
        'questions_codingquestionconfig', 'questions_sqlquestionconfig',
        'code_submissions', 'code_test_case_results',
        'results_assessmentresult', 'results_questionresult',
        'django_migrations', 'django_session', 'django_content_type',
        'celery_taskmeta', 'celery_tasksetmeta',
    }

    @classmethod
    def validate_candidate_query(cls, sql_text: str) -> None:
        """
        Validates candidate query text. Raises SQLValidationException on any violation.
        """
        if not sql_text or not sql_text.strip():
            raise SQLValidationException("SQL query cannot be empty.")

        if len(sql_text) > cls.MAX_QUERY_LENGTH:
            raise SQLValidationException("SQL query exceeds maximum length limit of 64KB.")

        # 1. Single Statement Validation
        # Remove empty or whitespace-only statements
        raw_statements = [s.strip() for s in sqlparse.split(sql_text) if s.strip()]
        if not raw_statements:
            raise SQLValidationException("No valid SQL statement found.")
        if len(raw_statements) > 1:
            raise SQLValidationException("Multiple SQL statements are strictly forbidden. Only a single query is allowed.")

        single_query = raw_statements[0]

        # 2. Check for semicolon injection inside statement
        # Strip trailing semicolon if present
        trimmed_query = single_query.rstrip(';').strip()
        if ';' in trimmed_query:
            raise SQLValidationException("Multiple SQL statements separated by semicolons are strictly forbidden.")

        # 3. Parse statement with sqlparse parse-tree tokens
        parsed = sqlparse.parse(trimmed_query)
        if not parsed:
            raise SQLValidationException("Failed to parse SQL statement.")

        stmt: Statement = parsed[0]
        stmt_type = stmt.get_type().upper()

        # Check statement type: Must be SELECT or WITH (CTE)
        first_token = None
        for tok in stmt.tokens:
            if not tok.is_whitespace:
                first_token = tok
                break

        first_token_val = first_token.value.upper() if first_token else ''
        if stmt_type not in ('SELECT', 'UNKNOWN') and first_token_val not in ('SELECT', 'WITH'):
            raise SQLValidationException(f"Forbidden statement type '{stmt_type}'. Only read-only SELECT queries are permitted.")

        if first_token_val not in ('SELECT', 'WITH'):
            raise SQLValidationException(f"Query must begin with SELECT or WITH, not '{first_token_val}'.")

        # 4. Deep Token Inspection
        cls._inspect_tokens(stmt.tokens)

    @classmethod
    def _inspect_tokens(cls, tokens) -> None:
        """Recursively checks tokens for forbidden keywords, functions, and system/app table references."""
        for token in tokens:
            if token.is_group:
                cls._inspect_tokens(token.tokens)
                continue

            val = token.value.strip().strip('`"\'').upper()
            if not val:
                continue

            # Check forbidden keywords
            if val in cls.FORBIDDEN_KEYWORDS:
                raise SQLValidationException(f"Forbidden SQL keyword detected: '{val}'")

            # Check forbidden functions
            clean_func = val.split('(')[0].strip()
            if clean_func in cls.FORBIDDEN_FUNCTIONS:
                raise SQLValidationException(f"Forbidden SQL function detected: '{clean_func}'")

            # Check forbidden identifiers / table names
            val_lower = val.lower()
            for forbidden_id in cls.FORBIDDEN_IDENTIFIERS:
                if val_lower == forbidden_id or val_lower.startswith(f"{forbidden_id}.") or f".{forbidden_id}" in val_lower:
                    raise SQLValidationException(f"Access to table or database '{val_lower}' is strictly forbidden.")

            # Check raw regex for dangerous patterns (INTO OUTFILE, etc.)
            raw_upper = token.value.upper()
            if 'INTO OUTFILE' in raw_upper or 'INTO DUMPFILE' in raw_upper or 'LOAD DATA' in raw_upper:
                raise SQLValidationException("File system access operations are strictly forbidden.")


# ==============================================================================
# 2. Structured Tabular Result Comparator
# ==============================================================================

class SQLResultComparator:
    """
    Deterministic tabular output comparison engine:
    - Normalizes types (int, float, Decimal, str, datetime, date)
    - Strictly preserves NULL distinction (NULL != '', NULL != 0, NULL == NULL)
    - Supports case-insensitive column name verification
    - Supports strict row ordering OR multiset/bag comparison preserving duplicate counts
    """

    FLOAT_EPSILON = 1e-5

    @classmethod
    def normalize_cell(cls, val: Any) -> Any:
        """Normalizes a single database cell value for structured equality checking."""
        if val is None:
            return None

        if isinstance(val, (datetime.datetime, datetime.date, datetime.time)):
            return val.isoformat()

        if isinstance(val, bytes):
            return val.decode('utf-8', errors='replace')

        if isinstance(val, Decimal):
            # Quantize or float-round for reliable numeric comparison
            return round(float(val), 6)

        if isinstance(val, float):
            return round(val, 6)

        if isinstance(val, int):
            return val

        if isinstance(val, str):
            return val.rstrip()

        return str(val).rstrip()

    @classmethod
    def normalize_row(cls, row: Tuple[Any, ...]) -> Tuple[Any, ...]:
        return tuple(cls.normalize_cell(v) for v in row)

    @classmethod
    def are_cells_equal(cls, a: Any, b: Any) -> bool:
        """Determines if two normalized cells match."""
        if a is None and b is None:
            return True
        if a is None or b is None:
            return False

        # Numeric tolerance comparison
        if isinstance(a, (int, float)) and isinstance(b, (int, float)):
            return abs(float(a) - float(b)) < cls.FLOAT_EPSILON

        return a == b

    @classmethod
    def are_rows_equal(cls, r1: Tuple[Any, ...], r2: Tuple[Any, ...]) -> bool:
        if len(r1) != len(r2):
            return False
        return all(cls.are_cells_equal(c1, c2) for c1, c2 in zip(r1, r2))

    @classmethod
    def compare(
        cls,
        candidate_cols: List[str],
        candidate_rows: List[Tuple[Any, ...]],
        expected_cols: List[str],
        expected_rows: List[Tuple[Any, ...]],
        ordering_required: bool = True
    ) -> Tuple[bool, str]:
        """
        Performs authoritative comparison between candidate result and expected result.
        Returns (is_correct, reason).
        """
        # 1. Column Count
        if len(candidate_cols) != len(expected_cols):
            return False, f"Column count mismatch: expected {len(expected_cols)}, got {len(candidate_cols)}."

        # 2. Column Names (Case-insensitive)
        norm_cand_cols = [c.strip().lower() for c in candidate_cols]
        norm_exp_cols = [c.strip().lower() for c in expected_cols]
        if norm_cand_cols != norm_exp_cols:
            return False, f"Column names mismatch: expected {norm_exp_cols}, got {norm_cand_cols}."

        # 3. Row Count
        if len(candidate_rows) != len(expected_rows):
            return False, f"Row count mismatch: expected {len(expected_rows)}, got {len(candidate_rows)}."

        # 4. Empty Result Sets
        if len(candidate_rows) == 0 and len(expected_rows) == 0:
            return True, "Both result sets are empty."

        # Normalize Rows
        norm_cand_rows = [cls.normalize_row(r) for r in candidate_rows]
        norm_exp_rows = [cls.normalize_row(r) for r in expected_rows]

        # 5. Row Content & Ordering
        if ordering_required:
            for idx, (c_row, e_row) in enumerate(zip(norm_cand_rows, norm_exp_rows), start=1):
                if not cls.are_rows_equal(c_row, e_row):
                    return False, f"Row mismatch at row index {idx}."
            return True, "Results match expected rows in exact order."
        else:
            # Unordered comparison: Multiset/bag comparison preserving duplicate counts
            exp_counter = Counter(norm_exp_rows)
            cand_counter = Counter(norm_cand_rows)

            if exp_counter != cand_counter:
                return False, "Row multiset mismatch (values or duplicate counts do not match expected result)."

            return True, "Results match expected multiset."


# ==============================================================================
# 3. Disposable MySQL Execution Sandbox
# ==============================================================================

class MySQLSandbox:
    """
    Manages the lifecycle of an isolated, disposable MySQL database sandbox:
    1. Generates ephemeral database `cg_sb_<uuid>`
    2. Provisions temporary read-only user restricted strictly to that database
    3. Executes question DDL/DML setup
    4. Executes reference query to capture expected ground truth
    5. Executes candidate query under strict execution limits as read-only user
    6. Drops ephemeral database and revokes privileges in finally block
    """

    @classmethod
    def get_admin_connection(cls, timeout: int = 5):
        """Creates connection using administrator privileges to manage sandbox databases."""
        host = getattr(settings, 'SQL_SANDBOX_HOST', os.getenv('SQL_SANDBOX_HOST', '127.0.0.1'))
        port = int(getattr(settings, 'SQL_SANDBOX_PORT', os.getenv('SQL_SANDBOX_PORT', 3306)))
        user = getattr(settings, 'SQL_SANDBOX_ADMIN_USER', os.getenv('SQL_SANDBOX_ADMIN_USER', 'root'))
        password = getattr(settings, 'SQL_SANDBOX_ADMIN_PASSWORD', os.getenv('SQL_SANDBOX_ADMIN_PASSWORD', 'root_secure_password'))

        return pymysql.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            connect_timeout=timeout,
            read_timeout=timeout,
            write_timeout=timeout,
            autocommit=True,
            charset='utf8mb4'
        )

    @classmethod
    def get_restricted_connection(cls, db_name: str, ro_user: str, ro_pass: str, timeout: int = 3):
        """Creates read-only connection restricted to the ephemeral sandbox database."""
        host = getattr(settings, 'SQL_SANDBOX_HOST', os.getenv('SQL_SANDBOX_HOST', '127.0.0.1'))
        port = int(getattr(settings, 'SQL_SANDBOX_PORT', os.getenv('SQL_SANDBOX_PORT', 3306)))

        return pymysql.connect(
            host=host,
            port=port,
            user=ro_user,
            password=ro_pass,
            database=db_name,
            connect_timeout=timeout,
            read_timeout=max(1, timeout),
            write_timeout=2,
            autocommit=True,
            charset='utf8mb4'
        )

    @classmethod
    def execute_in_sandbox(
        cls,
        schema_setup_sql: str,
        candidate_sql: str,
        expected_result_definition: str,
        time_limit_ms: int = 3000,
        ordering_required: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        Executes setup, reference query, and candidate query inside an isolated ephemeral MySQL schema.
        Guarantees cleanup and fail-closed security.
        """
        # 1. Validate Candidate Query
        try:
            SQLValidator.validate_candidate_query(candidate_sql)
        except SQLValidationException as e:
            return {
                "verdict": CodeVerdict.UNSAFE_QUERY if "Forbidden" in str(e) or "forbidden" in str(e) else CodeVerdict.WRONG_ANSWER,
                "is_correct": False,
                "execution_time_ms": 0,
                "candidate_columns": [],
                "candidate_rows": [],
                "error_message": str(e)
            }
        except Exception as e:
            return {
                "verdict": CodeVerdict.SYNTAX_ERROR,
                "is_correct": False,
                "execution_time_ms": 0,
                "candidate_columns": [],
                "candidate_rows": [],
                "error_message": f"Syntax or parsing error: {e}"
            }

        # 2. Connect to MySQL as Sandbox Admin
        try:
            admin_conn = cls.get_admin_connection()
        except Exception as e:
            logger.error(f"Failed to connect to MySQL sandbox admin daemon: {e}")
            return {
                "verdict": CodeVerdict.SYSTEM_ERROR,
                "is_correct": False,
                "execution_time_ms": 0,
                "candidate_columns": [],
                "candidate_rows": [],
                "error_message": "SQL execution sandbox is currently unavailable."
            }

        sandbox_id = uuid.uuid4().hex[:14]
        db_name = f"cg_sb_{sandbox_id}"
        ro_user = f"sb_u_{sandbox_id}"
        ro_pass = f"p_{uuid.uuid4().hex[:16]}"

        try:
            with admin_conn.cursor() as cur:
                # 3. Create Ephemeral Schema & User
                cur.execute(f"CREATE DATABASE `{db_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
                cur.execute(f"CREATE USER '{ro_user}'@'%' IDENTIFIED BY '{ro_pass}';")
                cur.execute(f"REVOKE ALL PRIVILEGES, GRANT OPTION FROM '{ro_user}'@'%';")
                cur.execute(f"GRANT SELECT ON `{db_name}`.* TO '{ro_user}'@'%';")
                cur.execute("FLUSH PRIVILEGES;")

                # 4. Apply Schema Setup DDL/DML as Admin in db_name
                cur.execute(f"USE `{db_name}`;")
                setup_statements = [s.strip() for s in sqlparse.split(schema_setup_sql) if s.strip()]
                for stmt in setup_statements:
                    cur.execute(stmt)

                # 5. Execute Reference / Expected Query to get ground truth
                # If expected_result_definition contains SQL, execute it
                expected_cols = []
                expected_rows = []
                ref_query = expected_result_definition.strip().rstrip(';')

                try:
                    cur.execute(ref_query)
                    expected_cols = [desc[0] for desc in cur.description] if cur.description else []
                    expected_rows = cur.fetchall()
                except Exception as e:
                    logger.error(f"Error executing reference query in sandbox setup: {e}")
                    return {
                        "verdict": CodeVerdict.SYSTEM_ERROR,
                        "is_correct": False,
                        "execution_time_ms": 0,
                        "candidate_columns": [],
                        "candidate_rows": [],
                        "error_message": "Reference solution evaluation error."
                    }

            # If ordering_required not explicitly specified, deduce from reference query
            if ordering_required is None:
                ordering_required = "ORDER BY" in ref_query.upper()

            # 6. Connect as Restricted Read-Only User to Execute Candidate Query
            timeout_sec = max(1, int(time_limit_ms / 1000) + 1)
            try:
                ro_conn = cls.get_restricted_connection(db_name, ro_user, ro_pass, timeout=timeout_sec)
            except Exception as e:
                logger.error(f"Failed to connect as restricted sandbox user: {e}")
                return {
                    "verdict": CodeVerdict.SYSTEM_ERROR,
                    "is_correct": False,
                    "execution_time_ms": 0,
                    "candidate_columns": [],
                    "candidate_rows": [],
                    "error_message": "Failed to initialize restricted sandbox connection."
                }

            start_t = time.perf_counter()
            cand_cols = []
            cand_rows = []

            try:
                with ro_conn.cursor() as ro_cur:
                    # Enforce session execution timeout limit
                    ro_cur.execute(f"SET SESSION max_execution_time = {time_limit_ms};")
                    ro_cur.execute(candidate_sql.strip().rstrip(';'))
                    cand_cols = [desc[0] for desc in ro_cur.description] if ro_cur.description else []
                    
                    # Fetch up to 1001 rows to detect output limit overrun
                    raw_rows = ro_cur.fetchmany(1001)
                    if len(raw_rows) > 1000:
                        return {
                            "verdict": CodeVerdict.OUTPUT_LIMIT_EXCEEDED,
                            "is_correct": False,
                            "execution_time_ms": int((time.perf_counter() - start_t) * 1000),
                            "candidate_columns": cand_cols,
                            "candidate_rows": [],
                            "error_message": "Query returned more than 1000 rows (output limit exceeded)."
                        }
                    cand_rows = raw_rows
            except pymysql.MySQLError as err:
                errno = err.args[0] if len(err.args) > 0 else 0
                errmsg = err.args[1] if len(err.args) > 1 else str(err)
                exec_time_ms = int((time.perf_counter() - start_t) * 1000)

                # MySQL Error 3024 or 1317: Query execution was interrupted (max_execution_time exceeded)
                if errno in (3024, 1317) or "max_execution_time" in errmsg.lower():
                    return {
                        "verdict": CodeVerdict.TIME_LIMIT_EXCEEDED,
                        "is_correct": False,
                        "execution_time_ms": exec_time_ms,
                        "candidate_columns": [],
                        "candidate_rows": [],
                        "error_message": "Query execution time limit exceeded."
                    }

                # MySQL Error 1142: Access denied (DROP, INSERT, cross-DB query)
                if errno == 1142:
                    return {
                        "verdict": CodeVerdict.UNSAFE_QUERY,
                        "is_correct": False,
                        "execution_time_ms": exec_time_ms,
                        "candidate_columns": [],
                        "candidate_rows": [],
                        "error_message": "Permission denied: query attempted unauthorized or modifying operations."
                    }

                # Syntax / query compilation error
                return {
                    "verdict": CodeVerdict.SYNTAX_ERROR,
                    "is_correct": False,
                    "execution_time_ms": exec_time_ms,
                    "candidate_columns": [],
                    "candidate_rows": [],
                    "error_message": f"SQL error: {errmsg}"
                }
            except Exception as e:
                # Socket timeout (OperationalError)
                if "timeout" in str(e).lower():
                    return {
                        "verdict": CodeVerdict.TIME_LIMIT_EXCEEDED,
                        "is_correct": False,
                        "execution_time_ms": int((time.perf_counter() - start_t) * 1000),
                        "candidate_columns": [],
                        "candidate_rows": [],
                        "error_message": "Query execution timed out."
                    }
                return {
                    "verdict": CodeVerdict.RUNTIME_ERROR,
                    "is_correct": False,
                    "execution_time_ms": int((time.perf_counter() - start_t) * 1000),
                    "candidate_columns": [],
                    "candidate_rows": [],
                    "error_message": f"Execution error: {e}"
                }
            finally:
                ro_conn.close()

            exec_time_ms = max(1, int((time.perf_counter() - start_t) * 1000))

            # 7. Compare Outputs via SQLResultComparator
            is_correct, reason = SQLResultComparator.compare(
                candidate_cols=cand_cols,
                candidate_rows=cand_rows,
                expected_cols=expected_cols,
                expected_rows=expected_rows,
                ordering_required=ordering_required
            )

            # Sanitize candidate rows for student preview (limit to first 20 rows)
            safe_preview_rows = [
                list(SQLResultComparator.normalize_row(r)) for r in cand_rows[:20]
            ]

            return {
                "verdict": CodeVerdict.ACCEPTED if is_correct else CodeVerdict.WRONG_ANSWER,
                "is_correct": is_correct,
                "execution_time_ms": exec_time_ms,
                "candidate_columns": cand_cols,
                "candidate_rows": safe_preview_rows,
                "error_message": "" if is_correct else reason
            }

        finally:
            # 8. Clean up disposable database and user
            try:
                with admin_conn.cursor() as cur:
                    cur.execute(f"DROP DATABASE IF EXISTS `{db_name}`;")
                    cur.execute(f"DROP USER IF EXISTS '{ro_user}'@'%';")
                    cur.execute("FLUSH PRIVILEGES;")
            except Exception as e:
                logger.warning(f"Error cleaning up disposable sandbox {db_name}: {e}")
            finally:
                admin_conn.close()


# ==============================================================================
# 4. Authoritative SQL Execution Service
# ==============================================================================

class SQLExecutionService:
    """
    Authoritative domain service orchestrating SQL sandbox evaluation,
    result comparison, submission persistence, and scoring consumption.
    """

    @classmethod
    def evaluate_query(
        cls,
        candidate_sql: str,
        schema_setup_sql: str,
        expected_result_definition: str,
        time_limit_ms: int = 3000,
        ordering_required: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        Directly evaluates a query inside the isolated MySQL sandbox.
        Used by Admin runner and Result service.
        """
        return MySQLSandbox.execute_in_sandbox(
            schema_setup_sql=schema_setup_sql,
            candidate_sql=candidate_sql,
            expected_result_definition=expected_result_definition,
            time_limit_ms=time_limit_ms,
            ordering_required=ordering_required
        )

    @classmethod
    def evaluate_sql_submission(cls, submission: CodeSubmission) -> CodeSubmission:
        """
        Authoritative evaluation of an SQL CodeSubmission.
        Executes query against isolated MySQL, records test case result, updates attempt answer,
        and broadcasts real-time WebSocket notifications.
        """
        snap_q = submission.snapshot_question
        snapshot = snap_q.snapshot
        attempt = submission.attempt

        # Resolve server evaluation parameters from frozen bundle
        questions_eval = snapshot.server_evaluation_bundle.get('questions_eval', {})
        q_eval = questions_eval.get(snap_q.snapshot_question_id, {})
        server_sql_eval = q_eval.get('server_sql_eval', {})

        schema_setup = server_sql_eval.get('schema_setup_sql') or snap_q.sql_config.get('schema_setup_sql', '')
        expected_def = server_sql_eval.get('expected_result_definition') or ''
        time_limit_ms = server_sql_eval.get('time_limit_ms') or snap_q.sql_config.get('time_limit_ms', 3000)
        ordering_required = server_sql_eval.get('ordering_required')
        if ordering_required is None:
            ordering_required = (snap_q.sql_config or {}).get('ordering_required')

        # Run Sandbox Evaluation
        res = cls.evaluate_query(
            candidate_sql=submission.source_code,
            schema_setup_sql=schema_setup,
            expected_result_definition=expected_def,
            time_limit_ms=time_limit_ms,
            ordering_required=ordering_required
        )

        verdict = res.get('verdict', CodeVerdict.SYSTEM_ERROR)
        is_correct = res.get('is_correct', False)
        exec_time_ms = res.get('execution_time_ms', 0)
        err_msg = res.get('error_message', '')

        # Calculate Score
        max_score = Decimal(str(snap_q.points)) if submission.submission_type == SubmissionType.SUBMIT else Decimal('0.00')
        earned_score = max_score if is_correct else Decimal('0.00')

        with transaction.atomic():
            sub = CodeSubmission.objects.select_for_update().get(id=submission.id)
            if verdict == CodeVerdict.SYSTEM_ERROR:
                sub.status = SubmissionStatus.FAILED
            else:
                sub.status = SubmissionStatus.COMPLETED

            sub.verdict = verdict
            sub.total_test_cases = 1
            sub.passed_test_cases = 1 if is_correct else 0
            sub.score_awarded = earned_score
            sub.execution_time_ms = exec_time_ms
            sub.compilation_error = err_msg if verdict in (CodeVerdict.SYNTAX_ERROR, CodeVerdict.UNSAFE_QUERY) else ""
            sub.completed_at = timezone.now()
            sub.save()

            # Record Single Test Case Result
            sub.test_case_results.all().delete()
            CodeTestCaseResult.objects.create(
                submission=sub,
                test_case_index=1,
                is_hidden=False,
                verdict=TestCaseVerdict.PASSED if is_correct else TestCaseVerdict.FAILED,
                points_awarded=earned_score,
                max_points=max_score,
                execution_time_ms=exec_time_ms,
                memory_used_kb=0,
                public_input=None,
                expected_output=None,  # NEVER leak expected output
                actual_output=None,
                error_message=err_msg if not is_correct else None
            )

            # If SUBMIT: Update AttemptAnswer
            if submission.submission_type == SubmissionType.SUBMIT:
                from apps.assessments.models import AttemptAnswer
                from django.db.models import F
                ans, _ = AttemptAnswer.objects.get_or_create(
                    attempt=attempt,
                    snapshot_question=snap_q,
                    defaults={
                        'question_id': snap_q.snapshot_question_id,
                        'question_type': 'SQL',
                        'revision': 1
                    }
                )
                ans.sql_response = submission.source_code
                ans.is_answered = bool(submission.source_code and submission.source_code.strip())
                ans.revision = F('revision') + 1
                ans.save()

        # Broadcast WebSocket event
        from apps.evaluator.services import CodeSubmissionService
        CodeSubmissionService._broadcast_ws_event(sub, "CODE_SUBMISSION_COMPLETED")

        return sub
