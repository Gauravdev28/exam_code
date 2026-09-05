from django.urls import path
from .views import (
    AdminAssessmentListView,
    AdminAssessmentDetailView,
    AdminAssessmentPublishView,
    AdminAssessmentArchiveView,
    AdminAssessmentAudienceView,
    AdminAssessmentAudiencePreviewView,
    AdminAssessmentQuestionAddView,
    AdminAssessmentQuestionRemoveView,
    AdminAssessmentAssignmentListView,
    AdminAssessmentAssignmentRevokeView,
    StudentAssessmentListView,
    StudentAssessmentDetailView,
    StudentAssessmentStartView,
    StudentAttemptDetailView,
    StudentAttemptSaveAnswerView,
    StudentAttemptSubmitView,
)

app_name = 'assessments'

urlpatterns = [
    # Admin Assessment Endpoints
    path('admin/assessments/', AdminAssessmentListView.as_view(), name='admin-assessment-list'),
    path('admin/assessments/<uuid:pk>/', AdminAssessmentDetailView.as_view(), name='admin-assessment-detail'),
    path('admin/assessments/<uuid:pk>/publish/', AdminAssessmentPublishView.as_view(), name='admin-assessment-publish'),
    path('admin/assessments/<uuid:pk>/archive/', AdminAssessmentArchiveView.as_view(), name='admin-assessment-archive'),
    path('admin/assessments/<uuid:pk>/audience/', AdminAssessmentAudienceView.as_view(), name='admin-assessment-audience'),
    path('admin/assessments/<uuid:pk>/audience/preview/', AdminAssessmentAudiencePreviewView.as_view(), name='admin-assessment-audience-preview'),
    path('admin/assessments/<uuid:pk>/questions/', AdminAssessmentQuestionAddView.as_view(), name='admin-assessment-question-add'),
    path('admin/assessments/<uuid:pk>/questions/<uuid:question_version_id>/', AdminAssessmentQuestionRemoveView.as_view(), name='admin-assessment-question-remove'),
    path('admin/assessments/<uuid:pk>/assignments/', AdminAssessmentAssignmentListView.as_view(), name='admin-assessment-assignment-list'),
    path('admin/assessments/<uuid:pk>/assignments/<uuid:student_id>/', AdminAssessmentAssignmentRevokeView.as_view(), name='admin-assessment-assignment-revoke'),

    # Student Assessment & Attempt Endpoints
    path('student/assessments/', StudentAssessmentListView.as_view(), name='student-assessment-list'),
    path('student/assessments/<uuid:pk>/', StudentAssessmentDetailView.as_view(), name='student-assessment-detail'),
    path('student/assessments/<uuid:pk>/start/', StudentAssessmentStartView.as_view(), name='student-assessment-start'),
    path('student/attempts/<uuid:pk>/', StudentAttemptDetailView.as_view(), name='student-attempt-detail'),
    path('student/attempts/<uuid:pk>/answers/<str:question_id>/', StudentAttemptSaveAnswerView.as_view(), name='student-attempt-save-answer'),
    path('student/attempts/<uuid:pk>/submit/', StudentAttemptSubmitView.as_view(), name='student-attempt-submit'),
]
