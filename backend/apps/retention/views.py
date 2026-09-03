import io
from django.conf import settings
from django.shortcuts import get_object_or_404
from django.http import HttpResponse, Http404
from django.utils import timezone
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.accounts.permissions import IsAdmin, IsStudent, IsActiveUser
from apps.core.views import APIResponse
from apps.assessments.models import Assessment, TestAttempt
from apps.retention.models import (
    RetentionPolicy,
    RetentionRecord,
    LegalHold,
    RetentionTombstone,
    ExportJob,
    FileCleanupQueue,
    PurgeJobRun,
    PurgeState,
)
from apps.retention.services import (
    RetentionMetricsService,
    RetentionPolicyEngine,
    LegalHoldManager,
    AuthoritativeScrubbingService,
    DsarExportService,
)
from apps.retention.serializers import (
    RetentionPolicySerializer,
    LegalHoldSerializer,
    LegalHoldReleaseSerializer,
    RetentionTombstoneSerializer,
    ExportJobSerializer,
    CreateExportJobSerializer,
    RetentionRecordSerializer,
    FileCleanupQueueSerializer,
    PurgeJobRunSerializer,
)


class StandardResultsPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


# ==============================================================================
# Admin Retention Management Views
# ==============================================================================

class AdminRetentionMetricsView(APIView):
    """
    GET /api/v1/admin/retention/metrics/
    Retrieves aggregate storage metrics, tombstone counts, and active holds.
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsAdmin]

    def get(self, request):
        metrics = RetentionMetricsService.get_retention_metrics()
        return APIResponse(
            data=metrics,
            message="Retention metrics retrieved successfully."
        )


class AdminRetentionPolicyListCreateView(APIView):
    """
    GET /api/v1/admin/retention/policies/
    POST /api/v1/admin/retention/policies/
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsAdmin]

    def get(self, request):
        policies = RetentionPolicy.objects.select_related('assessment', 'created_by').all()
        serializer = RetentionPolicySerializer(policies, many=True)
        return APIResponse(data=serializer.data)

    def post(self, request):
        serializer = RetentionPolicySerializer(data=request.data)
        if serializer.is_valid():
            policy = serializer.save(created_by=request.user)
            return APIResponse(
                data=RetentionPolicySerializer(policy).data,
                message="Retention policy created successfully.",
                status_code=status.HTTP_201_CREATED
            )
        return APIResponse(
            data=serializer.errors,
            message="Invalid policy configuration.",
            status_code=status.HTTP_400_BAD_REQUEST
        )


class AdminRetentionPolicyDetailView(APIView):
    """
    GET /api/v1/admin/retention/policies/<uuid:pk>/
    PATCH /api/v1/admin/retention/policies/<uuid:pk>/
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsAdmin]

    def get(self, request, pk):
        policy = get_object_or_404(RetentionPolicy.objects.select_related('assessment', 'created_by'), pk=pk)
        serializer = RetentionPolicySerializer(policy)
        return APIResponse(data=serializer.data)

    def patch(self, request, pk):
        policy = get_object_or_404(RetentionPolicy, pk=pk)
        serializer = RetentionPolicySerializer(policy, data=request.data, partial=True)
        if serializer.is_valid():
            # Bump version on edit to preserve audit trail
            policy.version += 1
            updated = serializer.save()
            return APIResponse(
                data=RetentionPolicySerializer(updated).data,
                message=f"Retention policy updated to version {updated.version}."
            )
        return APIResponse(
            data=serializer.errors,
            message="Invalid policy update.",
            status_code=status.HTTP_400_BAD_REQUEST
        )


class AdminRetentionCandidateListView(APIView):
    """
    GET /api/v1/admin/retention/candidates/
    List attempts due or approaching retention expiration.
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsAdmin]

    def get(self, request):
        now = timezone.now()
        assessment_id = request.query_params.get('assessment_id')
        records = RetentionRecord.objects.filter(
            detailed_data_expires_at__lte=now + timezone.timedelta(days=7)
        ).select_related('attempt', 'attempt__student', 'attempt__assessment').order_by('detailed_data_expires_at')

        if assessment_id:
            records = records.filter(attempt__assessment_id=assessment_id)

        paginator = StandardResultsPagination()
        page = paginator.paginate_queryset(records, request)
        serializer = RetentionRecordSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class AdminPurgePreviewView(APIView):
    """
    POST /api/v1/admin/retention/preview-purge/
    Generates a dry-run candidate list and issues a signed 5-minute preview token.
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsAdmin]

    def post(self, request):
        assessment_id = request.data.get('assessment_id')
        preview_data = RetentionMetricsService.generate_purge_preview(assessment_id=assessment_id)
        return APIResponse(
            data=preview_data,
            message="Purge preview generated. Token is valid for 5 minutes."
        )


class AdminPurgeExecuteView(APIView):
    """
    POST /api/v1/admin/retention/execute-purge/
    Executes purge after re-validating the signed preview token and row-level eligibility.
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsAdmin]

    def post(self, request):
        token = request.data.get('preview_token')
        if not token:
            return APIResponse(
                message="preview_token is required.",
                status_code=status.HTTP_400_BAD_REQUEST
            )

        try:
            summary = RetentionMetricsService.validate_and_execute_preview_purge(
                preview_token=token,
                operator_user=request.user,
                process_filesystem_sync=True
            )
            return APIResponse(
                data=summary,
                message="Purge execution completed successfully."
            )
        except ValidationError as e:
            return APIResponse(
                message=str(e),
                status_code=status.HTTP_400_BAD_REQUEST
            )


