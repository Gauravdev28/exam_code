from django.urls import path
from .views import (
    LoginView,
    LogoutView,
    CurrentUserView,
    ChangePasswordView,
    StudentProfileView,
    AdminStudentListView,
    AdminStudentDetailView,
    AdminStudentStatusView,
    AdminStudentImportPreviewView,
    AdminStudentImportConfirmView,
    AdminOnlyTestView,
    StudentOnlyTestView,
)

app_name = 'accounts'

urlpatterns = [
    # Auth endpoints
    path('auth/login/', LoginView.as_view(), name='login'),
    path('auth/logout/', LogoutView.as_view(), name='logout'),
    path('auth/me/', CurrentUserView.as_view(), name='current-user'),
    path('auth/change-password/', ChangePasswordView.as_view(), name='change-password'),
    path('auth/admin-only/', AdminOnlyTestView.as_view(), name='admin-only-test'),
    path('auth/student-only/', StudentOnlyTestView.as_view(), name='student-only-test'),

    # Student-facing endpoints
    path('student/profile/', StudentProfileView.as_view(), name='student-profile'),

    # Admin Student Management endpoints
    path('admin/students/', AdminStudentListView.as_view(), name='admin-student-list'),
    path('admin/students/<uuid:pk>/', AdminStudentDetailView.as_view(), name='admin-student-detail'),
    path('admin/students/<uuid:pk>/disable/', AdminStudentStatusView.as_view(), {'action': 'disable'}, name='admin-student-disable'),
    path('admin/students/<uuid:pk>/enable/', AdminStudentStatusView.as_view(), {'action': 'enable'}, name='admin-student-enable'),
    path('admin/students/import/preview/', AdminStudentImportPreviewView.as_view(), name='admin-student-import-preview'),
    path('admin/students/import/confirm/', AdminStudentImportConfirmView.as_view(), name='admin-student-import-confirm'),
]
