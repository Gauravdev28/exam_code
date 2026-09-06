from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.db.models import Q
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination

from apps.accounts.permissions import IsAdmin, IsActiveUser, IsStudent, IsFirstLoginSatisfied
from apps.core.views import APIResponse
from apps.questions.models import QuestionVersion
from .models import (
    Assessment,
    AssessmentStatus,
    AssessmentAssignment,
    AssignmentStatus,
    AssessmentQuestion,
    TestAttempt,
    AttemptStatus,
    AttemptAnswer,
)
from .services import (
    AssessmentService,
    AttemptService,
    AttemptTimerService,
    AssessmentAudienceService,
    AssessmentAttendanceService,
)
from .serializers import (
    AssessmentAdminListSerializer,
    AssessmentAdminDetailSerializer,
    CreateAssessmentSerializer,
    UpdateAssessmentSerializer,
    AddQuestionToAssessmentSerializer,
    AssessmentAssignmentSerializer,
    AssignStudentsPayloadSerializer,
    StudentAssessmentListSerializer,
    StudentAttemptAnswerSerializer,
    SaveAnswerPayloadSerializer,
    ConfigureAudienceSerializer,
)


class StandardPagination(PageNumberPagination):
    page_size = 15
    page_size_query_param = 'page_size'
    max_page_size = 100

    def get_paginated_response(self, data):
        return APIResponse(
            data={
                'count': self.page.paginator.count,
                'next': self.get_next_link(),
                'previous': self.get_previous_link(),
                'results': data
            }
        )


# ==============================================================================
# Admin Assessment Management Views
# ==============================================================================

