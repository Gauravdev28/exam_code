"""
Tests for Phase 11 Isolated MySQL SQL Sandbox, Validator, Result Comparator, and Security Protections.
"""
import pytest
from decimal import Decimal
import datetime

from apps.evaluator.sql_sandbox import (
    SQLValidator,
    SQLValidationException,
    SQLResultComparator,
    MySQLSandbox,
    SQLExecutionService,
)
from apps.evaluator.models import CodeVerdict


# ==============================================================================
# 1. SQL Static Parser & Token-Level Security Validator Tests
# ==============================================================================

class TestSQLValidator:

    def test_valid_simple_select(self):
        SQLValidator.validate_candidate_query("SELECT id, name FROM employees WHERE salary > 50000;")

    def test_valid_with_cte_select(self):
        SQLValidator.validate_candidate_query("""
            WITH high_earners AS (
                SELECT id, name, salary FROM employees WHERE salary > 100000
            )
            SELECT name, salary FROM high_earners ORDER BY salary DESC;
        """)

    def test_valid_joins_and_aggregates(self):
        SQLValidator.validate_candidate_query("""
            SELECT d.name, COUNT(e.id) AS emp_count, AVG(e.salary) AS avg_sal
            FROM departments d
            LEFT JOIN employees e ON d.id = e.dept_id
            GROUP BY d.name
            HAVING emp_count > 5
            ORDER BY avg_sal DESC;
        """)

    def test_reject_empty_query(self):
        with pytest.raises(SQLValidationException, match="cannot be empty"):
            SQLValidator.validate_candidate_query("   ")

    def test_reject_multi_statement_semicolon(self):
        with pytest.raises(SQLValidationException, match="Multiple SQL statements"):
            SQLValidator.validate_candidate_query("SELECT * FROM t; DROP TABLE t;")

    def test_reject_multi_statement_inline(self):
        with pytest.raises(SQLValidationException, match="Multiple SQL statements"):
            SQLValidator.validate_candidate_query("SELECT * FROM t; SELECT * FROM u;")

    def test_reject_drop_table(self):
        with pytest.raises(SQLValidationException, match="Forbidden statement type 'DROP'"):
            SQLValidator.validate_candidate_query("DROP TABLE employees;")

    def test_reject_delete_statement(self):
        with pytest.raises(SQLValidationException, match="Forbidden statement type 'DELETE'"):
            SQLValidator.validate_candidate_query("DELETE FROM employees WHERE id = 1;")

    def test_reject_update_statement(self):
        with pytest.raises(SQLValidationException, match="Forbidden statement type 'UPDATE'"):
            SQLValidator.validate_candidate_query("UPDATE employees SET salary = 99999;")

    def test_reject_insert_statement(self):
        with pytest.raises(SQLValidationException, match="Forbidden statement type 'INSERT'"):
            SQLValidator.validate_candidate_query("INSERT INTO employees VALUES (1, 'Hacker', 1000000);")

    def test_reject_alter_table(self):
        with pytest.raises(SQLValidationException, match="Forbidden statement type 'ALTER'"):
            SQLValidator.validate_candidate_query("ALTER TABLE employees ADD COLUMN hacked INT;")

    def test_reject_create_table(self):
        with pytest.raises(SQLValidationException, match="Forbidden statement type 'CREATE'"):
            SQLValidator.validate_candidate_query("CREATE TABLE hacked (id INT);")

    def test_reject_truncate(self):
        with pytest.raises(SQLValidationException, match="Forbidden statement type 'TRUNCATE'"):
            SQLValidator.validate_candidate_query("TRUNCATE TABLE employees;")

    def test_reject_grant_revoke(self):
        with pytest.raises(SQLValidationException, match="Query must begin with SELECT or WITH"):
            SQLValidator.validate_candidate_query("GRANT ALL ON *.* TO 'hacker'@'%';")

    def test_reject_sleep_function(self):
        with pytest.raises(SQLValidationException, match="Forbidden SQL function"):
            SQLValidator.validate_candidate_query("SELECT name, SLEEP(5) FROM employees;")

    def test_reject_benchmark_function(self):
        with pytest.raises(SQLValidationException, match="Forbidden SQL function"):
            SQLValidator.validate_candidate_query("SELECT BENCHMARK(1000000, MD5('test'));")

    def test_reject_into_outfile(self):
        with pytest.raises(SQLValidationException, match="Forbidden SQL keyword detected: 'OUTFILE'"):
            SQLValidator.validate_candidate_query("SELECT * FROM employees INTO OUTFILE '/tmp/leak.txt';")

    def test_reject_load_file(self):
        with pytest.raises(SQLValidationException, match="Forbidden SQL function"):
            SQLValidator.validate_candidate_query("SELECT LOAD_FILE('/etc/passwd');")

    def test_reject_access_to_mysql_system_db(self):
        with pytest.raises(SQLValidationException, match="Access to table or database 'mysql'"):
            SQLValidator.validate_candidate_query("SELECT user, host FROM mysql.user;")

    def test_reject_access_to_information_schema(self):
        with pytest.raises(SQLValidationException, match="Access to table or database 'information_schema'"):
            SQLValidator.validate_candidate_query("SELECT table_name FROM information_schema.tables;")

    def test_reject_access_to_codeguard_app_tables(self):
        with pytest.raises(SQLValidationException, match="Access to table or database 'auth_user'"):
            SQLValidator.validate_candidate_query("SELECT * FROM auth_user;")

        with pytest.raises(SQLValidationException, match="Access to table or database 'accounts_user'"):
            SQLValidator.validate_candidate_query("SELECT * FROM accounts_user;")

        with pytest.raises(SQLValidationException, match="Access to table or database 'code_submissions'"):
            SQLValidator.validate_candidate_query("SELECT * FROM code_submissions;")


