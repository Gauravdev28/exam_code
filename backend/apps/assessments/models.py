import uuid
from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError, PermissionDenied
from django.utils import timezone

from apps.core.models import UUIDModel, TimeStampedModel
from apps.questions.models import QuestionVersion, VersionStatus


class AssessmentStatus(models.TextChoices):
    DRAFT = 'DRAFT', 'Draft'
    PUBLISHED = 'PUBLISHED', 'Published'
    ARCHIVED = 'ARCHIVED', 'Archived'


class AssignmentStatus(models.TextChoices):
    ASSIGNED = 'ASSIGNED', 'Assigned'
    REVOKED = 'REVOKED', 'Revoked'


class AttemptStatus(models.TextChoices):
    NOT_STARTED = 'NOT_STARTED', 'Not Started'
    IN_PROGRESS = 'IN_PROGRESS', 'In Progress'
    SUBMITTED = 'SUBMITTED', 'Submitted'
    EXPIRED = 'EXPIRED', 'Expired'
    CANCELLED = 'CANCELLED', 'Cancelled'


class ResultVisibility(models.TextChoices):
    IMMEDIATE = 'IMMEDIATE', 'Immediate'
    AFTER_DEADLINE = 'AFTER_DEADLINE', 'After Deadline'
    MANUAL = 'MANUAL', 'Manual Release'


class Assessment(UUIDModel, TimeStampedModel):
    """
    Logical container and scheduling configuration for a technical exam.
    """
    title = models.CharField(max_length=255)
    description = models.TextField()
    instructions = models.TextField(blank=True, default='')
    status = models.CharField(
        max_length=20,
        choices=AssessmentStatus.choices,
        default=AssessmentStatus.DRAFT,
        db_index=True
    )
    start_datetime = models.DateTimeField(db_index=True)
    end_datetime = models.DateTimeField(db_index=True)
    duration_minutes = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        help_text="Duration allocated per attempt in minutes."
    )
    total_points = models.PositiveIntegerField(
        default=0,
        help_text="Total marks for the assessment. Must equal SUM(AssessmentQuestion.points) at publish time."
    )
    negative_marking_enabled = models.BooleanField(
        default=False,
        help_text="Global switch allowing negative marking on questions in this assessment."
    )
    attempt_limit = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        help_text="Maximum number of attempts allowed per student."
    )
    randomize_questions = models.BooleanField(
        default=False,
        help_text="If enabled, questions are presented in deterministic pseudo-random order per attempt."
    )
    randomize_options = models.BooleanField(
        default=False,
        help_text="If enabled, MCQ/Multi-select options are shuffled deterministically per attempt."
    )
    passing_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0.00,
        help_text="Minimum score percentage required to pass the assessment."
    )
    result_visibility = models.CharField(
        max_length=20,
        choices=ResultVisibility.choices,
        default=ResultVisibility.AFTER_DEADLINE
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='created_assessments'
    )
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'assessments'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'start_datetime', 'end_datetime'], name='idx_assessment_status_sched'),
        ]

    def __str__(self):
        return f"{self.title} ({self.status})"

    def clean(self):
        super().clean()
        if self.start_datetime and self.end_datetime:
            if self.end_datetime <= self.start_datetime:
                raise ValidationError({"end_datetime": "End datetime must be strictly after start datetime."})

    def save(self, *args, **kwargs):
        self.clean()
        if not self._state.adding:
            original = Assessment.objects.get(pk=self.pk)
            # Immutability check: Published or Archived assessments cannot mutate core properties
            if original.status in [AssessmentStatus.PUBLISHED, AssessmentStatus.ARCHIVED]:
                # The ONLY allowed mutation is transitioning PUBLISHED -> ARCHIVED
                is_archiving = (
                    original.status == AssessmentStatus.PUBLISHED and
                    self.status == AssessmentStatus.ARCHIVED
                )
                if not is_archiving:
                    raise PermissionDenied(
                        f"Cannot modify assessment in {original.status} status. Published assessments are immutable."
                    )
        super().save(*args, **kwargs)


class AssessmentAssignment(UUIDModel, TimeStampedModel):
    """
    Explicit authorization link designating which students are permitted to take an assessment.
    """
    assessment = models.ForeignKey(
        Assessment,
        on_delete=models.CASCADE,
        related_name='assignments'
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='assessment_assignments'
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='assigned_assessments_by'
    )
    assigned_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=20,
        choices=AssignmentStatus.choices,
        default=AssignmentStatus.ASSIGNED,
        db_index=True
    )

    class Meta:
        db_table = 'assessment_assignments'
        constraints = [
            models.UniqueConstraint(
                fields=['assessment', 'student'],
                name='unique_assessment_student_assignment'
            )
        ]
        indexes = [
            models.Index(fields=['student', 'status'], name='idx_assignment_student_status'),
        ]

    def __str__(self):
        return f"Assignment: {self.student.email} -> {self.assessment.title} ({self.status})"


