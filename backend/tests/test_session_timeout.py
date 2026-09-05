import pytest
from datetime import timedelta
from django.utils import timezone
from django.urls import reverse
from django.contrib.auth import get_user_model
from apps.accounts.models import Role, AuditLog
from apps.accounts.session_policy import SessionActivityPolicy
from apps.assessments.models import Assessment, AssessmentSnapshot, AssessmentStatus, TestAttempt, AttemptStatus

User = get_user_model()


@pytest.fixture
def admin_user(db):
    return User.objects.create_superuser(
        email="admin@codeguard.local",
        password="ValidAdminPass123!",
        role=Role.ADMIN
    )


@pytest.fixture
def student_user(db):
    return User.objects.create_user(
        email="student@codeguard.local",
        password="ValidStudentPass123!",
        role=Role.STUDENT
    )


@pytest.fixture
def assessment_with_attempt(db, admin_user, student_user):
    now = timezone.now()
    ass = Assessment.objects.create(
        title="Session Test Assessment",
        description="Assessment for testing session exemption",
        duration_minutes=60,
        start_datetime=now - timedelta(minutes=10),
        end_datetime=now + timedelta(hours=2),
        created_by=admin_user,
        status=AssessmentStatus.PUBLISHED,
        passing_percentage=50.0
    )
    snap = AssessmentSnapshot.objects.create(
        assessment=ass,
        version_number=1,
        snapshot_data={"title": ass.title}
    )
    attempt = TestAttempt.objects.create(
        student=student_user,
        assessment=ass,
        assessment_snapshot=snap,
        attempt_number=1,
        status=AttemptStatus.IN_PROGRESS,
        started_at=now - timedelta(minutes=5),
        expires_at=now + timedelta(minutes=55)
    )
    return ass, snap, attempt


