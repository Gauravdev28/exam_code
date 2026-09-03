from django.urls import path
from .views import (
    AdminQuestionListView,
    AdminQuestionDetailView,
    AdminQuestionArchiveView,
    AdminQuestionVersionListView,
    AdminQuestionVersionDetailView,
    AdminQuestionVersionPublishView,
    AdminQuestionVersionArchiveView,
    AdminQuestionVersionPreviewView,
    AdminTagListView,
)

app_name = 'questions'

urlpatterns = [
    # Question CRUD & Roster
    path('admin/questions/', AdminQuestionListView.as_view(), name='admin-question-list'),
    path('admin/questions/<uuid:pk>/', AdminQuestionDetailView.as_view(), name='admin-question-detail'),
    path('admin/questions/<uuid:pk>/archive/', AdminQuestionArchiveView.as_view(), name='admin-question-archive'),

    # Question Versions
    path('admin/questions/<uuid:pk>/versions/', AdminQuestionVersionListView.as_view(), name='admin-question-version-list'),
    path('admin/questions/<uuid:pk>/versions/<int:version_number>/', AdminQuestionVersionDetailView.as_view(), name='admin-question-version-detail'),
    path('admin/questions/<uuid:pk>/versions/<int:version_number>/publish/', AdminQuestionVersionPublishView.as_view(), name='admin-question-version-publish'),
    path('admin/questions/<uuid:pk>/versions/<int:version_number>/archive/', AdminQuestionVersionArchiveView.as_view(), name='admin-question-version-archive'),
    path('admin/questions/<uuid:pk>/versions/<int:version_number>/preview/', AdminQuestionVersionPreviewView.as_view(), name='admin-question-version-preview'),

    # Tags
    path('admin/tags/', AdminTagListView.as_view(), name='admin-tag-list'),
]
