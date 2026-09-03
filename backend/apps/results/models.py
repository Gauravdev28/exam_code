import uuid
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.utils import timezone

from apps.core.models import UUIDModel, TimeStampedModel


class ResultStatus(models.TextChoices):
    PENDING = 'PENDING', 'Pending Evaluation'
    PROCESSING = 'PROCESSING', 'Processing Scoring'
    FINALIZED = 'FINALIZED', 'Finalized & Immutable'


class ReportType(models.TextChoices):
    STUDENT_SCORECARD = 'STUDENT_SCORECARD', 'Student Scorecard'
    ASSESSMENT_SUMMARY = 'ASSESSMENT_SUMMARY', 'Assessment Executive Summary'
    ASSESSMENT_ROSTER = 'ASSESSMENT_ROSTER', 'Assessment Roster Gradebook'


class ReportFormat(models.TextChoices):
    PDF = 'PDF', 'PDF Document'
    XLSX = 'XLSX', 'Excel Spreadsheet'
    CSV = 'CSV', 'Comma-Separated Values'


class ReportStatus(models.TextChoices):
    PENDING = 'PENDING', 'Pending Generation'
    PROCESSING = 'PROCESSING', 'Processing Report'
    COMPLETED = 'COMPLETED', 'Completed & Ready'
    FAILED = 'FAILED', 'Generation Failed'
    EXPIRED = 'EXPIRED', 'Expired & Purged'


class AssessmentResultQuerySet(models.QuerySet):
    def update(self, **kwargs):
        if self.filter(status=ResultStatus.FINALIZED).exists():
            allowed = {'is_released', 'updated_at'}
            if not set(kwargs.keys()).issubset(allowed):
                raise PermissionDenied("Direct update of finalized AssessmentResult records is blocked.")
        return super().update(**kwargs)

    def delete(self):
        if self.filter(status=ResultStatus.FINALIZED).exists():
            raise PermissionDenied("Finalized AssessmentResult records cannot be deleted.")
        return super().delete()


class AssessmentResultManager(models.Manager.from_queryset(AssessmentResultQuerySet)):
    def bulk_update(self, objs, fields, **kwargs):
        finalized_pks = [obj.pk for obj in objs if getattr(obj, 'status', None) == ResultStatus.FINALIZED]
        if finalized_pks:
            allowed = {'is_released', 'updated_at'}
            if not set(fields).issubset(allowed):
                raise PermissionDenied("Bulk update of finalized AssessmentResult records is blocked.")
        return super().bulk_update(objs, fields, **kwargs)


class QuestionResultQuerySet(models.QuerySet):
    def update(self, **kwargs):
        if self.filter(assessment_result__status=ResultStatus.FINALIZED).exists():
            raise PermissionDenied("QuestionResult of finalized AssessmentResult records cannot be updated.")
        return super().update(**kwargs)

    def delete(self):
        if self.filter(assessment_result__status=ResultStatus.FINALIZED).exists():
            raise PermissionDenied("QuestionResult of finalized AssessmentResult records cannot be deleted.")
        return super().delete()


class QuestionResultManager(models.Manager.from_queryset(QuestionResultQuerySet)):
    def bulk_update(self, objs, fields, **kwargs):
        finalized_qrs = [obj for obj in objs if getattr(getattr(obj, 'assessment_result', None), 'status', None) == ResultStatus.FINALIZED]
        if finalized_qrs:
            raise PermissionDenied("Bulk update of finalized QuestionResult records is blocked.")
        return super().bulk_update(objs, fields, **kwargs)


