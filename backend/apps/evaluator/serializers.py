from rest_framework import serializers
from apps.evaluator.models import CodeSubmission, CodeTestCaseResult, SubmissionType, SubmissionStatus, CodeVerdict


class CodeRunRequestSerializer(serializers.Serializer):
    source_code = serializers.CharField(max_length=65536, required=True)
    language = serializers.CharField(max_length=32, required=True)
    custom_input = serializers.CharField(required=False, allow_null=True, allow_blank=True, default=None)
    client_nonce = serializers.CharField(required=False, allow_null=True, allow_blank=True, default=None)


class CodeSubmitRequestSerializer(serializers.Serializer):
    source_code = serializers.CharField(max_length=65536, required=True)
    language = serializers.CharField(max_length=32, required=True)
    client_nonce = serializers.CharField(required=False, allow_null=True, allow_blank=True, default=None)


class StudentTestCaseResultSerializer(serializers.ModelSerializer):
    index = serializers.IntegerField(source='test_case_index')
    input = serializers.CharField(source='public_input', allow_null=True)
    points_awarded = serializers.SerializerMethodField()
    max_points = serializers.SerializerMethodField()

    class Meta:
        model = CodeTestCaseResult
        fields = [
            'index',
            'is_hidden',
            'verdict',
            'points_awarded',
            'max_points',
            'execution_time_ms',
            'memory_used_kb',
            'input',
            'expected_output',
            'actual_output',
            'error_message',
        ]

    def get_points_awarded(self, obj):
        if obj.is_hidden:
            return None
        return obj.points_awarded

    def get_max_points(self, obj):
        if obj.is_hidden:
            return None
        return obj.max_points


class StudentCodeSubmissionSerializer(serializers.ModelSerializer):
    submission_id = serializers.UUIDField(source='id')
    test_cases = StudentTestCaseResultSerializer(source='test_case_results', many=True, read_only=True)

    class Meta:
        model = CodeSubmission
        fields = [
            'submission_id',
            'status',
            'verdict',
            'submission_type',
            'language',
            'total_test_cases',
            'passed_test_cases',
            'score_awarded',
            'max_score',
            'execution_time_ms',
            'memory_used_kb',
            'compilation_error',
            'test_cases',
            'started_at',
            'completed_at',
        ]


class AdminCodeSubmissionSerializer(serializers.ModelSerializer):
    submission_id = serializers.UUIDField(source='id')
    student_email = serializers.EmailField(source='attempt.student.email', read_only=True)
    student_name = serializers.CharField(source='attempt.student.get_full_name', read_only=True)
    test_cases = StudentTestCaseResultSerializer(source='test_case_results', many=True, read_only=True)

    class Meta:
        model = CodeSubmission
        fields = [
            'submission_id',
            'student_email',
            'student_name',
            'attempt',
            'snapshot_question',
            'status',
            'verdict',
            'submission_type',
            'language',
            'source_code',
            'environment_version',
            'execution_policy_version',
            'comparison_policy_version',
            'total_test_cases',
            'passed_test_cases',
            'score_awarded',
            'max_score',
            'execution_time_ms',
            'memory_used_kb',
            'compilation_error',
            'test_cases',
            'idempotency_key',
            'started_at',
            'completed_at',
            'created_at',
        ]