@pytest.mark.django_db
class TestSessionTimeout:
    """Tests for 30-minute inactivity timeout, 2m warning, and student assessment exemption."""

    def test_session_status_unauthenticated(self, api_client):
        """Unauthenticated call to /auth/session/status/ returns 401."""
        url = reverse('accounts:session-status')
        resp = api_client.get(url)
        assert resp.status_code == 401

    def test_session_status_authenticated_admin(self, api_client, admin_user):
        """Authenticated admin receives accurate session status and timeout config."""
        api_client.force_authenticate(user=admin_user)
        url = reverse('accounts:session-status')
        resp = api_client.get(url)
        assert resp.status_code == 200
        data = resp.json()['data']

        assert data['idle_timeout_seconds'] == 1800
        assert data['warning_seconds'] == 120
        assert data['remaining_seconds'] <= 1800
        assert data['is_warning'] is False
        assert data['in_active_assessment'] is False
        assert data['idle_timeout_exempt'] is False

    def test_session_refresh_success(self, api_client, admin_user):
        """Active session can be explicitly refreshed before expiry."""
        api_client.force_authenticate(user=admin_user)
        url = reverse('accounts:session-refresh')
        resp = api_client.post(url)
        assert resp.status_code == 200
        data = resp.json()
        assert data['status'] == 'success'
        assert data['data']['remaining_seconds'] >= 1795

    def test_session_idle_timeout_enforcement(self, api_client, admin_user):
        """When an idle session exceeds 30 minutes, authenticated requests receive 401 SESSION_EXPIRED."""
        login_url = reverse('accounts:login')
        login_resp = api_client.post(login_url, {
            "email": "admin@codeguard.local",
            "password": "ValidAdminPass123!"
        }, format='json')
        assert login_resp.status_code == 200

        # Simulate 31 minutes of idle time by aging the last_activity in session
        session = api_client.session
        session[SessionActivityPolicy.LAST_ACTIVITY_KEY] = timezone.now().timestamp() - 1860
        session.save()

        # Next request must be rejected as expired
        status_url = reverse('accounts:session-status')
        resp = api_client.get(status_url)
        assert resp.status_code == 401
        err = resp.json()['error']
        assert err['code'] == 'SESSION_EXPIRED'

        # Audit log must record the expiration
        assert AuditLog.objects.filter(
            action="SESSION_IDLE_EXPIRED",
            actor=admin_user
        ).exists()

    def test_expired_session_cannot_be_refreshed(self, api_client, admin_user):
        """Calling /auth/session/refresh/ on an already-expired session returns 401."""
        api_client.post(reverse('accounts:login'), {
            "email": "admin@codeguard.local",
            "password": "ValidAdminPass123!"
        }, format='json')

        session = api_client.session
        session[SessionActivityPolicy.LAST_ACTIVITY_KEY] = timezone.now().timestamp() - 1900
        session.save()

        refresh_url = reverse('accounts:session-refresh')
        resp = api_client.post(refresh_url)
        assert resp.status_code == 401
        assert resp.json()['error']['code'] == 'SESSION_EXPIRED'

    def test_disabled_user_cannot_refresh_session(self, api_client, student_user):
        """A user disabled by an administrator cannot refresh their session."""
        api_client.force_authenticate(user=student_user)
        student_user.is_active = False
        student_user.save()

        refresh_url = reverse('accounts:session-refresh')
        resp = api_client.post(refresh_url)
        assert resp.status_code in (401, 403)

    def test_active_student_assessment_exemption(self, api_client, student_user, assessment_with_attempt):
        """
        Students with an IN_PROGRESS assessment attempt are strictly exempt from idle logout.
        Deep reading and thinking time must never cause session termination.
        """
        ass, snap, attempt = assessment_with_attempt
        assert attempt.status == AttemptStatus.IN_PROGRESS

        # Log in as student
        api_client.post(reverse('accounts:login'), {
            "email": "student@codeguard.local",
            "password": "ValidStudentPass123!"
        }, format='json')

        # Age the session to 45 minutes of inactivity (well beyond 30 min)
        session = api_client.session
        session[SessionActivityPolicy.LAST_ACTIVITY_KEY] = timezone.now().timestamp() - 2700
        session.save()

        # Check status: should remain authenticated and report exempt
        status_url = reverse('accounts:session-status')
        resp = api_client.get(status_url)
        assert resp.status_code == 200
        data = resp.json()['data']
        assert data['in_active_assessment'] is True
        assert data['idle_timeout_exempt'] is True
        assert data['is_expired'] is False

    def test_submitted_assessment_removes_exemption(self, api_client, student_user, assessment_with_attempt):
        """Once the student's assessment is submitted, the inactivity exemption ceases to apply."""
        ass, snap, attempt = assessment_with_attempt
        attempt.status = AttemptStatus.SUBMITTED
        attempt.submitted_at = timezone.now()
        attempt.save()

        # Log in as student
        api_client.post(reverse('accounts:login'), {
            "email": "student@codeguard.local",
            "password": "ValidStudentPass123!"
        }, format='json')

        # Age session past 30 min
        session = api_client.session
        session[SessionActivityPolicy.LAST_ACTIVITY_KEY] = timezone.now().timestamp() - 1900
        session.save()

        status_url = reverse('accounts:session-status')
        resp = api_client.get(status_url)
        assert resp.status_code == 401
        assert resp.json()['error']['code'] == 'SESSION_EXPIRED'

    def test_session_policy_does_not_mutate_attempt_timer(self, api_client, student_user, assessment_with_attempt):
        """
        Session activity inspection and refresh must NOT touch Phase 5 authoritative attempt timer.
        TestAttempt.expires_at and started_at must remain invariant.
        """
        ass, snap, attempt = assessment_with_attempt
        initial_expires_at = attempt.expires_at
        initial_started_at = attempt.started_at

        api_client.force_authenticate(user=student_user)
        api_client.post(reverse('accounts:session-refresh'))

        attempt.refresh_from_db()
        assert attempt.expires_at == initial_expires_at
        assert attempt.started_at == initial_started_at
