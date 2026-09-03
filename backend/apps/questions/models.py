from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from django.core.exceptions import PermissionDenied, ValidationError
from django.utils.text import slugify
from apps.core.models import UUIDModel, TimeStampedModel

class QuestionType(models.TextChoices):
    MCQ = 'MCQ', 'Multiple Choice Question'
    MULTI_SELECT = 'MULTI_SELECT', 'Multiple Select Question'
    TRUE_FALSE = 'TRUE_FALSE', 'True / False Question'
    SHORT_ANSWER = 'SHORT_ANSWER', 'Short Answer Question'
    CODING = 'CODING', 'Coding Question'
    SQL = 'SQL', 'SQL Query Question'


class Difficulty(models.TextChoices):
    EASY = 'EASY', 'Easy'
    MEDIUM = 'MEDIUM', 'Medium'
    HARD = 'HARD', 'Hard'


class VersionStatus(models.TextChoices):
    DRAFT = 'DRAFT', 'Draft'
    PUBLISHED = 'PUBLISHED', 'Published'
    ARCHIVED = 'ARCHIVED', 'Archived'


class CodingLanguage(models.TextChoices):
    PYTHON = 'PYTHON', 'Python'
    CPP = 'CPP', 'C++'
    JAVA = 'JAVA', 'Java'


class QuestionStatus(models.TextChoices):
    ACTIVE = 'ACTIVE', 'Active'
    ARCHIVED = 'ARCHIVED', 'Archived'


class Tag(UUIDModel, TimeStampedModel):
    """
    Categorization tag for filtering questions across domains, algorithms, and concepts.
    """
    name = models.CharField(max_length=64, unique=True, db_index=True)
    slug = models.SlugField(max_length=64, unique=True, db_index=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Question(UUIDModel, TimeStampedModel):
    """
    Logical Question entity.
    Maintains stable identity and question_type anchor across all version iterations.
    """
    question_type = models.CharField(
        max_length=32,
        choices=QuestionType.choices,
        editable=False,
        db_index=True
    )
    status = models.CharField(
        max_length=16,
        choices=QuestionStatus.choices,
        default=QuestionStatus.ACTIVE,
        db_index=True
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_questions'
    )

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Question {self.id} ({self.question_type})"

    def save(self, *args, **kwargs):
        # Enforce question_type immutability on update
        if not self._state.adding and self.pk:
            old_inst = Question.objects.filter(pk=self.pk).values('question_type').first()
            if old_inst and old_inst['question_type'] != self.question_type:
                raise PermissionDenied(
                    f"Question type is permanently immutable. Cannot change '{old_inst['question_type']}' to '{self.question_type}'."
                )
        super().save(*args, **kwargs)


class QuestionVersion(UUIDModel, TimeStampedModel):
    """
    Self-contained, immutable version of a Question's content and configuration.
    """
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name='versions'
    )
    version_number = models.PositiveIntegerField()
    question_type = models.CharField(
        max_length=32,
        choices=QuestionType.choices
    )
    title = models.CharField(max_length=255)
    description = models.TextField(help_text="Markdown problem statement / prompt")
    instructions = models.TextField(blank=True, default="")
    points = models.PositiveIntegerField(
        default=10,
        validators=[MinValueValidator(1)]
    )
    negative_marking_enabled = models.BooleanField(default=False)
    negative_points = models.PositiveIntegerField(default=0)
    difficulty = models.CharField(
        max_length=16,
        choices=Difficulty.choices,
        default=Difficulty.MEDIUM,
        db_index=True
    )
    tags = models.ManyToManyField(
        Tag,
        related_name='question_versions',
        blank=True
    )
    status = models.CharField(
        max_length=16,
        choices=VersionStatus.choices,
        default=VersionStatus.DRAFT,
        db_index=True
    )
    type_config = models.JSONField(
        default=dict,
        blank=True,
        help_text="Structured type-specific options and matching rules"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_question_versions'
    )
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('question', 'version_number')
        ordering = ['version_number']

    def __str__(self):
        return f"{self.question.id} v{self.version_number} ({self.status})"

    def clean(self):
        super().clean()
        if self.question_id and self.question_type != self.question.question_type:
            raise ValidationError(
                f"QuestionVersion type '{self.question_type}' must match Question type '{self.question.question_type}'."
            )

    def save(self, *args, **kwargs):
        # Validate question_type consistency with parent Question
        if self.question_id:
            parent_type = self.question.question_type if hasattr(self, 'question') else Question.objects.filter(id=self.question_id).values_list('question_type', flat=True).first()
            if parent_type and self.question_type != parent_type:
                raise ValidationError(
                    f"QuestionVersion type '{self.question_type}' must match Question type '{parent_type}'."
                )

        # Enforce server-side immutability
        if not self._state.adding and self.pk:
            old_inst = QuestionVersion.objects.filter(pk=self.pk).values('status').first()
            if old_inst:
                old_status = old_inst['status']
                if old_status == VersionStatus.ARCHIVED:
                    raise PermissionDenied("Archived question versions are permanently immutable.")
                elif old_status == VersionStatus.PUBLISHED:
                    if self.status != VersionStatus.ARCHIVED:
                        raise PermissionDenied(
                            "Published question versions are immutable and cannot be edited or reverted to draft."
                        )

        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.status in [VersionStatus.PUBLISHED, VersionStatus.ARCHIVED]:
            raise PermissionDenied(
                f"Cannot delete question version in '{self.status}' status. Historical versions must be preserved."
            )
        super().delete(*args, **kwargs)