class AssessmentResult(UUIDModel, TimeStampedModel):
    """
    Authoritative immutable ledger recording the projected final score,
    percentage, passing verdict, and completion metrics of an assessment attempt.
    """
    attempt = models.OneToOneField(
        'assessments.TestAttempt',
        on_delete=models.PROTECT,
        related_name='result'
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='assessment_results'
    )
    assessment = models.ForeignKey(
        'assessments.Assessment',
        on_delete=models.PROTECT,
        related_name='results'
    )
    assessment_snapshot = models.ForeignKey(
        'assessments.AssessmentSnapshot',
        on_delete=models.PROTECT
    )
    status = models.CharField(
        max_length=20,
        choices=ResultStatus.choices,
        default=ResultStatus.PENDING,
        db_index=True
    )
    total_score_earned = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal('0.00')
    )
    total_possible_score = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal('0.00')
    )
    percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00')
    )
    is_passed = models.BooleanField(null=True, blank=True)
    total_questions = models.PositiveIntegerField(default=0)
    answered_questions = models.PositiveIntegerField(default=0)
    correct_questions = models.PositiveIntegerField(default=0)
    partially_correct_questions = models.PositiveIntegerField(default=0)
    incorrect_questions = models.PositiveIntegerField(default=0)
    skipped_questions = models.PositiveIntegerField(default=0)
    time_spent_seconds = models.PositiveIntegerField(default=0)
    is_released = models.BooleanField(default=False, db_index=True)
    finalized_at = models.DateTimeField(null=True, blank=True)
    retention_class = models.CharField(max_length=32, default='DETAILED_RESULT_30D')

    class Meta:
        db_table = 'assessment_results'
        constraints = [
            models.UniqueConstraint(
                fields=['attempt'],
                name='unique_attempt_assessment_result'
            )
        ]
        indexes = [
            models.Index(fields=['assessment', 'status', '-total_score_earned'], name='idx_res_assmt_score'),
            models.Index(fields=['student', '-created_at'], name='idx_res_student_created'),
            models.Index(fields=['assessment', 'is_released'], name='idx_res_assmt_released'),
        ]

    objects = AssessmentResultManager()

    def __str__(self):
        return f"Result for Attempt {self.attempt_id} ({self.status} - {self.total_score_earned}/{self.total_possible_score})"

    def save(self, *args, **kwargs):
        if not self._state.adding and self.pk:
            original = AssessmentResult.objects.filter(pk=self.pk).values('status').first()
            if original and original['status'] == ResultStatus.FINALIZED:
                # Disallow mutation of finalized results except explicitly updating release state
                update_fields = kwargs.get('update_fields')
                if update_fields and set(update_fields).issubset({'is_released', 'updated_at'}):
                    pass
                else:
                    raise PermissionDenied("AssessmentResult is finalized and permanently immutable.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.status == ResultStatus.FINALIZED:
            raise PermissionDenied("Finalized AssessmentResult records cannot be deleted.")
        super().delete(*args, **kwargs)


class QuestionResult(UUIDModel, TimeStampedModel):
    """
    Per-question scoring projection and student-safe evaluation summary.
    """
    assessment_result = models.ForeignKey(
        AssessmentResult,
        on_delete=models.CASCADE,
        related_name='question_results'
    )
    snapshot_question = models.ForeignKey(
        'assessments.AssessmentSnapshotQuestion',
        on_delete=models.PROTECT
    )
    question_id = models.CharField(max_length=64, db_index=True)
    question_type = models.CharField(max_length=32)
    earned_points = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal('0.00')
    )
    max_points = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal('0.00')
    )
    is_correct = models.BooleanField(default=False)
    is_partially_correct = models.BooleanField(default=False)
    is_skipped = models.BooleanField(default=False)
    evaluation_details = models.JSONField(
        default=dict,
        help_text="Student-safe scoring metadata excluding hidden test case internals."
    )
    time_spent_seconds = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'question_results'
        constraints = [
            models.UniqueConstraint(
                fields=['assessment_result', 'question_id'],
                name='unique_res_question'
            )
        ]
        indexes = [
            models.Index(fields=['question_id', 'is_correct'], name='idx_q_res_correctness'),
            models.Index(fields=['snapshot_question', 'is_correct'], name='idx_q_res_snap_q'),
        ]

    objects = QuestionResultManager()

    def __str__(self):
        return f"QResult {self.question_id} for Result {self.assessment_result_id} ({self.earned_points}/{self.max_points})"

    def save(self, *args, **kwargs):
        if not self._state.adding and self.pk:
            parent_status = AssessmentResult.objects.filter(pk=self.assessment_result_id).values_list('status', flat=True).first()
            if parent_status == ResultStatus.FINALIZED:
                raise PermissionDenied("QuestionResult is part of a finalized result and permanently immutable.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        parent_status = AssessmentResult.objects.filter(pk=self.assessment_result_id).values_list('status', flat=True).first()
        if parent_status == ResultStatus.FINALIZED:
            raise PermissionDenied("QuestionResult of finalized AssessmentResult cannot be deleted.")
        super().delete(*args, **kwargs)


class HistoricalResultSummary(UUIDModel, TimeStampedModel):
    """
    Permanent lightweight academic transcript designed to survive 30-day retention purges.
    """
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='historical_summaries'
    )
    student_euid = models.CharField(max_length=64, db_index=True)
    student_roll_number = models.CharField(max_length=64, db_index=True)
    assessment_id = models.UUIDField(db_index=True)
    assessment_snapshot_id = models.UUIDField(db_index=True)
    assessment_title_snapshot = models.CharField(max_length=255)
    total_score_earned = models.DecimalField(max_digits=8, decimal_places=2)
    total_possible_score = models.DecimalField(max_digits=8, decimal_places=2)
    percentage = models.DecimalField(max_digits=5, decimal_places=2)
    is_passed = models.BooleanField(null=True, blank=True)
    completion_status = models.CharField(max_length=32)
    started_at = models.DateTimeField()
    completed_at = models.DateTimeField()
    details_purged = models.BooleanField(default=False)
    retention_class = models.CharField(max_length=32, default='PERMANENT_SUMMARY')

    class Meta:
        db_table = 'historical_result_summaries'
        constraints = [
            models.UniqueConstraint(
                fields=['student', 'assessment_id'],
                name='unique_student_assessment_summary'
            )
        ]
        indexes = [
            models.Index(fields=['student', '-completed_at'], name='idx_hist_student_completed'),
            models.Index(fields=['student_euid', '-completed_at'], name='idx_hist_euid_completed'),
        ]

    def __str__(self):
        return f"HistoricalSummary: {self.student_euid} on {self.assessment_title_snapshot} ({self.total_score_earned}/{self.total_possible_score})"


