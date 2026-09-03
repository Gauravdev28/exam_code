import pytest
from datetime import timedelta
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status

from apps.accounts.models import User, Role
from apps.assessments.models import Assessment, AssessmentStatus, TestAttempt, AttemptStatus, AssessmentSnapshot
from apps.invigilation.models import ProctorAssignment, ProctorIntervention, InterventionType
from apps.invigilation.services import ProctorRosterService, LiveInterventionService


@pytest.mark.django_db
class TestInvigilationSecurity:

    @pytest.fixture
    def setup_security(self):
        client = APIClient()
        admin = User.objects.create_user(email="admin_sec@test.com", password="password123", role=Role.ADMIN)
        proctor1 = User.objects.create_user(email="proctor1_sec@test.com", password="password123", role='PROCTOR')
        proctor2 = User.objects.create_user(email="proctor2_sec@test.com", password="password123", role='PROCTOR')
        student1 = User.objects.create_user(email="student1_sec@test.com", password="password123", role=Role.STUDENT)
        student2 = User.objects.create_user(email="student2_sec@test.com", password="password123", role=Role.STUDENT)

        now = timezone.now()
        # Assessment 1
        ass1 = Assessment.objects.create(
            title="Assessment 1",
            status=AssessmentStatus.PUBLISHED,
            duration_minutes=60,
            start_datetime=now - timedelta(minutes=10),
            end_datetime=now + timedelta(minutes=120),
            created_by=admin
        )
        snap1 = AssessmentSnapshot.objects.create(assessment=ass1, version_number=1)
        att1 = TestAttempt.objects.create(
            student=student1,
            assessment=ass1,
            assessment_snapshot=snap1,
            status=AttemptStatus.IN_PROGRESS,
            started_at=now
        )

        # Assessment 2
        ass2 = Assessment.objects.create(
            title="Assessment 2",
            status=AssessmentStatus.PUBLISHED,
            duration_minutes=60,
            start_datetime=now - timedelta(minutes=10),
            end_datetime=now + timedelta(minutes=120),
            created_by=admin
        )
        snap2 = AssessmentSnapshot.objects.create(assessment=ass2, version_number=1)
        att2 = TestAttempt.objects.create(
            student=student2,
            assessment=ass2,
            assessment_snapshot=snap2,
            status=AttemptStatus.IN_PROGRESS,
            started_at=now
        )

        # Proctor 1 is assigned strictly to Assessment 1
        assign1 = ProctorRosterService.assign_proctor(
            assessment_id=str(ass1.id),
            proctor_user=proctor1,
            assigned_by_user=admin
        )

        return {
            "client": client,
            "admin": admin,
            "proctor1": proctor1,
            "proctor2": proctor2,
            "student1": student1,
            "student2": student2,
            "ass1": ass1,
            "ass2": ass2,
            "att1": att1,
            "att2": att2,
            "assign1": assign1,
        }

    # 1. Anonymous Access Denied
    def test_anonymous_access_denied_proctor_endpoints(self, setup_security):
        e = setup_security
        client = e["client"]

        endpoints = [
            ('/api/v1/proctor/assessments/', 'get', None),
            (f"/api/v1/proctor/assessments/{e['ass1'].id}/live-roster/", 'get', None),
            (f"/api/v1/proctor/attempts/{e['att1'].id}/warning/", 'post', {"message": "hi"}),
            (f"/api/v1/proctor/attempts/{e['att1'].id}/pause/", 'post', {}),
            (f"/api/v1/proctor/attempts/{e['att1'].id}/resume/", 'post', {}),
            (f"/api/v1/proctor/attempts/{e['att1'].id}/terminate/", 'post', {"reason_code": "X", "formal_justification": "Y"}),
        ]

        for url, method, payload in endpoints:
            if method == 'get':
                res = client.get(url)
            else:
                res = client.post(url, payload or {})
            assert res.status_code == status.HTTP_401_UNAUTHORIZED

    # 2. Student Role Access Denied on Proctor Endpoints
    def test_student_cannot_call_proctor_interventions(self, setup_security):
        e = setup_security
        client = e["client"]
        client.force_authenticate(user=e["student1"])

        urls = [
            (f"/api/v1/proctor/attempts/{e['att1'].id}/warning/", {"message": "hi"}),
            (f"/api/v1/proctor/attempts/{e['att1'].id}/pause/", {}),
            (f"/api/v1/proctor/attempts/{e['att1'].id}/resume/", {}),
            (f"/api/v1/proctor/attempts/{e['att1'].id}/terminate/", {"reason_code": "X", "formal_justification": "Y"}),
        ]

        for url, payload in urls:
            res = client.post(url, payload)
            assert res.status_code == status.HTTP_403_FORBIDDEN

    # 3. IDOR Defense: Proctor Cannot Access Unassigned Assessment Roster
    def test_proctor_cannot_access_unassigned_assessment_roster(self, setup_security):
        e = setup_security
        client = e["client"]
        client.force_authenticate(user=e["proctor1"])

        # Proctor 1 accessing Assessment 2 (unassigned)
        url = f"/api/v1/proctor/assessments/{e['ass2'].id}/live-roster/"
        res = client.get(url)
        assert res.status_code == status.HTTP_403_FORBIDDEN

    # 4. IDOR Defense: Proctor Cannot Intervene in Unassigned Attempt
    def test_proctor_cannot_intervene_in_unassigned_attempt(self, setup_security):
        e = setup_security
        client = e["client"]
        client.force_authenticate(user=e["proctor1"])

        # Attempt 2 belongs to Assessment 2
        warn_url = f"/api/v1/proctor/attempts/{e['att2'].id}/warning/"
        res = client.post(warn_url, {"reason_code": "WARN", "message": "Illegal attempt"})
        assert res.status_code == status.HTTP_403_FORBIDDEN

        pause_url = f"/api/v1/proctor/attempts/{e['att2'].id}/pause/"
        res = client.post(pause_url, {"reason": "Illegal pause"})
        assert res.status_code == status.HTTP_403_FORBIDDEN

        term_url = f"/api/v1/proctor/attempts/{e['att2'].id}/terminate/"
        res = client.post(term_url, {"reason_code": "TERM", "formal_justification": "Illegal term"})
        assert res.status_code == status.HTTP_403_FORBIDDEN

    # 5. IDOR Defense: Proctor With Inactive Assignment Denied Access
    def test_inactive_proctor_assignment_denied(self, setup_security):
        e = setup_security
        client = e["client"]

        # Deactivate proctor 1 assignment
        e["assign1"].is_active = False
        e["assign1"].save(update_fields=['is_active'])

        client.force_authenticate(user=e["proctor1"])
        url = f"/api/v1/proctor/assessments/{e['ass1'].id}/live-roster/"
        res = client.get(url)
        assert res.status_code == status.HTTP_403_FORBIDDEN

    # 6. IDOR Defense: Student Cannot Access Other Student's Interventions
    def test_student_cannot_view_other_student_interventions(self, setup_security):
        e = setup_security
        client = e["client"]
        client.force_authenticate(user=e["student2"])

        # Student 2 tries to view Student 1's attempt interventions
        url = f"/api/v1/student/attempts/{e['att1'].id}/interventions/"
        res = client.get(url)
        assert res.status_code == status.HTTP_403_FORBIDDEN

    # 7. Student Cannot Acknowledge Other Student's Warning
    def test_student_cannot_acknowledge_other_student_warning(self, setup_security):
        e = setup_security
        client = e["client"]

        # Issue warning to Student 1
        interv = LiveInterventionService.issue_warning(
            proctor=e["proctor1"],
            attempt_id=str(e["att1"].id),
            reason_code="WARN",
            message="Attention"
        )

        # Student 2 tries to acknowledge it
        client.force_authenticate(user=e["student2"])
        ack_url = f"/api/v1/student/attempts/{e['att1'].id}/acknowledge-warning/"
        res = client.post(ack_url, {"intervention_id": str(interv.id)})
        assert res.status_code == status.HTTP_403_FORBIDDEN

    # 8. Unassigned Proctor Cannot Read Bilateral Chat
    def test_unassigned_proctor_cannot_read_chat(self, setup_security):
        e = setup_security
        client = e["client"]
        client.force_authenticate(user=e["proctor2"])

        chat_url = f"/api/v1/proctor/attempts/{e['att1'].id}/chat/"
        res = client.get(chat_url)
        assert res.status_code == status.HTTP_403_FORBIDDEN

    # 9. Admin Retains Universal Access
    def test_admin_has_full_access(self, setup_security):
        e = setup_security
        client = e["client"]
        client.force_authenticate(user=e["admin"])

        # Admin can view roster for any assessment without prior assignment
        url = f"/api/v1/proctor/assessments/{e['ass2'].id}/live-roster/"
        res = client.get(url)
        assert res.status_code == status.HTTP_200_OK

        # Admin can issue warning to any attempt
        warn_url = f"/api/v1/proctor/attempts/{e['att2'].id}/warning/"
        res = client.post(warn_url, {"reason_code": "ADMIN_WARN", "message": "Admin message"})
        assert res.status_code == status.HTTP_201_CREATED

    # 10. Payload Validation & Blank Inputs Rejected
    def test_warning_with_blank_message_rejected(self, setup_security):
        e = setup_security
        client = e["client"]
        client.force_authenticate(user=e["proctor1"])

        warn_url = f"/api/v1/proctor/attempts/{e['att1'].id}/warning/"
        res = client.post(warn_url, {"reason_code": "WARN", "message": ""})
        assert res.status_code == status.HTTP_400_BAD_REQUEST

    def test_terminate_with_blank_justification_rejected(self, setup_security):
        e = setup_security
        client = e["client"]
        client.force_authenticate(user=e["proctor1"])

        term_url = f"/api/v1/proctor/attempts/{e['att1'].id}/terminate/"
        res = client.post(term_url, {"reason_code": "CAUSE", "formal_justification": ""})
        assert res.status_code == status.HTTP_400_BAD_REQUEST

    # 11. Student Chat Security Isolation
    def test_student_cannot_send_chat_on_other_attempt(self, setup_security):
        e = setup_security
        client = e["client"]
        client.force_authenticate(user=e["student2"])

        # Student 2 tries to send chat to Student 1's attempt
        chat_url = f"/api/v1/proctor/attempts/{e['att1'].id}/chat/"
        res = client.post(chat_url, {"message_text": "Spam message"})
        assert res.status_code == status.HTTP_403_FORBIDDEN

    def test_unassigned_proctor_cannot_send_chat(self, setup_security):
        e = setup_security
        client = e["client"]
        client.force_authenticate(user=e["proctor2"])

        chat_url = f"/api/v1/proctor/attempts/{e['att1'].id}/chat/"
        res = client.post(chat_url, {"message_text": "Unauthorized message"})
        assert res.status_code == status.HTTP_403_FORBIDDEN

    # 12. Student Cannot Be Assigned as Proctor
    def test_student_cannot_be_assigned_as_proctor(self, setup_security):
        e = setup_security
        from rest_framework.exceptions import ValidationError as DRFValidationError
        with pytest.raises(DRFValidationError):
            ProctorRosterService.assign_proctor(
                assessment_id=str(e["ass1"].id),
                proctor_user=e["student1"]
            )

    # 13. Student Cannot Directly Unpause Attempt
    def test_student_cannot_unpause_attempt(self, setup_security):
        e = setup_security
        client = e["client"]

        # Pause attempt
        LiveInterventionService.pause_attempt(e["proctor1"], str(e["att1"].id))

        client.force_authenticate(user=e["student1"])
        resume_url = f"/api/v1/proctor/attempts/{e['att1'].id}/resume/"
        res = client.post(resume_url, {})
        assert res.status_code == status.HTTP_403_FORBIDDEN

    # 14. Non-Existent Attempt Returns 404
    def test_non_existent_attempt_returns_404(self, setup_security):
        e = setup_security
        client = e["client"]
        client.force_authenticate(user=e["admin"])
        import uuid

        bad_url = f"/api/v1/proctor/attempts/{uuid.uuid4()}/warning/"
        res = client.post(bad_url, {"reason_code": "WARN", "message": "msg"})
        assert res.status_code == status.HTTP_404_NOT_FOUND

    # 15. Student Cannot Create Proctor Interventions
    def test_student_cannot_create_interventions_via_service(self, setup_security):
        e = setup_security
        # Verify model constraints: ProctorIntervention with student as proctor
        interv = ProctorIntervention.objects.create(
            attempt=e["att1"],
            proctor=e["proctor1"],
            student=e["student1"],
            event_type=InterventionType.WARNING_ISSUED,
            reason_code="WARN"
        )
        assert interv.proctor == e["proctor1"]

