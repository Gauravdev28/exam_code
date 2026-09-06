import os
import hashlib
from decimal import Decimal
from django.shortcuts import get_object_or_404
from django.http import FileResponse, Http404
from django.db.models import Q
from django.utils import timezone
from django.conf import settings
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from rest_framework.exceptions import PermissionDenied, ValidationError as DRFValidationError

from apps.accounts.permissions import IsAdmin, IsStudent, IsActiveUser
from apps.accounts.models import User
from apps.accounts.services import AuditService
from apps.core.views import APIResponse
from apps.assessments.models import Assessment, AssessmentAssignment, AssignmentStatus, TestAttempt
from .models import (
    AssessmentResult,
    QuestionResult,
    HistoricalResultSummary,
    ReportJob,
    ResultStatus,
    ReportStatus,
    ReportType,
    ReportFormat,
)
from .services import (
    ResultFinalizationService,
    ResultAccessPolicyService,
    AnalyticsService,
    ReportService,
)
from .serializers import (
    StudentBasicSerializer,
    AssessmentResultStudentDetailSerializer,
    AssessmentResultAdminListSerializer,
    AssessmentResultAdminDetailSerializer,
    HistoricalResultSummarySerializer,
    CreateReportJobSerializer,
    ReportJobDetailSerializer,
)


class StandardResultsPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


# ==============================================================================
# Student Result Endpoints
# ==============================================================================

class StudentAttemptResultView(APIView):
    """
    Retrieve finalized scoring and question breakdown for a specific attempt.
    GET /api/v1/student/attempts/<attempt_id>/result/
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsStudent]

    def get(self, request, attempt_id):
        attempt = get_object_or_404(
            TestAttempt.objects.select_related('assessment', 'student'),
            id=attempt_id
        )

        if attempt.student_id != request.user.id:
            raise PermissionDenied("You are not authorized to view this attempt's results.")

        # If result does not exist yet and attempt is terminal, finalize on-demand
        result = AssessmentResult.objects.filter(attempt=attempt).first()
        if not result and attempt.status in ['SUBMITTED', 'EXPIRED', 'CANCELLED']:
            result = ResultFinalizationService.finalize_attempt(attempt_id=str(attempt.id), actor=request.user, request=request)

        if not result:
            return APIResponse(
                message="Result is not yet available for this attempt.",
                status_code=status.HTTP_404_NOT_FOUND
            )

        can_view, reason = ResultAccessPolicyService.can_view_result(request.user, result)
        if not can_view:
            return APIResponse(
                message=reason or "Result is not yet released.",
                status_code=status.HTTP_403_FORBIDDEN
            )

        serializer = AssessmentResultStudentDetailSerializer(result)
        return APIResponse(
            data=serializer.data,
            message="Assessment result retrieved successfully."
        )


class StudentResultListView(APIView):
    """
    List all finalized, visible assessment results for the student.
    GET /api/v1/student/results/
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsStudent]
    pagination_class = StandardResultsPagination

    def get(self, request):
        queryset = AssessmentResult.objects.filter(
            student=request.user,
            status=ResultStatus.FINALIZED
        ).select_related('assessment', 'attempt').order_by('-finalized_at')

        # Filter only visible results
        visible_pks = []
        for res in queryset:
            can_view, _ = ResultAccessPolicyService.can_view_result(request.user, res)
            if can_view:
                visible_pks.append(res.id)

        visible_queryset = queryset.filter(id__in=visible_pks)

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(visible_queryset, request)
        serializer = AssessmentResultStudentDetailSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class StudentResultDetailView(APIView):
    """
    Get detailed result by result_id.
    GET /api/v1/student/results/<result_id>/
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsStudent]

    def get(self, request, pk):
        result = get_object_or_404(
            AssessmentResult.objects.prefetch_related('question_results__snapshot_question').select_related('assessment', 'student'),
            id=pk
        )
        can_view, reason = ResultAccessPolicyService.can_view_result(request.user, result)
        if not can_view:
            raise PermissionDenied(reason or "Result is not accessible.")

        serializer = AssessmentResultStudentDetailSerializer(result)
        return APIResponse(data=serializer.data, message="Result details retrieved.")


class StudentTopicAnalyticsView(APIView):
    """
    Retrieve topic performance analytics for the authenticated student.
    GET /api/v1/student/analytics/topics/
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsStudent]

    def get(self, request):
        analytics = AnalyticsService.get_student_topic_analytics(request.user)
        return APIResponse(
            data={"topics": analytics},
            message="Topic analytics retrieved successfully."
        )


