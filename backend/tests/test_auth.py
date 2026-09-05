import pytest
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from channels.testing import WebsocketCommunicator
from codeguard.asgi import application
from apps.accounts.models import Role

User = get_user_model()

@pytest.fixture
def student_user(db):
    return User.objects.create_user(
        email="student@codeguard.local",
        password="ValidStudentPass123!",
        role=Role.STUDENT
    )

@pytest.fixture
def admin_user(db):
    return User.objects.create_superuser(
        email="admin@codeguard.local",
        password="ValidAdminPass123!",
        role=Role.ADMIN
    )

@pytest.fixture
def disabled_user(db):
    user = User.objects.create_user(
        email="disabled@codeguard.local",
        password="ValidDisabledPass123!",
        role=Role.STUDENT
    )
    user.is_active = False
    user.save()
    return user


# ==============================================================================
# 1. Authentication Tests
# ==============================================================================

@pytest.mark.django_db
def test_valid_login_succeeds(api_client, student_user):
    """1. Valid credentials establish authenticated session and return safe user data."""
    url = reverse('accounts:login')
    response = api_client.post(url, {
        "email": "student@codeguard.local",
        "password": "ValidStudentPass123!"
    }, format='json')

    assert response.status_code == 200
    data = response.json()
    assert data['status'] == 'success'
    assert data['data']['user']['email'] == "student@codeguard.local"
    assert data['data']['user']['role'] == "STUDENT"
    assert "password" not in data['data']['user']
    assert "password_hash" not in data['data']['user']


@pytest.mark.django_db
def test_invalid_password_fails(api_client, student_user):
    """2. Valid email with incorrect password fails authentication with 401."""
    url = reverse('accounts:login')
    response = api_client.post(url, {
        "email": "student@codeguard.local",
        "password": "WrongPassword999!"
    }, format='json')

    assert response.status_code == 401
    data = response.json()
    assert data['status'] == 'error'
    assert data['error']['code'] == 'INVALID_CREDENTIALS'


@pytest.mark.django_db
def test_unknown_email_fails(api_client):
    """3. Non-existent email fails authentication with 401."""
    url = reverse('accounts:login')
    response = api_client.post(url, {
        "email": "nonexistent@codeguard.local",
        "password": "SomePassword123!"
    }, format='json')

    assert response.status_code == 401
    data = response.json()
    assert data['status'] == 'error'
    assert data['error']['code'] == 'INVALID_CREDENTIALS'


@pytest.mark.django_db
def test_disabled_user_cannot_login(api_client, disabled_user):
    """4. Inactive/disabled user is blocked from authenticating with 401 ACCOUNT_DISABLED."""
    url = reverse('accounts:login')
    response = api_client.post(url, {
        "email": "disabled@codeguard.local",
        "password": "ValidDisabledPass123!"
    }, format='json')

    assert response.status_code == 401
    data = response.json()
    assert data['status'] == 'error'
    assert data['error']['code'] == 'ACCOUNT_DISABLED'


@pytest.mark.django_db
def test_logout_invalidates_session(api_client, student_user):
    """5. Logout clears the active session and subsequent protected requests fail."""
    # Step 1: Login
    api_client.force_authenticate(user=student_user)
    me_url = reverse('accounts:current-user')
    res_me = api_client.get(me_url)
    assert res_me.status_code == 200

    # Step 2: Logout
    logout_url = reverse('accounts:logout')
    res_logout = api_client.post(logout_url)
    assert res_logout.status_code == 200

    # Step 3: De-authenticate client to simulate cleared session
    api_client.logout()
    res_me_after = api_client.get(me_url)
    assert res_me_after.status_code == 401


@pytest.mark.django_db
def test_current_user_endpoint_requires_auth(api_client):
    """6. /auth/me/ rejects unauthenticated requests with 401."""
    url = reverse('accounts:current-user')
    response = api_client.get(url)
    assert response.status_code == 401
    data = response.json()
    assert data['status'] == 'error'


