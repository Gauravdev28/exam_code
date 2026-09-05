import io
import pytest
from django.urls import reverse
from rest_framework import status
from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.accounts.models import User, Role
from apps.questions.models import Question, QuestionVersion, QuestionType, VersionStatus, Difficulty
from apps.questions.services_ingestion import SpreadsheetQuestionImporter, ImageQuestionExtractor

@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        email="gauravagldeveloper28@gmail.com",
        password="SecureDevAdminPass2026!",
        role=Role.ADMIN,
        is_staff=True,
    )

@pytest.fixture
def student_user(db):
    return User.objects.create_user(
        email="student.candidate@institution.edu",
        password="Password@123",
        role=Role.STUDENT,
    )

@pytest.fixture
def proctor_user(db):
    return User.objects.create_user(
        email="proctor.invigilator@institution.edu",
        password="Password@123",
        role=Role.PROCTOR,
    )

@pytest.mark.django_db
class TestAuthoritativeAdminIdentity:
    def test_authoritative_admin_id_is_euad_gaurav_099(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        res = api_client.get(reverse('accounts:current-user'))
        assert res.status_code == status.HTTP_200_OK
        data = res.data['data']
        assert data['admin_id'] == "EUAD-GAURAV-099"
        assert data['display_name'] == "Gaurav Agarwal"
        assert data['first_name'] == "Gaurav"
        assert data['role'] == "ADMIN"

    def test_admin_id_cannot_silently_revert(self, db):
        # Verify primary admin accounts always produce EUAD-GAURAV-099
        admin1 = User.objects.create_user(
            email="gauravagldeveloper28@gmail.com",
            password="Pass",
            role=Role.ADMIN
        )
        assert admin1.admin_id == "EUAD-GAURAV-099"

        admin2 = User.objects.create_user(
            email="admin@codeguard.local",
            password="Pass",
            role=Role.ADMIN
        )
        assert admin2.admin_id.startswith("CG-ADM-")
        assert admin2.admin_id != "EUAD-GAURAV-099"

    def test_login_returns_euad_gaurav_099(self, api_client, admin_user):
        url = reverse('accounts:login')
        res = api_client.post(url, {
            'email': admin_user.email,
            'password': 'SecureDevAdminPass2026!'
        })
        assert res.status_code == status.HTTP_200_OK
        user_data = res.data['data']['user']
        assert user_data['admin_id'] == "EUAD-GAURAV-099"
        assert user_data['display_name'] == "Gaurav Agarwal"

    def test_email_change_does_not_change_admin_id(self, db, admin_user):
        from django.core.exceptions import PermissionDenied
        assert admin_user.admin_id == "EUAD-GAURAV-099"
        # Admin identity is immutable: changing email must raise PermissionDenied
        admin_user.email = "gaurav.newemail@institution.edu"
        with pytest.raises(PermissionDenied, match="Administrator email address is strictly immutable"):
            admin_user.save()
        admin_user.refresh_from_db()
        assert admin_user.admin_id == "EUAD-GAURAV-099"
        assert admin_user.display_name == "Gaurav Agarwal"
        assert admin_user.email == "gauravagldeveloper28@gmail.com"


@pytest.mark.django_db
class TestStudentIdentityAndLifecycle:
    def test_student_enrollment_and_email_update_preserves_identity(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)

        # 1. Create Student
        create_res = api_client.post(reverse('accounts:admin-student-list'), {
            'roll_number': 'CS2026099',
            'email': 'student.original@institution.edu'
        })
        assert create_res.status_code == status.HTTP_201_CREATED
        data = create_res.data['data']
        student_id = data['id']
        expected_euid = f"CG-CS2026099"
        assert data['roll_number'] == 'CS2026099'
        assert data['euid'] == expected_euid

        # 2. Update Student Email
        detail_url = reverse('accounts:admin-student-detail', kwargs={'pk': student_id})
        update_res = api_client.patch(detail_url, {
            'email': 'student.updated@institution.edu'
        })
        assert update_res.status_code == status.HTTP_200_OK
        updated_data = update_res.data['data']
        assert updated_data['email'] == 'student.updated@institution.edu'
        # Crucial: Roll Number & EUID remain permanently immutable
        assert updated_data['roll_number'] == 'CS2026099'
        assert updated_data['euid'] == expected_euid

        # 3. Invalid Email validation
        invalid_res = api_client.patch(detail_url, {
            'email': 'not-an-email'
        })
        assert invalid_res.status_code == status.HTTP_400_BAD_REQUEST

    def test_question_version_draft_and_immutability(self, api_client, admin_user):
        from apps.questions.services import QuestionService
        q, v = QuestionService.create_question(
            question_type=QuestionType.MCQ,
            title="Immutable Version Question",
            description="Testing immutability",
            type_config={
                'options': [
                    {'id': 'A', 'text': 'Option A'},
                    {'id': 'B', 'text': 'Option B'},
                ],
                'correct_options': ['A']
            },
            actor=admin_user
        )
        assert v.status == VersionStatus.DRAFT

        # Publish version
        QuestionService.publish_version(v, actor=admin_user)
        v.refresh_from_db()
        assert v.status == VersionStatus.PUBLISHED

        # Attempt to edit published version must fail with 403 Forbidden (immutability rule)
        api_client.force_authenticate(user=admin_user)
        url = reverse('questions:admin-question-version-detail', kwargs={'pk': q.id, 'version_number': v.version_number})
        patch_res = api_client.patch(url, {'title': 'Mutated Title'})
        assert patch_res.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestSpreadsheetQuestionIngestion:
    def test_template_download_csv(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        url = reverse('questions:admin-question-import-template') + "?format=csv"
        res = api_client.get(url)
        assert res.status_code == status.HTTP_200_OK
        assert "text/csv" in res['Content-Type']
        assert b"question_title,question_type" in res.content

    def test_template_download_xlsx(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        url = reverse('questions:admin-question-import-template') + "?format=xlsx"
        res = api_client.get(url)
        assert res.status_code == status.HTTP_200_OK
        assert "application/vnd.openxmlformats" in res['Content-Type']
        assert len(res.content) > 1000

    def test_unauthenticated_cannot_access_ingestion(self, api_client):
        url = reverse('questions:admin-question-import-preview')
        res = api_client.post(url, {})
        assert res.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    def test_student_and_proctor_cannot_access_ingestion(self, api_client, student_user, proctor_user):
        url = reverse('questions:admin-question-import-preview')
        for user in [student_user, proctor_user]:
            api_client.force_authenticate(user=user)
            res = api_client.post(url, {})
            assert res.status_code == status.HTTP_403_FORBIDDEN

    def test_spreadsheet_preview_valid_csv(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        csv_data = SpreadsheetQuestionImporter.generate_template_csv()
        uploaded = SimpleUploadedFile("test_questions.csv", csv_data, content_type="text/csv")

        url = reverse('questions:admin-question-import-preview')
        res = api_client.post(url, {'file': uploaded}, format='multipart')
        assert res.status_code == status.HTTP_200_OK
        data = res.data['data']
        assert data['total_rows'] >= 2
        assert data['valid_count'] >= 2
        assert data['error_count'] == 0

    def test_spreadsheet_preview_row_level_errors(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        invalid_csv = (
            "question_title,question_type,difficulty,total_points,problem_statement,option_a,option_b,correct_option\n"
            ",MCQ,EASY,10,Problem without title,A,B,A\n"
            "Valid Title,INVALID_TYPE,EASY,10,Problem with invalid type,A,B,A\n"
            "Another Title,MCQ,SUPER_HARD,-5,Problem with bad points and diff,A,B,A\n"
            "Incomplete MCQ,MCQ,MEDIUM,10,Problem statement,OnlyOptionA,,A\n"
        ).encode('utf-8')
        uploaded = SimpleUploadedFile("broken.csv", invalid_csv, content_type="text/csv")

        url = reverse('questions:admin-question-import-preview')
        res = api_client.post(url, {'file': uploaded}, format='multipart')
        assert res.status_code == status.HTTP_200_OK
        data = res.data['data']
        assert data['total_rows'] == 4
        assert data['error_count'] == 4
        assert len(data['rows'][0]['errors']) > 0
        assert any("Missing required field: question_title" in e for e in data['rows'][0]['errors'])
        assert any("Invalid question_type" in e for e in data['rows'][1]['errors'])

    def test_duplicate_question_detection_warning(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)

        # Create pre-existing question
        q = Question.objects.create(question_type=QuestionType.MCQ, created_by=admin_user)
        QuestionVersion.objects.create(
            question=q,
            version_number=1,
            question_type=QuestionType.MCQ,
            title="Existing Question In Bank",
            description="Existing description",
            points=10,
            status=VersionStatus.PUBLISHED,
            created_by=admin_user
        )

        csv_content = (
            "question_title,question_type,difficulty,total_points,problem_statement,option_a,option_b,correct_option\n"
            "Existing Question In Bank,MCQ,EASY,10,Fresh import problem statement,A,B,A\n"
        ).encode('utf-8')
        uploaded = SimpleUploadedFile("duplicate.csv", csv_content, content_type="text/csv")

        url = reverse('questions:admin-question-import-preview')
        res = api_client.post(url, {'file': uploaded}, format='multipart')
        assert res.status_code == status.HTTP_200_OK
        data = res.data['data']
        row = data['rows'][0]
        assert row['is_duplicate'] is True
        assert row['status'] == "DUPLICATE_WARNING"
        assert row['duplicate_of'] == "Existing Question In Bank"

    def test_spreadsheet_confirm_creates_draft_never_published(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)

        payload = {
            "rows": [
                {
                    "data": {
                        "title": "Imported Algorithmic Draft",
                        "question_type": "CODING",
                        "difficulty": "HARD",
                        "points": 25,
                        "description": "Implement Dijkstra's shortest path algorithm.",
                        "instructions": "Return list of distances.",
                        "tags": ["Graphs", "Shortest Path"],
                        "type_config": {"_source": "EXCEL_IMPORT"},
                        "coding_config": {
                            "problem_statement": "Implement Dijkstra's shortest path algorithm.",
                            "allowed_languages": ["PYTHON", "CPP"],
                            "starter_code": "def dijkstra(graph, start):\n    pass",
                            "constraints": "V <= 10^4, E <= 10^5",
                            "time_limit_ms": 2000,
                            "memory_limit_mb": 256
                        },
                        "test_cases": [
                            {
                                "input_data": "4 4\n0 1 1\n1 2 2\n2 3 3\n0 3 10",
                                "expected_output": "0 1 3 6",
                                "points": 10,
                                "is_hidden": False
                            }
                        ]
                    }
                }
            ]
        }

        url = reverse('questions:admin-question-import-confirm')
        res = api_client.post(url, payload, format='json')
        assert res.status_code == status.HTTP_201_CREATED
        data = res.data['data']
        assert data['created_count'] == 1
        created = data['created_questions'][0]

        # Verify status is strictly DRAFT, NEVER PUBLISHED
        assert created['status'] == VersionStatus.DRAFT
        version = QuestionVersion.objects.get(id=created['version_id'])
        assert version.status == VersionStatus.DRAFT
        assert version.published_at is None
        assert version.coding_config.allowed_languages == ["PYTHON", "CPP"]
        assert version.coding_config.test_cases.count() == 1

@pytest.mark.django_db
class TestImageQuestionExtraction:
    def test_image_extraction_student_and_proctor_forbidden(self, api_client, student_user, proctor_user):
        url = reverse('questions:admin-question-extract-image')
        for user in [student_user, proctor_user]:
            api_client.force_authenticate(user=user)
            res = api_client.post(url, {})
            assert res.status_code == status.HTTP_403_FORBIDDEN

    def test_image_extraction_invalid_file_rejected(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        bad_file = SimpleUploadedFile("script.py", b"print('malicious')", content_type="text/x-python")
        url = reverse('questions:admin-question-extract-image')
        res = api_client.post(url, {'image': bad_file}, format='multipart')
        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert "Unsupported image extension" in str(res.data)

    def test_image_extraction_success(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)

        # Create a valid in-memory test image
        img = Image.new('RGB', (200, 100), color=(255, 255, 255))
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        uploaded = SimpleUploadedFile("screenshot.png", buffer.read(), content_type="image/png")

        url = reverse('questions:admin-question-extract-image')
        res = api_client.post(url, {'image': uploaded}, format='multipart')
        assert res.status_code == status.HTTP_200_OK
        data = res.data['data']

        assert 'image_id' in data
        assert 'image_url' in data
        assert 'confidence_notice' in data
        assert 'question_type' in data
        assert 'title' in data
        assert 'description' in data

    def test_temp_image_serving_and_path_traversal_prevention(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)

        # Attempt invalid identifier / non-hex uuid name
        bad_url = reverse('questions:admin-question-temp-image', kwargs={'image_id': 'malicious_path_file.png'})
        res = api_client.get(bad_url)
        assert res.status_code == status.HTTP_404_NOT_FOUND

        # Non-existent valid format
        bad_uuid_url = reverse('questions:admin-question-temp-image', kwargs={'image_id': '0123456789abcdef0123456789abcdef.png'})
        res2 = api_client.get(bad_uuid_url)
        assert res2.status_code == status.HTTP_404_NOT_FOUND
