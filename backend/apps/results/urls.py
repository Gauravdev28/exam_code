from django.urls import path
from .views import (
    StudentAttemptResultView,
    StudentResultListView,
    StudentResultDetailView,
    StudentTopicAnalyticsView,
    StudentReportCreateView,
    StudentReportDetailView,
    StudentReportDownloadView,
    AdminAssessmentResultListView,
    AdminAssessmentResultDetailView,
    AdminAssessmentAnalyticsView,
    AdminQuestionAnalyticsView,
    AdminReleaseResultsView,
    AdminReportCreateView,
    AdminReportDetailView,
    AdminReportDownloadView,
)

urlpatterns = [
    # Student Result Endpoints
    path('student/attempts/<uuid:attempt_id>/result/', StudentAttemptResultView.as_view(), name='student-attempt-result'),
    path('student/results/', StudentResultListView.as_view(), name='student-result-list'),
    path('student/results/<uuid:pk>/', StudentResultDetailView.as_view(), name='student-result-detail'),
    path('student/analytics/topics/', StudentTopicAnalyticsView.as_view(), name='student-topic-analytics'),
    path('student/reports/', StudentReportCreateView.as_view(), name='student-report-create'),
    path('student/reports/<uuid:pk>/', StudentReportDetailView.as_view(), name='student-report-detail'),
    path('student/reports/<uuid:pk>/download/', StudentReportDownloadView.as_view(), name='student-report-download'),

    # Admin Result & Analytics Endpoints
    path('admin/assessments/<uuid:assessment_id>/results/', AdminAssessmentResultListView.as_view(), name='admin-assessment-results'),
    path('admin/assessments/<uuid:assessment_id>/analytics/', AdminAssessmentAnalyticsView.as_view(), name='admin-assessment-analytics'),
    path('admin/assessments/<uuid:assessment_id>/analytics/questions/', AdminQuestionAnalyticsView.as_view(), name='admin-question-analytics'),
    path('admin/assessments/<uuid:assessment_id>/release-results/', AdminReleaseResultsView.as_view(), name='admin-release-results'),
    path('admin/results/<uuid:pk>/', AdminAssessmentResultDetailView.as_view(), name='admin-result-detail'),
    path('admin/reports/', AdminReportCreateView.as_view(), name='admin-report-create'),
    path('admin/reports/<uuid:pk>/', AdminReportDetailView.as_view(), name='admin-report-detail'),
    path('admin/reports/<uuid:pk>/download/', AdminReportDownloadView.as_view(), name='admin-report-download'),
]