class AssessmentQuestion(UUIDModel, TimeStampedModel):
    """
    Ordered link binding an assessment to a specific published QuestionVersion.
    """
    assessment = models.ForeignKey(
        Assessment,
        on_delete=models.CASCADE,
        related_name='assessment_questions'
    )
    question_version = models.ForeignKey(
        QuestionVersion,
        on_delete=models.PROTECT,
        related_name='assessment_associations'
    )
    order = models.PositiveIntegerField(default=1)
    points = models.PositiveIntegerField(
        default=10,
        validators=[MinValueValidator(1)],
        help_text="Points assigned to this question in this assessment."
    )
    negative_marking_enabled = models.BooleanField(
        default=False,
        help_text="If enabled for this question (and globally enabled), incorrect answers receive penalty."
    )
    negative_points = models.PositiveIntegerField(
        default=0,
        help_text="Points deducted for incorrect answers."
    )

    class Meta:
        db_table = 'assessment_questions'
        ordering = ['assessment', 'order']
        constraints = [
            models.UniqueConstraint(
                fields=['assessment', 'question_version'],
                name='unique_assessment_question_version'
            ),
            models.UniqueConstraint(
                fields=['assessment', 'order'],
                name='unique_assessment_question_order'
            )
        ]

    def __str__(self):
        return f"{self.assessment.title} - Q#{self.order} ({self.question_version.title})"

    def clean(self):
        super().clean()
        if self.question_version.status != VersionStatus.PUBLISHED:
            raise ValidationError(
                {"question_version": "Only PUBLISHED QuestionVersion records can be linked to an assessment."}
            )
        if self.negative_marking_enabled and self.negative_points > self.points:
            raise ValidationError(
                {"negative_points": "Negative points penalty cannot exceed the positive points of the question."}
            )

    def save(self, *args, **kwargs):
        self.clean()
        if self.assessment.status in [AssessmentStatus.PUBLISHED, AssessmentStatus.ARCHIVED]:
            raise PermissionDenied("Cannot add or modify questions on a published or archived assessment.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.assessment.status in [AssessmentStatus.PUBLISHED, AssessmentStatus.ARCHIVED]:
            raise PermissionDenied("Cannot delete questions from a published or archived assessment.")
        super().delete(*args, **kwargs)


class AssessmentSnapshot(UUIDModel, TimeStampedModel):
    """
    Frozen, immutable bundle capturing the exact assessment definition and question configurations upon publication.
    """
    assessment = models.OneToOneField(
        Assessment,
        on_delete=models.PROTECT,
        related_name='snapshot'
    )
    version_number = models.PositiveIntegerField(default=1)
    snapshot_data = models.JSONField(
        default=dict,
        help_text="Complete student-safe frozen payload: metadata, questions, public test cases."
    )
    server_evaluation_bundle = models.JSONField(
        default=dict,
        help_text="Server-only evaluation payload: hidden test cases, expected answers/queries. NEVER exposed to students."
    )

    class Meta:
        db_table = 'assessment_snapshots'

    def __str__(self):
        return f"Snapshot v{self.version_number} for {self.assessment.title}"

    def save(self, *args, **kwargs):
        # Model-level immutability: Once created, AssessmentSnapshot cannot be updated
        if not self._state.adding:
            raise PermissionDenied("AssessmentSnapshot records are permanently immutable and cannot be updated.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionDenied("AssessmentSnapshot records are permanently immutable and cannot be deleted.")


class AssessmentSnapshotQuestion(UUIDModel, TimeStampedModel):
    """
    Discrete frozen question entity within an AssessmentSnapshot.
    Guarantees that AttemptAnswer directly references an immutable snapshot question record.
    """
    snapshot = models.ForeignKey(
        AssessmentSnapshot,
        on_delete=models.PROTECT,
        related_name='snapshot_questions'
    )
    question_version = models.ForeignKey(
        QuestionVersion,
        on_delete=models.PROTECT,
        related_name='snapshot_usages'
    )
    snapshot_question_id = models.CharField(max_length=64, db_index=True)
    order = models.PositiveIntegerField(default=1)
    question_type = models.CharField(max_length=32)
    title = models.CharField(max_length=255)
    description = models.TextField()
    instructions = models.TextField(blank=True, default='')
    points = models.PositiveIntegerField(default=10)
    negative_marking_enabled = models.BooleanField(default=False)
    negative_points = models.PositiveIntegerField(default=0)
    difficulty = models.CharField(max_length=20, default='MEDIUM')
    type_config = models.JSONField(default=dict)
    coding_config = models.JSONField(default=dict)
    sql_config = models.JSONField(default=dict)
    tags = models.JSONField(default=list)

    class Meta:
        db_table = 'assessment_snapshot_questions'
        ordering = ['snapshot', 'order']
        constraints = [
            models.UniqueConstraint(
                fields=['snapshot', 'snapshot_question_id'],
                name='unique_snapshot_question_id'
            )
        ]

    def __str__(self):
        return f"SnapshotQ: {self.title} (Snapshot: {self.snapshot.id})"

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise PermissionDenied("AssessmentSnapshotQuestion records are permanently immutable.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionDenied("AssessmentSnapshotQuestion records are permanently immutable.")


class TestAttempt(UUIDModel, TimeStampedModel):
    """
    Student-specific runtime state and server-authoritative timer for an assessment attempt.
    """
    __test__ = False

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='test_attempts'
    )
    assessment = models.ForeignKey(
        Assessment,
        on_delete=models.PROTECT,
        related_name='attempts'
    )
    assessment_snapshot = models.ForeignKey(
        AssessmentSnapshot,
        on_delete=models.PROTECT,
        related_name='attempts'
    )
    attempt_number = models.PositiveIntegerField(default=1)
    status = models.CharField(
        max_length=20,
        choices=AttemptStatus.choices,
        default=AttemptStatus.NOT_STARTED,
        db_index=True
    )
    randomization_seed = models.CharField(
        max_length=128,
        help_text="Authoritative random seed for deterministic question & option shuffle."
    )
    question_order = models.JSONField(
        default=list,
        help_text="Ordered list of snapshot_question_ids presented to this attempt."
    )
    option_orders = models.JSONField(
        default=dict,
        help_text="Mapping of {snapshot_question_id: [shuffled_option_ids]}."
    )
    started_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'test_attempts'
        constraints = [
            models.UniqueConstraint(
                fields=['student', 'assessment', 'attempt_number'],
                name='unique_student_assessment_attempt'
            )
        ]
        indexes = [
            models.Index(fields=['student', 'assessment', 'status'], name='idx_attempt_student_assessment'),
        ]

    def __str__(self):
        return f"Attempt #{self.attempt_number} by {self.student.email} on {self.assessment.title} ({self.status})"

    def clean(self):
        super().clean()
        # Enforce valid state transitions
        if not self._state.adding:
            original = TestAttempt.objects.get(pk=self.pk)
            old_status = original.status
            new_status = self.status

            if old_status in [AttemptStatus.SUBMITTED, AttemptStatus.EXPIRED, AttemptStatus.CANCELLED]:
                if new_status != old_status:
                    raise PermissionDenied(
                        f"Cannot transition terminal attempt from {old_status} to {new_status}."
                    )


class AttemptAnswer(UUIDModel, TimeStampedModel):
    """
    Persisted student response for a specific snapshot question within an attempt.
    Supports optimistic concurrency revision control to prevent stale overwrite races.
    """
    attempt = models.ForeignKey(
        TestAttempt,
        on_delete=models.CASCADE,
        related_name='answers'
    )
    snapshot_question = models.ForeignKey(
        AssessmentSnapshotQuestion,
        on_delete=models.PROTECT,
        related_name='attempt_answers'
    )
    question_id = models.CharField(max_length=64, db_index=True)
    question_type = models.CharField(max_length=32)
    revision = models.PositiveIntegerField(
        default=1,
        help_text="Monotonically increasing version counter preventing out-of-order write races."
    )
    selected_options = models.JSONField(null=True, blank=True)
    text_response = models.TextField(null=True, blank=True)
    code_response = models.TextField(null=True, blank=True)
    code_language = models.CharField(max_length=32, null=True, blank=True)
    sql_response = models.TextField(null=True, blank=True)
    is_answered = models.BooleanField(default=False)
    last_saved_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'attempt_answers'
        constraints = [
            models.UniqueConstraint(
                fields=['attempt', 'snapshot_question'],
                name='unique_attempt_snapshot_question_answer'
            )
        ]
        indexes = [
            models.Index(fields=['attempt', 'question_id'], name='idx_attempt_question_lookup'),
        ]

    def __str__(self):
        return f"Answer for Q#{self.question_id} in Attempt {self.attempt.id} (rev: {self.revision})"
