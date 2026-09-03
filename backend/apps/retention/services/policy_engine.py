from datetime import timedelta
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError

from apps.assessments.models import AttemptStatus
from apps.results.models import ResultStatus
from apps.retention.models import (
    RetentionPolicy,
    PolicyScope,
    RetentionRecord,
    PurgeState,
    ScrubStatus,
    FileCleanupStatus,
)


class RetentionPolicyEngine:
    @staticmethod
    def get_or_create_default_institution_policy(user=None):
        policy = RetentionPolicy.objects.filter(
            scope=PolicyScope.INSTITUTION,
            is_active=True
        ).first()
        if not policy:
            policy = RetentionPolicy.objects.create(
                name="Default Institutional Retention Policy",
                version=1,
                scope=PolicyScope.INSTITUTION,
                detailed_data_ttl_days=getattr(settings, 'RETENTION_DEFAULT_DETAILED_DATA_TTL_DAYS', 30),
                proctoring_evidence_ttl_days=getattr(settings, 'RETENTION_DEFAULT_PROCTORING_EVIDENCE_TTL_DAYS', 30),
                report_retention_ttl_days=getattr(settings, 'RETENTION_DEFAULT_REPORT_TTL_DAYS', 7),
                is_active=True,
                created_by=user
            )
        return policy

    @classmethod
    def resolve_for_assessment(cls, assessment):
        """
        Resolves the applicable active retention policy for an assessment.
        Checks for an assessment-specific active policy first; falls back to institutional default.
        """
        if assessment:
            specific_policy = RetentionPolicy.objects.filter(
                scope=PolicyScope.ASSESSMENT,
                assessment=assessment,
                is_active=True
            ).first()
            if specific_policy:
                return specific_policy
        return cls.get_or_create_default_institution_policy()

    @classmethod
    def create_retention_record_for_finalized_attempt(cls, attempt):
        """
        Strictly binds a RetentionRecord 1:1 with a TestAttempt once it is terminal and finalized.
        Deterministic deadlines are calculated and frozen onto the record.
        """
        if attempt.status not in [AttemptStatus.SUBMITTED, AttemptStatus.EXPIRED, AttemptStatus.CANCELLED]:
            raise ValidationError(f"Cannot create RetentionRecord for non-terminal attempt status '{attempt.status}'.")

        if not hasattr(attempt, 'result') or attempt.result.status != ResultStatus.FINALIZED:
            raise ValidationError("Cannot create RetentionRecord for unfinalized assessment attempt.")

        # Idempotent return if record already exists
        existing = RetentionRecord.objects.filter(attempt=attempt).first()
        if existing:
            return existing

        policy = cls.resolve_for_assessment(attempt.assessment)
        base_timestamp = attempt.submitted_at or attempt.started_at or timezone.now()

        detailed_expires_at = base_timestamp + timedelta(days=policy.detailed_data_ttl_days)
        proctoring_expires_at = base_timestamp + timedelta(days=policy.proctoring_evidence_ttl_days)

        with transaction.atomic():
            # Acquire row lock on TestAttempt to serialize concurrent finalization calls
            from apps.assessments.models import TestAttempt as AttemptModel
            attempt_locked = AttemptModel.objects.select_for_update().get(id=attempt.id)
            existing_locked = RetentionRecord.objects.filter(attempt=attempt_locked).first()
            if existing_locked:
                return existing_locked

            record = RetentionRecord.objects.create(
                attempt=attempt_locked,
                retention_policy=policy,
                policy_version=policy.version,
                detailed_data_expires_at=detailed_expires_at,
                proctoring_evidence_expires_at=proctoring_expires_at,
                purge_state=PurgeState.SCHEDULED,
                database_scrub_status=ScrubStatus.PENDING,
                filesystem_cleanup_status=FileCleanupStatus.PENDING,
            )
        return record
