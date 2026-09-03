from django.db import transaction, models
from django.utils import timezone
from django.core.exceptions import ValidationError

from apps.accounts.models import User
from apps.assessments.models import Assessment, TestAttempt
from apps.retention.models import (
    LegalHold,
    LegalHoldScope,
    LegalHoldStatus,
    RetentionRecord,
    PurgeState,
)


class LegalHoldManager:
    @staticmethod
    def create_attempt_hold(attempt_id, title, case_reference, reason, user):
        """
        Creates an attempt-scoped legal hold.
        Acquires row lock on TestAttempt FOR UPDATE.
        Prevents duplicate active holds for the same attempt.
        """
        with transaction.atomic():
            attempt = TestAttempt.objects.select_for_update().get(id=attempt_id)
            if LegalHold.objects.filter(scope=LegalHoldScope.ATTEMPT, attempt=attempt, status=LegalHoldStatus.ACTIVE).exists():
                raise ValidationError(f"An active legal hold already exists for attempt {attempt_id}.")

            hold = LegalHold.objects.create(
                scope=LegalHoldScope.ATTEMPT,
                attempt=attempt,
                title=title,
                case_reference=case_reference,
                reason=reason,
                placed_by=user,
                status=LegalHoldStatus.ACTIVE,
                placed_at=timezone.now()
            )
            return hold

    @staticmethod
    def create_student_hold(student_id, title, case_reference, reason, user):
        """
        Creates a student-scoped legal hold.
        Acquires row lock on User (Student row) FOR UPDATE.
        Scales to any cohort size without locking thousands of attempt rows.
        Prevents duplicate active holds for the same student.
        """
        with transaction.atomic():
            student = User.objects.select_for_update().get(id=student_id)
            if LegalHold.objects.filter(scope=LegalHoldScope.STUDENT, student=student, status=LegalHoldStatus.ACTIVE).exists():
                raise ValidationError(f"An active legal hold already exists for student {student_id}.")

            hold = LegalHold.objects.create(
                scope=LegalHoldScope.STUDENT,
                student=student,
                title=title,
                case_reference=case_reference,
                reason=reason,
                placed_by=user,
                status=LegalHoldStatus.ACTIVE,
                placed_at=timezone.now()
            )
            return hold

    @staticmethod
    def create_assessment_hold(assessment_id, title, case_reference, reason, user):
        """
        Creates an assessment-scoped legal hold.
        Acquires row lock on Assessment row FOR UPDATE.
        Scales to thousands of attempts without table-wide locking.
        Prevents duplicate active holds for the same assessment.
        """
        with transaction.atomic():
            assessment = Assessment.objects.select_for_update().get(id=assessment_id)
            if LegalHold.objects.filter(scope=LegalHoldScope.ASSESSMENT, assessment=assessment, status=LegalHoldStatus.ACTIVE).exists():
                raise ValidationError(f"An active legal hold already exists for assessment {assessment_id}.")

            hold = LegalHold.objects.create(
                scope=LegalHoldScope.ASSESSMENT,
                assessment=assessment,
                title=title,
                case_reference=case_reference,
                reason=reason,
                placed_by=user,
                status=LegalHoldStatus.ACTIVE,
                placed_at=timezone.now()
            )
            return hold

    @staticmethod
    def release_hold(hold_id, release_reason, user):
        """
        Releases an active legal hold.
        Acquires parent scope owner lock first according to global lock hierarchy,
        then locks the LegalHold row FOR UPDATE.
        """
        with transaction.atomic():
            hold = LegalHold.objects.get(id=hold_id)
            if hold.status == LegalHoldStatus.RELEASED:
                raise ValidationError("Hold is already released.")

            # Acquire scope owner lock according to global hierarchy:
            if hold.scope == LegalHoldScope.ASSESSMENT and hold.assessment_id:
                Assessment.objects.select_for_update().get(id=hold.assessment_id)
            elif hold.scope == LegalHoldScope.STUDENT and hold.student_id:
                User.objects.select_for_update().get(id=hold.student_id)
            elif hold.scope == LegalHoldScope.ATTEMPT and hold.attempt_id:
                TestAttempt.objects.select_for_update().get(id=hold.attempt_id)

            hold = LegalHold.objects.select_for_update().get(id=hold_id)
            hold.status = LegalHoldStatus.RELEASED
            hold.released_at = timezone.now()
            hold.released_by = user
            hold.release_reason = release_reason
            hold.save()
            return hold

    @staticmethod
    def get_active_holds_for_attempt(attempt, assessment=None, student=None):
        assessment = assessment or attempt.assessment
        student = student or attempt.student
        return LegalHold.objects.filter(
            models.Q(scope=LegalHoldScope.ATTEMPT, attempt=attempt) |
            models.Q(scope=LegalHoldScope.STUDENT, student=student) |
            models.Q(scope=LegalHoldScope.ASSESSMENT, assessment=assessment),
            status=LegalHoldStatus.ACTIVE
        )

    @classmethod
    def has_active_hold_for_attempt(cls, attempt, assessment=None, student=None):
        return cls.get_active_holds_for_attempt(attempt, assessment, student).exists()
