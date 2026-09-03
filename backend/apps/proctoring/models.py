import uuid
from decimal import Decimal
from django.conf import settings
from django.db import models
from apps.core.models import UUIDModel, TimeStampedModel
from apps.assessments.models import TestAttempt


class ProctoringSessionStatus(models.TextChoices):
    ACTIVE = 'ACTIVE', 'Active'
    PAUSED = 'PAUSED', 'Paused'
    TERMINATED = 'TERMINATED', 'Terminated'
    DEGRADED = 'DEGRADED', 'Degraded'


class RiskBand(models.TextChoices):
    NORMAL = 'NORMAL', 'Normal (0-20)'
    LOW = 'LOW', 'Low (21-45)'
    MEDIUM = 'MEDIUM', 'Medium (46-70)'
    HIGH = 'HIGH', 'High (71-85)'
    CRITICAL = 'CRITICAL', 'Critical (86-100)'


class ReviewStatus(models.TextChoices):
    UNREVIEWED = 'UNREVIEWED', 'Unreviewed'
    UNDER_REVIEW = 'UNDER_REVIEW', 'Under Review'
    REVIEWED = 'REVIEWED', 'Reviewed'
    DISMISSED = 'DISMISSED', 'Dismissed'
    ESCALATED = 'ESCALATED', 'Escalated'


class EventSource(models.TextChoices):
    BROWSER = 'BROWSER', 'Browser Client Telemetry'
    AI = 'AI', 'Asynchronous AI Inference'
    SERVER = 'SERVER', 'Authoritative Server State'
    SYSTEM = 'SYSTEM', 'System Infrastructure'


class EventSeverity(models.TextChoices):
    LOW = 'LOW', 'Low'
    MEDIUM = 'MEDIUM', 'Medium'
    HIGH = 'HIGH', 'High'
    CRITICAL = 'CRITICAL', 'Critical'


class RetentionClass(models.TextChoices):
    EPHEMERAL_BUFFER = 'EPHEMERAL_BUFFER', 'Ephemeral Buffer (0s)'
    TEMPORARY_EVIDENCE = 'TEMPORARY_EVIDENCE', 'Temporary Flagged Evidence (30d)'
    OPERATIONAL_AUDIT = 'OPERATIONAL_AUDIT', 'Operational Audit Ledger (90d)'
    PERMANENT_RECORD = 'PERMANENT_RECORD', 'Permanent Academic Summary'


class ProctoringSession(UUIDModel, TimeStampedModel):
    """
    1-to-1 proctoring envelope linked to a specific student TestAttempt.
    Tracks mathematical risk score, risk band, event counts, and administrative review status.
    """
    attempt = models.OneToOneField(
        TestAttempt,
        on_delete=models.CASCADE,
        related_name='proctoring_session'
    )
    status = models.CharField(
        max_length=20,
        choices=ProctoringSessionStatus.choices,
        default=ProctoringSessionStatus.ACTIVE,
        db_index=True
    )
    risk_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        db_index=True
    )
    risk_band = models.CharField(
        max_length=20,
        choices=RiskBand.choices,
        default=RiskBand.NORMAL,
        db_index=True
    )
    total_events_count = models.PositiveIntegerField(default=0)
    total_warnings_count = models.PositiveIntegerField(default=0)
    review_status = models.CharField(
        max_length=20,
        choices=ReviewStatus.choices,
        default=ReviewStatus.UNREVIEWED,
        db_index=True
    )

    class Meta:
        db_table = 'proctoring_sessions'
        indexes = [
            models.Index(fields=['attempt', 'status'], name='idx_proct_attempt_status'),
            models.Index(fields=['risk_band', 'review_status'], name='idx_proct_risk_review'),
        ]

    def __str__(self):
        return f"ProctoringSession {self.id} for Attempt {self.attempt_id} [{self.risk_band}: {self.risk_score}]"