class AdminRetentionTombstoneListView(APIView):
    """
    GET /api/v1/admin/retention/tombstones/
    Restricted admin-only immutable ledger of deleted attempts.
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsAdmin]

    def get(self, request):
        qs = RetentionTombstone.objects.all().order_by('-purged_at')
        euid = request.query_params.get('student_euid')
        assessment_id = request.query_params.get('assessment_id')

        if euid:
            qs = qs.filter(student_euid__icontains=euid)
        if assessment_id:
            qs = qs.filter(assessment_id=assessment_id)

        paginator = StandardResultsPagination()
        page = paginator.paginate_queryset(qs, request)
        serializer = RetentionTombstoneSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class AdminFileCleanupQueueListView(APIView):
    """
    GET /api/v1/admin/retention/cleanup-queue/
    Read-only view of pending and retrying filesystem cleanup jobs.
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsAdmin]

    def get(self, request):
        qs = FileCleanupQueue.objects.all().order_by('status', '-created_at')
        paginator = StandardResultsPagination()
        page = paginator.paginate_queryset(qs, request)
        serializer = FileCleanupQueueSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


# ==============================================================================
# Admin Legal Hold Views
# ==============================================================================

class AdminLegalHoldListCreateView(APIView):
    """
    GET /api/v1/admin/legal-holds/
    POST /api/v1/admin/legal-holds/
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsAdmin]

    def get(self, request):
        qs = LegalHold.objects.select_related('attempt', 'student', 'assessment', 'placed_by', 'released_by').all()
        status_filter = request.query_params.get('status')
        scope_filter = request.query_params.get('scope')

        if status_filter:
            qs = qs.filter(status=status_filter)
        if scope_filter:
            qs = qs.filter(scope=scope_filter)

        paginator = StandardResultsPagination()
        page = paginator.paginate_queryset(qs, request)
        serializer = LegalHoldSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request):
        serializer = LegalHoldSerializer(data=request.data)
        if serializer.is_valid():
            data = serializer.validated_data
            scope = data['scope']

            if scope == 'ATTEMPT':
                hold = LegalHoldManager.create_attempt_hold(
                    attempt_id=data['attempt'].id,
                    title=data['title'],
                    case_reference=data['case_reference'],
                    reason=data['reason'],
                    user=request.user
                )
            elif scope == 'STUDENT':
                hold = LegalHoldManager.create_student_hold(
                    student_id=data['student'].id,
                    title=data['title'],
                    case_reference=data['case_reference'],
                    reason=data['reason'],
                    user=request.user
                )
            elif scope == 'ASSESSMENT':
                hold = LegalHoldManager.create_assessment_hold(
                    assessment_id=data['assessment'].id,
                    title=data['title'],
                    case_reference=data['case_reference'],
                    reason=data['reason'],
                    user=request.user
                )
            return APIResponse(
                data=LegalHoldSerializer(hold).data,
                message=f"Legal hold placed successfully on scope {scope}.",
                status_code=status.HTTP_201_CREATED
            )
        return APIResponse(
            data=serializer.errors,
            message="Invalid legal hold parameters.",
            status_code=status.HTTP_400_BAD_REQUEST
        )


class AdminLegalHoldReleaseView(APIView):
    """
    POST /api/v1/admin/legal-holds/<uuid:pk>/release/
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsAdmin]

    def post(self, request, pk):
        hold = get_object_or_404(LegalHold, pk=pk)
        serializer = LegalHoldReleaseSerializer(data=request.data)
        if serializer.is_valid():
            reason = serializer.validated_data['release_reason']
            try:
                updated_hold = LegalHoldManager.release_hold(
                    hold_id=hold.id,
                    release_reason=reason,
                    user=request.user
                )
                return APIResponse(
                    data=LegalHoldSerializer(updated_hold).data,
                    message="Legal hold released successfully."
                )
            except ValidationError as e:
                return APIResponse(
                    message=str(e),
                    status_code=status.HTTP_400_BAD_REQUEST
                )
        return APIResponse(
            data=serializer.errors,
            message="Release reason is required.",
            status_code=status.HTTP_400_BAD_REQUEST
        )


