from django.urls import path
from .views import (
    CSRFTokenView,
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
    AdminDashboardOverviewView,
    AdministratorListView,
    AdministratorDetailView,
    AdministratorStatusView,
    AdministratorResetPasswordView,
    AdminStudentResetPasswordView,
    SecurityAuditLogView,
    SessionStatusView,
    SessionRefreshView,
    AdminSectionListView,
    AdminSectionDetailView,
)

app_name = 'accounts'

urlpatterns = [
    # Auth endpoints
    path('auth/csrf/', CSRFTokenView.as_view(), name='csrf-init'),
    path('auth/login/', LoginView.as_view(), name='login'),
    path('auth/logout/', LogoutView.as_view(), name='logout'),
    path('auth/me/', CurrentUserView.as_view(), name='current-user'),
    path('auth/change-password/', ChangePasswordView.as_view(), name='change-password'),
    path('auth/session/status/', SessionStatusView.as_view(), name='session-status'),
    path('auth/session/refresh/', SessionRefreshView.as_view(), name='session-refresh'),
    path('auth/admin-only/', AdminOnlyTestView.as_view(), name='admin-only-test'),
    path('auth/student-only/', StudentOnlyTestView.as_view(), name='student-only-test'),

    # Student-facing endpoints
    path('student/profile/', StudentProfileView.as_view(), name='student-profile'),

    # Admin Dashboard & Overview
    path('admin/overview/', AdminDashboardOverviewView.as_view(), name='admin-dashboard-overview'),

    # Admin Management endpoints
    path('admin/administrators/', AdministratorListView.as_view(), name='admin-administrator-list'),
    path('admin/administrators/<uuid:pk>/', AdministratorDetailView.as_view(), name='admin-administrator-detail'),
    path('admin/administrators/<uuid:pk>/status/', AdministratorStatusView.as_view(), name='admin-administrator-status'),
    path('admin/administrators/<uuid:pk>/reset-password/', AdministratorResetPasswordView.as_view(), name='admin-administrator-reset-password'),
    path('admin/audit-logs/', SecurityAuditLogView.as_view(), name='admin-security-audit-logs'),

    # Admin Student Management endpoints
    path('admin/students/', AdminStudentListView.as_view(), name='admin-student-list'),
    path('admin/students/<uuid:pk>/', AdminStudentDetailView.as_view(), name='admin-student-detail'),
    path('admin/students/<uuid:pk>/disable/', AdminStudentStatusView.as_view(), {'action': 'disable'}, name='admin-student-disable'),
    path('admin/students/<uuid:pk>/enable/', AdminStudentStatusView.as_view(), {'action': 'enable'}, name='admin-student-enable'),
    path('admin/students/<uuid:pk>/reset-password/', AdminStudentResetPasswordView.as_view(), name='admin-student-reset-password'),
    path('admin/students/import/preview/', AdminStudentImportPreviewView.as_view(), name='admin-student-import-preview'),
    path('admin/students/import/confirm/', AdminStudentImportConfirmView.as_view(), name='admin-student-import-confirm'),

    # Admin Section Management endpoints
    path('admin/sections/', AdminSectionListView.as_view(), name='admin-section-list'),
    path('admin/sections/<uuid:pk>/', AdminSectionDetailView.as_view(), name='admin-section-detail'),
]

