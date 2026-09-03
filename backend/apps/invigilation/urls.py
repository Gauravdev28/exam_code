from django.urls import path
from apps.invigilation.views import (
    ProctorAssignedAssessmentsView,
    ProctorLiveRosterView,
    ProctorIssueWarningView,
    ProctorPauseAttemptView,
    ProctorResumeAttemptView,
    ProctorRoomScanRequestView,
    ProctorTerminateAttemptView,
    ProctorInterventionHistoryView,
    ProctorChatHistoryView,
    StudentAcknowledgeWarningView,
    StudentCompleteRoomScanView,
    StudentInterventionListView,
)

urlpatterns = [
    # Proctor Console Endpoints
    path('proctor/assessments/', ProctorAssignedAssessmentsView.as_view(), name='proctor-assigned-assessments'),
    path('proctor/assessments/<uuid:assessment_id>/live-roster/', ProctorLiveRosterView.as_view(), name='proctor-live-roster'),
    path('proctor/attempts/<uuid:attempt_id>/warning/', ProctorIssueWarningView.as_view(), name='proctor-issue-warning'),
    path('proctor/attempts/<uuid:attempt_id>/pause/', ProctorPauseAttemptView.as_view(), name='proctor-pause-attempt'),
    path('proctor/attempts/<uuid:attempt_id>/resume/', ProctorResumeAttemptView.as_view(), name='proctor-resume-attempt'),
    path('proctor/attempts/<uuid:attempt_id>/room-scan/', ProctorRoomScanRequestView.as_view(), name='proctor-room-scan'),
    path('proctor/attempts/<uuid:attempt_id>/terminate/', ProctorTerminateAttemptView.as_view(), name='proctor-terminate-attempt'),
    path('proctor/attempts/<uuid:attempt_id>/interventions/', ProctorInterventionHistoryView.as_view(), name='proctor-intervention-history'),
    path('proctor/attempts/<uuid:attempt_id>/chat/', ProctorChatHistoryView.as_view(), name='proctor-chat'),

    # Student-Facing Intervention Endpoints
    path('student/attempts/<uuid:attempt_id>/acknowledge-warning/', StudentAcknowledgeWarningView.as_view(), name='student-acknowledge-warning'),
    path('student/attempts/<uuid:attempt_id>/complete-room-scan/', StudentCompleteRoomScanView.as_view(), name='student-complete-room-scan'),
    path('student/attempts/<uuid:attempt_id>/interventions/', StudentInterventionListView.as_view(), name='student-interventions'),
]
