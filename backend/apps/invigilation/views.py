from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied, NotFound

from apps.accounts.models import Role, User
from apps.assessments.models import Assessment, TestAttempt
from apps.invigilation.models import ProctorAssignment, ProctorIntervention
from apps.invigilation.permissions import (
    IsProctorOrAdmin,
    HasAssignedAssessmentAccess,
    HasAttemptInvigilationAccess,
)
from apps.invigilation.serializers import (
    ProctorAssignmentSerializer,
    ProctorInterventionSerializer,
    StudentInterventionSerializer,
    ProctorChatMessageSerializer,
    WarningIssueSerializer,
    PauseAttemptSerializer,
    ResumeAttemptSerializer,
    RoomScanRequestSerializer,
    TerminateAttemptSerializer,
    ChatMessageSendSerializer,
    AcknowledgeWarningSerializer,
    CompleteRoomScanSerializer,
)
from apps.invigilation.services import (
    ProctorRosterService,
    LiveInterventionService,
    ProctorTriageQueueService,
    ProctorChatService,
)


class ProctorAssignedAssessmentsView(APIView):
    """
    Lists all published assessments that the authenticated proctor is assigned to monitor.
    Admins see all published assessments.
    """
    permission_classes = [IsAuthenticated, IsProctorOrAdmin]

    def get(self, request):
        if request.user.role == Role.ADMIN or request.user.is_staff or request.user.is_superuser:
            assignments = ProctorAssignment.objects.filter(is_active=True).select_related('proctor', 'assessment')
        else:
            assignments = ProctorAssignment.objects.filter(
                proctor=request.user,
                is_active=True
            ).select_related('proctor', 'assessment')

        serializer = ProctorAssignmentSerializer(assignments, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ProctorLiveRosterView(APIView):
    """
    Retrieves the real-time prioritized candidate roster for a specific assessment.
    Ordered by AI risk band (CRITICAL -> HIGH -> MEDIUM -> LOW -> NORMAL).
    """
    permission_classes = [IsAuthenticated, IsProctorOrAdmin, HasAssignedAssessmentAccess]

    def get(self, request, assessment_id):
        roster = ProctorTriageQueueService.get_triage_roster(
            assessment_id=assessment_id,
            proctor_user=request.user
        )
        return Response({
            "assessment_id": str(assessment_id),
            "count": len(roster),
            "candidates": roster
        }, status=status.HTTP_200_OK)


class ProctorIssueWarningView(APIView):
    """
    Issues an authoritative warning intervention to an in-progress candidate attempt.
    """
    permission_classes = [IsAuthenticated, IsProctorOrAdmin, HasAttemptInvigilationAccess]

    def post(self, request, attempt_id):
        serializer = WarningIssueSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        intervention = LiveInterventionService.issue_warning(
            proctor=request.user,
            attempt_id=attempt_id,
            reason_code=data['reason_code'],
            message=data['message'],
            internal_notes=data.get('internal_notes', ''),
            idempotency_key=data.get('idempotency_key', '')
        )

        resp_serializer = ProctorInterventionSerializer(intervention)
        return Response(resp_serializer.data, status=status.HTTP_201_CREATED)


class ProctorPauseAttemptView(APIView):
    """
    Pauses an in-progress candidate attempt, temporarily suspending countdown timer.
    Enforces single active pause and operational 15-minute cumulative cap.
    """
    permission_classes = [IsAuthenticated, IsProctorOrAdmin, HasAttemptInvigilationAccess]

    def post(self, request, attempt_id):
        serializer = PauseAttemptSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        intervention = LiveInterventionService.pause_attempt(
            proctor=request.user,
            attempt_id=attempt_id,
            reason=data.get('reason', ''),
            internal_notes=data.get('internal_notes', ''),
            idempotency_key=data.get('idempotency_key', ''),
            max_pause_seconds=data.get('max_pause_seconds', 900)
        )

        resp_serializer = ProctorInterventionSerializer(intervention)
        return Response(resp_serializer.data, status=status.HTTP_201_CREATED)


class ProctorResumeAttemptView(APIView):
    """
    Resumes a paused candidate attempt, extending expires_at by elapsed pause duration
    strictly bounded by assessment.end_datetime.
    """
    permission_classes = [IsAuthenticated, IsProctorOrAdmin, HasAttemptInvigilationAccess]

    def post(self, request, attempt_id):
        serializer = ResumeAttemptSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        intervention = LiveInterventionService.resume_attempt(
            proctor=request.user,
            attempt_id=attempt_id,
            reason=data.get('reason', ''),
            internal_notes=data.get('internal_notes', ''),
            idempotency_key=data.get('idempotency_key', '')
        )

        if intervention:
            resp_serializer = ProctorInterventionSerializer(intervention)
            return Response(resp_serializer.data, status=status.HTTP_200_OK)
        return Response({"status": "NOT_PAUSED", "detail": "Attempt is not currently paused."}, status=status.HTTP_200_OK)


class ProctorRoomScanRequestView(APIView):
    """
    Directs a candidate to perform a room scan.
    """
    permission_classes = [IsAuthenticated, IsProctorOrAdmin, HasAttemptInvigilationAccess]

    def post(self, request, attempt_id):
        serializer = RoomScanRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        intervention = LiveInterventionService.request_room_scan(
            proctor=request.user,
            attempt_id=attempt_id,
            reason=data.get('reason', ''),
            internal_notes=data.get('internal_notes', '')
        )

        resp_serializer = ProctorInterventionSerializer(intervention)
        return Response(resp_serializer.data, status=status.HTTP_201_CREATED)


class ProctorTerminateAttemptView(APIView):
    """
    Authoritatively terminates an attempt with cause.
    Transitions TestAttempt.status to CANCELLED and initiates Phase 8 finalization.
    """
    permission_classes = [IsAuthenticated, IsProctorOrAdmin, HasAttemptInvigilationAccess]

    def post(self, request, attempt_id):
        serializer = TerminateAttemptSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        attempt, intervention = LiveInterventionService.terminate_attempt(
            proctor=request.user,
            attempt_id=attempt_id,
            reason_code=data['reason_code'],
            formal_justification=data['formal_justification'],
            internal_notes=data.get('internal_notes', ''),
            idempotency_key=data.get('idempotency_key', '')
        )

        return Response({
            "status": "TERMINATED",
            "attempt_status": attempt.status,
            "intervention": ProctorInterventionSerializer(intervention).data
        }, status=status.HTTP_200_OK)


class ProctorInterventionHistoryView(APIView):
    """
    Returns the comprehensive immutable intervention audit ledger for an attempt.
    """
    permission_classes = [IsAuthenticated, IsProctorOrAdmin, HasAttemptInvigilationAccess]

    def get(self, request, attempt_id):
        interventions = ProctorIntervention.objects.filter(
            attempt_id=attempt_id
        ).select_related('proctor', 'student').order_by('issued_at')
        serializer = ProctorInterventionSerializer(interventions, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ProctorChatHistoryView(APIView):
    """
    Retrieves bilateral chat messages for an attempt.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, attempt_id):
        messages = ProctorChatService.get_chat_history(attempt_id, request.user)
        serializer = ProctorChatMessageSerializer(messages, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, attempt_id):
        attempt = TestAttempt.objects.filter(id=attempt_id).first()
        if not attempt:
            raise NotFound("Test attempt not found.")

        is_student = (attempt.student_id == request.user.id)
        is_proctor = ProctorRosterService.is_proctor_assigned(request.user, str(attempt.assessment_id))
        if not is_student and not is_proctor:
            raise PermissionDenied("You are not authorized to participate in this attempt's chat.")

        serializer = ChatMessageSendSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        recipient = None
        if data.get('recipient_id'):
            recipient = User.objects.filter(id=data['recipient_id']).first()

        message = ProctorChatService.send_message(
            sender=request.user,
            attempt_id=attempt_id,
            message_text=data['message_text'],
            recipient=recipient
        )

        return Response(ProctorChatMessageSerializer(message).data, status=status.HTTP_201_CREATED)


# ==============================================================================
# Student Facing Endpoints
# ==============================================================================

class StudentAcknowledgeWarningView(APIView):
    """
    Enables candidate to acknowledge an issued warning.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, attempt_id):
        serializer = AcknowledgeWarningSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        ack_event = LiveInterventionService.acknowledge_warning(
            student=request.user,
            attempt_id=attempt_id,
            intervention_id=serializer.validated_data['intervention_id']
        )

        return Response(StudentInterventionSerializer(ack_event).data, status=status.HTTP_200_OK)


class StudentCompleteRoomScanView(APIView):
    """
    Enables candidate to mark room scan complete.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, attempt_id):
        serializer = CompleteRoomScanSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        comp_event = LiveInterventionService.complete_room_scan(
            student=request.user,
            attempt_id=attempt_id,
            scan_event_id=serializer.validated_data['scan_event_id']
        )

        return Response(StudentInterventionSerializer(comp_event).data, status=status.HTTP_200_OK)


class StudentInterventionListView(APIView):
    """
    Candidate-safe intervention list.
    STRICTLY MASKS proctor identity and internal_notes (DSAR & privacy compliance).
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, attempt_id):
        attempt = TestAttempt.objects.filter(id=attempt_id).first()
        if not attempt:
            raise NotFound("Test attempt not found.")
        if attempt.student != request.user:
            raise PermissionDenied("You can only view interventions for your own test attempt.")

        interventions = ProctorIntervention.objects.filter(
            attempt=attempt
        ).order_by('issued_at')

        serializer = StudentInterventionSerializer(interventions, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