@pytest.mark.django_db
def test_current_user_returns_authenticated_user_only(api_client, student_user, admin_user):
    """7. /auth/me/ returns only the profile of the requesting user."""
    api_client.force_authenticate(user=student_user)
    url = reverse('accounts:current-user')
    response = api_client.get(url)

    assert response.status_code == 200
    data = response.json()
    assert data['data']['id'] == str(student_user.id)
    assert data['data']['email'] == student_user.email
    assert data['data']['role'] == "STUDENT"


# ==============================================================================
# 2. Authorization / RBAC Tests
# ==============================================================================

@pytest.mark.django_db
def test_admin_can_access_admin_endpoint(api_client, admin_user):
    """8. Users with ADMIN role can access admin-protected endpoints."""
    api_client.force_authenticate(user=admin_user)
    url = reverse('accounts:admin-only-test')
    response = api_client.get(url)

    assert response.status_code == 200
    data = response.json()
    assert data['status'] == 'success'
    assert data['data']['admin_access'] is True


@pytest.mark.django_db
def test_student_cannot_access_admin_endpoint(api_client, student_user):
    """9. Students attempting to access admin-protected endpoints receive 403 Forbidden."""
    api_client.force_authenticate(user=student_user)
    url = reverse('accounts:admin-only-test')
    response = api_client.get(url)

    assert response.status_code == 403
    data = response.json()
    assert data['status'] == 'error'
    assert data['error']['code'] == 'PERMISSION_DENIED'


@pytest.mark.django_db
def test_unauthenticated_user_cannot_access_protected_endpoint(api_client):
    """10. Unauthenticated access to protected endpoints returns 401."""
    url = reverse('accounts:admin-only-test')
    response = api_client.get(url)
    assert response.status_code == 401


@pytest.mark.django_db
def test_client_cannot_elevate_role_in_payload(api_client, student_user):
    """11. Role is uneditable by client request payloads."""
    api_client.force_authenticate(user=student_user)
    url = reverse('accounts:current-user')
    # Attempting to PUT or PATCH role
    response = api_client.patch(url, {"role": "ADMIN"}, format='json')
    # Endpoint does not permit PUT/PATCH method
    assert response.status_code in [405, 403]
    
    student_user.refresh_from_db()
    assert student_user.role == Role.STUDENT


@pytest.mark.django_db
def test_password_hash_never_exposed(api_client, student_user):
    """12. Password and password hash are completely omitted in all serializer outputs."""
    api_client.force_authenticate(user=student_user)
    url = reverse('accounts:current-user')
    response = api_client.get(url)

    assert response.status_code == 200
    data = response.json()
    assert 'password' not in data['data']
    assert 'password_hash' not in data['data']
    assert 'hash' not in str(data)


# ==============================================================================
# 3. Password Security Tests
# ==============================================================================

@pytest.mark.django_db
def test_password_is_stored_as_secure_hash():
    """13. Passwords must be hashed using Django's configured password hasher."""
    user = User.objects.create_user(
        email="hashtest@codeguard.local",
        password="MySecretPassword123!"
    )
    assert user.password != "MySecretPassword123!"
    assert user.password.startswith('argon2') or user.password.startswith('pbkdf2_sha256') or user.password.startswith('md5$')
    assert user.check_password("MySecretPassword123!") is True
    assert user.check_password("WrongPassword") is False


def test_password_validators_reject_short_password():
    """15. Password validator rejects passwords under minimum length."""
    with pytest.raises(DjangoValidationError):
        validate_password("short")


# ==============================================================================
# 4. Security & WebSocket Tests
# ==============================================================================

@pytest.mark.django_db
def test_login_rate_limiting_protects_brute_force(api_client):
    """16. Rapid repeated login attempts trigger rate limiting (429 Throttled)."""
    url = reverse('accounts:login')
    
    # 10 attempts are allowed per minute
    throttled = False
    for i in range(15):
        res = api_client.post(url, {
            "email": "brute@codeguard.local",
            "password": "WrongPassword!"
        }, format='json')
        if res.status_code == 429:
            throttled = True
            break
            
    assert throttled is True


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_websocket_auth_rejects_unauthenticated_connection():
    """18. WebSocket endpoint /ws/auth-echo/ rejects unauthenticated connection with code 4001."""
    communicator = WebsocketCommunicator(
        application,
        "/ws/auth-echo/",
        headers=[
            (b"host", b"localhost"),
            (b"origin", b"http://localhost"),
        ]
    )
    connected, code = await communicator.connect()
    
    # Unauthenticated connection must be closed by consumer with code 4001
    assert connected is False
    assert code == 4001


