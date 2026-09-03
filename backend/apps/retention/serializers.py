from rest_framework import serializers
from apps.retention.models import (
    RetentionPolicy,
    RetentionRecord,
    LegalHold,
    RetentionTombstone,
    ExportJob,
    FileCleanupQueue,
    PurgeJobRun,
)


class RetentionPolicySerializer(serializers.ModelSerializer):
    created_by_email = serializers.EmailField(source='created_by.email', read_only=True)
    assessment_title = serializers.CharField(source='assessment.title', read_only=True)

    class Meta:
        model = RetentionPolicy
        fields = [
            'id',
            'name',
            'version',
            'scope',
            'assessment',
            'assessment_title',
            'detailed_data_ttl_days',
            'proctoring_evidence_ttl_days',
            'report_retention_ttl_days',
            'is_active',
            'created_by',
            'created_by_email',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'version', 'created_by', 'created_at', 'updated_at']

    def validate(self, attrs):
        scope = attrs.get('scope', getattr(self.instance, 'scope', None))
        assessment = attrs.get('assessment', getattr(self.instance, 'assessment', None))

        if scope == 'ASSESSMENT' and not assessment:
            raise serializers.ValidationError({"assessment": "Assessment is required for assessment-scoped policies."})
        if scope == 'INSTITUTION' and assessment:
            raise serializers.ValidationError({"assessment": "Assessment must not be specified for institution-wide policies."})
        return attrs


class LegalHoldSerializer(serializers.ModelSerializer):
    placed_by_email = serializers.EmailField(source='placed_by.email', read_only=True)
    released_by_email = serializers.EmailField(source='released_by.email', read_only=True)
    assessment_title = serializers.CharField(source='assessment.title', read_only=True)
    student_email = serializers.EmailField(source='student.email', read_only=True)

    class Meta:
        model = LegalHold
        fields = [
            'id',
            'title',
            'case_reference',
            'reason',
            'scope',
            'attempt',
            'student',
            'student_email',
            'assessment',
            'assessment_title',
            'status',
            'placed_by',
            'placed_by_email',
            'placed_at',
            'released_by',
            'released_by_email',
            'released_at',
            'release_reason',
            'created_at',
        ]
        read_only_fields = [
            'id',
            'status',
            'placed_by',
            'placed_at',
            'released_by',
            'released_at',
            'release_reason',
            'created_at',
        ]

    def validate(self, attrs):
        scope = attrs.get('scope')
        if scope == 'ATTEMPT':
            if not attrs.get('attempt'):
                raise serializers.ValidationError({"attempt": "Attempt is required for attempt-scoped holds."})
            if LegalHold.objects.filter(scope='ATTEMPT', attempt=attrs.get('attempt'), status='ACTIVE').exists():
                raise serializers.ValidationError({"attempt": "An active legal hold already exists for this attempt."})
        elif scope == 'STUDENT':
            if not attrs.get('student'):
                raise serializers.ValidationError({"student": "Student is required for student-scoped holds."})
            if LegalHold.objects.filter(scope='STUDENT', student=attrs.get('student'), status='ACTIVE').exists():
                raise serializers.ValidationError({"student": "An active legal hold already exists for this student."})
        elif scope == 'ASSESSMENT':
            if not attrs.get('assessment'):
                raise serializers.ValidationError({"assessment": "Assessment is required for assessment-scoped holds."})
            if LegalHold.objects.filter(scope='ASSESSMENT', assessment=attrs.get('assessment'), status='ACTIVE').exists():
                raise serializers.ValidationError({"assessment": "An active legal hold already exists for this assessment."})
        return attrs


class LegalHoldReleaseSerializer(serializers.Serializer):
    release_reason = serializers.CharField(required=True, allow_blank=False, min_length=5)


class RetentionTombstoneSerializer(serializers.ModelSerializer):
    operator_email = serializers.EmailField(source='operator_user.email', read_only=True)

    class Meta:
        model = RetentionTombstone
        fields = [
            'id',
            'attempt_id',
            'student_id',
            'student_euid',
            'assessment_id',
            'assessment_title_snapshot',
            'purged_at',
            'purged_by_system',
            'operator_user',
            'operator_email',
            'answers_scrubbed_count',
            'code_submissions_scrubbed_count',
            'proctoring_events_scrubbed_count',
            'evidence_files_deleted_count',
            'confirmed_bytes_reclaimed',
            'sha256_audit_proof',
            'created_at',
        ]
        read_only_fields = fields


class ExportJobSerializer(serializers.ModelSerializer):
    assessment_title = serializers.CharField(source='attempt.assessment.title', read_only=True)

    class Meta:
        model = ExportJob
        fields = [
            'id',
            'student',
            'attempt',
            'assessment_title',
            'status',
            'archive_type',
            'started_at',
            'lease_expires_at',
            'encryption_algorithm',
            'encryption_key_version',
            'file_bytes',
            'expires_at',
            'error_message',
            'created_at',
        ]
        read_only_fields = fields


class CreateExportJobSerializer(serializers.Serializer):
    attempt_id = serializers.UUIDField(required=False, allow_null=True)


class RetentionRecordSerializer(serializers.ModelSerializer):
    assessment_title = serializers.CharField(source='attempt.assessment.title', read_only=True)
    student_euid = serializers.CharField(source='attempt.student.euid', read_only=True)

    class Meta:
        model = RetentionRecord
        fields = [
            'id',
            'attempt',
            'assessment_title',
            'student_euid',
            'retention_policy',
            'policy_version',
            'detailed_data_expires_at',
            'proctoring_evidence_expires_at',
            'purge_state',
            'database_scrub_status',
            'filesystem_cleanup_status',
            'last_scrubbed_at',
            'created_at',
        ]
        read_only_fields = fields


class FileCleanupQueueSerializer(serializers.ModelSerializer):
    class Meta:
        model = FileCleanupQueue
        fields = [
            'id',
            'attempt_id',
            'file_path',
            'file_bytes',
            'status',
            'retry_count',
            'last_error',
            'confirmed_deleted_at',
            'created_at',
        ]
        read_only_fields = fields


class PurgeJobRunSerializer(serializers.ModelSerializer):
    operator_email = serializers.EmailField(source='operator_user.email', read_only=True)

    class Meta:
        model = PurgeJobRun
        fields = [
            'id',
            'trigger_type',
            'status',
            'operator_user',
            'operator_email',
            'started_at',
            'completed_at',
            'attempts_evaluated_count',
            'attempts_purged_count',
            'attempts_deferred_hold_count',
            'attempts_deferred_export_count',
            'total_bytes_reclaimed',
            'error_summary',
        ]
        read_only_fields = fields