class AdminAssessmentListView(APIView):
    """
    List & Create Assessments.
    GET /api/v1/admin/assessments/
    POST /api/v1/admin/assessments/
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsAdmin]
    pagination_class = StandardPagination

    def get(self, request):
        queryset = Assessment.objects.prefetch_related('assessment_questions', 'assignments').select_related('created_by').all()

        # Status filter
        status_filter = request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter.upper())

        # Search
        search = request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search.strip()) |
                Q(description__icontains=search.strip())
            )

        ordering = request.query_params.get('ordering', '-created_at')
        if ordering in ['created_at', '-created_at', 'start_datetime', '-start_datetime', 'title', '-title']:
            queryset = queryset.order_by(ordering)
        else:
            queryset = queryset.order_by('-created_at')

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request)
        serializer = AssessmentAdminListSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request):
        serializer = CreateAssessmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        assessment = AssessmentService.create_assessment(
            title=data['title'],
            description=data['description'],
            instructions=data.get('instructions', ''),
            start_datetime=data['start_datetime'],
            end_datetime=data['end_datetime'],
            duration_minutes=data['duration_minutes'],
            total_points=data.get('total_points', 0),
            passing_percentage=data.get('passing_percentage', 0.00),
            negative_marking_enabled=data.get('negative_marking_enabled', False),
            attempt_limit=data.get('attempt_limit', 1),
            randomize_questions=data.get('randomize_questions', False),
            randomize_options=data.get('randomize_options', False),
            result_visibility=data.get('result_visibility', 'AFTER_DEADLINE'),
            created_by=request.user,
            request=request
        )

        return APIResponse(
            data=AssessmentAdminDetailSerializer(assessment).data,
            message="Assessment created successfully in DRAFT status.",
            status_code=status.HTTP_201_CREATED
        )


class AdminAssessmentDetailView(APIView):
    """
    Retrieve, Update, or Delete an Assessment.
    GET /api/v1/admin/assessments/<id>/
    PATCH /api/v1/admin/assessments/<id>/
    DELETE /api/v1/admin/assessments/<id>/
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsAdmin]

    def get(self, request, pk):
        assessment = get_object_or_404(
            Assessment.objects.prefetch_related(
                'assessment_questions__question_version__tags',
                'assignments__student__student_profile'
            ).select_related('created_by'),
            id=pk
        )
        return APIResponse(
            data=AssessmentAdminDetailSerializer(assessment).data,
            message="Assessment details retrieved."
        )

    def patch(self, request, pk):
        assessment = get_object_or_404(Assessment, id=pk)
        serializer = UpdateAssessmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        updated = AssessmentService.update_draft_assessment(
            assessment=assessment,
            actor=request.user,
            title=data.get('title'),
            description=data.get('description'),
            instructions=data.get('instructions'),
            start_datetime=data.get('start_datetime'),
            end_datetime=data.get('end_datetime'),
            duration_minutes=data.get('duration_minutes'),
            total_points=data.get('total_points'),
            passing_percentage=data.get('passing_percentage'),
            negative_marking_enabled=data.get('negative_marking_enabled'),
            attempt_limit=data.get('attempt_limit'),
            randomize_questions=data.get('randomize_questions'),
            randomize_options=data.get('randomize_options'),
            result_visibility=data.get('result_visibility'),
            target_section_ids=data.get('target_section_ids'),
            target_student_ids=data.get('target_student_ids'),
            request=request
        )
        return APIResponse(
            data=AssessmentAdminDetailSerializer(updated).data,
            message="Assessment updated successfully."
        )

    def delete(self, request, pk):
        assessment = get_object_or_404(Assessment, id=pk)
        if assessment.status in [AssessmentStatus.PUBLISHED, AssessmentStatus.ARCHIVED]:
            return APIResponse(
                message="Cannot delete a published or archived assessment.",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        assessment.delete()
        return APIResponse(message="Assessment deleted successfully.")


class AdminAssessmentPublishView(APIView):
    """
    Validate points invariant, resolve audience, create assignments, freeze AssessmentSnapshot, and publish assessment.
    POST /api/v1/admin/assessments/<id>/publish/
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsAdmin]

    def post(self, request, pk):
        assessment = get_object_or_404(Assessment, id=pk)
        published = AssessmentService.publish_assessment(
            assessment=assessment,
            actor=request.user,
            request=request,
            enforce_audience=True
        )
        return APIResponse(
            data=AssessmentAdminDetailSerializer(published).data,
            message="Assessment published successfully and snapshot permanently locked."
        )


class AdminAssessmentAudienceView(APIView):
    """
    Retrieve or configure audience targeting for a DRAFT assessment.
    GET /api/v1/admin/assessments/<id>/audience/
    POST /api/v1/admin/assessments/<id>/audience/
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsAdmin]

    def get(self, request, pk):
        assessment = get_object_or_404(Assessment, id=pk)
        resolved = AssessmentAudienceService.resolve_audience(assessment)
        return APIResponse(data=resolved)

    def post(self, request, pk):
        assessment = get_object_or_404(Assessment, id=pk)
        serializer = ConfigureAudienceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        section_ids = [str(sid) for sid in serializer.validated_data.get('section_ids', [])]
        student_ids = [str(uid) for uid in serializer.validated_data.get('student_ids', [])]

        resolved = AssessmentAudienceService.configure_audience(
            assessment=assessment,
            section_ids=section_ids,
            student_ids=student_ids,
            actor=request.user,
            request=request
        )
        return APIResponse(
            data=resolved,
            message="Assessment target audience updated successfully."
        )


class AdminAssessmentAudiencePreviewView(APIView):
    """
    Pure preview of resolved audience without mutating draft state or creating assignments.
    POST /api/v1/admin/assessments/<id>/audience/preview/
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsAdmin]

    def post(self, request, pk):
        assessment = get_object_or_404(Assessment, id=pk)
        serializer = ConfigureAudienceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        section_ids = [str(sid) for sid in serializer.validated_data.get('section_ids', [])]
        student_ids = [str(uid) for uid in serializer.validated_data.get('student_ids', [])]

        resolved = AssessmentAudienceService.resolve_audience(
            assessment=assessment,
            section_ids=section_ids,
            student_ids=student_ids
        )
        return APIResponse(data=resolved)


class AdminAssessmentArchiveView(APIView):
    """
    Archive an assessment.
    POST /api/v1/admin/assessments/<id>/archive/
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsAdmin]

    def post(self, request, pk):
        assessment = get_object_or_404(Assessment, id=pk)
        archived = AssessmentService.archive_assessment(assessment=assessment, actor=request.user, request=request)
        return APIResponse(
            data=AssessmentAdminDetailSerializer(archived).data,
            message="Assessment archived."
        )