class StudentReportCreateView(APIView):
    """
    Request generation of a student scorecard report.
    POST /api/v1/student/reports/
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsStudent]

    def post(self, request):
        serializer = CreateReportJobSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        assessment_id = data.get('assessment_id')
        if not assessment_id:
            raise DRFValidationError({"assessment_id": "assessment_id is required."})

        # Check visibility
        result = AssessmentResult.objects.filter(
            assessment_id=assessment_id,
            student=request.user,
            status=ResultStatus.FINALIZED
        ).first()

        if not result:
            raise DRFValidationError({"assessment_id": "No finalized result found for this assessment."})

        can_view, reason = ResultAccessPolicyService.can_view_result(request.user, result)
        if not can_view:
            raise PermissionDenied(reason or "Result is not yet released.")

        job = ReportService.create_report_job(
            user=request.user,
            report_type=ReportType.STUDENT_SCORECARD,
            format=data['format'],
            assessment_id=str(assessment_id),
            student_id=str(request.user.id)
        )
        return APIResponse(
            data=ReportJobDetailSerializer(job).data,
            message="Report generation requested.",
            status_code=status.HTTP_202_ACCEPTED
        )


class StudentReportDetailView(APIView):
    """
    Check status of student report job.
    GET /api/v1/student/reports/<report_id>/
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsStudent]

    def get(self, request, pk):
        job = get_object_or_404(ReportJob, id=pk, requested_by=request.user)
        return APIResponse(
            data=ReportJobDetailSerializer(job).data,
            message="Report status retrieved."
        )


