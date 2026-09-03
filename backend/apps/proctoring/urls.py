from django.urls import path
from apps.proctoring.views import (
    StudentProctoringStartView,
    StudentProctoringHeartbeatView,
    StudentProctoringEventIngestionView,
    StudentProctoringFrameUploadView,
    StudentProctoringAudioUploadView,
    StudentProctoringWarningAckView,
    AdminProctoringSessionListView,
    AdminProctoringSessionDetailView,
    AdminProctoringEvidenceStreamView,
    AdminProctoringReviewView,
)

urlpatterns = [
    # Student Proctoring Endpoints
    path('student/attempts/<uuid:attempt_id>/proctoring/start/', StudentProctoringStartView.as_view(), name='student-proctoring-start'),
    path('student/attempts/<uuid:attempt_id>/proctoring/heartbeat/', StudentProctoringHeartbeatView.as_view(), name='student-proctoring-heartbeat'),
    path('student/attempts/<uuid:attempt_id>/proctoring/events/', StudentProctoringEventIngestionView.as_view(), name='student-proctoring-events'),
    path('student/attempts/<uuid:attempt_id>/proctoring/frames/', StudentProctoringFrameUploadView.as_view(), name='student-proctoring-frames'),
    path('student/attempts/<uuid:attempt_id>/proctoring/audio/', StudentProctoringAudioUploadView.as_view(), name='student-proctoring-audio'),
    path('student/attempts/<uuid:attempt_id>/proctoring/warnings/<uuid:warning_id>/ack/', StudentProctoringWarningAckView.as_view(), name='student-proctoring-warning-ack'),

    # Admin Proctoring Endpoints
    path('admin/assessments/<uuid:assessment_id>/proctoring/sessions/', AdminProctoringSessionListView.as_view(), name='admin-proctoring-session-list'),
    path('admin/proctoring/sessions/<uuid:session_id>/', AdminProctoringSessionDetailView.as_view(), name='admin-proctoring-session-detail'),
    path('admin/proctoring/evidence/<uuid:evidence_id>/', AdminProctoringEvidenceStreamView.as_view(), name='admin-proctoring-evidence-stream'),
    path('admin/proctoring/sessions/<uuid:session_id>/review/', AdminProctoringReviewView.as_view(), name='admin-proctoring-review'),
]
