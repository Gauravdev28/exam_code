from rest_framework import serializers
from apps.proctoring.models import (
    ProctoringSession,
    ProctoringEvent,
    ProctoringEvidence,
    ProctoringWarning,
    ProctoringReview,
)


class StudentProctoringSessionSerializer(serializers.ModelSerializer):
    session_id = serializers.UUIDField(source='id', read_only=True)
    frame_sampling_interval_seconds = serializers.SerializerMethodField()
    heartbeat_interval_seconds = serializers.SerializerMethodField()

    class Meta:
        model = ProctoringSession
        fields = [
            'session_id',
            'status',
            'frame_sampling_interval_seconds',
            'heartbeat_interval_seconds',
            'created_at',
        ]
        read_only_fields = ['session_id', 'status', 'created_at']

    def get_frame_sampling_interval_seconds(self, obj):
        return 2.0

    def get_heartbeat_interval_seconds(self, obj):
        return 15.0


class StudentProctoringEventIngestSerializer(serializers.Serializer):
    event_type = serializers.CharField(max_length=64)
    client_detected_at = serializers.DateTimeField(required=False, allow_null=True)
    metadata = serializers.DictField(required=False, default=dict)

    def validate_event_type(self, value):
        allowed = [
            'WINDOW_BLUR',
            'TAB_SWITCH',
            'FULLSCREEN_EXIT',
            'FULLSCREEN_ENTER',
            'PAGE_VISIBILITY_CHANGE',
            'CAMERA_UNAVAILABLE',
            'MICROPHONE_UNAVAILABLE',
        ]
        if value not in allowed:
            raise serializers.ValidationError(f"Invalid client event type: '{value}'.")
        return value


class StudentProctoringFrameUploadSerializer(serializers.Serializer):
    frame = serializers.FileField(required=True)
    sequence_number = serializers.IntegerField(required=False, default=0)

    def validate_frame(self, value):
        # 300 KB max frame size
        if value.size > 300 * 1024:
            raise serializers.ValidationError("Frame image size exceeds 300 KB limit.")
        return value


class StudentProctoringAudioUploadSerializer(serializers.Serializer):
    audio = serializers.FileField(required=True)
    rms_db = serializers.FloatField(required=False, default=0.0)

    def validate_audio(self, value):
        # 100 KB max audio snippet size
        if value.size > 100 * 1024:
            raise serializers.ValidationError("Audio snippet size exceeds 100 KB limit.")
        return value


class ProctoringWarningSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProctoringWarning
        fields = [
            'id',
            'warning_type',
            'message',
            'issued_at',
            'acknowledged_at',
        ]
        read_only_fields = ['id', 'warning_type', 'message', 'issued_at']


class AdminProctoringSessionListSerializer(serializers.ModelSerializer):
    session_id = serializers.UUIDField(source='id', read_only=True)
    attempt_id = serializers.UUIDField(source='attempt.id', read_only=True)
    student = serializers.SerializerMethodField()

    class Meta:
        model = ProctoringSession
        fields = [
            'session_id',
            'attempt_id',
            'student',
            'status',
            'risk_score',
            'risk_band',
            'total_events_count',
            'total_warnings_count',
            'review_status',
            'created_at',
            'updated_at',
        ]

    def get_student(self, obj):
        student_user = obj.attempt.student
        profile = getattr(student_user, 'student_profile', None)
        return {
            'id': str(student_user.id),
            'email': student_user.email,
            'euid': getattr(profile, 'euid', ''),
            'full_name': getattr(profile, 'full_name', student_user.email) if profile else student_user.email,
        }


class AdminProctoringEventSerializer(serializers.ModelSerializer):
    evidence_id = serializers.UUIDField(source='evidence.id', read_only=True, allow_null=True)

    class Meta:
        model = ProctoringEvent
        fields = [
            'id',
            'event_type',
            'source',
            'severity',
            'confidence',
            'started_at',
            'ended_at',
            'duration_ms',
            'client_detected_at',
            'server_received_at',
            'model_name',
            'model_version',
            'threshold_version',
            'inference_policy_version',
            'risk_delta',
            'metadata',
            'evidence_id',
        ]


class AdminProctoringReviewSerializer(serializers.ModelSerializer):
    reviewed_by = serializers.CharField(source='reviewer.email', read_only=True)

    class Meta:
        model = ProctoringReview
        fields = [
            'id',
            'decision',
            'notes',
            'reviewed_by',
            'reviewed_at',
        ]
        read_only_fields = ['id', 'reviewed_by', 'reviewed_at']


class AdminProctoringSessionDetailSerializer(serializers.ModelSerializer):
    session_id = serializers.UUIDField(source='id', read_only=True)
    attempt_id = serializers.UUIDField(source='attempt.id', read_only=True)
    student = serializers.SerializerMethodField()
    events = AdminProctoringEventSerializer(many=True, read_only=True)
    warnings = ProctoringWarningSerializer(many=True, read_only=True)
    review = AdminProctoringReviewSerializer(read_only=True)

    class Meta:
        model = ProctoringSession
        fields = [
            'session_id',
            'attempt_id',
            'student',
            'status',
            'risk_score',
            'risk_band',
            'total_events_count',
            'total_warnings_count',
            'review_status',
            'events',
            'warnings',
            'review',
            'created_at',
            'updated_at',
        ]

    def get_student(self, obj):
        student_user = obj.attempt.student
        profile = getattr(student_user, 'student_profile', None)
        return {
            'id': str(student_user.id),
            'email': student_user.email,
            'euid': getattr(profile, 'euid', ''),
            'full_name': getattr(profile, 'full_name', student_user.email) if profile else student_user.email,
        }