class StudentReportDownloadView(APIView):
    """
    Securely download student generated report.
    GET /api/v1/student/reports/<report_id>/download/
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsStudent]

    def get(self, request, pk):
        job = get_object_or_404(ReportJob, id=pk, requested_by=request.user)

        if job.status != ReportStatus.COMPLETED or not job.file_path:
            return APIResponse(
                message="Report is not ready for download.",
                status_code=status.HTTP_400_BAD_REQUEST
            )

        if timezone.now() > job.expires_at:
            job.status = ReportStatus.EXPIRED
            job.save(update_fields=['status'])
            return APIResponse(
                message="Report link has expired.",
                status_code=status.HTTP_410_GONE
            )

        reports_dir = os.path.abspath(os.path.join(settings.MEDIA_ROOT, 'reports'))
        job_real_path = os.path.abspath(job.file_path)
        if not job_real_path.startswith(reports_dir):
            raise PermissionDenied("Access to file outside reports directory is forbidden.")

        if not os.path.exists(job.file_path):
            raise Http404("Report file missing from storage.")

        # Verify SHA-256 integrity
        with open(job.file_path, 'rb') as f:
            current_hash = hashlib.sha256(f.read()).hexdigest()

        if current_hash != job.sha256_hash:
            raise PermissionDenied("Report integrity check failed.")

        content_types = {
            ReportFormat.PDF: 'application/pdf',
            ReportFormat.XLSX: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            ReportFormat.CSV: 'text/csv'
        }

        AuditService.log(
            action="REPORT_DOWNLOADED",
            actor=request.user,
            target_type="ReportJob",
            target_id=str(job.id),
            metadata={
                "report_type": job.report_type,
                "format": job.format,
                "sha256": job.sha256_hash
            },
            request=request
        )

        response = FileResponse(
            open(job.file_path, 'rb'),
            content_type=content_types.get(job.format, 'application/octet-stream')
        )
        response['Content-Disposition'] = f'attachment; filename="scorecard_{job.id}.{job.format.lower()}"'
        return response


# ==============================================================================
# Admin Result Endpoints
# ==============================================================================

class AdminAssessmentResultListView(APIView):
    """
    List candidate results and assignment roster for an assessment with search, filters, and pagination.
    Primary roster is AssessmentAssignment so assigned candidates appear even if NOT_STARTED.
    GET /api/v1/admin/assessments/<assessment_id>/results/
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsAdmin]
    pagination_class = StandardResultsPagination

    def get(self, request, assessment_id):
        assessment = get_object_or_404(Assessment, id=assessment_id)
        
        # Primary roster: All assigned students for this assessment
        assignments = list(AssessmentAssignment.objects.filter(
            assessment=assessment,
            status=AssignmentStatus.ASSIGNED
        ).select_related('student', 'student__student_profile'))

        # Map existing results and attempts by student_id
        results_map = {
            res.student_id: res for res in AssessmentResult.objects.filter(assessment=assessment).select_related(
                'student', 'student__student_profile', 'attempt', 'attempt__proctoring_session'
            )
        }
        attempts_map = {
            att.student_id: att for att in TestAttempt.objects.filter(assessment=assessment).select_related(
                'student', 'student__student_profile', 'proctoring_session'
            )
        }

        roster_items = []
        for asgn in assignments:
            stu = asgn.student
            if stu.id in results_map:
                res = results_map[stu.id]
                roster_items.append({
                    'id': str(res.id),
                    'attempt_id': str(res.attempt_id) if res.attempt_id else None,
                    'student': StudentBasicSerializer(stu).data,
                    'status': 'RELEASED' if res.is_released else 'EVALUATED',
                    'total_score_earned': str(res.total_score_earned),
                    'total_possible_score': str(res.total_possible_score),
                    'percentage': str(res.percentage),
                    'is_passed': res.is_passed,
                    'is_released': res.is_released,
                    'time_spent_seconds': res.time_spent_seconds,
                    'finalized_at': res.finalized_at.isoformat() if res.finalized_at else None,
                    'proctoring_summary': {
                        'risk_score': str(res.attempt.proctoring_session.risk_score),
                        'risk_band': res.attempt.proctoring_session.risk_band,
                        'status': res.attempt.proctoring_session.status
                    } if hasattr(res.attempt, 'proctoring_session') and res.attempt.proctoring_session else None
                })
            elif stu.id in attempts_map:
                att = attempts_map[stu.id]
                roster_items.append({
                    'id': str(att.id),
                    'attempt_id': str(att.id),
                    'student': StudentBasicSerializer(stu).data,
                    'status': att.status,
                    'total_score_earned': "0.00",
                    'total_possible_score': str(assessment.total_points),
                    'percentage': "0.00",
                    'is_passed': False,
                    'is_released': False,
                    'time_spent_seconds': att.time_spent_seconds or 0,
                    'finalized_at': None,
                    'proctoring_summary': {
                        'risk_score': str(att.proctoring_session.risk_score),
                        'risk_band': att.proctoring_session.risk_band,
                        'status': att.proctoring_session.status
                    } if hasattr(att, 'proctoring_session') and att.proctoring_session else None
                })
            else:
                roster_items.append({
                    'id': str(asgn.id),
                    'attempt_id': None,
                    'student': StudentBasicSerializer(stu).data,
                    'status': 'NOT_STARTED',
                    'total_score_earned': "0.00",
                    'total_possible_score': str(assessment.total_points),
                    'percentage': "0.00",
                    'is_passed': False,
                    'is_released': False,
                    'time_spent_seconds': 0,
                    'finalized_at': None,
                    'proctoring_summary': None
                })

        # Filtering
        status_filter = request.query_params.get('status')
        if status_filter:
            sf = status_filter.upper()
            roster_items = [item for item in roster_items if item['status'] == sf]

        is_passed = request.query_params.get('is_passed')
        if is_passed is not None:
            passed_bool = is_passed.lower() in ['true', '1']
            roster_items = [item for item in roster_items if item['is_passed'] == passed_bool]

        score_min = request.query_params.get('score_min')
        if score_min is not None:
            try:
                min_val = Decimal(score_min)
                roster_items = [item for item in roster_items if Decimal(item['total_score_earned']) >= min_val]
            except Exception:
                pass

        score_max = request.query_params.get('score_max')
        if score_max is not None:
            try:
                max_val = Decimal(score_max)
                roster_items = [item for item in roster_items if Decimal(item['total_score_earned']) <= max_val]
            except Exception:
                pass

        search = request.query_params.get('search')
        if search:
            s = search.strip().lower()
            roster_items = [
                item for item in roster_items
                if s in item['student']['email'].lower()
                or s in item['student']['roll_number'].lower()
                or s in item['student']['euid'].lower()
            ]

        # Manual in-memory pagination over full roster items
        try:
            page_num = int(request.query_params.get('page', 1))
        except (ValueError, TypeError):
            page_num = 1

        try:
            page_size = int(request.query_params.get('page_size', 20))
        except (ValueError, TypeError):
            page_size = 20

        if page_size > 100:
            page_size = 100
        elif page_size < 1:
            page_size = 20

        total_count = len(roster_items)
        start_idx = (page_num - 1) * page_size
        end_idx = start_idx + page_size
        page_data = roster_items[start_idx:end_idx]

        return Response({
            'count': total_count,
            'next': None,
            'previous': None,
            'results': page_data
        })


class AdminAssessmentResultDetailView(APIView):
    """
    Retrieve full admin details for a specific result.
    GET /api/v1/admin/results/<result_id>/
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsAdmin]

    def get(self, request, pk):
        result = get_object_or_404(
            AssessmentResult.objects.prefetch_related(
                'question_results__snapshot_question'
            ).select_related(
                'student',
                'student__student_profile',
                'assessment',
                'attempt',
                'attempt__proctoring_session'
            ),
            id=pk
        )
        serializer = AssessmentResultAdminDetailSerializer(result)
        return APIResponse(data=serializer.data, message="Result details retrieved.")


class AdminAssessmentAnalyticsView(APIView):
    """
    Retrieve cohort analytics and score distributions for an assessment.
    GET /api/v1/admin/assessments/<assessment_id>/analytics/
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsAdmin]

    def get(self, request, assessment_id):
        analytics = AnalyticsService.get_assessment_analytics(str(assessment_id))
        return APIResponse(data=analytics, message="Assessment analytics retrieved.")