# ==============================================================================
# Student Privacy & DSAR Views
# ==============================================================================

class StudentRetentionStatusView(APIView):
    """
    GET /api/v1/student/privacy/retention-status/
    Displays student's data retention countdown and applicable policies.
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsStudent]

    def get(self, request):
        now = timezone.now()
        attempts = TestAttempt.objects.filter(
            student=request.user,
            status__in=['SUBMITTED', 'EXPIRED', 'CANCELLED']
        ).select_related('assessment', 'retention_record').order_by('-submitted_at')

        results = []
        for att in attempts:
            rec = getattr(att, 'retention_record', None)
            days_remaining = None
            if rec:
                delta = rec.detailed_data_expires_at - now
                days_remaining = max(0, delta.days)

            results.append({
                'attempt_id': str(att.id),
                'assessment_title': att.assessment.title,
                'submitted_at': att.submitted_at.isoformat() if att.submitted_at else None,
                'purge_state': rec.purge_state if rec else 'UNCONFIGURED',
                'detailed_data_expires_at': rec.detailed_data_expires_at.isoformat() if rec else None,
                'days_remaining_until_purge': days_remaining,
            })

        return APIResponse(
            data={
                'default_policy_days': getattr(settings, 'RETENTION_DEFAULT_DETAILED_DATA_TTL_DAYS', 30),
                'attempts': results
            },
            message="Student retention status retrieved successfully."
        )


class StudentExportJobListCreateView(APIView):
    """
    GET /api/v1/student/privacy/export-requests/
    POST /api/v1/student/privacy/export-requests/
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsStudent]

    def get(self, request):
        jobs = ExportJob.objects.filter(student=request.user).order_by('-created_at')
        serializer = ExportJobSerializer(jobs, many=True)
        return APIResponse(data=serializer.data)

    def post(self, request):
        serializer = CreateExportJobSerializer(data=request.data)
        if serializer.is_valid():
            attempt_id = serializer.validated_data.get('attempt_id')
            try:
                job = DsarExportService.create_export_request(
                    student=request.user,
                    attempt_id=attempt_id
                )
                # Queue async Celery task
                try:
                    from apps.retention.tasks import generate_student_dsar_archive
                    generate_student_dsar_archive.delay(str(job.id))
                except Exception:
                    # In test/synchronous mode, acquire and generate immediately
                    DsarExportService.acquire_snapshot(str(job.id))
                    DsarExportService.generate_and_encrypt_archive(str(job.id))

                job.refresh_from_db()
                return APIResponse(
                    data=ExportJobSerializer(job).data,
                    message="Export request queued successfully.",
                    status_code=status.HTTP_201_CREATED
                )
            except ValidationError as e:
                return APIResponse(
                    message=str(e),
                    status_code=status.HTTP_400_BAD_REQUEST
                )
        return APIResponse(
            data=serializer.errors,
            message="Invalid export request parameters.",
            status_code=status.HTTP_400_BAD_REQUEST
        )


class StudentExportJobDownloadView(APIView):
    """
    GET /api/v1/student/privacy/export-requests/<uuid:pk>/download/
    Authenticated streaming download of decrypted DSAR ZIP archive.
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsStudent]

    def get(self, request, pk):
        job = get_object_or_404(ExportJob, pk=pk)

        # IDOR prevention
        if job.student_id != request.user.id:
            raise PermissionDenied("You are not authorized to download this export archive.")

        if job.status != 'READY':
            return APIResponse(
                message=f"Export is not ready (current status: {job.status}).",
                status_code=status.HTTP_400_BAD_REQUEST
            )

        if job.expires_at and job.expires_at <= timezone.now():
            return APIResponse(
                message="Export archive has expired and has been unlinked.",
                status_code=status.HTTP_410_GONE
            )

        try:
            plaintext_zip = DsarExportService.decrypt_archive(job)
            response = HttpResponse(plaintext_zip, content_type='application/zip')
            response['Content-Disposition'] = f'attachment; filename="dsar_export_{job.id}.zip"'
            response['Content-Length'] = len(plaintext_zip)
            return response
        except ValidationError as e:
            return APIResponse(message=str(e), status_code=status.HTTP_400_BAD_REQUEST)
        except PermissionDenied as e:
            return APIResponse(message=str(e), status_code=status.HTTP_403_FORBIDDEN)
        except Exception as exc:
            return APIResponse(
                message=f"Decryption failed: {exc}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
