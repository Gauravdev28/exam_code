from rest_framework import serializers
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

class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ['id', 'name', 'slug', 'created_at']
        read_only_fields = ['id', 'slug', 'created_at']


class TestCaseAdminSerializer(serializers.ModelSerializer):
    """Full test case representation for administrative management."""
    class Meta:
        model = TestCase
        fields = [
            'id',
            'name',
            'input_data',
            'expected_output',
            'points',
            'is_hidden',
            'is_verified',
            'execution_order',
            'time_limit_override_ms',
            'memory_limit_override_mb',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class TestCasePublicSerializer(serializers.ModelSerializer):
    """Public representation strictly redacting hidden test case inputs and outputs."""
    class Meta:
        model = TestCase
        fields = [
            'id',
            'name',
            'input_data',
            'expected_output',
            'points',
            'is_hidden',
            'execution_order',
        ]
        read_only_fields = fields


class CodingQuestionConfigAdminSerializer(serializers.ModelSerializer):
    test_cases = TestCaseAdminSerializer(many=True, read_only=True)

    class Meta:
        model = CodingQuestionConfig
        fields = [
            'id',
            'problem_statement',
            'input_description',
            'output_description',
            'constraints',
            'allowed_languages',
            'time_limit_ms',
            'memory_limit_mb',
            'starter_codes',
            'examples',
            'reference_solutions',
            'reference_solution_language',
            'reference_solution_hash',
            'reference_solution_verified',
            'reference_solution_verified_at',
            'test_cases',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class CodingQuestionConfigPublicSerializer(serializers.ModelSerializer):
    test_cases = serializers.SerializerMethodField()

    class Meta:
        model = CodingQuestionConfig
        fields = [
            'id',
            'problem_statement',
            'input_description',
            'output_description',
            'constraints',
            'allowed_languages',
            'time_limit_ms',
            'memory_limit_mb',
            'starter_codes',
            'examples',
            'test_cases',
        ]
        read_only_fields = fields

    def get_test_cases(self, obj: CodingQuestionConfig):
        # Strictly return only public example test cases
        public_tcs = obj.test_cases.filter(is_hidden=False)
        return TestCasePublicSerializer(public_tcs, many=True).data


class SQLQuestionConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = SQLQuestionConfig
        fields = [
            'id',
            'problem_statement',
            'schema_setup_sql',
            'expected_result_definition',
            'allowed_dialect',
            'time_limit_ms',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class QuestionVersionAdminDetailSerializer(serializers.ModelSerializer):
    """Complete QuestionVersion representation with all child configs and full test cases."""
    tags = TagSerializer(many=True, read_only=True)
    coding_config = CodingQuestionConfigAdminSerializer(read_only=True)
    sql_config = SQLQuestionConfigSerializer(read_only=True)
    created_by_email = serializers.EmailField(source='created_by.email', read_only=True)
    health_status = serializers.SerializerMethodField()

    class Meta:
        model = QuestionVersion
        fields = [
            'id',
            'question_id',
            'version_number',
            'question_type',
            'title',
            'description',
            'instructions',
            'points',
            'negative_marking_enabled',
            'negative_points',
            'difficulty',
            'tags',
            'status',
            'type_config',
            'coding_config',
            'sql_config',
            'health_status',
            'created_by_email',
            'published_at',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'question_id',
            'version_number',
            'question_type',
            'status',
            'health_status',
            'created_by_email',
            'published_at',
            'created_at',
            'updated_at',
        ]

    def get_health_status(self, obj: QuestionVersion):
        from .services import CodingQuestionValidationService
        if obj.question_type == QuestionType.CODING and hasattr(obj, 'coding_config') and obj.coding_config:
            return CodingQuestionValidationService.get_health_status(obj)
        return None


class QuestionVersionPublicDetailSerializer(serializers.ModelSerializer):
    """Student/Preview safe representation strictly excluding hidden test cases."""
    tags = TagSerializer(many=True, read_only=True)
    coding_config = CodingQuestionConfigPublicSerializer(read_only=True)
    sql_config = SQLQuestionConfigSerializer(read_only=True)

    class Meta:
        model = QuestionVersion
        fields = [
            'id',
            'question_id',
            'version_number',
            'question_type',
            'title',
            'description',
            'instructions',
            'points',
            'difficulty',
            'tags',
            'type_config',
            'coding_config',
            'sql_config',
        ]
        read_only_fields = fields

    def to_representation(self, instance):
        import copy
        ret = super().to_representation(instance)
        if isinstance(ret.get('type_config'), dict):
            safe_type_config = copy.deepcopy(ret['type_config'])
            for private_key in ['admin_notes', 'internal_notes', 'solution_notes', 'secret']:
                safe_type_config.pop(private_key, None)
            ret['type_config'] = safe_type_config
        return ret


class QuestionVersionSummarySerializer(serializers.ModelSerializer):
    tags = TagSerializer(many=True, read_only=True)

    class Meta:
        model = QuestionVersion
        fields = [
            'id',
            'version_number',
            'question_type',
            'title',
            'points',
            'difficulty',
            'status',
            'tags',
            'published_at',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields


class QuestionListSerializer(serializers.ModelSerializer):
    """Summary representation for Question Bank roster table."""
    latest_version = serializers.SerializerMethodField()
    published_version = serializers.SerializerMethodField()
    created_by_email = serializers.EmailField(source='created_by.email', read_only=True)

    class Meta:
        model = Question
        fields = [
            'id',
            'question_type',
            'status',
            'created_by_email',
            'latest_version',
            'published_version',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields

    def get_latest_version(self, obj: Question):
        v = obj.versions.order_by('-version_number').first()
        return QuestionVersionSummarySerializer(v).data if v else None

    def get_published_version(self, obj: Question):
        v = obj.versions.filter(status=VersionStatus.PUBLISHED).first()
        return QuestionVersionSummarySerializer(v).data if v else None


class QuestionDetailSerializer(serializers.ModelSerializer):
    """Detailed Question view including full version history."""
    versions = QuestionVersionSummarySerializer(many=True, read_only=True)
    created_by_email = serializers.EmailField(source='created_by.email', read_only=True)

    class Meta:
        model = Question
        fields = [
            'id',
            'question_type',
            'status',
            'created_by_email',
            'versions',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields


class CreateQuestionSerializer(serializers.Serializer):
    """Payload validator for creating a new logical Question and Version 1."""
    question_type = serializers.ChoiceField(choices=QuestionType.choices)
    title = serializers.CharField(max_length=255)
    description = serializers.CharField()
    instructions = serializers.CharField(required=False, allow_blank=True, default="")
    points = serializers.IntegerField(default=10, min_value=1)
    negative_marking_enabled = serializers.BooleanField(default=False)
    negative_points = serializers.IntegerField(default=0, min_value=0)
    difficulty = serializers.ChoiceField(choices=Difficulty.choices, default=Difficulty.MEDIUM)
    tags = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    type_config = serializers.DictField(required=False, default=dict)
    coding_config = serializers.DictField(required=False, default=dict)
    test_cases = serializers.ListField(child=serializers.DictField(), required=False, default=list)
    sql_config = serializers.DictField(required=False, default=dict)


class UpdateDraftVersionSerializer(serializers.Serializer):
    """Payload validator for updating an existing DRAFT version."""
    title = serializers.CharField(max_length=255, required=False)
    description = serializers.CharField(required=False)
    instructions = serializers.CharField(required=False, allow_blank=True)
    points = serializers.IntegerField(required=False, min_value=1)
    negative_marking_enabled = serializers.BooleanField(required=False)
    negative_points = serializers.IntegerField(required=False, min_value=0)
    difficulty = serializers.ChoiceField(choices=Difficulty.choices, required=False)
    tags = serializers.ListField(child=serializers.CharField(), required=False)
    type_config = serializers.DictField(required=False)
    coding_config = serializers.DictField(required=False)
    test_cases = serializers.ListField(child=serializers.DictField(), required=False)
    sql_config = serializers.DictField(required=False)
