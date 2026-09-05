import copy
import logging
from typing import Dict, Any, Optional, List, Tuple
from django.db import transaction, IntegrityError
from django.utils import timezone
from django.core.exceptions import PermissionDenied
from rest_framework.exceptions import ValidationError as DRFValidationError

from apps.accounts.models import User
from apps.accounts.services import AuditService
from .models import (
    Question,
    QuestionVersion,
    QuestionType,
    Difficulty,
    VersionStatus,
    QuestionStatus,
    CodingLanguage,
    CodingQuestionConfig,
    TestCase,
    SQLQuestionConfig,
    Tag,
)

logger = logging.getLogger(__name__)

class QuestionValidationService:
    """
    Validation engine ensuring structural correctness, integrity, and scoring invariants
    across all 6 supported question types.
    """

    @classmethod
    def validate_for_publish(cls, version: QuestionVersion) -> None:
        """
        Validates complete question configuration prior to publication.
        Raises DRFValidationError if any invariant is violated.
        """
        errors: Dict[str, Any] = {}

        # 1. Base Metadata Validation
        if not version.title or not version.title.strip():
            errors['title'] = "Question title cannot be empty."

        if not version.description or not version.description.strip():
            errors['description'] = "Problem statement/description cannot be empty."

        if version.points < 1:
            errors['points'] = "Total points must be at least 1."

        if version.negative_marking_enabled:
            if version.negative_points < 0:
                errors['negative_points'] = "Negative points cannot be less than 0."
            elif version.negative_points > version.points:
                errors['negative_points'] = f"Negative marking penalty ({version.negative_points}) cannot exceed total question points ({version.points})."

        # 2. Invariant: question_type consistency
        if version.question_type != version.question.question_type:
            errors['question_type'] = (
                f"QuestionVersion type '{version.question_type}' must match parent Question type '{version.question.question_type}'."
            )

        # 3. Type-Specific Validation
        type_config = version.type_config or {}

        if version.question_type == QuestionType.MCQ:
            cls._validate_mcq(type_config, errors)

        elif version.question_type == QuestionType.MULTI_SELECT:
            cls._validate_multi_select(type_config, errors)

        elif version.question_type == QuestionType.TRUE_FALSE:
            cls._validate_true_false(type_config, errors)

        elif version.question_type == QuestionType.SHORT_ANSWER:
            cls._validate_short_answer(type_config, errors)

        elif version.question_type == QuestionType.CODING:
            cls._validate_coding(version, errors)

        elif version.question_type == QuestionType.SQL:
            cls._validate_sql(version, errors)

        if errors:
            raise DRFValidationError(errors)

    @staticmethod
    def _validate_mcq(type_config: Dict[str, Any], errors: Dict[str, Any]) -> None:
        options = type_config.get('options', [])
        correct_options = type_config.get('correct_options', [])

        if not isinstance(options, list) or len(options) < 2:
            errors['options'] = "MCQ questions must provide at least 2 options."
            return

        option_ids = set()
        for idx, opt in enumerate(options):
            if not isinstance(opt, dict) or not opt.get('id') or not str(opt.get('text', '')).strip():
                errors['options'] = f"Option at index {idx} must have non-empty 'id' and 'text'."
                return
            opt_id = str(opt['id']).strip()
            if opt_id in option_ids:
                errors['options'] = f"Duplicate option ID '{opt_id}' detected."
                return
            option_ids.add(opt_id)

        if not isinstance(correct_options, list) or len(correct_options) != 1:
            errors['correct_options'] = "MCQ questions must have exactly one correct option selected."
            return

        selected_id = str(correct_options[0]).strip()
        if selected_id not in option_ids:
            errors['correct_options'] = f"Selected correct option '{selected_id}' does not exist in options."

    @staticmethod
    def _validate_multi_select(type_config: Dict[str, Any], errors: Dict[str, Any]) -> None:
        options = type_config.get('options', [])
        correct_options = type_config.get('correct_options', [])

        if not isinstance(options, list) or len(options) < 2:
            errors['options'] = "Multi-Select questions must provide at least 2 options."
            return

        option_ids = set()
        for idx, opt in enumerate(options):
            if not isinstance(opt, dict) or not opt.get('id') or not str(opt.get('text', '')).strip():
                errors['options'] = f"Option at index {idx} must have non-empty 'id' and 'text'."
                return
            opt_id = str(opt['id']).strip()
            if opt_id in option_ids:
                errors['options'] = f"Duplicate option ID '{opt_id}' detected."
                return
            option_ids.add(opt_id)

        if not isinstance(correct_options, list) or len(correct_options) < 1:
            errors['correct_options'] = "Multi-Select questions must specify at least one correct option."
            return

        for corr_id in correct_options:
            if str(corr_id).strip() not in option_ids:
                errors['correct_options'] = f"Selected correct option '{corr_id}' does not exist in options."
                return

    @staticmethod
    def _validate_true_false(type_config: Dict[str, Any], errors: Dict[str, Any]) -> None:
        if 'correct_answer' not in type_config or not isinstance(type_config['correct_answer'], bool):
            errors['correct_answer'] = "True/False questions must have 'correct_answer' set to true or false."

    @staticmethod
    def _validate_short_answer(type_config: Dict[str, Any], errors: Dict[str, Any]) -> None:
        accepted = type_config.get('accepted_answers', [])
        if not isinstance(accepted, list) or len(accepted) < 1:
            errors['accepted_answers'] = "Short Answer questions must provide at least one accepted answer string."
            return

        for item in accepted:
            if not isinstance(item, str) or not item.strip():
                errors['accepted_answers'] = "Accepted answer tokens cannot be empty."
                return

    @staticmethod
    def _validate_coding(version: QuestionVersion, errors: Dict[str, Any]) -> None:
        if not hasattr(version, 'coding_config') or version.coding_config is None:
            errors['coding_config'] = "Coding question is missing coding configuration."
            return

        config = version.coding_config
        if not config.problem_statement or not config.problem_statement.strip():
            errors['problem_statement'] = "Coding problem statement cannot be empty."

        allowed = config.allowed_languages or []
        valid_langs = [c[0] for c in CodingLanguage.choices]
        if not isinstance(allowed, list) or len(allowed) < 1:
            errors['allowed_languages'] = f"At least one allowed language must be specified from {valid_langs}."
        else:
            invalid = [l for l in allowed if l not in valid_langs]
            if invalid:
                errors['allowed_languages'] = f"Invalid languages specified: {invalid}. Supported: {valid_langs}."

        test_cases = list(config.test_cases.all())
        if not test_cases:
            errors['test_cases'] = "Coding question must have at least one test case before publication."
            return

        # Critical Invariant: SUM(test_cases.points) == version.points
        total_tc_points = sum(tc.points for tc in test_cases)
        if total_tc_points != version.points:
            errors['test_cases'] = (
                f"Sum of test case points ({total_tc_points}) must equal total question points ({version.points})."
            )

    @staticmethod
    def _validate_sql(version: QuestionVersion, errors: Dict[str, Any]) -> None:
        if not hasattr(version, 'sql_config') or version.sql_config is None:
            errors['sql_config'] = "SQL question is missing SQL configuration."
            return

        config = version.sql_config
        if not config.problem_statement or not config.problem_statement.strip():
            errors['problem_statement'] = "SQL problem statement cannot be empty."

        if not config.schema_setup_sql or not config.schema_setup_sql.strip():
            errors['schema_setup_sql'] = "SQL schema setup DDL/DML cannot be empty."

        if not config.expected_result_definition or not config.expected_result_definition.strip():
            errors['expected_result_definition'] = "SQL expected result definition cannot be empty."

        if config.allowed_dialect != "MYSQL":
            errors['allowed_dialect'] = "Currently only 'MYSQL' dialect is supported."


