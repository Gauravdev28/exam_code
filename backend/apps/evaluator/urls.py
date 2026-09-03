from django.urls import path
from apps.evaluator.views import (
    StudentCodeRunView,
    StudentCodeSubmitView,
    StudentSubmissionDetailView,
    AdminSubmissionListView,
    AdminSubmissionDetailView,
)

app_name = 'evaluator'

urlpatterns = [
    # Student Execution APIs
    path(
        'student/attempts/<uuid:attempt_id>/questions/<str:question_id>/run/',
        StudentCodeRunView.as_view(),
        name='student-code-run'
    ),
    path(
        'student/attempts/<uuid:attempt_id>/questions/<str:question_id>/submit/',
        StudentCodeSubmitView.as_view(),
        name='student-code-submit'
    ),
    path(
        'student/submissions/<uuid:submission_id>/',
        StudentSubmissionDetailView.as_view(),
        name='student-submission-detail'
    ),

    # Admin Monitoring APIs
    path(
        'admin/assessments/<uuid:assessment_id>/submissions/',
        AdminSubmissionListView.as_view(),
        name='admin-assessment-submissions'
    ),
    path(
        'admin/submissions/<uuid:submission_id>/',
        AdminSubmissionDetailView.as_view(),
        name='admin-submission-detail'
    ),
]
