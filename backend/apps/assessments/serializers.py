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
    eligible_students_count = serializers.SerializerMethodField()
    target_sections_summary = serializers.SerializerMethodField()
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
            'eligible_students_count',
            'target_sections_summary',
            'created_by_email',
            'published_at',
            'created_at',
            'updated_at',
        ]

    def get_question_count(self, obj: Assessment):
        return obj.assessment_questions.count()

    def get_assigned_count(self, obj: Assessment):
        return obj.assignments.filter(status=AssignmentStatus.ASSIGNED).count()

    def get_eligible_students_count(self, obj: Assessment):
        if obj.status == AssessmentStatus.PUBLISHED:
            return obj.assignments.filter(status=AssignmentStatus.ASSIGNED).count()
        from .services import AssessmentAudienceService
        resolved = AssessmentAudienceService.resolve_audience(obj)
        return resolved['total_eligible']

    def get_target_sections_summary(self, obj: Assessment):
        return list(obj.target_sections.values_list('code', flat=True))


class AssessmentAdminDetailSerializer(serializers.ModelSerializer):
    assessment_questions = AssessmentQuestionAdminSerializer(many=True, read_only=True)
    created_by_email = serializers.EmailField(source='created_by.email', read_only=True)
    assigned_count = serializers.SerializerMethodField()
    eligible_students_count = serializers.SerializerMethodField()
    target_sections_summary = serializers.SerializerMethodField()
    audience_summary = serializers.SerializerMethodField()

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
            'eligible_students_count',
            'target_sections_summary',
            'audience_summary',
            'created_at',
            'updated_at',
        ]

    def get_assigned_count(self, obj: Assessment):
        return obj.assignments.filter(status=AssignmentStatus.ASSIGNED).count()

    def get_eligible_students_count(self, obj: Assessment):
        if obj.status == AssessmentStatus.PUBLISHED:
            return obj.assignments.filter(status=AssignmentStatus.ASSIGNED).count()
        from .services import AssessmentAudienceService
        resolved = AssessmentAudienceService.resolve_audience(obj)
        return resolved['total_eligible']

    def get_target_sections_summary(self, obj: Assessment):
        return list(obj.target_sections.values_list('code', flat=True))

    def get_audience_summary(self, obj: Assessment):
        assigned_qs = obj.assignments.all()
        return {
            "sections": list(obj.target_sections.values_list('code', flat=True)),
            "individual_count": obj.target_students.count(),
            "total_assigned": assigned_qs.count(),
            "active_assigned": assigned_qs.filter(status=AssignmentStatus.ASSIGNED).count(),
            "revoked": assigned_qs.filter(status=AssignmentStatus.REVOKED).count(),
        }


class ConfigureAudienceSerializer(serializers.Serializer):
    section_ids = serializers.ListField(child=serializers.UUIDField(), required=False, default=list)
    student_ids = serializers.ListField(child=serializers.UUIDField(), required=False, default=list)
    sectionIds = serializers.ListField(child=serializers.UUIDField(), required=False)
    studentIds = serializers.ListField(child=serializers.UUIDField(), required=False)
    target_section_ids = serializers.ListField(child=serializers.UUIDField(), required=False)
    target_student_ids = serializers.ListField(child=serializers.UUIDField(), required=False)
    targetSectionIds = serializers.ListField(child=serializers.UUIDField(), required=False)
    targetStudentIds = serializers.ListField(child=serializers.UUIDField(), required=False)

    def validate(self, attrs):
        # Normalize sections across all supported aliases
        sec_ids = (
            attrs.get('section_ids')
            or attrs.get('sectionIds')
            or attrs.get('target_section_ids')
            or attrs.get('targetSectionIds')
            or []
        )
        # Normalize students across all supported aliases
        stu_ids = (
            attrs.get('student_ids')
            or attrs.get('studentIds')
            or attrs.get('target_student_ids')
            or attrs.get('targetStudentIds')
            or []
        )
        attrs['section_ids'] = sec_ids
        attrs['student_ids'] = stu_ids
        return attrs


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
    target_section_ids = serializers.ListField(child=serializers.UUIDField(), required=False, allow_empty=True)
    target_student_ids = serializers.ListField(child=serializers.CharField(), required=False, allow_empty=True)
    section_ids = serializers.ListField(child=serializers.UUIDField(), required=False, allow_empty=True)
    student_ids = serializers.ListField(child=serializers.CharField(), required=False, allow_empty=True)

    def validate(self, attrs):
        start = attrs.get('start_datetime')
        end = attrs.get('end_datetime')
        if start and end and end <= start:
            raise serializers.ValidationError({"end_datetime": "End datetime must be strictly after start datetime."})

        # Normalize audience fields across alias keys
        if 'target_section_ids' in attrs or 'section_ids' in attrs:
            attrs['target_section_ids'] = attrs.get('target_section_ids', attrs.get('section_ids', []))
        if 'target_student_ids' in attrs or 'student_ids' in attrs:
            attrs['target_student_ids'] = attrs.get('target_student_ids', attrs.get('student_ids', []))
        return attrs


class AddQuestionToAssessmentSerializer(serializers.Serializer):
    question_version_id = serializers.UUIDField()
    order = serializers.IntegerField(min_value=1, required=False)
    points = serializers.IntegerField(min_value=1, required=False)
    negative_marking_enabled = serializers.BooleanField(default=False)
    negative_points = serializers.IntegerField(min_value=0, default=0)


class AssessmentAssignmentSerializer(serializers.ModelSerializer):
    student_id = serializers.UUIDField(source='student.id', read_only=True)
    user_id = serializers.UUIDField(source='student.id', read_only=True)
    student_profile_id = serializers.SerializerMethodField()
    student_email = serializers.EmailField(source='student.email', read_only=True)
    student_roll_number = serializers.SerializerMethodField()
    assigned_by_email = serializers.EmailField(source='assigned_by.email', read_only=True)

    class Meta:
        model = AssessmentAssignment
        fields = [
            'id',
            'student_id',
            'user_id',
            'student_profile_id',
            'student_email',
            'student_roll_number',
            'status',
            'assigned_by_email',
            'assigned_at',
        ]

    def get_student_profile_id(self, obj: AssessmentAssignment):
        if hasattr(obj.student, 'student_profile') and obj.student.student_profile:
            return str(obj.student.student_profile.id)
        return None

    def get_student_roll_number(self, obj: AssessmentAssignment):
        if hasattr(obj.student, 'student_profile') and obj.student.student_profile:
            return obj.student.student_profile.roll_number
        return None


class AssignStudentsPayloadSerializer(serializers.Serializer):
    student_ids = serializers.ListField(child=serializers.UUIDField(), required=False)
    studentIds = serializers.ListField(child=serializers.UUIDField(), required=False)
    student_id = serializers.UUIDField(required=False)
    studentId = serializers.UUIDField(required=False)
    target_student_ids = serializers.ListField(child=serializers.UUIDField(), required=False)
    targetStudentIds = serializers.ListField(child=serializers.UUIDField(), required=False)

    def validate(self, attrs):
        ids = []
        for key in ['student_ids', 'studentIds', 'target_student_ids', 'targetStudentIds']:
            if key in attrs and attrs[key]:
                ids.extend([str(item) for item in attrs[key]])
        for key in ['student_id', 'studentId']:
            if key in attrs and attrs[key]:
                ids.append(str(attrs[key]))

        if not ids:
            raise serializers.ValidationError({"student_ids": "At least one student ID is required."})

        attrs['student_ids'] = ids
        return attrs


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