class AdminAssessmentQuestionAddView(APIView):
    """
    Add a published QuestionVersion to a DRAFT assessment.
    POST /api/v1/admin/assessments/<id>/questions/
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsAdmin]

    def post(self, request, pk):
        assessment = get_object_or_404(Assessment, id=pk)
        serializer = AddQuestionToAssessmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        qv = get_object_or_404(QuestionVersion, id=data['question_version_id'])
        aq = AssessmentService.add_question(
            assessment=assessment,
            question_version=qv,
            actor=request.user,
            order=data.get('order'),
            points=data.get('points'),
            negative_marking_enabled=data.get('negative_marking_enabled', False),
            negative_points=data.get('negative_points', 0),
            request=request
        )
        return APIResponse(
            data=AssessmentAdminDetailSerializer(assessment).data,
            message="Question added to assessment.",
            status_code=status.HTTP_201_CREATED
        )


class AdminAssessmentQuestionRemoveView(APIView):
    """
    Remove a question from a DRAFT assessment.
    DELETE /api/v1/admin/assessments/<id>/questions/<question_version_id>/
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsAdmin]

    def delete(self, request, pk, question_version_id):
        assessment = get_object_or_404(Assessment, id=pk)
        AssessmentService.remove_question(
            assessment=assessment,
            question_version_id=str(question_version_id),
            actor=request.user,
            request=request
        )
        return APIResponse(
            data=AssessmentAdminDetailSerializer(assessment).data,
            message="Question removed from assessment."
        )


class AdminAssessmentAssignmentListView(APIView):
    """
    List & Assign students to an assessment.
    GET /api/v1/admin/assessments/<id>/assignments/
    POST /api/v1/admin/assessments/<id>/assignments/
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsAdmin]

    def get(self, request, pk):
        assessment = get_object_or_404(Assessment, id=pk)
        assignments = assessment.assignments.select_related('student__student_profile', 'assigned_by').all()
        serializer = AssessmentAssignmentSerializer(assignments, many=True)
        return APIResponse(data=serializer.data)

    def post(self, request, pk):
        assessment = get_object_or_404(Assessment, id=pk)
        serializer = AssignStudentsPayloadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        student_ids = [str(sid) for sid in serializer.validated_data['student_ids']]

        assignments = AssessmentService.assign_students(
            assessment=assessment,
            student_ids=student_ids,
            actor=request.user,
            request=request,
            sync_draft_target=True
        )
        return APIResponse(
            data=AssessmentAssignmentSerializer(assignments, many=True).data,
            message=f"Successfully assigned {len(assignments)} student(s).",
            status_code=status.HTTP_201_CREATED
        )


class AdminAssessmentAssignmentRevokeView(APIView):
    """
    Revoke a student's assignment to an assessment.
    DELETE /api/v1/admin/assessments/<id>/assignments/<student_id>/
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsAdmin]

    def delete(self, request, pk, student_id):
        assessment = get_object_or_404(Assessment, id=pk)
        assignment = AssessmentService.revoke_assignment(
            assessment=assessment,
            student_id=str(student_id),
            actor=request.user,
            request=request
        )
        return APIResponse(
            data=AssessmentAssignmentSerializer(assignment).data,
            message="Student assignment revoked."
        )


# ==============================================================================
# Student Assessment & Test Room Views
# ==============================================================================

