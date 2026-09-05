from rest_framework import serializers
from apps.questions.serializers import TagSerializer
from .models import (
    Assessment,
    AssessmentStatus,
    AssessmentAssignment,
    AssignmentStatus,
    AssessmentQuestion,
    AssessmentSnapshot,
    AssessmentSnapshotQuestion,
    TestAttempt,
    AttemptStatus,
    AttemptAnswer,
    ResultVisibility,
)
from .services import AttemptTimerService


# ==============================================================================
# Admin Serializers
# ==============================================================================

class AssessmentQuestionAdminSerializer(serializers.ModelSerializer):
    question_title = serializers.CharField(source='question_version.title', read_only=True)
    question_type = serializers.CharField(source='question_version.question_type', read_only=True)
    difficulty = serializers.CharField(source='question_version.difficulty', read_only=True)
    version_number = serializers.IntegerField(source='question_version.version_number', read_only=True)
    tags = serializers.SerializerMethodField()

    class Meta:
        model = AssessmentQuestion
        fields = [
            'id',
            'question_version_id',
            'version_number',
            'question_title',
            'question_type',
            'difficulty',
            'order',
            'points',
            'negative_marking_enabled',
            'negative_points',
            'tags',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']

    def get_tags(self, obj: AssessmentQuestion):
        return list(obj.question_version.tags.values_list('name', flat=True))


class AssessmentAdminListSerializer(serializers.ModelSerializer):
    question_count = serializers.SerializerMethodField()
    assigned_count = serializers.SerializerMethodField()
    created_by_email = serializers.EmailField(source='created_by.email', read_only=True)

    class Meta:
        model = Assessment
        fields = [
            'id',
            'title',
            'status',
            'start_datetime',
            'end_datetime',
            'duration_minutes',
            'total_points',
            'passing_percentage',
            'attempt_limit',
            'negative_marking_enabled',
            'randomize_questions',
            'randomize_options',
            'result_visibility',
            'question_count',
            'assigned_count',
            'created_by_email',
            'published_at',
            'created_at',
            'updated_at',
        ]

    def get_question_count(self, obj: Assessment):
        return obj.assessment_questions.count()

    def get_assigned_count(self, obj: Assessment):
        return obj.assignments.filter(status=AssignmentStatus.ASSIGNED).count()


class AssessmentAdminDetailSerializer(serializers.ModelSerializer):
    assessment_questions = AssessmentQuestionAdminSerializer(many=True, read_only=True)
    created_by_email = serializers.EmailField(source='created_by.email', read_only=True)
    assigned_count = serializers.SerializerMethodField()

    class Meta:
        model = Assessment
        fields = [
            'id',
            'title',
            'description',
            'instructions',
            'status',
            'start_datetime',
            'end_datetime',
            'duration_minutes',
            'total_points',
            'passing_percentage',
            'negative_marking_enabled',
            'attempt_limit',
            'randomize_questions',
            'randomize_options',
            'result_visibility',
            'created_by_email',
            'published_at',
            'assessment_questions',
            'assigned_count',
            'created_at',
            'updated_at',
        ]

    def get_assigned_count(self, obj: Assessment):
        return obj.assignments.filter(status=AssignmentStatus.ASSIGNED).count()


class CreateAssessmentSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255)
    description = serializers.CharField(
        required=False,
        allow_blank=True,
        default=""
    )
    instructions = serializers.CharField(required=False, allow_blank=True, default="")
    start_datetime = serializers.DateTimeField()
    end_datetime = serializers.DateTimeField()
    duration_minutes = serializers.IntegerField(min_value=1)
    total_points = serializers.IntegerField(min_value=0, default=0)
    passing_percentage = serializers.DecimalField(max_digits=5, decimal_places=2, min_value=0, max_value=100, required=False, default=0.00)
    negative_marking_enabled = serializers.BooleanField(default=False)
    attempt_limit = serializers.IntegerField(min_value=1, default=1)
    randomize_questions = serializers.BooleanField(default=False)
    randomize_options = serializers.BooleanField(default=False)
    result_visibility = serializers.ChoiceField(choices=ResultVisibility.choices, default=ResultVisibility.AFTER_DEADLINE)

    def validate(self, attrs):
        start = attrs.get('start_datetime')
        end = attrs.get('end_datetime')
        if start and end and end <= start:
            raise serializers.ValidationError({"end_datetime": "End datetime must be strictly after start datetime."})
        return attrs


class UpdateAssessmentSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255, required=False)
    description = serializers.CharField(
        required=False,
        allow_blank=True
    )
    instructions = serializers.CharField(required=False, allow_blank=True)
    start_datetime = serializers.DateTimeField(required=False)
    end_datetime = serializers.DateTimeField(required=False)
    duration_minutes = serializers.IntegerField(min_value=1, required=False)
    total_points = serializers.IntegerField(min_value=0, required=False)
    passing_percentage = serializers.DecimalField(max_digits=5, decimal_places=2, min_value=0, max_value=100, required=False)
    negative_marking_enabled = serializers.BooleanField(required=False)
    attempt_limit = serializers.IntegerField(min_value=1, required=False)
    randomize_questions = serializers.BooleanField(required=False)
    randomize_options = serializers.BooleanField(required=False)
    result_visibility = serializers.ChoiceField(choices=ResultVisibility.choices, required=False)

    def validate(self, attrs):
        start = attrs.get('start_datetime')
        end = attrs.get('end_datetime')
        if start and end and end <= start:
            raise serializers.ValidationError({"end_datetime": "End datetime must be strictly after start datetime."})
        return attrs


class AddQuestionToAssessmentSerializer(serializers.Serializer):
    question_version_id = serializers.UUIDField()
    order = serializers.IntegerField(min_value=1, required=False)
    points = serializers.IntegerField(min_value=1, required=False)
    negative_marking_enabled = serializers.BooleanField(default=False)
    negative_points = serializers.IntegerField(min_value=0, default=0)


class AssessmentAssignmentSerializer(serializers.ModelSerializer):
    student_id = serializers.UUIDField(source='student.id', read_only=True)
    student_email = serializers.EmailField(source='student.email', read_only=True)
    student_roll_number = serializers.SerializerMethodField()
    assigned_by_email = serializers.EmailField(source='assigned_by.email', read_only=True)

    class Meta:
        model = AssessmentAssignment
        fields = [
            'id',
            'student_id',
            'student_email',
            'student_roll_number',
            'status',
            'assigned_by_email',
            'assigned_at',
        ]

    def get_student_roll_number(self, obj: AssessmentAssignment):
        if hasattr(obj.student, 'student_profile') and obj.student.student_profile:
            return obj.student.student_profile.roll_number
        return None


class AssignStudentsPayloadSerializer(serializers.Serializer):
    student_ids = serializers.ListField(child=serializers.UUIDField(), min_length=1)


# ==============================================================================
# Student Serializers (Strictly Redacting server_evaluation_bundle)
# ==============================================================================

class StudentAssessmentListSerializer(serializers.ModelSerializer):
    """
    Sanitized assessment metadata for assigned students.
    """
    attempts_used = serializers.SerializerMethodField()
    active_attempt_id = serializers.SerializerMethodField()
    is_eligible = serializers.SerializerMethodField()

    class Meta:
        model = Assessment
        fields = [
            'id',
            'title',
            'description',
            'instructions',
            'start_datetime',
            'end_datetime',
            'duration_minutes',
            'total_points',
            'attempt_limit',
            'attempts_used',
            'is_eligible',
            'active_attempt_id',
        ]

    def get_attempts_used(self, obj: Assessment):
        user = self.context.get('request').user
        return obj.attempts.filter(student=user).count()

    def get_active_attempt_id(self, obj: Assessment):
        user = self.context.get('request').user
        active = obj.attempts.filter(student=user, status=AttemptStatus.IN_PROGRESS).first()
        return str(active.id) if active else None

    def get_is_eligible(self, obj: Assessment):
        user = self.context.get('request').user
        used = obj.attempts.filter(student=user).count()
        return used < obj.attempt_limit


class StudentAttemptAnswerSerializer(serializers.ModelSerializer):
    class Meta:
        model = AttemptAnswer
        fields = [
            'question_id',
            'question_type',
            'revision',
            'selected_options',
            'text_response',
            'code_response',
            'code_language',
            'sql_response',
            'is_answered',
            'last_saved_at',
        ]


class SaveAnswerPayloadSerializer(serializers.Serializer):
    selected_options = serializers.ListField(child=serializers.CharField(), required=False)
    text_response = serializers.CharField(required=False, allow_blank=True)
    code_response = serializers.CharField(required=False, allow_blank=True)
    code_language = serializers.CharField(required=False, allow_blank=True)
    sql_response = serializers.CharField(required=False, allow_blank=True)
    revision = serializers.IntegerField(default=1, min_value=1)
