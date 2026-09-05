from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.db import transaction
from django.db.models import Q

from apps.accounts.models import User, StudentProfile, Section, Role, AuditLog
from apps.assessments.models import (
    Assessment, AssessmentAssignment, AssessmentQuestion,
    AssessmentSnapshot, AssessmentSnapshotQuestion, TestAttempt, AttemptAnswer
)
from apps.results.models import (
    AssessmentResult, QuestionResult, HistoricalResultSummary,
    AssessmentAnalyticsSnapshot, ReportJob
)
from apps.proctoring.models import (
    ProctoringSession, ProctoringEvidence, ProctoringEvent,
    ProctoringWarning, ProctoringReview
)
from apps.invigilation.models import (
    ProctorAssignment, ProctorIntervention, ProctorDutySession, ProctorChatMessage
)
from apps.retention.models import (
    RetentionRecord, LegalHold, FileCleanupQueue, ExportJob
)


class Command(BaseCommand):
    help = (
        "Completely and safely remove temporary assessment/student/UAT data "
        "from the local development database so testing starts from a clean state."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Confirm execution of UAT data cleanup. Without this flag, a dry-run summary is displayed.',
        )
        parser.add_argument(
            '--keep-sections',
            action='store_true',
            help='Do not remove temporary sections (AIML-A, AIML-B, CSE-A, CORE-A).',
        )

    def handle(self, *args, **options):
        # 1. Strict environment guard: refuse to run in production
        if not settings.DEBUG:
            raise CommandError(
                "SAFETY HALT: cleanup_uat_data is strictly restricted to development/test environments (DEBUG=False)."
            )

        confirm = options.get('confirm', False)
        clean_sections = not options.get('keep_sections', False)

        self.stdout.write(self.style.MIGRATE_HEADING("\n=== CODEGUARD UAT DATA CLEANUP INSPECTION ==="))

        # 2. Identify target temporary students
        # Preserve Primary Admin, secondary admins, proctors, and permanent students
        permanent_emails = ['gauravagl07@gmail.com', 'gauravagldeveloper28@gmail.com', 'vikul@gmail.com', 'proctor@codeguard.local']

        temp_students_qs = User.objects.filter(role=Role.STUDENT).exclude(
            email__in=permanent_emails
        ).filter(
            Q(email__endswith='@test.edu') |
            Q(email__startswith='aiml') |
            Q(email__startswith='csetarget') |
            Q(email__startswith='cse_excluded') |
            Q(email__startswith='student.updated.') |
            Q(student_profile__roll_number__startswith='R_')
        )
        temp_student_ids = list(temp_students_qs.values_list('id', flat=True))

        # 3. Identify target temporary assessments
        temp_assessments_qs = Assessment.objects.filter(
            Q(title__startswith='Midterm Exam 1788') |
            Q(title__startswith='UAT Payload') |
            Q(title__startswith='Test Deletion Draft') |
            Q(title__startswith='Copy of Midterm Exam') |
            Q(title__contains='Targeting Test Assessment')
        )
        temp_assessment_ids = list(temp_assessments_qs.values_list('id', flat=True))

        # 4. Identify dependent attempts and assignments
        temp_attempts_qs = TestAttempt.objects.filter(
            Q(assessment_id__in=temp_assessment_ids) | Q(student_id__in=temp_student_ids)
        )
        temp_attempt_ids = list(temp_attempts_qs.values_list('id', flat=True))

        temp_assignments_qs = AssessmentAssignment.objects.filter(
            Q(assessment_id__in=temp_assessment_ids) | Q(student_id__in=temp_student_ids)
        )
        temp_assignment_ids = list(temp_assignments_qs.values_list('id', flat=True))

        # 5. Identify temporary sections
        temp_sections_qs = Section.objects.filter(
            Q(code__in=['AIML-A', 'AIML-B', 'CSE-A', 'CORE-A'])
        ) if clean_sections else Section.objects.none()
        temp_section_ids = list(temp_sections_qs.values_list('id', flat=True))

        # Display Summary
        self.stdout.write(f"Temporary Student Accounts identified:  {len(temp_student_ids)}")
        self.stdout.write(f"Temporary Assessments identified:       {len(temp_assessment_ids)}")
        self.stdout.write(f"Dependent Test Attempts identified:     {len(temp_attempt_ids)}")
        self.stdout.write(f"Dependent Assignments identified:       {len(temp_assignment_ids)}")
        self.stdout.write(f"Target Sections to clean:               {len(temp_section_ids)}")

        if not confirm:
            self.stdout.write(self.style.WARNING(
                "\n[DRY RUN] No changes were made. Run with --confirm to execute cleanup."
            ))
            return

        self.stdout.write(self.style.WARNING("\n[EXECUTION] Beginning atomic cleanup..."))

        stats = {}
        with transaction.atomic():
            # A. Clean TestAttempt dependencies
            if temp_attempt_ids:
                # 1. Attempt answers
                c, _ = AttemptAnswer.objects.filter(attempt_id__in=temp_attempt_ids).delete()
                stats['AttemptAnswer'] = c

                # 2. Proctoring records
                c, _ = ProctoringEvidence.objects.filter(session__attempt_id__in=temp_attempt_ids).delete()
                stats['ProctoringEvidence'] = c
                c, _ = ProctoringEvent.objects.filter(session__attempt_id__in=temp_attempt_ids).delete()
                stats['ProctoringEvent'] = c
                c, _ = ProctoringWarning.objects.filter(session__attempt_id__in=temp_attempt_ids).delete()
                stats['ProctoringWarning'] = c
                c, _ = ProctoringReview.objects.filter(session__attempt_id__in=temp_attempt_ids).delete()
                stats['ProctoringReview'] = c
                c, _ = ProctoringSession.objects.filter(attempt_id__in=temp_attempt_ids).delete()
                stats['ProctoringSession'] = c

                # 3. Results & Analytics
                c, _ = QuestionResult.objects.filter(assessment_result__attempt_id__in=temp_attempt_ids).delete()
                stats['QuestionResult'] = c
                c, _ = AssessmentResult.objects.filter(attempt_id__in=temp_attempt_ids).delete()
                stats['AssessmentResult'] = c
                c, _ = HistoricalResultSummary.objects.filter(student_id__in=temp_student_ids).delete()
                stats['HistoricalResultSummary'] = c

                # 4. Retention records for attempts
                c, _ = RetentionRecord.objects.filter(attempt_id__in=temp_attempt_ids).delete()
                stats['RetentionRecord'] = c
                c, _ = LegalHold.objects.filter(Q(attempt_id__in=temp_attempt_ids) | Q(student_id__in=temp_student_ids)).delete()
                stats['LegalHold'] = c
                c, _ = FileCleanupQueue.objects.filter(attempt_id__in=temp_attempt_ids).delete()
                stats['FileCleanupQueue'] = c
                c, _ = ExportJob.objects.filter(student_id__in=temp_student_ids).delete()
                stats['ExportJob'] = c

                # 5. Delete TestAttempts
                c, _ = temp_attempts_qs.delete()
                stats['TestAttempt'] = c

            # B. Clean Invigilation records for temporary attempts and assessments
            if temp_attempt_ids:
                try:
                    c = ProctorChatMessage.objects.filter(attempt_id__in=temp_attempt_ids).hard_purge_for_retention()
                    stats['ProctorChatMessage'] = c[0] if isinstance(c, tuple) else c
                except Exception:
                    pass

                try:
                    c = ProctorIntervention.objects.filter(attempt_id__in=temp_attempt_ids).hard_purge_for_retention()
                    stats['ProctorIntervention'] = c[0] if isinstance(c, tuple) else c
                except Exception:
                    pass

            if temp_assessment_ids:
                c, _ = ProctorDutySession.objects.filter(assessment_id__in=temp_assessment_ids).delete()
                stats['ProctorDutySession'] = c
                c, _ = ProctorAssignment.objects.filter(assessment_id__in=temp_assessment_ids).delete()
                stats['ProctorAssignment'] = c
                c, _ = ReportJob.objects.filter(assessment_id__in=temp_assessment_ids).delete()
                stats['ReportJob'] = c
                c, _ = AssessmentAnalyticsSnapshot.objects.filter(assessment_id__in=temp_assessment_ids).delete()
                stats['AssessmentAnalyticsSnapshot'] = c

            # C. Clean Assessment assignments
            c, _ = AssessmentAssignment.objects.filter(
                Q(assessment_id__in=temp_assessment_ids) | Q(student_id__in=temp_student_ids)
            ).delete()
            stats['AssessmentAssignment'] = c

            # D. Clean Assessment Snapshots (bypassing model.delete() via QuerySet delete)
            if temp_assessment_ids:
                c, _ = AssessmentSnapshotQuestion.objects.filter(snapshot__assessment_id__in=temp_assessment_ids).delete()
                stats['AssessmentSnapshotQuestion'] = c
                c, _ = AssessmentSnapshot.objects.filter(assessment_id__in=temp_assessment_ids).delete()
                stats['AssessmentSnapshot'] = c

                # Clean Assessment questions
                c, _ = AssessmentQuestion.objects.filter(assessment_id__in=temp_assessment_ids).delete()
                stats['AssessmentQuestion'] = c

                # Clear M2M target relations through tables directly before deleting assessments
                Assessment.target_sections.through.objects.filter(assessment_id__in=temp_assessment_ids).delete()
                Assessment.target_students.through.objects.filter(assessment_id__in=temp_assessment_ids).delete()

                c, _ = Assessment.objects.filter(id__in=temp_assessment_ids).delete()
                stats['Assessment'] = c

            # E. Clean Student Profiles and User records
            if temp_student_ids:
                c, _ = StudentProfile.objects.filter(user_id__in=temp_student_ids).delete()
                stats['StudentProfile'] = c

                c, _ = AuditLog.objects.filter(
                    Q(actor_id__in=temp_student_ids) | Q(target_id__in=[str(uid) for uid in temp_student_ids])
                ).delete()
                stats['AuditLog'] = c

                user_del_count = 0
                for u in User.objects.filter(id__in=temp_student_ids):
                    u.delete()
                    user_del_count += 1
                stats['User'] = user_del_count

            # F. Clean Sections if requested and no non-temp students reference them
            if clean_sections and temp_section_ids:
                for sec in Section.objects.filter(id__in=temp_section_ids):
                    remaining_count = sec.students.count()
                    if remaining_count == 0:
                        sec_code = sec.code
                        sec.delete()
                        stats.setdefault('Section', 0)
                        stats['Section'] += 1

        self.stdout.write(self.style.SUCCESS("\nCleanup completed successfully! Entities removed:"))
        for entity, count in stats.items():
            if count > 0:
                self.stdout.write(f"  ✓ {entity:30}: {count}")

        # Post-cleanup integrity verification
        primary_admin = User.objects.filter(role=Role.ADMIN, primary_admin_marker='PRIMARY').first()
        if not primary_admin:
            raise CommandError("CRITICAL INVARIANT VIOLATION: Primary administrator was lost during cleanup!")

        self.stdout.write(self.style.SUCCESS(f"\nIntegrity Check: Primary Admin intact ({primary_admin.email}, {primary_admin.admin_id})"))
        remaining_students = User.objects.filter(role=Role.STUDENT).count()
        remaining_assessments = Assessment.objects.count()
        orphan_assignments = AssessmentAssignment.objects.filter(
            Q(assessment__isnull=True) | Q(student__isnull=True)
        ).count()
        orphan_attempts = TestAttempt.objects.filter(
            Q(assessment__isnull=True) | Q(student__isnull=True)
        ).count()

        self.stdout.write(f"Remaining Student Users:     {remaining_students}")
        self.stdout.write(f"Remaining Assessments:       {remaining_assessments}")
        self.stdout.write(f"Orphan Assignments:          {orphan_assignments}")
        self.stdout.write(f"Orphan Test Attempts:        {orphan_attempts}")

        if orphan_assignments > 0 or orphan_attempts > 0:
            raise CommandError("Integrity Check Failed: Orphan assignments or attempts remain!")

        self.stdout.write(self.style.SUCCESS("All integrity checks PASSED.\n"))
