import pytest
from datetime import timedelta
from decimal import Decimal
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status

from apps.accounts.models import User, Role
from apps.assessments.models import (
    Assessment,
    AssessmentStatus,
    TestAttempt,
    AttemptStatus,
    AssessmentSnapshot,
    AssessmentSnapshotQuestion,
    AttemptAnswer,
)
from apps.results.models import AssessmentResult, HistoricalResultSummary, ResultStatus
from apps.results.services import ResultFinalizationService
from apps.invigilation.models import (
    ProctorAssignment,
    ProctorIntervention,
    InterventionType,
)
from apps.invigilation.services import ProctorRosterService


@pytest.mark.django_db
class TestInvigilationIntegration:

    @pytest.fixture
    def setup_integration(self):
        client = APIClient()
        admin = User.objects.create_user(email="admin_int@test.com", password="password123", role=Role.ADMIN)
        proctor = User.objects.create_user(email="proctor_int@test.com", password="password123", role='PROCTOR')
        student = User.objects.create_user(email="student_int@test.com", password="password123", role=Role.STUDENT)

        now = timezone.now()
        assessment = Assessment.objects.create(
            title="Integration Exam",
            status=AssessmentStatus.PUBLISHED,
            duration_minutes=60,
            passing_percentage=50.00,
            start_datetime=now - timedelta(minutes=10),
            end_datetime=now + timedelta(minutes=180),
            created_by=admin
        )
        snapshot = AssessmentSnapshot.objects.create(
            assessment=assessment,
            version_number=1,
            snapshot_data={"title": "Integration Exam", "passing_percentage": 50.00},
            server_evaluation_bundle={"questions": {}}
        )

        from apps.questions.services import QuestionService
        from apps.questions.models import QuestionType

        q, v = QuestionService.create_question(
            question_type=QuestionType.MCQ,
            title="Q1",
            description="Sample",
            points=10,
            type_config={
                "options": [
                    {"id": "OPT_A", "text": "Option A"},
                    {"id": "OPT_B", "text": "Option B"}
                ],
                "correct_options": ["OPT_A"]
            },
            actor=admin
        )
        pv = QuestionService.publish_version(v, actor=admin)

        sq = AssessmentSnapshotQuestion.objects.create(
            snapshot=snapshot,
            question_version=pv,
            snapshot_question_id="Q1",
            question_type="MCQ",
            title="Question 1",
            description="Sample question",
            points=10,
            order=1
        )

        attempt = TestAttempt.objects.create(
            student=student,
            assessment=assessment,
            assessment_snapshot=snapshot,
            status=AttemptStatus.IN_PROGRESS,
            started_at=now - timedelta(minutes=15),
            expires_at=now + timedelta(minutes=45)
        )

        # Pre-populate an answer
        AttemptAnswer.objects.create(
            attempt=attempt,
            snapshot_question=sq,
            question_id="Q1",
            question_type="MCQ",
            is_answered=True,
            selected_options=["OPT_A"]
        )

        assignment = ProctorRosterService.assign_proctor(
            assessment_id=str(assessment.id),
            proctor_user=proctor,
            assigned_by_user=admin
        )

        return {
            "client": client,
            "admin": admin,
            "proctor": proctor,
            "student": student,
            "assessment": assessment,
            "snapshot": snapshot,
            "attempt": attempt,
            "assignment": assignment,
            "sq": sq,
        }

    def test_proctor_assigned_assessments_endpoint(self, setup_integration):
        e = setup_integration
        client = e["client"]
        client.force_authenticate(user=e["proctor"])

        res = client.get('/api/v1/proctor/assessments/')
        assert res.status_code == status.HTTP_200_OK
        assert len(res.data) >= 1
        assert str(res.data[0]['assessment']) == str(e["assessment"].id)

    def test_proctor_live_roster_endpoint(self, setup_integration):
        e = setup_integration
        client = e["client"]
        client.force_authenticate(user=e["proctor"])

        url = f"/api/v1/proctor/assessments/{e['assessment'].id}/live-roster/"
        res = client.get(url)
        assert res.status_code == status.HTTP_200_OK
        assert res.data['count'] == 1
        assert res.data['candidates'][0]['attempt_id'] == str(e["attempt"].id)

    def test_warning_and_acknowledgement_flow(self, setup_integration):
        e = setup_integration
        client = e["client"]

        # 1. Proctor issues warning
        client.force_authenticate(user=e["proctor"])
        warn_url = f"/api/v1/proctor/attempts/{e['attempt'].id}/warning/"
        warn_res = client.post(warn_url, {
            "reason_code": "SUSPICIOUS_GAZE",
            "message": "Please do not look away from the monitor.",
            "internal_notes": "Looked right for 12 seconds."
        })
        assert warn_res.status_code == status.HTTP_201_CREATED
        interv_id = warn_res.data['id']
        assert warn_res.data['internal_notes'] == "Looked right for 12 seconds."

        # 2. Student acknowledges warning
        client.force_authenticate(user=e["student"])
        ack_url = f"/api/v1/student/attempts/{e['attempt'].id}/acknowledge-warning/"
        ack_res = client.post(ack_url, {"intervention_id": interv_id})
        assert ack_res.status_code == status.HTTP_200_OK
        assert ack_res.data['event_type'] == InterventionType.WARNING_ACKNOWLEDGED

    def test_pause_and_resume_flow(self, setup_integration):
        e = setup_integration
        client = e["client"]
        client.force_authenticate(user=e["proctor"])

        # 1. Pause
        pause_url = f"/api/v1/proctor/attempts/{e['attempt'].id}/pause/"
        p_res = client.post(pause_url, {"reason": "Network instability"})
        assert p_res.status_code == status.HTTP_201_CREATED
        assert p_res.data['event_type'] == InterventionType.PAUSE_STARTED

        # Verify attempt has active pause
        e["attempt"].refresh_from_db()
        assert ProctorIntervention.objects.filter(
            attempt=e["attempt"],
            event_type=InterventionType.PAUSE_STARTED
        ).exists()

        # 2. Resume
        resume_url = f"/api/v1/proctor/attempts/{e['attempt'].id}/resume/"
        r_res = client.post(resume_url, {"reason": "Network resolved"})
        assert r_res.status_code == status.HTTP_200_OK
        assert r_res.data['event_type'] == InterventionType.PAUSE_ENDED

    def test_room_scan_flow(self, setup_integration):
        e = setup_integration
        client = e["client"]

        # Proctor requests scan
        client.force_authenticate(user=e["proctor"])
        req_url = f"/api/v1/proctor/attempts/{e['attempt'].id}/room-scan/"
        r_res = client.post(req_url, {"reason": "Unusual background noise"})
        assert r_res.status_code == status.HTTP_201_CREATED
        scan_id = r_res.data['id']

        # Student completes scan
        client.force_authenticate(user=e["student"])
        comp_url = f"/api/v1/student/attempts/{e['attempt'].id}/complete-room-scan/"
        c_res = client.post(comp_url, {"scan_event_id": scan_id})
        assert c_res.status_code == status.HTTP_200_OK
        assert c_res.data['event_type'] == InterventionType.ROOM_SCAN_COMPLETED

    def test_termination_and_phase8_finalization_flow(self, setup_integration):
        e = setup_integration
        client = e["client"]
        client.force_authenticate(user=e["proctor"])

        term_url = f"/api/v1/proctor/attempts/{e['attempt'].id}/terminate/"
        term_res = client.post(term_url, {
            "reason_code": "PROHIBITED_DEVICE",
            "formal_justification": "Candidate found using unauthorized secondary computer.",
            "internal_notes": "Camera capture shows dual display reflection."
        })
        assert term_res.status_code == status.HTTP_200_OK
        assert term_res.data['status'] == "TERMINATED"
        assert term_res.data['attempt_status'] == AttemptStatus.CANCELLED

        # Verify TestAttempt in Phase 5 is CANCELLED
        e["attempt"].refresh_from_db()
        assert e["attempt"].status == AttemptStatus.CANCELLED

        # Run Phase 8 finalization to verify end-to-end scoring compatibility
        result = ResultFinalizationService.finalize_attempt(str(e["attempt"].id))
        assert result.status == ResultStatus.FINALIZED

        # Verify HistoricalResultSummary reflects CANCELLED without schema modifications
        history = HistoricalResultSummary.objects.get(
            student=e["student"],
            assessment_id=e["assessment"].id
        )
        assert history.completion_status == AttemptStatus.CANCELLED
        # Result summary contains valid score without crashing
        assert history.total_score_earned >= Decimal('0.00')

    def test_dsar_sanitization_masks_internal_notes_and_proctors(self, setup_integration):
        e = setup_integration
        client = e["client"]

        # Proctor creates intervention with internal notes
        client.force_authenticate(user=e["proctor"])
        warn_url = f"/api/v1/proctor/attempts/{e['attempt'].id}/warning/"
        client.post(warn_url, {
            "reason_code": "FLAGGED",
            "message": "Candidate alert.",
            "internal_notes": "TOP SECRET INTERNAL PROCTOR NOTES"
        })

        # Student accesses their interventions list
        client.force_authenticate(user=e["student"])
        stud_url = f"/api/v1/student/attempts/{e['attempt'].id}/interventions/"
        res = client.get(stud_url)
        assert res.status_code == status.HTTP_200_OK
        data = res.data
        assert len(data) >= 1

        for item in data:
            # internal_notes must NOT be present in student response
            assert 'internal_notes' not in item
            # proctor private ID or email must NOT be present
            assert 'proctor' not in item
            assert 'proctor_email' not in item

    def test_bilateral_chat_rest_flow(self, setup_integration):
        e = setup_integration
        client = e["client"]

        # Proctor sends chat
        client.force_authenticate(user=e["proctor"])
        chat_url = f"/api/v1/proctor/attempts/{e['attempt'].id}/chat/"
        send_res = client.post(chat_url, {"message_text": "Hello, please sit upright."})
        assert send_res.status_code == status.HTTP_201_CREATED
        assert send_res.data['message_text'] == "Hello, please sit upright."

        # Student reads chat
        client.force_authenticate(user=e["student"])
        hist_res = client.get(chat_url)
        assert hist_res.status_code == status.HTTP_200_OK
        assert len(hist_res.data) == 1
        assert hist_res.data[0]['message_text'] == "Hello, please sit upright."

    def test_proctor_intervention_history_endpoint(self, setup_integration):
        e = setup_integration
        client = e["client"]

        # Create two interventions
        client.force_authenticate(user=e["proctor"])
        warn_url = f"/api/v1/proctor/attempts/{e['attempt'].id}/warning/"
        client.post(warn_url, {"reason_code": "W1", "message": "First warning", "internal_notes": "Note 1"})
        client.post(warn_url, {"reason_code": "W2", "message": "Second warning", "internal_notes": "Note 2"})

        hist_url = f"/api/v1/proctor/attempts/{e['attempt'].id}/interventions/"
        res = client.get(hist_url)
        assert res.status_code == status.HTTP_200_OK
        assert len(res.data) >= 2
        # Proctor sees internal notes
        notes = [item['internal_notes'] for item in res.data]
        assert "Note 1" in notes
        assert "Note 2" in notes

    def test_student_chat_reply_flow(self, setup_integration):
        e = setup_integration
        client = e["client"]

        # Student sends chat to proctor
        client.force_authenticate(user=e["student"])
        chat_url = f"/api/v1/proctor/attempts/{e['attempt'].id}/chat/"
        res = client.post(chat_url, {"message_text": "I had a connection drop, sorry!"})
        assert res.status_code == status.HTTP_201_CREATED
        assert res.data['message_text'] == "I had a connection drop, sorry!"

        # Proctor reads chat
        client.force_authenticate(user=e["proctor"])
        hist = client.get(chat_url)
        assert hist.status_code == status.HTTP_200_OK
        assert any("connection drop" in m['message_text'] for m in hist.data)

    def test_admin_can_view_and_intervene_any_assessment(self, setup_integration):
        e = setup_integration
        client = e["client"]
        client.force_authenticate(user=e["admin"])

        # Admin accesses live roster
        url = f"/api/v1/proctor/assessments/{e['assessment'].id}/live-roster/"
        res = client.get(url)
        assert res.status_code == status.HTTP_200_OK

        # Admin issues pause
        pause_url = f"/api/v1/proctor/attempts/{e['attempt'].id}/pause/"
        p_res = client.post(pause_url, {"reason": "Admin pause"})
        assert p_res.status_code == status.HTTP_201_CREATED

        # Admin resumes
        resume_url = f"/api/v1/proctor/attempts/{e['attempt'].id}/resume/"
        r_res = client.post(resume_url, {"reason": "Admin resume"})
        assert r_res.status_code == status.HTTP_200_OK

    @pytest.mark.asyncio
    @pytest.mark.django_db(transaction=True)
    async def test_invigilation_consumer_authorized_proctor(self, setup_integration):
        from channels.testing import WebsocketCommunicator
        from codeguard.routing import websocket_urlpatterns
        from channels.routing import URLRouter
        from channels.auth import AuthMiddlewareStack

        e = setup_integration
        application = URLRouter(websocket_urlpatterns)
        path = f"/ws/proctor/assessments/{e['assessment'].id}/"

        communicator = WebsocketCommunicator(application, path)
        communicator.scope['user'] = e['proctor']
        communicator.scope['url_route'] = {'kwargs': {'assessment_id': str(e['assessment'].id)}}

        connected, subprotocol = await communicator.connect()
        assert connected is True
        # Verify initial CONNECTED message
        response = await communicator.receive_json_from()
        assert response['type'] == 'CONNECTED'
        assert response['assessment_id'] == str(e['assessment'].id)
        await communicator.disconnect()

    @pytest.mark.asyncio
    @pytest.mark.django_db(transaction=True)
    async def test_invigilation_consumer_unauthorized_rejected(self, setup_integration):
        from channels.testing import WebsocketCommunicator
        from codeguard.routing import websocket_urlpatterns
        from channels.routing import URLRouter

        e = setup_integration
        application = URLRouter(websocket_urlpatterns)
        path = f"/ws/proctor/assessments/{e['assessment'].id}/"

        communicator = WebsocketCommunicator(application, path)
        # Student user attempting to connect to proctor channel
        communicator.scope['user'] = e['student']
        communicator.scope['url_route'] = {'kwargs': {'assessment_id': str(e['assessment'].id)}}

        connected, close_code = await communicator.connect()
        # Should be closed with 4003
        assert connected is False