class QuestionService:
    """
    Domain service orchestrating Question and QuestionVersion lifecycles,
    deep cloning, publishing transactions, and immutability guarantees.
    """

    @classmethod
    def create_question(
        cls,
        question_type: str,
        title: str,
        description: str,
        instructions: str = "",
        points: int = 10,
        negative_marking_enabled: bool = False,
        negative_points: int = 0,
        difficulty: str = Difficulty.MEDIUM,
        tags: Optional[List[str]] = None,
        type_config: Optional[Dict[str, Any]] = None,
        coding_config_data: Optional[Dict[str, Any]] = None,
        test_cases_data: Optional[List[Dict[str, Any]]] = None,
        sql_config_data: Optional[Dict[str, Any]] = None,
        actor: Optional[User] = None,
        request=None
    ) -> Tuple[Question, QuestionVersion]:
        """
        Atomically creates a new logical Question and its initial Version 1 Draft.
        """
        valid_types = [t[0] for t in QuestionType.choices]
        if question_type not in valid_types:
            raise DRFValidationError({"question_type": f"Invalid question type '{question_type}'. Supported: {valid_types}"})

        valid_diffs = [d[0] for d in Difficulty.choices]
        if difficulty not in valid_diffs:
            raise DRFValidationError({"difficulty": f"Invalid difficulty '{difficulty}'. Supported: {valid_diffs}"})

        if points < 1:
            raise DRFValidationError({"points": "Total points must be at least 1."})

        if negative_marking_enabled and (negative_points < 0 or negative_points > points):
            raise DRFValidationError({"negative_points": f"Negative points ({negative_points}) cannot exceed total points ({points})."})

        with transaction.atomic():
            question = Question.objects.create(
                question_type=question_type,
                status=QuestionStatus.ACTIVE,
                created_by=actor
            )

            version = QuestionVersion.objects.create(
                question=question,
                version_number=1,
                question_type=question_type,
                title=title.strip(),
                description=description.strip(),
                instructions=instructions.strip() if instructions else "",
                points=points,
                negative_marking_enabled=negative_marking_enabled,
                negative_points=negative_points,
                difficulty=difficulty,
                status=VersionStatus.DRAFT,
                type_config=type_config or {},
                created_by=actor
            )

            # Assign tags
            if tags:
                tag_objs = cls._resolve_tags(tags)
                version.tags.set(tag_objs)

            # Type-specific child configs
            if question_type == QuestionType.CODING:
                c_data = coding_config_data or {}
                coding_config = CodingQuestionConfig.objects.create(
                    question_version=version,
                    problem_statement=c_data.get('problem_statement', description),
                    input_description=c_data.get('input_description', ''),
                    output_description=c_data.get('output_description', ''),
                    constraints=c_data.get('constraints', ''),
                    allowed_languages=c_data.get('allowed_languages', [CodingLanguage.PYTHON, CodingLanguage.CPP, CodingLanguage.JAVA]),
                    time_limit_ms=c_data.get('time_limit_ms', 2000),
                    memory_limit_mb=c_data.get('memory_limit_mb', 256)
                )

                if test_cases_data:
                    for tc_idx, tc_item in enumerate(test_cases_data, start=1):
                        TestCase.objects.create(
                            coding_config=coding_config,
                            input_data=tc_item.get('input_data', ''),
                            expected_output=tc_item.get('expected_output', ''),
                            points=tc_item.get('points', 1),
                            is_hidden=tc_item.get('is_hidden', False),
                            execution_order=tc_item.get('execution_order', tc_idx),
                            time_limit_override_ms=tc_item.get('time_limit_override_ms'),
                            memory_limit_override_mb=tc_item.get('memory_limit_override_mb')
                        )

            elif question_type == QuestionType.SQL:
                s_data = sql_config_data or {}
                SQLQuestionConfig.objects.create(
                    question_version=version,
                    problem_statement=s_data.get('problem_statement', description),
                    schema_setup_sql=s_data.get('schema_setup_sql', ''),
                    expected_result_definition=s_data.get('expected_result_definition', ''),
                    allowed_dialect=s_data.get('allowed_dialect', 'MYSQL'),
                    time_limit_ms=s_data.get('time_limit_ms', 3000)
                )

            AuditService.log(
                action="QUESTION_CREATED",
                actor=actor,
                target_type="Question",
                target_id=str(question.id),
                metadata={
                    "question_id": str(question.id),
                    "version_number": 1,
                    "question_type": question_type,
                    "title": version.title,
                    "points": version.points
                },
                request=request
            )

        return question, version

    @classmethod
    def update_draft_version(
        cls,
        version: QuestionVersion,
        title: Optional[str] = None,
        description: Optional[str] = None,
        instructions: Optional[str] = None,
        points: Optional[int] = None,
        negative_marking_enabled: Optional[bool] = None,
        negative_points: Optional[int] = None,
        difficulty: Optional[str] = None,
        tags: Optional[List[str]] = None,
        type_config: Optional[Dict[str, Any]] = None,
        coding_config_data: Optional[Dict[str, Any]] = None,
        test_cases_data: Optional[List[Dict[str, Any]]] = None,
        sql_config_data: Optional[Dict[str, Any]] = None,
        actor: Optional[User] = None,
        request=None
    ) -> QuestionVersion:
        """
        Updates an existing DRAFT version. Rejects edits if version is PUBLISHED or ARCHIVED.
        """
        if version.status != VersionStatus.DRAFT:
            raise PermissionDenied(f"Cannot edit question version in '{version.status}' status. Only DRAFT versions can be modified.")

        with transaction.atomic():
            if title is not None:
                version.title = title.strip()
            if description is not None:
                version.description = description.strip()
            if instructions is not None:
                version.instructions = instructions.strip()
            if points is not None:
                if points < 1:
                    raise DRFValidationError({"points": "Total points must be at least 1."})
                version.points = points
            if negative_marking_enabled is not None:
                version.negative_marking_enabled = negative_marking_enabled
            if negative_points is not None:
                version.negative_points = negative_points
            if difficulty is not None:
                version.difficulty = difficulty
            if type_config is not None:
                version.type_config = type_config

            if version.negative_marking_enabled and (version.negative_points < 0 or version.negative_points > version.points):
                raise DRFValidationError({"negative_points": f"Negative penalty ({version.negative_points}) cannot exceed total points ({version.points})."})

            version.save()

            if tags is not None:
                tag_objs = cls._resolve_tags(tags)
                version.tags.set(tag_objs)

            # Update child configs
            if version.question_type == QuestionType.CODING:
                if coding_config_data is not None or test_cases_data is not None:
                    c_conf, _ = CodingQuestionConfig.objects.get_or_create(question_version=version)
                    if coding_config_data:
                        if 'problem_statement' in coding_config_data:
                            c_conf.problem_statement = coding_config_data['problem_statement']
                        if 'input_description' in coding_config_data:
                            c_conf.input_description = coding_config_data['input_description']
                        if 'output_description' in coding_config_data:
                            c_conf.output_description = coding_config_data['output_description']
                        if 'constraints' in coding_config_data:
                            c_conf.constraints = coding_config_data['constraints']
                        if 'allowed_languages' in coding_config_data:
                            c_conf.allowed_languages = coding_config_data['allowed_languages']
                        if 'time_limit_ms' in coding_config_data:
                            c_conf.time_limit_ms = coding_config_data['time_limit_ms']
                        if 'memory_limit_mb' in coding_config_data:
                            c_conf.memory_limit_mb = coding_config_data['memory_limit_mb']
                        c_conf.save()

                    if test_cases_data is not None:
                        # Replace draft test cases atomically
                        c_conf.test_cases.all().delete()
                        for tc_idx, tc_item in enumerate(test_cases_data, start=1):
                            TestCase.objects.create(
                                coding_config=c_conf,
                                input_data=tc_item.get('input_data', ''),
                                expected_output=tc_item.get('expected_output', ''),
                                points=tc_item.get('points', 1),
                                is_hidden=tc_item.get('is_hidden', False),
                                execution_order=tc_item.get('execution_order', tc_idx),
                                time_limit_override_ms=tc_item.get('time_limit_override_ms'),
                                memory_limit_override_mb=tc_item.get('memory_limit_override_mb')
                            )

            elif version.question_type == QuestionType.SQL and sql_config_data is not None:
                s_conf, _ = SQLQuestionConfig.objects.get_or_create(question_version=version)
                if 'problem_statement' in sql_config_data:
                    s_conf.problem_statement = sql_config_data['problem_statement']
                if 'schema_setup_sql' in sql_config_data:
                    s_conf.schema_setup_sql = sql_config_data['schema_setup_sql']
                if 'expected_result_definition' in sql_config_data:
                    s_conf.expected_result_definition = sql_config_data['expected_result_definition']
                if 'allowed_dialect' in sql_config_data:
                    s_conf.allowed_dialect = sql_config_data['allowed_dialect']
                if 'time_limit_ms' in sql_config_data:
                    s_conf.time_limit_ms = sql_config_data['time_limit_ms']
                s_conf.save()

            AuditService.log(
                action="QUESTION_UPDATED",
                actor=actor,
                target_type="QuestionVersion",
                target_id=str(version.id),
                metadata={
                    "question_id": str(version.question.id),
                    "version_number": version.version_number,
                    "title": version.title
                },
                request=request
            )

        return version

    @classmethod
    def create_new_version(
        cls,
        question: Question,
        actor: Optional[User] = None,
        request=None
    ) -> QuestionVersion:
        """
        Creates a new sequential DRAFT version by performing a deep independent clone of the latest version.
        """
        with transaction.atomic():
            # Lock parent question row to prevent concurrent version number collision
            locked_question = Question.objects.select_for_update().get(id=question.id)
            latest_version = locked_question.versions.order_by('-version_number').first()

            if not latest_version:
                raise DRFValidationError("Cannot create a new version for a question without an existing version.")

            next_version_num = latest_version.version_number + 1

            # 1. Deep clone QuestionVersion row
            new_version = QuestionVersion.objects.create(
                question=locked_question,
                version_number=next_version_num,
                question_type=locked_question.question_type,
                title=latest_version.title,
                description=latest_version.description,
                instructions=latest_version.instructions,
                points=latest_version.points,
                negative_marking_enabled=latest_version.negative_marking_enabled,
                negative_points=latest_version.negative_points,
                difficulty=latest_version.difficulty,
                status=VersionStatus.DRAFT,
                type_config=copy.deepcopy(latest_version.type_config),
                created_by=actor
            )

            # Copy Tag relations
            new_version.tags.set(latest_version.tags.all())

            # 2. Deep clone Coding config & TestCases
            if locked_question.question_type == QuestionType.CODING and hasattr(latest_version, 'coding_config'):
                old_c = latest_version.coding_config
                new_c = CodingQuestionConfig.objects.create(
                    question_version=new_version,
                    problem_statement=old_c.problem_statement,
                    input_description=old_c.input_description,
                    output_description=old_c.output_description,
                    constraints=old_c.constraints,
                    allowed_languages=copy.deepcopy(old_c.allowed_languages),
                    time_limit_ms=old_c.time_limit_ms,
                    memory_limit_mb=old_c.memory_limit_mb
                )
                for tc in old_c.test_cases.all():
                    TestCase.objects.create(
                        coding_config=new_c,
                        input_data=tc.input_data,
                        expected_output=tc.expected_output,
                        points=tc.points,
                        is_hidden=tc.is_hidden,
                        execution_order=tc.execution_order,
                        time_limit_override_ms=tc.time_limit_override_ms,
                        memory_limit_override_mb=tc.memory_limit_override_mb
                    )

            # 3. Deep clone SQL config
            elif locked_question.question_type == QuestionType.SQL and hasattr(latest_version, 'sql_config'):
                old_s = latest_version.sql_config
                SQLQuestionConfig.objects.create(
                    question_version=new_version,
                    problem_statement=old_s.problem_statement,
                    schema_setup_sql=old_s.schema_setup_sql,
                    expected_result_definition=old_s.expected_result_definition,
                    allowed_dialect=old_s.allowed_dialect,
                    time_limit_ms=old_s.time_limit_ms
                )

            AuditService.log(
                action="QUESTION_VERSION_CREATED",
                actor=actor,
                target_type="QuestionVersion",
                target_id=str(new_version.id),
                metadata={
                    "question_id": str(locked_question.id),
                    "version_number": next_version_num,
                    "cloned_from_version": latest_version.version_number
                },
                request=request
            )

        return new_version

    @classmethod
    def publish_version(
        cls,
        version: QuestionVersion,
        actor: Optional[User] = None,
        request=None
    ) -> QuestionVersion:
        """
        Validates invariants and atomically publishes the question version.
        Transitions any previous PUBLISHED version to ARCHIVED.
        """
        if version.status != VersionStatus.DRAFT:
            raise DRFValidationError(f"Cannot publish question version in '{version.status}' status. Only DRAFT versions can be published.")

        # Full invariant validation
        QuestionValidationService.validate_for_publish(version)

        with transaction.atomic():
            question = Question.objects.select_for_update().get(id=version.question_id)

            # Atomically archive any currently active published version
            currently_published = question.versions.filter(status=VersionStatus.PUBLISHED)
            for prev_pub in currently_published:
                prev_pub.status = VersionStatus.ARCHIVED
                prev_pub.save(update_fields=['status', 'updated_at'])

            version.status = VersionStatus.PUBLISHED
            version.published_at = timezone.now()
            version.save(update_fields=['status', 'published_at', 'updated_at'])

            AuditService.log(
                action="QUESTION_PUBLISHED",
                actor=actor,
                target_type="QuestionVersion",
                target_id=str(version.id),
                metadata={
                    "question_id": str(question.id),
                    "version_number": version.version_number,
                    "points": version.points,
                    "question_type": version.question_type
                },
                request=request
            )

        return version

    @classmethod
    def archive_version(
        cls,
        version: QuestionVersion,
        actor: Optional[User] = None,
        request=None
    ) -> QuestionVersion:
        """
        Transitions a PUBLISHED version to ARCHIVED.
        """
        if version.status != VersionStatus.PUBLISHED:
            raise DRFValidationError(f"Cannot archive question version in '{version.status}' status. Only PUBLISHED versions can be archived.")

        with transaction.atomic():
            version.status = VersionStatus.ARCHIVED
            version.save(update_fields=['status', 'updated_at'])

            AuditService.log(
                action="QUESTION_ARCHIVED",
                actor=actor,
                target_type="QuestionVersion",
                target_id=str(version.id),
                metadata={
                    "question_id": str(version.question.id),
                    "version_number": version.version_number
                },
                request=request
            )

        return version

    @classmethod
    def archive_question(
        cls,
        question: Question,
        actor: Optional[User] = None,
        request=None
    ) -> Question:
        """
        Logically archives a logical Question and all its active versions.
        """
        with transaction.atomic():
            question.status = QuestionStatus.ARCHIVED
            question.save(update_fields=['status', 'updated_at'])

            for v in question.versions.filter(status=VersionStatus.PUBLISHED):
                v.status = VersionStatus.ARCHIVED
                v.save(update_fields=['status', 'updated_at'])

            AuditService.log(
                action="QUESTION_ARCHIVED",
                actor=actor,
                target_type="Question",
                target_id=str(question.id),
                metadata={"question_id": str(question.id)},
                request=request
            )

        return question

    @classmethod
    def get_or_create_draft_version(
        cls,
        question: Question,
        actor: Optional[User] = None,
        request=None
    ) -> Tuple[QuestionVersion, bool]:
        """
        If an existing editable DRAFT version already exists for the question, returns it.
        Otherwise, creates the next sequential DRAFT version by deep-cloning the latest version.
        Returns (version, created: bool).
        """
        existing_draft = question.versions.filter(status=VersionStatus.DRAFT).order_by('-version_number').first()
        if existing_draft:
            return existing_draft, False
        new_version = cls.create_new_version(question=question, actor=actor, request=request)
        return new_version, True

    @classmethod
    def get_question_usage(cls, question: Question) -> Dict[str, Any]:
        """
        Dependency-aware usage check across assessments, snapshots, attempts, results,
        and legal holds/retention records.
        """
        from apps.assessments.models import AssessmentQuestion, AssessmentSnapshotQuestion, AttemptAnswer
        from apps.retention.models import LegalHold, LegalHoldStatus

        assessment_ids = list(
            AssessmentQuestion.objects.filter(question_version__question=question)
            .values_list('assessment_id', flat=True)
            .distinct()
        )
        assessment_count = len(assessment_ids)
        snapshot_count = AssessmentSnapshotQuestion.objects.filter(question_version__question=question).count()
        attempt_answers_count = AttemptAnswer.objects.filter(snapshot_question__question_version__question=question).count()

        has_legal_hold = False
        if assessment_ids:
            has_legal_hold = LegalHold.objects.filter(
                attempt__assessment_id__in=assessment_ids,
                status=LegalHoldStatus.ACTIVE
            ).exists()

        has_published_or_archived = question.versions.filter(
            status__in=[VersionStatus.PUBLISHED, VersionStatus.ARCHIVED]
        ).exists()

        is_deletable = (
            not has_published_or_archived
            and assessment_count == 0
            and snapshot_count == 0
            and attempt_answers_count == 0
            and not has_legal_hold
        )

        reasons = []
        if assessment_count > 0:
            reasons.append(f"referenced by {assessment_count} assessment(s)")
        if snapshot_count > 0:
            reasons.append(f"frozen in {snapshot_count} assessment snapshot(s)")
        if attempt_answers_count > 0:
            reasons.append(f"has {attempt_answers_count} recorded student answer(s)")
        if has_legal_hold:
            reasons.append("has an active legal hold on associated assessments")
        if has_published_or_archived:
            reasons.append("contains published or archived version history")

        if not is_deletable:
            reason_str = f"This question cannot be permanently deleted because it is {', '.join(reasons)}. Archive it instead to preserve examination integrity."
        else:
            reason_str = ""

        latest_v = question.versions.order_by('-version_number').first()

        return {
            "question_id": str(question.id),
            "title": latest_v.title if latest_v else "Unknown Question",
            "question_type": question.question_type,
            "version_count": question.versions.count(),
            "latest_version_number": latest_v.version_number if latest_v else 1,
            "status": question.status,
            "assessment_count": assessment_count,
            "snapshot_count": snapshot_count,
            "attempt_answers_count": attempt_answers_count,
            "has_legal_hold": has_legal_hold,
            "has_published_or_archived": has_published_or_archived,
            "is_deletable": is_deletable,
            "reason_blocked": reason_str,
        }

    @classmethod
    def delete_draft_question(
        cls,
        question: Question,
        actor: Optional[User] = None,
        request=None
    ) -> None:
        """
        Hard-deletes a logical question ONLY if it is an unreferenced DRAFT.
        If historical or protected dependencies exist, hard delete is blocked.
        """
        usage = cls.get_question_usage(question)
        if not usage["is_deletable"]:
            raise DRFValidationError({"detail": usage["reason_blocked"]})

        with transaction.atomic():
            q_id = str(question.id)
            title = usage["title"]
            q_type = usage["question_type"]
            v_count = usage["version_count"]

            question.delete()

            AuditService.log(
                action="QUESTION_DELETED",
                actor=actor,
                target_type="Question",
                target_id=q_id,
                metadata={
                    "question_id": q_id,
                    "title": title,
                    "question_type": q_type,
                    "version_count": v_count,
                    "reason": "Administrative deletion of unreferenced draft question."
                },
                request=request
            )

    @staticmethod
    def _resolve_tags(tag_names: List[str]) -> List[Tag]:
        tag_objs = []
        for name in tag_names:
            clean = name.strip()
            if clean:
                tag, _ = Tag.objects.get_or_create(name=clean)
                tag_objs.append(tag)
        return tag_objs
