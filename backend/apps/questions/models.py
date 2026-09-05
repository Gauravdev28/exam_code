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
    Single authoritative source of truth for coding questions.
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
    starter_codes = models.JSONField(
        default=dict,
        blank=True,
        help_text="Mapping of language key to starter code e.g. {'PYTHON': '...'}"
    )
    examples = models.JSONField(
        default=list,
        blank=True,
        help_text="List of example cases: [{'input': '...', 'output': '...', 'explanation': '...'}]"
    )
    reference_solutions = models.JSONField(
        default=dict,
        blank=True,
        help_text="Admin reference solutions: {language: code}"
    )
    reference_solution_language = models.CharField(
        max_length=32,
        blank=True,
        default="",
        help_text="Primary verified reference solution language"
    )
    reference_solution_hash = models.CharField(
        max_length=64,
        blank=True,
        default="",
        help_text="SHA-256 hash of verified reference solution source and language"
    )
    reference_solution_verified = models.BooleanField(
        default=False,
        help_text="Whether the reference solution has been verified against all test cases"
    )
    reference_solution_verified_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when the reference solution was verified"
    )

    def __str__(self):
        return f"CodingConfig for {self.question_version}"

    @staticmethod
    def compute_reference_hash(code: str, language: str) -> str:
        import hashlib
        if not code or not language:
            return ""
        norm_code = str(code).replace('\r\n', '\n').strip()
        norm_lang = str(language).strip().upper()
        return hashlib.sha256(f"{norm_lang}:{norm_code}".encode('utf-8')).hexdigest()

    def get_current_reference_hash(self) -> str:
        lang = self.reference_solution_language
        if not lang and self.reference_solutions and isinstance(self.reference_solutions, dict):
            lang = next(iter(self.reference_solutions.keys()))
        code = self.reference_solutions.get(lang, "") if isinstance(self.reference_solutions, dict) else ""
        return self.compute_reference_hash(code, lang)

    def is_reference_solution_current(self) -> bool:
        if not self.reference_solution_verified or not self.reference_solution_hash:
            return False
        return self.get_current_reference_hash() == self.reference_solution_hash

    def mark_reference_solution_verified(self, language: str, code: str):
        from django.utils import timezone
        self.reference_solution_language = str(language).strip().upper()
        self.reference_solution_hash = self.compute_reference_hash(code, language)
        self.reference_solution_verified = True
        self.reference_solution_verified_at = timezone.now()

    def save(self, *args, **kwargs):
        if not self._state.adding and self.pk:
            if self.question_version.status in [VersionStatus.PUBLISHED, VersionStatus.ARCHIVED]:
                raise PermissionDenied("Coding configuration belonging to a published/archived version is immutable.")
            
            # Detect reference solution source or language changes to invalidate verification
            old = CodingQuestionConfig.objects.filter(pk=self.pk).values(
                'reference_solutions', 'reference_solution_language', 'reference_solution_hash', 'reference_solution_verified'
            ).first()
            if old and old['reference_solution_verified']:
                old_ref_solutions = old['reference_solutions'] or {}
                old_ref_lang = old['reference_solution_language'] or ""
                curr_code = self.reference_solutions.get(self.reference_solution_language, "") if isinstance(self.reference_solutions, dict) else ""
                old_code = old_ref_solutions.get(old_ref_lang, "") if isinstance(old_ref_solutions, dict) else ""

                curr_hash = self.compute_reference_hash(curr_code, self.reference_solution_language)
                if curr_hash != old['reference_solution_hash'] or self.reference_solution_language != old_ref_lang:
                    # Invalidate reference solution verification
                    self.reference_solution_verified = False
                    self.reference_solution_verified_at = None
                    # Invalidate all associated verified test cases
                    self.test_cases.filter(is_verified=True).update(is_verified=False)

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
    name = models.CharField(
        max_length=128,
        blank=True,
        default="",
        help_text="Test case name or label"
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
    is_verified = models.BooleanField(
        default=False,
        help_text="Whether the expected output has been explicitly verified by an administrator"
    )
    execution_order = models.PositiveIntegerField(default=1)
    time_limit_override_ms = models.PositiveIntegerField(null=True, blank=True)
    memory_limit_override_mb = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ['execution_order', 'created_at']

    def __str__(self):
        return f"TestCase {self.id} (Hidden: {self.is_hidden}, Points: {self.points}, Verified: {self.is_verified})"

    def save(self, *args, **kwargs):
        if not self._state.adding and self.pk:
            if self.coding_config.question_version.status in [VersionStatus.PUBLISHED, VersionStatus.ARCHIVED]:
                raise PermissionDenied("Test cases belonging to a published/archived version are immutable.")
            
            # Invalidate verification if input_data or expected_output changes
            old = TestCase.objects.filter(pk=self.pk).values('input_data', 'expected_output', 'is_verified').first()
            if old and old['is_verified']:
                if old['input_data'] != self.input_data or old['expected_output'] != self.expected_output:
                    self.is_verified = False

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
