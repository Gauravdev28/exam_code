from django.db import models
from apps.core.models import UUIDModel, TimeStampedModel


class SubmissionType(models.TextChoices):
    RUN = 'RUN', 'Run Code (Public Test Cases)'
    SUBMIT = 'SUBMIT', 'Submit Solution (Authoritative Evaluation)'


class SubmissionStatus(models.TextChoices):
    QUEUED = 'QUEUED', 'Queued for Execution'
    PROCESSING = 'PROCESSING', 'Processing Submission'
    COMPILING = 'COMPILING', 'Compiling Source Code'
    RUNNING = 'RUNNING', 'Running Test Cases'
    EVALUATING = 'EVALUATING', 'Evaluating Outputs'
    COMPLETED = 'COMPLETED', 'Execution Completed'
    FAILED = 'FAILED', 'System Infrastructure Failure'
    CANCELLED = 'CANCELLED', 'Cancelled'


class CodeVerdict(models.TextChoices):
    ACCEPTED = 'ACCEPTED', 'Accepted'
    WRONG_ANSWER = 'WRONG_ANSWER', 'Wrong Answer'
    TIME_LIMIT_EXCEEDED = 'TIME_LIMIT_EXCEEDED', 'Time Limit Exceeded'
    MEMORY_LIMIT_EXCEEDED = 'MEMORY_LIMIT_EXCEEDED', 'Memory Limit Exceeded'
    COMPILATION_ERROR = 'COMPILATION_ERROR', 'Compilation Error'
    RUNTIME_ERROR = 'RUNTIME_ERROR', 'Runtime Error'
    OUTPUT_LIMIT_EXCEEDED = 'OUTPUT_LIMIT_EXCEEDED', 'Output Limit Exceeded'
    SYSTEM_ERROR = 'SYSTEM_ERROR', 'System Error'
    SYNTAX_ERROR = 'SYNTAX_ERROR', 'Syntax Error'
    UNSAFE_QUERY = 'UNSAFE_QUERY', 'Unsafe Query'



class TestCaseVerdict(models.TextChoices):
    __test__ = False
    PASSED = 'PASSED', 'Passed'
    FAILED = 'FAILED', 'Failed'
    TIME_LIMIT_EXCEEDED = 'TIME_LIMIT_EXCEEDED', 'Time Limit Exceeded'
    MEMORY_LIMIT_EXCEEDED = 'MEMORY_LIMIT_EXCEEDED', 'Memory Limit Exceeded'
    RUNTIME_ERROR = 'RUNTIME_ERROR', 'Runtime Error'


class CodeSubmission(UUIDModel, TimeStampedModel):
    """
    Tracks a student's code execution request (Run or Submit) against a frozen snapshot question.
    """
    attempt = models.ForeignKey(
        'assessments.TestAttempt',
        on_delete=models.PROTECT,
        related_name='code_submissions'
    )
    snapshot_question = models.ForeignKey(
        'assessments.AssessmentSnapshotQuestion',
        on_delete=models.PROTECT,
        related_name='code_submissions'
    )
    submission_type = models.CharField(
        max_length=16,
        choices=SubmissionType.choices
    )
    source_code = models.TextField()
    language = models.CharField(max_length=32)
    environment_version = models.CharField(
        max_length=64,
        default='CG-ENV-PY311-V1',
        help_text="Immutable compiler/runtime environment version used."
    )
    execution_policy_version = models.CharField(
        max_length=64,
        default='CG-EXEC-V1',
        help_text="Immutable execution resource policy schema version used."
    )
    comparison_policy_version = models.CharField(
        max_length=64,
        default='CG-CMP-V1',
        help_text="Immutable output comparison algorithm version used."
    )
    status = models.CharField(
        max_length=20,
        choices=SubmissionStatus.choices,
        default=SubmissionStatus.QUEUED,
        db_index=True
    )
    verdict = models.CharField(
        max_length=32,
        choices=CodeVerdict.choices,
        null=True,
        blank=True,
        db_index=True
    )
    total_test_cases = models.PositiveIntegerField(default=0)
    passed_test_cases = models.PositiveIntegerField(default=0)
    score_awarded = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=0.00
    )
    max_score = models.PositiveIntegerField(default=0)
    execution_time_ms = models.PositiveIntegerField(
        default=0,
        help_text="Maximum CPU execution time across all test cases (ms)"
    )
    memory_used_kb = models.PositiveIntegerField(
        default=0,
        help_text="Maximum resident set memory used across all test cases (KB)"
    )
    compilation_error = models.TextField(
        blank=True,
        default="",
        help_text="Sanitized compiler error log (if compilation failed)"
    )
    idempotency_key = models.CharField(
        max_length=128,
        db_index=True
    )
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'code_submissions'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['attempt', 'snapshot_question', '-created_at'], name='idx_subm_att_q'),
            models.Index(fields=['idempotency_key', 'status'], name='idx_subm_idemp_st'),
            models.Index(fields=['attempt', 'status'], name='idx_subm_att_st'),
        ]

    def __str__(self):
        return f"CodeSubmission {self.id} [{self.submission_type}] ({self.status} - {self.verdict or 'N/A'})"


class CodeTestCaseResult(UUIDModel, TimeStampedModel):
    """
    Per-test-case execution result and scoring breakdown.
    For hidden test cases, public_input, expected_output, and actual_output are strictly NULL in database.
    """
    submission = models.ForeignKey(
        CodeSubmission,
        on_delete=models.CASCADE,
        related_name='test_case_results'
    )
    test_case_index = models.PositiveIntegerField()
    is_hidden = models.BooleanField(default=False)
    verdict = models.CharField(
        max_length=32,
        choices=TestCaseVerdict.choices
    )
    points_awarded = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=0.00
    )
    max_points = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=0.00
    )
    execution_time_ms = models.PositiveIntegerField(default=0)
    memory_used_kb = models.PositiveIntegerField(default=0)

    # Public-only fields (NULL if is_hidden == True)
    public_input = models.TextField(null=True, blank=True)
    expected_output = models.TextField(null=True, blank=True)
    actual_output = models.TextField(null=True, blank=True)
    error_message = models.TextField(null=True, blank=True)

    class Meta:
        db_table = 'code_test_case_results'
        ordering = ['submission', 'test_case_index']
        constraints = [
            models.UniqueConstraint(
                fields=['submission', 'test_case_index'],
                name='unique_submission_tc_index'
            )
        ]

    def __str__(self):
        return f"TC#{self.test_case_index} for Submission {self.submission_id} ({self.verdict})"
