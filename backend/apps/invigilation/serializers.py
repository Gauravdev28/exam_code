from rest_framework import serializers
from apps.invigilation.models import (
    ProctorAssignment,
    ProctorIntervention,
    InterventionType,
    ProctorDutySession,
    ProctorChatMessage,
)


class ProctorAssignmentSerializer(serializers.ModelSerializer):
    proctor_email = serializers.CharField(source='proctor.email', read_only=True)
    assessment_title = serializers.CharField(source='assessment.title', read_only=True)

    class Meta:
        model = ProctorAssignment
        fields = [
            'id',
            'proctor',
            'proctor_email',
            'assessment',
            'assessment_title',
            'is_active',
            'max_candidates',
            'notes',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class ProctorInterventionSerializer(serializers.ModelSerializer):
    """
    Comprehensive proctor-facing intervention serializer including internal investigation notes.
    """
    proctor_email = serializers.CharField(source='proctor.email', read_only=True, default=None)
    student_email = serializers.CharField(source='student.email', read_only=True)

    class Meta:
        model = ProctorIntervention
        fields = [
            'id',
            'attempt',
            'proctor',
            'proctor_email',
            'student',
            'student_email',
            'event_type',
            'reason_code',
            'reason_text',
            'internal_notes',
            'parent_event',
            'metadata',
            'issued_at'
        ]
        read_only_fields = ['id', 'issued_at']


class StudentInterventionSerializer(serializers.ModelSerializer):
    """
    Candidate-safe intervention serializer.
    STRICTLY EXCLUDES internal_notes and proctor identity information.
    """
    class Meta:
        model = ProctorIntervention
        fields = [
            'id',
            'attempt',
            'event_type',
            'reason_code',
            'reason_text',
            'parent_event',
            'issued_at'
        ]
        read_only_fields = ['id', 'issued_at']


class ProctorChatMessageSerializer(serializers.ModelSerializer):
    sender_email = serializers.CharField(source='sender.email', read_only=True)
    sender_role = serializers.CharField(source='sender.role', read_only=True)
    recipient_email = serializers.CharField(source='recipient.email', read_only=True)

    class Meta:
        model = ProctorChatMessage
        fields = [
            'id',
            'attempt',
            'sender',
            'sender_email',
            'sender_role',
            'recipient',
            'recipient_email',
            'message_text',
            'is_read',
            'sent_at'
        ]
        read_only_fields = ['id', 'is_read', 'sent_at']


class WarningIssueSerializer(serializers.Serializer):
    reason_code = serializers.CharField(max_length=64, default='PROCTOR_WARNING')
    message = serializers.CharField(max_length=1000)
    internal_notes = serializers.CharField(max_length=2000, required=False, allow_blank=True, default='')
    idempotency_key = serializers.CharField(max_length=128, required=False, allow_blank=True, default='')


class PauseAttemptSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=1000, required=False, allow_blank=True, default='')
    internal_notes = serializers.CharField(max_length=2000, required=False, allow_blank=True, default='')
    idempotency_key = serializers.CharField(max_length=128, required=False, allow_blank=True, default='')
    max_pause_seconds = serializers.IntegerField(required=False, default=900, min_value=60, max_value=3600)


class ResumeAttemptSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=1000, required=False, allow_blank=True, default='')
    internal_notes = serializers.CharField(max_length=2000, required=False, allow_blank=True, default='')
    idempotency_key = serializers.CharField(max_length=128, required=False, allow_blank=True, default='')


class RoomScanRequestSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=1000, required=False, allow_blank=True, default='')
    internal_notes = serializers.CharField(max_length=2000, required=False, allow_blank=True, default='')


class TerminateAttemptSerializer(serializers.Serializer):
    reason_code = serializers.CharField(max_length=64)
    formal_justification = serializers.CharField(max_length=2000)
    internal_notes = serializers.CharField(max_length=2000, required=False, allow_blank=True, default='')
    idempotency_key = serializers.CharField(max_length=128, required=False, allow_blank=True, default='')


class ChatMessageSendSerializer(serializers.Serializer):
    message_text = serializers.CharField(max_length=2000)
    recipient_id = serializers.UUIDField(required=False, allow_null=True, default=None)


class AcknowledgeWarningSerializer(serializers.Serializer):
    intervention_id = serializers.UUIDField()


class CompleteRoomScanSerializer(serializers.Serializer):
    scan_event_id = serializers.UUIDField()
