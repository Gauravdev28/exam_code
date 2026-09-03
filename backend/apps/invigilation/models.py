import uuid
from django.db import models
from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone

from apps.core.models import UUIDModel, TimeStampedModel
from apps.assessments.models import Assessment, TestAttempt


class InterventionType(models.TextChoices):
    WARNING_ISSUED = 'WARNING_ISSUED', 'Warning Issued'
    WARNING_ACKNOWLEDGED = 'WARNING_ACKNOWLEDGED', 'Warning Acknowledged'
    PAUSE_STARTED = 'PAUSE_STARTED', 'Pause Started'
    PAUSE_ENDED = 'PAUSE_ENDED', 'Pause Ended'
    ROOM_SCAN_REQUESTED = 'ROOM_SCAN_REQUESTED', 'Room Scan Requested'
    ROOM_SCAN_COMPLETED = 'ROOM_SCAN_COMPLETED', 'Room Scan Completed'
    TERMINATION_REQUESTED = 'TERMINATION_REQUESTED', 'Termination Requested'
    TERMINATION_CONFIRMED = 'TERMINATION_CONFIRMED', 'Termination Confirmed'


class ImmutableInterventionQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise PermissionDenied(
            "ProctorIntervention records are strictly append-only and cannot be updated via QuerySet."
        )

    def delete(self):
        raise PermissionDenied(
            "ProctorIntervention records cannot be deleted directly via QuerySet. Deletion is governed by Phase 9 retention lifecycle."
        )


class ImmutableInterventionManager(models.Manager.from_queryset(ImmutableInterventionQuerySet)):
    pass


class ProctorAssignment(UUIDModel, TimeStampedModel):
    """
    Explicit authorization link designating which proctors are permitted to monitor
    and intervene in specific assessment cohorts.
    """
    proctor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='proctor_assignments',
        help_text="User with PROCTOR or ADMIN role."
    )
    assessment = models.ForeignKey(
        Assessment,
        on_delete=models.CASCADE,
        related_name='proctor_assignments',
        help_text="Target assessment cohort."
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Designates whether the proctor is currently on active duty."
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='proctor_assignments_created'
    )
    max_candidates = models.PositiveIntegerField(
        default=30,
        help_text="Configurable operational capacity limit (default 30 candidates per proctor)."
    )
    notes = models.TextField(
        blank=True,
        default='',
        help_text="Administrative notes regarding the duty assignment."
    )

    class Meta:
        db_table = 'proctor_assignments'
        constraints = [
            models.UniqueConstraint(
                fields=['proctor', 'assessment'],
                name='unique_proctor_assessment_assignment'
            )
        ]
        indexes = [
            models.Index(fields=['assessment', 'is_active'], name='idx_proct_assign_active'),
        ]

    def __str__(self):
        return f"Proctor {self.proctor.email} -> {self.assessment.title} (Active: {self.is_active})"


