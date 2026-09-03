from django.urls import path
from .views import (
    AdminRetentionMetricsView,
    AdminRetentionPolicyListCreateView,
    AdminRetentionPolicyDetailView,
    AdminRetentionCandidateListView,
    AdminPurgePreviewView,
    AdminPurgeExecuteView,
    AdminRetentionTombstoneListView,
    AdminFileCleanupQueueListView,
    AdminLegalHoldListCreateView,
    AdminLegalHoldReleaseView,
    StudentRetentionStatusView,
    StudentExportJobListCreateView,
    StudentExportJobDownloadView,
)

urlpatterns = [
    # Admin Retention Dashboard & Policy Engine
    path('admin/retention/metrics/', AdminRetentionMetricsView.as_view(), name='admin-retention-metrics'),
    path('admin/retention/policies/', AdminRetentionPolicyListCreateView.as_view(), name='admin-retention-policies'),
    path('admin/retention/policies/<uuid:pk>/', AdminRetentionPolicyDetailView.as_view(), name='admin-retention-policy-detail'),
    path('admin/retention/candidates/', AdminRetentionCandidateListView.as_view(), name='admin-retention-candidates'),
    path('admin/retention/preview-purge/', AdminPurgePreviewView.as_view(), name='admin-retention-preview-purge'),
    path('admin/retention/execute-purge/', AdminPurgeExecuteView.as_view(), name='admin-retention-execute-purge'),
    path('admin/retention/tombstones/', AdminRetentionTombstoneListView.as_view(), name='admin-retention-tombstones'),
    path('admin/retention/cleanup-queue/', AdminFileCleanupQueueListView.as_view(), name='admin-retention-cleanup-queue'),

    # Admin Legal Holds
    path('admin/legal-holds/', AdminLegalHoldListCreateView.as_view(), name='admin-legal-holds'),
    path('admin/legal-holds/<uuid:pk>/release/', AdminLegalHoldReleaseView.as_view(), name='admin-legal-hold-release'),

    # Student Privacy & DSAR Lifecycle
    path('student/privacy/retention-status/', StudentRetentionStatusView.as_view(), name='student-privacy-retention-status'),
    path('student/privacy/export-requests/', StudentExportJobListCreateView.as_view(), name='student-privacy-export-requests'),
    path('student/privacy/export-requests/<uuid:pk>/download/', StudentExportJobDownloadView.as_view(), name='student-privacy-export-download'),
]
