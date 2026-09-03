from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.permissions import IsActiveUser, IsAdmin, IsStudent, IsFirstLoginSatisfied
from apps.core.responses import APIResponse
from apps.evaluator.models import CodeSubmission, SubmissionType
from apps.evaluator.serializers import (
    CodeRunRequestSerializer,
    CodeSubmitRequestSerializer,
    StudentCodeSubmissionSerializer,
    AdminCodeSubmissionSerializer,
)
from apps.evaluator.services import CodeSubmissionService


class StudentCodeRunView(APIView):
    """
    Queue an asynchronous test run on public test cases only.
    POST /api/v1/student/attempts/<attempt_id>/questions/<question_id>/run/
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsStudent, IsFirstLoginSatisfied]

    def post(self, request, attempt_id, question_id):
        serializer = CodeRunRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        submission, created = CodeSubmissionService.create_submission(
            student=request.user,
            attempt_id=str(attempt_id),
            question_id=str(question_id),
            submission_type=SubmissionType.RUN,
            source_code=serializer.validated_data['source_code'],
            language=serializer.validated_data['language'],
            client_nonce=serializer.validated_data.get('client_nonce'),
            custom_input=serializer.validated_data.get('custom_input')
        )

        return APIResponse(
            data={
                "submission_id": str(submission.id),
                "status": submission.status,
                "submission_type": submission.submission_type,
                "language": submission.language,
                "is_new": created,
                "estimated_wait_seconds": 2
            },
            message="Code run queued for execution." if created else "Returning existing execution request.",
            status_code=status.HTTP_202_ACCEPTED
        )


class StudentCodeSubmitView(APIView):
    """
    Queue an authoritative evaluation on all test cases (public + hidden) and update AttemptAnswer.
    POST /api/v1/student/attempts/<attempt_id>/questions/<question_id>/submit/
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsStudent, IsFirstLoginSatisfied]

    def post(self, request, attempt_id, question_id):
        serializer = CodeSubmitRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        submission, created = CodeSubmissionService.create_submission(
            student=request.user,
            attempt_id=str(attempt_id),
            question_id=str(question_id),
            submission_type=SubmissionType.SUBMIT,
            source_code=serializer.validated_data['source_code'],
            language=serializer.validated_data['language'],
            client_nonce=serializer.validated_data.get('client_nonce')
        )

        return APIResponse(
            data={
                "submission_id": str(submission.id),
                "status": submission.status,
                "submission_type": submission.submission_type,
                "language": submission.language,
                "is_new": created,
                "estimated_wait_seconds": 3
            },
            message="Solution queued for authoritative evaluation." if created else "Returning existing submission request.",
            status_code=status.HTTP_202_ACCEPTED
        )


class StudentSubmissionDetailView(APIView):
    """
    Poll or retrieve submission status and results (with hidden test cases sanitized).
    GET /api/v1/student/submissions/<submission_id>/
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsStudent, IsFirstLoginSatisfied]

    def get(self, request, submission_id):
        submission = get_object_or_404(
            CodeSubmission.objects.select_related('attempt', 'snapshot_question').prefetch_related('test_case_results'),
            id=submission_id
        )

        # IDOR check
        if submission.attempt.student != request.user:
            return APIResponse(
                message="You do not have permission to access this submission.",
                status_code=status.HTTP_403_FORBIDDEN
            )

        serializer = StudentCodeSubmissionSerializer(submission)
        return APIResponse(
            data=serializer.data,
            message="Submission state retrieved."
        )


class AdminSubmissionListView(APIView):
    """
    List and filter code submissions for an assessment.
    GET /api/v1/admin/assessments/<assessment_id>/submissions/
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsAdmin]

    def get(self, request, assessment_id):
        queryset = CodeSubmission.objects.filter(
            attempt__assessment_id=assessment_id
        ).select_related('attempt', 'attempt__student', 'snapshot_question').order_by('-created_at')

        attempt_id = request.query_params.get('attempt_id')
        if attempt_id:
            queryset = queryset.filter(attempt_id=attempt_id)

        question_id = request.query_params.get('question_id')
        if question_id:
            queryset = queryset.filter(snapshot_question__snapshot_question_id=question_id)

        serializer = AdminCodeSubmissionSerializer(queryset[:100], many=True)
        return APIResponse(data=serializer.data)


class AdminSubmissionDetailView(APIView):
    """
    Retrieve full submission diagnostics including source code and unredacted logs.
    GET /api/v1/admin/submissions/<submission_id>/
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsAdmin]

    def get(self, request, submission_id):
        submission = get_object_or_404(
            CodeSubmission.objects.select_related('attempt', 'attempt__student', 'snapshot_question').prefetch_related('test_case_results'),
            id=submission_id
        )
        serializer = AdminCodeSubmissionSerializer(submission)
        return APIResponse(data=serializer.data)