# ==============================================================================
# 2. Structured Tabular Result Comparator Tests
# ==============================================================================

class TestSQLResultComparator:

    def test_identical_results_match(self):
        cols = ['id', 'name', 'salary']
        rows = [(1, 'Alice', 90000), (2, 'Bob', 80000)]
        matched, reason = SQLResultComparator.compare(cols, rows, cols, rows, ordering_required=True)
        assert matched is True
        assert "exact order" in reason

    def test_case_insensitive_column_names(self):
        cand_cols = ['ID', 'NAME', 'SALARY']
        exp_cols = ['id', 'name', 'salary']
        rows = [(1, 'Alice', 90000)]
        matched, _ = SQLResultComparator.compare(cand_cols, rows, exp_cols, rows)
        assert matched is True

    def test_column_count_mismatch(self):
        cand_cols = ['id', 'name']
        exp_cols = ['id', 'name', 'salary']
        rows = [(1, 'Alice')]
        exp_rows = [(1, 'Alice', 90000)]
        matched, reason = SQLResultComparator.compare(cand_cols, rows, exp_cols, exp_rows)
        assert matched is False
        assert "Column count mismatch" in reason

    def test_column_names_mismatch(self):
        cand_cols = ['id', 'username']
        exp_cols = ['id', 'name']
        rows = [(1, 'Alice')]
        matched, reason = SQLResultComparator.compare(cand_cols, rows, exp_cols, rows)
        assert matched is False
        assert "Column names mismatch" in reason

    def test_row_count_mismatch_extra_rows(self):
        cols = ['id']
        cand_rows = [(1,), (2,), (3,)]
        exp_rows = [(1,), (2,)]
        matched, reason = SQLResultComparator.compare(cols, cand_rows, cols, exp_rows)
        assert matched is False
        assert "Row count mismatch" in reason

    def test_row_count_mismatch_missing_rows(self):
        cols = ['id']
        cand_rows = [(1,)]
        exp_rows = [(1,), (2,)]
        matched, reason = SQLResultComparator.compare(cols, cand_rows, cols, exp_rows)
        assert matched is False
        assert "Row count mismatch" in reason

    def test_empty_results_match(self):
        cols = ['id', 'name']
        matched, _ = SQLResultComparator.compare(cols, [], cols, [])
        assert matched is True

    def test_empty_candidate_with_non_empty_expected(self):
        cols = ['id']
        matched, _ = SQLResultComparator.compare(cols, [], cols, [(1,)])
        assert matched is False

    def test_null_handling_distinction(self):
        cols = ['val']
        # NULL == NULL
        assert SQLResultComparator.compare(cols, [(None,)], cols, [(None,)])[0] is True
        # NULL != ''
        assert SQLResultComparator.compare(cols, [(None,)], cols, [('',)])[0] is False
        # NULL != 0
        assert SQLResultComparator.compare(cols, [(None,)], cols, [(0,)])[0] is False

    def test_numeric_float_tolerance(self):
        cols = ['avg_score']
        cand_rows = [(Decimal('85.333333'),)]
        exp_rows = [(85.333334,)]
        matched, _ = SQLResultComparator.compare(cols, cand_rows, cols, exp_rows)
        assert matched is True

    def test_string_trailing_whitespace_normalization(self):
        cols = ['name']
        cand_rows = [('Alice  ',)]
        exp_rows = [('Alice',)]
        matched, _ = SQLResultComparator.compare(cols, cand_rows, cols, exp_rows)
        assert matched is True

    def test_ordering_required_detects_out_of_order(self):
        cols = ['id']
        cand_rows = [(2,), (1,)]
        exp_rows = [(1,), (2,)]
        matched, reason = SQLResultComparator.compare(cols, cand_rows, cols, exp_rows, ordering_required=True)
        assert matched is False
        assert "Row mismatch at row index 1" in reason

    def test_ordering_not_required_allows_different_order(self):
        cols = ['id', 'val']
        cand_rows = [(2, 'B'), (1, 'A')]
        exp_rows = [(1, 'A'), (2, 'B')]
        matched, _ = SQLResultComparator.compare(cols, cand_rows, cols, exp_rows, ordering_required=False)
        assert matched is True

    def test_ordering_not_required_preserves_duplicate_counts(self):
        """
        Expected: A, A, B
        Candidate: A, B (Missing duplicate A)
        Must fail even with ordering_required=False!
        """
        cols = ['val']
        exp_rows = [('A',), ('A',), ('B',)]
        cand_rows = [('A',), ('B',)]
        matched, _ = SQLResultComparator.compare(cols, cand_rows, cols, exp_rows, ordering_required=False)
        assert matched is False

        cand_rows_match = [('B',), ('A',), ('A',)]
        matched, _ = SQLResultComparator.compare(cols, cand_rows_match, cols, exp_rows, ordering_required=False)
        assert matched is True


