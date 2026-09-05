from django.urls import path
from .views import (
    AdminQuestionListView,
    AdminQuestionDetailView,
    AdminQuestionArchiveView,
    AdminQuestionUsageView,
    AdminQuestionRunSandboxView,
    AdminQuestionVersionListView,
    AdminQuestionVersionDetailView,
    AdminQuestionVersionPublishView,
    AdminQuestionVersionArchiveView,
    AdminQuestionVersionPreviewView,
    AdminTagListView,
    AdminQuestionTemplateDownloadView,
    AdminQuestionSpreadsheetPreviewView,
    AdminQuestionSpreadsheetConfirmView,
    AdminQuestionImageExtractView,
    AdminQuestionTempImageView,
    AdminQuestionVersionHealthView,
    AdminSupportedLanguagesView,
    AdminPlatformImportStatusView,
    AdminPlatformImportPreviewView,
    AdminPlatformImportConfirmView,
)

app_name = 'questions'

urlpatterns = [
    # Supported Languages Registry
    path('admin/questions/languages/', AdminSupportedLanguagesView.as_view(), name='admin-question-languages'),

    # Ingestion: Platform Import (Authorized HackerRank, LeetCode Manual, ZIP Package)
    path('admin/questions/platform-import/status/', AdminPlatformImportStatusView.as_view(), name='admin-platform-import-status'),
    path('admin/questions/platform-import/preview/', AdminPlatformImportPreviewView.as_view(), name='admin-platform-import-preview'),
    path('admin/questions/platform-import/confirm/', AdminPlatformImportConfirmView.as_view(), name='admin-platform-import-confirm'),

    # Ingestion: Spreadsheet (Excel/CSV) & Image OCR Extraction
    path('admin/questions/import/template/', AdminQuestionTemplateDownloadView.as_view(), name='admin-question-import-template'),
    path('admin/questions/import/preview/', AdminQuestionSpreadsheetPreviewView.as_view(), name='admin-question-import-preview'),
    path('admin/questions/import/confirm/', AdminQuestionSpreadsheetConfirmView.as_view(), name='admin-question-import-confirm'),
    path('admin/questions/extract-image/', AdminQuestionImageExtractView.as_view(), name='admin-question-extract-image'),
    path('admin/questions/temp-image/<str:image_id>/', AdminQuestionTempImageView.as_view(), name='admin-question-temp-image'),

    # Sandbox Execution (Admin untrusted code runner via Judge0)
    path('admin/questions/run-sandbox/', AdminQuestionRunSandboxView.as_view(), name='admin-question-run-sandbox'),

    # Question CRUD & Roster
    path('admin/questions/', AdminQuestionListView.as_view(), name='admin-question-list'),
    path('admin/questions/<uuid:pk>/', AdminQuestionDetailView.as_view(), name='admin-question-detail'),
    path('admin/questions/<uuid:pk>/usage/', AdminQuestionUsageView.as_view(), name='admin-question-usage'),
    path('admin/questions/<uuid:pk>/archive/', AdminQuestionArchiveView.as_view(), name='admin-question-archive'),

    # Question Versions
    path('admin/questions/<uuid:pk>/versions/', AdminQuestionVersionListView.as_view(), name='admin-question-version-list'),
    path('admin/questions/<uuid:pk>/versions/<int:version_number>/', AdminQuestionVersionDetailView.as_view(), name='admin-question-version-detail'),
    path('admin/questions/<uuid:pk>/versions/<int:version_number>/health/', AdminQuestionVersionHealthView.as_view(), name='admin-question-version-health'),
    path('admin/questions/<uuid:pk>/versions/<int:version_number>/publish/', AdminQuestionVersionPublishView.as_view(), name='admin-question-version-publish'),
    path('admin/questions/<uuid:pk>/versions/<int:version_number>/archive/', AdminQuestionVersionArchiveView.as_view(), name='admin-question-version-archive'),
    path('admin/questions/<uuid:pk>/versions/<int:version_number>/preview/', AdminQuestionVersionPreviewView.as_view(), name='admin-question-version-preview'),

    # Tags
    path('admin/tags/', AdminTagListView.as_view(), name='admin-tag-list'),
]