class ProctorIntervention(UUIDModel, TimeStampedModel):
    """
    Append-only immutable audit ledger of all human proctor interventions and student acknowledgements.
    Once committed, audit fields on these records can NEVER be modified or deleted.
    Lifecycle transitions (e.g. PAUSE_STARTED -> PAUSE_ENDED) are represented by additional immutable events.
    """
    objects = ImmutableInterventionManager()

    attempt = models.ForeignKey(
        TestAttempt,
        on_delete=models.CASCADE,
        related_name='proctor_interventions',
        help_text="Target test attempt."
    )
    proctor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='issued_interventions',
        help_text="Acting human proctor (null for student actions like acknowledgement)."
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='student_interventions',
        help_text="Target candidate."
    )
    event_type = models.CharField(
        max_length=40,
        choices=InterventionType.choices,
        db_index=True
    )
    reason_code = models.CharField(
        max_length=64,
        blank=True,
        default='',
        help_text="Machine-readable reason code (e.g. MULTIPLE_FACES, SUSPICIOUS_AUDIO, DISQUALIFICATION_CAUSE)."
    )
    reason_text = models.TextField(
        blank=True,
        default='',
        help_text="Candidate-visible justification or warning message."
    )
    internal_notes = models.TextField(
        blank=True,
        default='',
        help_text="Restricted proctor/admin investigation remarks. Strictly excluded from student DSAR exports."
    )
    parent_event = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='child_events',
        help_text="Links lifecycle pairs (e.g. PAUSE_ENDED links to PAUSE_STARTED; ACK links to WARNING)."
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Structured operational telemetry (e.g. snapshot risk band, client latency, duration_seconds)."
    )
    request_idempotency_key = models.CharField(
        max_length=128,
        blank=True,
        default='',
        db_index=True,
        help_text="Client-supplied or server-generated idempotency key preventing duplicate dispatches."
    )
    issued_at = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        help_text="Authoritative server timestamp when the intervention occurred."
    )

    class Meta:
        db_table = 'proctor_interventions'
        ordering = ['issued_at']
        indexes = [
            models.Index(fields=['attempt', 'event_type'], name='idx_proct_interv_att_type'),
            models.Index(fields=['attempt', 'issued_at'], name='idx_proct_interv_att_time'),
            models.Index(fields=['request_idempotency_key'], name='idx_proct_interv_idempotent'),
        ]

    def __str__(self):
        return f"Intervention [{self.event_type}] on Attempt {self.attempt_id} by {self.proctor or 'System/Student'}"

    def save(self, *args, **kwargs):
        # Strict Append-Only Invariant: committed intervention records cannot be mutated
        if not self._state.adding:
            raise PermissionDenied(
                "ProctorIntervention records are strictly append-only and immutable. Updates are forbidden."
            )
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        # Destruction Invariant: interventions can only be purged by Phase 9 retention lifecycle
        raise PermissionDenied(
            "ProctorIntervention records cannot be deleted directly. Deletion is governed by Phase 9 retention lifecycle."
        )


class ProctorDutySession(UUIDModel, TimeStampedModel):
    """
    Operational audit log tracking proctor active duty intervals, heartbeats, and candidate load.
    """
    proctor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='duty_sessions'
    )
    assessment = models.ForeignKey(
        Assessment,
        on_delete=models.CASCADE,
        related_name='proctor_duty_sessions'
    )
    started_at = models.DateTimeField(default=timezone.now)
    ended_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    active_monitored_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of active student attempts monitored during this shift."
    )
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'proctor_duty_sessions'
        ordering = ['-started_at']

    def __str__(self):
        return f"DutySession: {self.proctor.email} on {self.assessment.title} (Active: {self.is_active})"


class ProctorChatMessage(UUIDModel, TimeStampedModel):
    """
    Ephemeral bilateral communication log between an authorized proctor and a candidate
    during an active examination attempt.
    """
    attempt = models.ForeignKey(
        TestAttempt,
        on_delete=models.CASCADE,
        related_name='proctor_chat_messages'
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='sent_proctor_chats'
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='received_proctor_chats'
    )
    message_text = models.TextField(
        help_text="Student-facing chat content. Excludes internal investigation remarks."
    )
    is_read = models.BooleanField(default=False)
    sent_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        db_table = 'proctor_chat_messages'
        ordering = ['sent_at']
        indexes = [
            models.Index(fields=['attempt', 'sent_at'], name='idx_proct_chat_att_time'),
        ]

    def __str__(self):
        return f"Chat on Attempt {self.attempt_id} from {self.sender.email} at {self.sent_at}"

    def save(self, *args, **kwargs):
        if not self._state.adding:
            # Only is_read can be updated
            update_fields = kwargs.get('update_fields')
            if update_fields and set(update_fields) == {'is_read', 'updated_at'}:
                super().save(*args, **kwargs)
                return
            raise PermissionDenied("ProctorChatMessage text is immutable once sent.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionDenied("ProctorChatMessage records cannot be deleted directly. Governed by Phase 9 retention.")