class CodingQuestionConfig(UUIDModel, TimeStampedModel):
    """
    Coding problem configuration (limits, allowed languages, problem constraints).
    Belongs 1:1 to a specific QuestionVersion.
    """
    question_version = models.OneToOneField(
        QuestionVersion,
        on_delete=models.CASCADE,
        related_name='coding_config'
    )
    problem_statement = models.TextField()
    input_description = models.TextField(blank=True, default="")
    output_description = models.TextField(blank=True, default="")
    constraints = models.TextField(blank=True, default="")
    allowed_languages = models.JSONField(
        default=list,
        help_text="List of permitted languages e.g. ['PYTHON', 'CPP', 'JAVA']"
    )
    time_limit_ms = models.PositiveIntegerField(default=2000, help_text="Execution time limit in milliseconds")
    memory_limit_mb = models.PositiveIntegerField(default=256, help_text="Memory limit in megabytes")

    def __str__(self):
        return f"CodingConfig for {self.question_version}"

    def save(self, *args, **kwargs):
        if not self._state.adding and self.pk:
            if self.question_version.status in [VersionStatus.PUBLISHED, VersionStatus.ARCHIVED]:
                raise PermissionDenied("Coding configuration belonging to a published/archived version is immutable.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.question_version.status in [VersionStatus.PUBLISHED, VersionStatus.ARCHIVED]:
            raise PermissionDenied("Cannot delete coding configuration belonging to a published/archived version.")
        super().delete(*args, **kwargs)


class TestCase(UUIDModel, TimeStampedModel):
    """
    Evaluation test case for a coding question.
    """
    __test__ = False

    coding_config = models.ForeignKey(
        CodingQuestionConfig,
        on_delete=models.CASCADE,
        related_name='test_cases'
    )
    input_data = models.TextField()
    expected_output = models.TextField()
    points = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)]
    )
    is_hidden = models.BooleanField(
        default=False,
        help_text="Hidden evaluation test case (never leaked to student-facing endpoints)"
    )
    execution_order = models.PositiveIntegerField(default=1)
    time_limit_override_ms = models.PositiveIntegerField(null=True, blank=True)
    memory_limit_override_mb = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ['execution_order', 'created_at']

    def __str__(self):
        return f"TestCase {self.id} (Hidden: {self.is_hidden}, Points: {self.points})"

    def save(self, *args, **kwargs):
        if not self._state.adding and self.pk:
            if self.coding_config.question_version.status in [VersionStatus.PUBLISHED, VersionStatus.ARCHIVED]:
                raise PermissionDenied("Test cases belonging to a published/archived version are immutable.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.coding_config.question_version.status in [VersionStatus.PUBLISHED, VersionStatus.ARCHIVED]:
            raise PermissionDenied("Cannot delete test case belonging to a published/archived version.")
        super().delete(*args, **kwargs)


class SQLQuestionConfig(UUIDModel, TimeStampedModel):
    """
    SQL sandbox problem configuration (schema setup DDL/DML, problem prompt, expected result definition).
    Belongs 1:1 to a specific QuestionVersion.
    """
    question_version = models.OneToOneField(
        QuestionVersion,
        on_delete=models.CASCADE,
        related_name='sql_config'
    )
    problem_statement = models.TextField()
    schema_setup_sql = models.TextField(help_text="DDL/DML SQL statements to construct sandbox tables and seed rows")
    expected_result_definition = models.TextField(help_text="Reference target query or tabular result specification")
    allowed_dialect = models.CharField(max_length=32, default="MYSQL")
    time_limit_ms = models.PositiveIntegerField(default=3000)

    def __str__(self):
        return f"SQLConfig for {self.question_version}"

    def save(self, *args, **kwargs):
        if not self._state.adding and self.pk:
            if self.question_version.status in [VersionStatus.PUBLISHED, VersionStatus.ARCHIVED]:
                raise PermissionDenied("SQL configuration belonging to a published/archived version is immutable.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.question_version.status in [VersionStatus.PUBLISHED, VersionStatus.ARCHIVED]:
            raise PermissionDenied("Cannot delete SQL configuration belonging to a published/archived version.")
        super().delete(*args, **kwargs)