class ProctoringEvidence(UUIDModel):
    """
    Immutable metadata representing captured visual or acoustic keyframe evidence.
    Includes SHA-256 hash for integrity non-tampering verification and Phase 9 retention metadata.
    """
    session = models.ForeignKey(
        ProctoringSession,
        on_delete=models.CASCADE,
        related_name='evidences'
    )
    media_type = models.CharField(
        max_length=32,
        choices=[('IMAGE_JPEG', 'JPEG Image Keyframe'), ('AUDIO_WEBM', 'WebM Opus Audio Snippet')],
        default='IMAGE_JPEG'
    )
    storage_path = models.CharField(max_length=512)
    sha256_hash = models.CharField(max_length=64)
    file_size_bytes = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    expires_at = models.DateTimeField(null=True, blank=True, db_index=True)
    retention_class = models.CharField(
        max_length=32,
        choices=RetentionClass.choices,
        default=RetentionClass.TEMPORARY_EVIDENCE,
        db_index=True
    )

    class Meta:
        db_table = 'proctoring_evidences'
        indexes = [
            models.Index(fields=['session', 'created_at'], name='idx_evidence_session_time'),
            models.Index(fields=['retention_class', 'expires_at'], name='idx_evidence_retention_expiry'),
        ]

    def __str__(self):
        return f"ProctoringEvidence {self.id} ({self.media_type}) [{self.sha256_hash[:8]}...]"


class ProctoringEvent(UUIDModel):
    """
    Append-only immutable event ledger recording client heuristics, AI signals, and system failures.
    """
    session = models.ForeignKey(
        ProctoringSession,
        on_delete=models.CASCADE,
        related_name='events'
    )
    event_type = models.CharField(max_length=64, db_index=True)
    source = models.CharField(
        max_length=20,
        choices=EventSource.choices,
        default=EventSource.BROWSER,
        db_index=True
    )
    severity = models.CharField(
        max_length=20,
        choices=EventSeverity.choices,
        default=EventSeverity.LOW,
        db_index=True
    )
    confidence = models.FloatField(default=1.0)
    started_at = models.DateTimeField(db_index=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    duration_ms = models.PositiveIntegerField(default=0)
    client_detected_at = models.DateTimeField(null=True, blank=True)
    server_received_at = models.DateTimeField(auto_now_add=True, db_index=True)
    model_name = models.CharField(max_length=64, blank=True, default='')
    model_version = models.CharField(max_length=32, blank=True, default='')
    threshold_version = models.CharField(max_length=32, default='V1')
    inference_policy_version = models.CharField(max_length=32, default='V1')
    risk_delta = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00')
    )
    metadata = models.JSONField(default=dict, blank=True)
    evidence = models.ForeignKey(
        ProctoringEvidence,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='events'
    )

    class Meta:
        db_table = 'proctoring_events'
        ordering = ['server_received_at']
        indexes = [
            models.Index(fields=['session', 'server_received_at'], name='idx_event_session_recv_time'),
            models.Index(fields=['session', 'event_type'], name='idx_event_session_type'),
            models.Index(fields=['event_type', 'server_received_at'], name='idx_event_type_time'),
        ]

    def __str__(self):
        return f"ProctoringEvent {self.id} [{self.event_type} - {self.source}] (Delta: +{self.risk_delta})"


class ProctoringWarning(UUIDModel):
    """
    Controlled, non-accusatory student feedback warnings generated with cooldowns.
    """
    session = models.ForeignKey(
        ProctoringSession,
        on_delete=models.CASCADE,
        related_name='warnings'
    )
    warning_type = models.CharField(max_length=64, db_index=True)
    message = models.CharField(max_length=255)
    issued_at = models.DateTimeField(auto_now_add=True, db_index=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'proctoring_warnings'
        indexes = [
            models.Index(fields=['session', 'issued_at'], name='idx_warning_session_time'),
        ]

    def __str__(self):
        return f"ProctoringWarning {self.id} ({self.warning_type}) for Session {self.session_id}"


class ProctoringReview(UUIDModel):
    """
    Authoritative administrator review decision and notes for a proctoring session.
    """
    session = models.OneToOneField(
        ProctoringSession,
        on_delete=models.CASCADE,
        related_name='review'
    )
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='proctoring_reviews'
    )
    decision = models.CharField(
        max_length=64,
        choices=[
            ('REVIEWED_CLEAN', 'Reviewed - Clean / Normal'),
            ('SUSPICIOUS_CONFIRMED', 'Suspicious Behavior Confirmed'),
            ('DISMISSED_FALSE_POSITIVE', 'Dismissed as False Positive'),
            ('REQUIRES_FURTHER_INSPECTION', 'Requires Further Inspection'),
        ],
        default='REVIEWED_CLEAN'
    )
    notes = models.TextField(blank=True, default='')
    reviewed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'proctoring_reviews'

    def __str__(self):
        return f"ProctoringReview {self.id} [{self.decision}] by {self.reviewer.email}"
