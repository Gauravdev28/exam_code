import io
import pytest
from datetime import timedelta
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient
from rest_framework import status

from apps.accounts.models import User, Role, StudentProfile
from apps.questions.services import QuestionService
from apps.assessments.models import (
    Assessment,
    AssessmentStatus,
    AssessmentQuestion,
    AssessmentAssignment,
    TestAttempt,
    AttemptStatus,
)
from apps.assessments.services import AssessmentService, AttemptService
from apps.proctoring.models import (
    ProctoringSession,
    ProctoringSessionStatus,
    ProctoringEvent,
    ProctoringEvidence,
    ProctoringWarning,
    RiskBand,
    ReviewStatus,
)
from apps.proctoring.services import (
    ProctoringSessionService,
    ProctoringEvidenceService,
)


@pytest.mark.django_db
class TestProctoringIntegration:
    @pytest.fixture(autouse=True)
    def setup_data(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            email="admin_proct_int@example.com",
            password="AdminPassword123!",
            role=Role.ADMIN
        )
        self.student = User.objects.create_user(
            email="student_proct_int@example.com",
            password="StudentPassword123!",
            role=Role.STUDENT
        )
        self.profile = StudentProfile.objects.create(
            user=self.student,
            roll_number="CS2026-INT",
            euid="EUID-PROCT-INT"
        )
        self.other_student = User.objects.create_user(
            email="other_student_proct@example.com",
            password="StudentPassword123!",
            role=Role.STUDENT
        )

        # Create and Publish Question & Assessment
        self.question, self.q_v1 = QuestionService.create_question(
            question_type='MCQ',
            title='Integration Sample Question',
            description='Question for proctoring integration test',
            points=100,
            type_config={'options': [{'id': 'A', 'text': 'Option A'}, {'id': 'B', 'text': 'Option B'}], 'correct_options': ['A']},
            actor=self.admin
        )
        self.q_v1 = QuestionService.publish_version(self.q_v1, actor=self.admin)

        now = timezone.now()
        self.assessment = Assessment.objects.create(
            title="Proctoring Integration Assessment",
            description="Testing full integration suite",
            created_by=self.admin,
            status=AssessmentStatus.DRAFT,
            start_datetime=now - timedelta(hours=1),
            end_datetime=now + timedelta(hours=2),
            duration_minutes=60,
            total_points=100
        )
        AssessmentQuestion.objects.create(
            assessment=self.assessment,
            question_version=self.q_v1,
            order=1,
            points=100
        )
        AssessmentAssignment.objects.create(
            assessment=self.assessment,
            student=self.student,
            assigned_by=self.admin
        )
        self.published_assessment = AssessmentService.publish_assessment(self.assessment, actor=self.admin)

        self.attempt, _ = AttemptService.start_attempt(
            student=self.student,
            assessment_id=str(self.published_assessment.id),
            actor=self.student
        )

    def test_student_can_start_proctoring_session(self):
        self.client.force_authenticate(user=self.student)
        url = f"/api/v1/student/attempts/{self.attempt.id}/proctoring/start/"
        response = self.client.post(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data['status'] == 'ACTIVE'
        assert 'session_id' in response.data
        assert response.data['frame_sampling_interval_seconds'] == 2.0

    def test_student_heartbeat_fallback(self):
        self.client.force_authenticate(user=self.student)
        url = f"/api/v1/student/attempts/{self.attempt.id}/proctoring/heartbeat/"
        response = self.client.post(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data['status'] == 'HEALTHY'
        assert response.data['session_status'] == 'ACTIVE'

    def test_student_ingest_browser_telemetry_and_receive_warning(self):
        self.client.force_authenticate(user=self.student)
        url = f"/api/v1/student/attempts/{self.attempt.id}/proctoring/events/"
        payload = {
            "event_type": "FULLSCREEN_EXIT",
            "client_detected_at": timezone.now().isoformat(),
            "metadata": {"viewport_width": 1920, "viewport_height": 1080}
        }
        response = self.client.post(url, data=payload, format='json')
        assert response.status_code == status.HTTP_202_ACCEPTED
        assert response.data['status'] == 'RECORDED'
        assert response.data['source'] == 'BROWSER'
        assert response.data['warning_issued'] is True
        assert 'Full-screen mode was exited' in response.data['warning']['message']

        # Verify warning created in DB
        warning_id = response.data['warning']['id']
        warning = ProctoringWarning.objects.filter(id=warning_id).first()
        assert warning is not None
        assert warning.acknowledged_at is None

        # Acknowledge Warning
        ack_url = f"/api/v1/student/attempts/{self.attempt.id}/proctoring/warnings/{warning_id}/ack/"
        ack_res = self.client.post(ack_url)
        assert ack_res.status_code == status.HTTP_200_OK
        assert ack_res.data['status'] == 'ACKNOWLEDGED'
        warning.refresh_from_db()
        assert warning.acknowledged_at is not None

    def test_student_frame_upload_queues_inference(self):
        self.client.force_authenticate(user=self.student)
        url = f"/api/v1/student/attempts/{self.attempt.id}/proctoring/frames/"

        # Construct synthetic JPEG file
        fake_jpeg = b'\xff\xd8\xff\xe0' + b'A' * 1024 + b'\xff\xd9'
        frame_file = SimpleUploadedFile("frame.jpg", fake_jpeg, content_type="image/jpeg")

        response = self.client.post(url, data={'frame': frame_file, 'sequence_number': 1}, format='multipart')
        assert response.status_code == status.HTTP_202_ACCEPTED
        assert response.data['status'] == 'QUEUED_FOR_INFERENCE'
        assert response.data['sequence_number'] == 1

    def test_student_audio_upload_queues_vad(self):
        self.client.force_authenticate(user=self.student)
        url = f"/api/v1/student/attempts/{self.attempt.id}/proctoring/audio/"

        fake_audio = b'\x1a\x45\xdf\xa3' + b'AUDIO_CLIP_DATA' * 50
        audio_file = SimpleUploadedFile("audio.webm", fake_audio, content_type="audio/webm")

        response = self.client.post(url, data={'audio': audio_file, 'rms_db': 68.5}, format='multipart')
        assert response.status_code == status.HTTP_202_ACCEPTED
        assert response.data['status'] == 'QUEUED_FOR_VAD_ANALYSIS'

    def test_admin_can_list_proctoring_sessions_and_filter(self):
        session = ProctoringSessionService.get_or_create_session(self.attempt)
        session.risk_score = 75.0
        session.risk_band = RiskBand.HIGH
        session.save()

        self.client.force_authenticate(user=self.admin)
        url = f"/api/v1/admin/assessments/{self.published_assessment.id}/proctoring/sessions/"
        response = self.client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data['count'] >= 1
        result = response.data['results'][0]
        assert result['risk_band'] == 'HIGH'
        assert result['student']['email'] == self.student.email
        assert result['student']['euid'] == 'EUID-PROCT-INT'

        # Filter by risk_band
        filter_res = self.client.get(f"{url}?risk_band=HIGH")
        assert filter_res.status_code == status.HTTP_200_OK
        assert filter_res.data['count'] == 1

        filter_none = self.client.get(f"{url}?risk_band=NORMAL")
        assert filter_none.status_code == status.HTTP_200_OK
        assert filter_none.data['count'] == 0

    def test_admin_can_view_session_detail_and_timeline(self):
        session = ProctoringSessionService.get_or_create_session(self.attempt)
        ProctoringEvent.objects.create(
            session=session,
            event_type='PHONE_DETECTED',
            source='AI',
            severity='CRITICAL',
            confidence=0.88,
            started_at=timezone.now(),
            risk_delta=40.0,
            metadata={'bbox': [10, 20, 100, 200]}
        )

        self.client.force_authenticate(user=self.admin)
        url = f"/api/v1/admin/proctoring/sessions/{session.id}/"
        response = self.client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data['session_id'] == str(session.id)
        assert len(response.data['events']) == 1
        assert response.data['events'][0]['event_type'] == 'PHONE_DETECTED'
        assert response.data['events'][0]['metadata']['bbox'] == [10, 20, 100, 200]

    def test_admin_can_patch_review_decision(self):
        session = ProctoringSessionService.get_or_create_session(self.attempt)
        self.client.force_authenticate(user=self.admin)
        url = f"/api/v1/admin/proctoring/sessions/{session.id}/review/"
        payload = {
            "decision": "REVIEWED_CLEAN",
            "notes": "Visual check confirmed no mobile device present."
        }
        response = self.client.patch(url, data=payload, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['decision'] == 'REVIEWED_CLEAN'
        assert response.data['reviewed_by'] == self.admin.email

        session.refresh_from_db()
        assert session.review_status == ReviewStatus.REVIEWED

    def test_admin_can_stream_evidence(self):
        session = ProctoringSessionService.get_or_create_session(self.attempt)
        raw_image = b'\xff\xd8\xff\xe0' + b'IMAGE_BYTES' * 10 + b'\xff\xd9'
        evidence = ProctoringEvidenceService.save_evidence(session, raw_image, 'IMAGE_JPEG')

        self.client.force_authenticate(user=self.admin)
        url = f"/api/v1/admin/proctoring/evidence/{evidence.id}/"
        response = self.client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response['Content-Type'] == 'image/jpeg'
        assert response.getvalue() == raw_image