class StudentAssessmentListView(APIView):
    """
    List all assessments assigned to the authenticated student.
    GET /api/v1/student/assessments/
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsStudent, IsFirstLoginSatisfied]

    def get(self, request):
        # Query only assigned assessments in PUBLISHED status
        assessments = Assessment.objects.filter(
            assignments__student=request.user,
            assignments__status=AssignmentStatus.ASSIGNED,
            status=AssessmentStatus.PUBLISHED
        ).order_by('start_datetime')

        serializer = StudentAssessmentListSerializer(assessments, many=True, context={'request': request})
        return APIResponse(data=serializer.data)


class StudentAssessmentDetailView(APIView):
    """
    Get instructions and eligibility for a specific assigned assessment.
    GET /api/v1/student/assessments/<id>/
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsStudent, IsFirstLoginSatisfied]

    def get(self, request, pk):
        assessment = get_object_or_404(
            Assessment.objects.filter(
                assignments__student=request.user,
                assignments__status=AssignmentStatus.ASSIGNED,
                status=AssessmentStatus.PUBLISHED
            ),
            id=pk
        )
        serializer = StudentAssessmentListSerializer(assessment, context={'request': request})
        return APIResponse(data=serializer.data)


class StudentAssessmentStartView(APIView):
    """
    Start or Resume a Test Attempt.
    POST /api/v1/student/assessments/<id>/start/
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsStudent, IsFirstLoginSatisfied]

    def post(self, request, pk):
        attempt, created = AttemptService.start_attempt(
            student=request.user,
            assessment_id=str(pk),
            actor=request.user,
            request=request
        )
        return APIResponse(
            data={"attempt_id": str(attempt.id), "status": attempt.status, "is_new": created},
            message="Test attempt started." if created else "Resuming active test attempt.",
            status_code=status.HTTP_201_CREATED if created else status.HTTP_200_OK
        )


class StudentAttemptDetailView(APIView):
    """
    Retrieve authoritative test attempt state, sanitized snapshot questions, and current answers.
    GET /api/v1/student/attempts/<id>/
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsStudent, IsFirstLoginSatisfied]

    def get(self, request, pk):
        attempt = get_object_or_404(
            TestAttempt.objects.select_related('assessment', 'assessment_snapshot').prefetch_related('answers'),
            id=pk
        )

        # IDOR Protection
        if attempt.student != request.user:
            return APIResponse(
                message="You do not have permission to access this test attempt.",
                status_code=status.HTTP_403_FORBIDDEN
            )

        # Check and handle timer expiry
        AttemptTimerService.check_and_expire_attempt_if_needed(attempt)

        snapshot = attempt.assessment_snapshot
        snapshot_data = snapshot.snapshot_data or {}
        raw_questions = snapshot_data.get('questions', [])

        # Index snapshot questions by ID
        questions_by_id = {q['snapshot_question_id']: dict(q) for q in raw_questions}

        # Format questions according to attempt's deterministic question_order and option_orders
        ordered_questions = []
        for q_id in attempt.question_order:
            if q_id in questions_by_id:
                q_item = dict(questions_by_id[q_id])
                # Shuffle options if randomized
                if q_id in attempt.option_orders and 'type_config' in q_item and 'options' in q_item['type_config']:
                    ordered_opt_ids = attempt.option_orders[q_id]
                    raw_opts = {opt['id']: opt for opt in q_item['type_config']['options']}
                    q_item['type_config']['options'] = [
                        raw_opts[opt_id] for opt_id in ordered_opt_ids if opt_id in raw_opts
                    ]
                ordered_questions.append(q_item)

        # Compile answers map
        answers_map = {}
        for ans in attempt.answers.all():
            answers_map[ans.question_id] = StudentAttemptAnswerSerializer(ans).data

        remaining_secs = AttemptTimerService.get_remaining_seconds(attempt)

        return APIResponse(
            data={
                "attempt_id": str(attempt.id),
                "assessment_id": str(attempt.assessment_id),
                "title": attempt.assessment.title,
                "instructions": attempt.assessment.instructions,
                "status": attempt.status,
                "attempt_number": attempt.attempt_number,
                "started_at": attempt.started_at.isoformat() if attempt.started_at else None,
                "expires_at": attempt.expires_at.isoformat() if attempt.expires_at else None,
                "submitted_at": attempt.submitted_at.isoformat() if attempt.submitted_at else None,
                "remaining_seconds": remaining_secs,
                "questions": ordered_questions,
                "answers": answers_map,
            },
            message="Attempt state retrieved."
        )