class AdminQuestionAnalyticsView(APIView):
    """
    Retrieve item analytics (Difficulty P, Discrimination D) for an assessment.
    GET /api/v1/admin/assessments/<assessment_id>/analytics/questions/
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsAdmin]

    def get(self, request, assessment_id):
        analytics = AnalyticsService.get_question_analytics(str(assessment_id))
        return APIResponse(data={"questions": analytics}, message="Question analytics retrieved.")


class AdminReleaseResultsView(APIView):
    """
    Manually release finalized results to students.
    POST /api/v1/admin/assessments/<assessment_id>/release-results/
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsAdmin]

    def post(self, request, assessment_id):
        assessment = get_object_or_404(Assessment, id=assessment_id)
        count = AssessmentResult.objects.filter(
            assessment=assessment,
            status=ResultStatus.FINALIZED
        ).update(is_released=True)

        AuditService.log(
            action="RESULTS_RELEASED",
            actor=request.user,
            target_type="Assessment",
            target_id=str(assessment.id),
            metadata={"released_count": count},
            request=request
        )
        return APIResponse(
            data={"released_count": count},
            message=f"Successfully released {count} results."
        )


class AdminReportCreateView(APIView):
    """
    Request asynchronous generation of an administrative export (PDF, XLSX, CSV).
    POST /api/v1/admin/reports/
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsAdmin]

    def post(self, request):
        serializer = CreateReportJobSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        assessment_id = data.get('assessment_id')
        if not assessment_id:
            raise DRFValidationError({"assessment_id": "assessment_id is required."})

        job = ReportService.create_report_job(
            user=request.user,
            report_type=data['report_type'],
            format=data['format'],
            assessment_id=str(assessment_id),
            student_id=str(data.get('student_id')) if data.get('student_id') else None
        )
        return APIResponse(
            data=ReportJobDetailSerializer(job).data,
            message="Report generation requested.",
            status_code=status.HTTP_202_ACCEPTED
        )


class AdminReportDetailView(APIView):
    """
    Get status of an admin report job.
    GET /api/v1/admin/reports/<report_id>/
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsAdmin]

    def get(self, request, pk):
        job = get_object_or_404(ReportJob, id=pk)
        return APIResponse(
            data=ReportJobDetailSerializer(job).data,
            message="Report status retrieved."
        )


class AdminReportDownloadView(APIView):
    """
    Download administrative report artifact.
    GET /api/v1/admin/reports/<report_id>/download/
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsAdmin]

    def get(self, request, pk):
        job = get_object_or_404(ReportJob, id=pk)

        if job.status != ReportStatus.COMPLETED or not job.file_path:
            return APIResponse(
                message="Report is not ready for download.",
                status_code=status.HTTP_400_BAD_REQUEST
            )

        if timezone.now() > job.expires_at:
            job.status = ReportStatus.EXPIRED
            job.save(update_fields=['status'])
            return APIResponse(
                message="Report has expired.",
                status_code=status.HTTP_410_GONE
            )

        reports_dir = os.path.abspath(os.path.join(settings.MEDIA_ROOT, 'reports'))
        job_real_path = os.path.abspath(job.file_path)
        if not job_real_path.startswith(reports_dir):
            raise PermissionDenied("Access to file outside reports directory is forbidden.")

        if not os.path.exists(job.file_path):
            raise Http404("Report file not found on disk.")

        # Verify SHA-256 integrity
        with open(job.file_path, 'rb') as f:
            current_hash = hashlib.sha256(f.read()).hexdigest()

        if current_hash != job.sha256_hash:
            raise PermissionDenied("Report integrity check failed.")

        content_types = {
            ReportFormat.PDF: 'application/pdf',
            ReportFormat.XLSX: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            ReportFormat.CSV: 'text/csv'
        }

        AuditService.log(
            action="REPORT_DOWNLOADED",
            actor=request.user,
            target_type="ReportJob",
            target_id=str(job.id),
            metadata={
                "report_type": job.report_type,
                "format": job.format,
                "sha256": job.sha256_hash
            },
            request=request
        )

        response = FileResponse(
            open(job.file_path, 'rb'),
            content_type=content_types.get(job.format, 'application/octet-stream')
        )
        response['Content-Disposition'] = f'attachment; filename="report_{job.id}.{job.format.lower()}"'
        return response