class AssessmentAnalyticsSnapshot(UUIDModel, TimeStampedModel):
    """
    Precomputed statistical aggregates across an entire assessment cohort.
    """
    assessment = models.ForeignKey(
        'assessments.Assessment',
        on_delete=models.CASCADE,
        related_name='analytics_snapshots'
    )
    total_assigned = models.PositiveIntegerField(default=0)
    total_started = models.PositiveIntegerField(default=0)
    total_completed = models.PositiveIntegerField(default=0)
    total_expired = models.PositiveIntegerField(default=0)
    mean_score = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'))
    median_score = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'))
    highest_score = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'))
    lowest_score = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'))
    standard_deviation = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'))
    score_distribution = models.JSONField(default=dict)
    question_performance = models.JSONField(default=dict)
    tag_performance = models.JSONField(default=dict)
    generated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'assessment_analytics_snapshots'
        ordering = ['-generated_at']

    def __str__(self):
        return f"AnalyticsSnapshot for Assessment {self.assessment_id} at {self.generated_at}"


class ReportJob(UUIDModel, TimeStampedModel):
    """
    Tracks asynchronous report generation requests, background Celery processing,
    and download gates with cryptographic SHA-256 integrity verification.
    """
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='requested_reports'
    )
    report_type = models.CharField(
        max_length=32,
        choices=ReportType.choices
    )
    format = models.CharField(
        max_length=16,
        choices=ReportFormat.choices
    )
    status = models.CharField(
        max_length=20,
        choices=ReportStatus.choices,
        default=ReportStatus.PENDING,
        db_index=True
    )
    assessment = models.ForeignKey(
        'assessments.Assessment',
        null=True,
        blank=True,
        on_delete=models.CASCADE
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL
    )
    file_path = models.CharField(max_length=512, null=True, blank=True)
    file_size_bytes = models.BigIntegerField(default=0)
    sha256_hash = models.CharField(max_length=64, null=True, blank=True)
    error_message = models.TextField(blank=True, default="")
    expires_at = models.DateTimeField(db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'report_jobs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['requested_by', '-created_at'], name='idx_report_user_created'),
            models.Index(fields=['status', 'expires_at'], name='idx_report_status_expiry'),
        ]

    def __str__(self):
        return f"ReportJob {self.id} [{self.report_type} / {self.format}] ({self.status})"