class StudentAttemptSaveAnswerView(APIView):
    """
    Save or Autosave an answer for a specific question within an attempt.
    POST /api/v1/student/attempts/<id>/answers/<question_id>/
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsStudent, IsFirstLoginSatisfied]

    def post(self, request, pk, question_id):
        serializer = SaveAnswerPayloadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        client_revision = data.get('revision', 1)
        answer_payload = {
            k: v for k, v in data.items() if k != 'revision'
        }

        result = AttemptService.save_answer(
            student=request.user,
            attempt_id=str(pk),
            snapshot_question_id=str(question_id),
            answer_data=answer_payload,
            client_revision=client_revision,
            actor=request.user,
            request=request
        )

        return APIResponse(data=result, message="Answer saved successfully.")


class StudentAttemptSubmitView(APIView):
    """
    Final submission of a test attempt.
    POST /api/v1/student/attempts/<id>/submit/
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsStudent, IsFirstLoginSatisfied]

    def post(self, request, pk):
        attempt = AttemptService.submit_attempt(
            student=request.user,
            attempt_id=str(pk),
            actor=request.user,
            request=request
        )
        return APIResponse(
            data={
                "attempt_id": str(attempt.id),
                "status": attempt.status,
                "submitted_at": attempt.submitted_at.isoformat() if attempt.submitted_at else None
            },
            message="Test attempt submitted successfully."
        )


class AdminAssessmentAttendanceView(APIView):
    """
    Get authoritative derived attendance data, section breakdown, and student roster.
    GET /api/v1/admin/assessments/<id>/attendance/
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsAdmin]

    def get(self, request, pk):
        assessment = get_object_or_404(Assessment, id=pk)
        filters = {
            'section_id': request.query_params.get('section_id'),
            'attendance_status': request.query_params.get('attendance_status'),
            'attempt_status': request.query_params.get('attempt_status'),
            'search': request.query_params.get('search'),
        }
        page = request.query_params.get('page', 1)
        page_size = request.query_params.get('page_size', 20)

        data = AssessmentAttendanceService.get_attendance_data(
            assessment=assessment,
            filters=filters,
            page=page,
            page_size=page_size
        )
        return APIResponse(data=data)


class AdminAssessmentAttendanceExportView(APIView):
    """
    Export attendance roster and section breakdown in XLSX or PDF format.
    GET /api/v1/admin/assessments/<id>/attendance/export/?format=xlsx|pdf
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsAdmin]

    def perform_content_negotiation(self, request, force=False):
        """
        Graceful content negotiation: client specifies ?format=xlsx or ?format=pdf
        for file downloads, but error responses (401, 403, 404) must still render as JSON.
        """
        renderers = self.get_renderers()
        try:
            return super().perform_content_negotiation(request, force)
        except Exception:
            return (renderers[0], renderers[0].media_type)

    def get(self, request, pk):
        assessment = get_object_or_404(Assessment, id=pk)
        export_format = request.query_params.get('format', 'xlsx').lower()
        filters = {
            'section_id': request.query_params.get('section_id'),
            'attendance_status': request.query_params.get('attendance_status'),
            'attempt_status': request.query_params.get('attempt_status'),
            'search': request.query_params.get('search'),
        }

        if export_format == 'pdf':
            pdf_buf = AssessmentAttendanceService.export_attendance_pdf(assessment, filters=filters)
            response = HttpResponse(pdf_buf.getvalue(), content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="attendance_{assessment.id}.pdf"'
            return response
        else:
            xlsx_buf = AssessmentAttendanceService.export_attendance_xlsx(assessment, filters=filters)
            response = HttpResponse(
                xlsx_buf.getvalue(),
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            response['Content-Disposition'] = f'attachment; filename="attendance_{assessment.id}.xlsx"'
            return response