# ==============================================================================
# 3. MySQL Sandbox Execution & Security Integration Tests
# ==============================================================================

@pytest.mark.django_db
class TestMySQLSandboxExecution:

    SCHEMA_SETUP = """
        CREATE TABLE departments (
            id INT PRIMARY KEY,
            name VARCHAR(50) NOT NULL
        );
        CREATE TABLE employees (
            id INT PRIMARY KEY,
            name VARCHAR(50) NOT NULL,
            salary INT NOT NULL,
            dept_id INT,
            FOREIGN KEY (dept_id) REFERENCES departments(id)
        );
        INSERT INTO departments VALUES (1, 'Engineering'), (2, 'Design'), (3, 'HR');
        INSERT INTO employees VALUES
            (101, 'Alice', 95000, 1),
            (102, 'Bob', 75000, 1),
            (103, 'Charlie', 80000, 2),
            (104, 'Diana', 60000, 3);
    """

    REFERENCE_QUERY = "SELECT name, salary FROM employees WHERE salary >= 75000 ORDER BY salary DESC;"

    def test_correct_candidate_query_accepted(self):
        cand_sql = "SELECT name, salary FROM employees WHERE salary >= 75000 ORDER BY salary DESC;"
        res = SQLExecutionService.evaluate_query(
            candidate_sql=cand_sql,
            schema_setup_sql=self.SCHEMA_SETUP,
            expected_result_definition=self.REFERENCE_QUERY
        )
        assert res['verdict'] == CodeVerdict.ACCEPTED
        assert res['is_correct'] is True
        assert len(res['candidate_rows']) == 3
        assert res['candidate_rows'][0][0] == 'Alice'

    def test_correct_alternative_sql_syntax_accepted(self):
        """Two different queries producing identical expected tabular output must both pass."""
        cand_sql = """
            SELECT e.name, e.salary
            FROM employees e
            INNER JOIN departments d ON e.dept_id = d.id
            WHERE e.salary > 74000
            ORDER BY e.salary DESC;
        """
        res = SQLExecutionService.evaluate_query(
            candidate_sql=cand_sql,
            schema_setup_sql=self.SCHEMA_SETUP,
            expected_result_definition=self.REFERENCE_QUERY
        )
        assert res['verdict'] == CodeVerdict.ACCEPTED
        assert res['is_correct'] is True

    def test_incorrect_filter_wrong_answer(self):
        cand_sql = "SELECT name, salary FROM employees WHERE salary > 90000 ORDER BY salary DESC;"
        res = SQLExecutionService.evaluate_query(
            candidate_sql=cand_sql,
            schema_setup_sql=self.SCHEMA_SETUP,
            expected_result_definition=self.REFERENCE_QUERY
        )
        assert res['verdict'] == CodeVerdict.WRONG_ANSWER
        assert res['is_correct'] is False

    def test_wrong_columns_wrong_answer(self):
        cand_sql = "SELECT id, name FROM employees WHERE salary >= 75000;"
        res = SQLExecutionService.evaluate_query(
            candidate_sql=cand_sql,
            schema_setup_sql=self.SCHEMA_SETUP,
            expected_result_definition=self.REFERENCE_QUERY
        )
        assert res['verdict'] == CodeVerdict.WRONG_ANSWER
        assert res['is_correct'] is False

    def test_syntax_error_rejected(self):
        cand_sql = "SELECT FROM WHERE;"
        res = SQLExecutionService.evaluate_query(
            candidate_sql=cand_sql,
            schema_setup_sql=self.SCHEMA_SETUP,
            expected_result_definition=self.REFERENCE_QUERY
        )
        assert res['verdict'] == CodeVerdict.SYNTAX_ERROR
        assert res['is_correct'] is False

    def test_destructive_drop_table_rejected(self):
        cand_sql = "DROP TABLE employees;"
        res = SQLExecutionService.evaluate_query(
            candidate_sql=cand_sql,
            schema_setup_sql=self.SCHEMA_SETUP,
            expected_result_definition=self.REFERENCE_QUERY
        )
        assert res['verdict'] in (CodeVerdict.UNSAFE_QUERY, CodeVerdict.WRONG_ANSWER)
        assert res['is_correct'] is False

    def test_destructive_delete_rejected(self):
        cand_sql = "DELETE FROM employees;"
        res = SQLExecutionService.evaluate_query(
            candidate_sql=cand_sql,
            schema_setup_sql=self.SCHEMA_SETUP,
            expected_result_definition=self.REFERENCE_QUERY
        )
        assert res['verdict'] in (CodeVerdict.UNSAFE_QUERY, CodeVerdict.WRONG_ANSWER)
        assert res['is_correct'] is False

    def test_cross_database_codeguard_app_access_rejected(self):
        cand_sql = "SELECT * FROM codeguard_db.auth_user;"
        res = SQLExecutionService.evaluate_query(
            candidate_sql=cand_sql,
            schema_setup_sql=self.SCHEMA_SETUP,
            expected_result_definition=self.REFERENCE_QUERY
        )
        assert res['verdict'] in (CodeVerdict.UNSAFE_QUERY, CodeVerdict.WRONG_ANSWER)
        assert res['is_correct'] is False

    def test_cross_student_isolation(self):
        """
        Student A sandbox contains Alice.
        Student B sandbox contains Bob.
        Student A cannot see Bob in Student B sandbox.
        """
        setup_a = "CREATE TABLE cand (name VARCHAR(50)); INSERT INTO cand VALUES ('Alice');"
        setup_b = "CREATE TABLE cand (name VARCHAR(50)); INSERT INTO cand VALUES ('Bob');"
        ref_q = "SELECT name FROM cand;"

        res_a = SQLExecutionService.evaluate_query("SELECT name FROM cand;", setup_a, ref_q)
        res_b = SQLExecutionService.evaluate_query("SELECT name FROM cand;", setup_b, ref_q)

        assert res_a['is_correct'] is True
        assert res_a['candidate_rows'] == [['Alice']]

        assert res_b['is_correct'] is True
        assert res_b['candidate_rows'] == [['Bob']]