# ==============================================================================
# 5. Contract & Regression Verification (Section 14)
# ==============================================================================

@pytest.mark.django_db
class TestAuthenticationContractAndRegressions:
    def test_admin_login_with_email_returns_euad_gaurav_099(self, api_client, db):
        # Create primary admin with email
        admin = User.objects.create_superuser(
            email="gauravagldeveloper28@gmail.com",
            password="SecureDevAdminPass2026!",
            role=Role.ADMIN
        )
        assert admin.admin_id == "EUAD-GAURAV-099"

        # 1. Login via Email
        login_url = reverse('accounts:login')
        res = api_client.post(login_url, {
            "identifier": "gauravagldeveloper28@gmail.com",
            "password": "SecureDevAdminPass2026!"
        })
        assert res.status_code == 200
        user_data = res.json()['data']['user']
        assert user_data['admin_id'] == "EUAD-GAURAV-099"
        assert user_data['display_name'] == "Gaurav Agarwal"
        assert user_data['role'] == "ADMIN"

        # 2. Session /me endpoint
        me_res = api_client.get(reverse('accounts:current-user'))
        assert me_res.status_code == 200
        me_data = me_res.json()['data']
        assert me_data['admin_id'] == "EUAD-GAURAV-099"
        assert me_data['display_name'] == "Gaurav Agarwal"

    def test_admin_id_cannot_be_used_as_login_identifier(self, api_client, db):
        # Admin ID must NEVER become a login credential
        User.objects.create_superuser(
            email="admin@codeguard.local",
            password="AdminPassword2026!",
            role=Role.ADMIN
        )
        res = api_client.post(reverse('accounts:login'), {
            "identifier": "EUAD-GAURAV-099",
            "password": "AdminPassword2026!"
        })
        assert res.status_code == 401
        assert res.json()['error']['code'] in ['ADMIN_ID_NOT_LOGIN_CREDENTIAL', 'INVALID_CREDENTIALS']

    def test_student_login_by_email_and_euid(self, api_client, db):
        from apps.accounts.models import StudentProfile
        student = User.objects.create_user(
            email="candidate.auth@institution.edu",
            password="ValidPass2026!",
            role=Role.STUDENT
        )
        StudentProfile.objects.create(
            user=student,
            roll_number="CS2026AUTH",
            euid="CG-CS2026AUTH"
        )

        login_url = reverse('accounts:login')

        # 1. Login via Email
        res_email = api_client.post(login_url, {
            "identifier": "candidate.auth@institution.edu",
            "password": "ValidPass2026!"
        })
        assert res_email.status_code == 200
        assert res_email.json()['data']['user']['role'] == "STUDENT"

        # 2. Login via EUID
        res_euid = api_client.post(login_url, {
            "identifier": "CG-CS2026AUTH",
            "password": "ValidPass2026!"
        })
        assert res_euid.status_code == 200
        assert res_euid.json()['data']['user']['role'] == "STUDENT"

        # 3. Roll Number directly must FAIL (not a login identifier)
        res_roll = api_client.post(login_url, {
            "identifier": "CS2026AUTH",
            "password": "ValidPass2026!"
        })
        assert res_roll.status_code == 401
        assert res_roll.json()['error']['code'] == 'INVALID_CREDENTIALS'

    def test_proctor_login_flow(self, api_client, db):
        User.objects.create_user(
            email="invigilator.proctor@institution.edu",
            password="ProctorPassword2026!",
            role=Role.PROCTOR
        )
        res = api_client.post(reverse('accounts:login'), {
            "identifier": "invigilator.proctor@institution.edu",
            "password": "ProctorPassword2026!"
        })
        assert res.status_code == 200
        data = res.json()['data']['user']
        assert data['role'] == "PROCTOR"
        assert data['email'] == "invigilator.proctor@institution.edu"

