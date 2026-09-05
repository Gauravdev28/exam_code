import io
import json
import zipfile
import pytest
from rest_framework.test import APIClient
from apps.accounts.models import User, Role
from apps.questions.models import Question, QuestionVersion, QuestionType, VersionStatus, TestCase, CodingLanguage
from apps.questions.services_platform_import import HackerRankQuestionImporter, LeetCodeManualImporter, PackageZipImporter, PlatformImportService

@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        email="admin_import@codeguard.internal",
        password="SecureAdminPassword123!",
        role=Role.ADMIN,
        is_active=True,
        is_staff=True
    )

@pytest.fixture
def admin_client(admin_user):
    client = APIClient()
    client.force_authenticate(user=admin_user)
    return client

@pytest.mark.django_db
class TestPlatformImportAndHealth:

    def test_platform_import_status_endpoint(self, admin_client):
        response = admin_client.get('/api/v1/admin/questions/platform-import/status/')
        assert response.status_code == 200
        data = response.data['data']
        assert 'hackerrank' in data
        assert 'leetcode' in data
        assert 'zip_package' in data
        assert data['zip_package']['supported'] is True
        assert data['leetcode']['auth_mode'] == 'MANUAL_IMPORT_REQUIRED'

    def test_hackerrank_unconfigured_rejects_empty_payload(self, admin_client):
        # When unconfigured and no data payload is passed
        response = admin_client.post('/api/v1/admin/questions/platform-import/preview/', {
            'source': 'HACKERRANK',
            'data': {'slug': 'solve-me-first'}
        }, format='json')
        # Expect error message that credentials are required
        assert response.status_code == 400
        assert 'hackerrank' in response.data['error']['details'] or 'hackerrank' in response.data['error']['message']

    def test_hackerrank_structured_import_creates_draft_with_unverified_tests(self, admin_client):
        sample_hr_data = {
            "name": "Solve Me First",
            "body": "Complete the function solveMeFirst to compute the sum of two integers.",
            "difficulty": "EASY",
            "languages": ["python3", "cpp20"],
            "examples": [
                {"input": "2\n3", "output": "5", "explanation": "2 + 3 = 5"}
            ],
            "test_cases": [
                {"name": "Test 1", "input": "2\n3", "output": "5", "points": 5, "is_hidden": False},
                {"name": "Test 2", "input": "10\n4", "output": "14", "points": 5, "is_hidden": True}
            ],
            "reference_solutions": {
                "PYTHON": "def solveMeFirst(a,b):\n\treturn a+b\n"
            },
            "reference_solution_language": "PYTHON"
        }

        # Preview
        prev_res = admin_client.post('/api/v1/admin/questions/platform-import/preview/', {
            'source': 'HACKERRANK',
            'data': sample_hr_data
        }, format='json')
        assert prev_res.status_code == 200
        preview = prev_res.data['data']
        assert preview['title'] == "Solve Me First"
        assert preview['test_case_count'] == 2
        assert preview['sample_test_count'] == 1
        assert preview['hidden_test_count'] == 1
        assert preview['expected_output_verification_status'] == "UNVERIFIED"
        assert preview['import_status'] == "DRAFT"

        # Confirm
        conf_res = admin_client.post('/api/v1/admin/questions/platform-import/confirm/', {
            'normalized_payload': preview['normalized_payload']
        }, format='json')
        assert conf_res.status_code == 201
        created = conf_res.data['data']
        assert created['status'] == 'DRAFT'
        assert created['title'] == "Solve Me First"

        # Verify in DB
        version = QuestionVersion.objects.get(id=created['id'])
        assert version.status == VersionStatus.DRAFT
        assert version.coding_config.reference_solution_verified is False
        for tc in version.coding_config.test_cases.all():
            assert tc.is_verified is False

    def test_leetcode_manual_structured_import_creates_draft(self, admin_client):
        lc_data = {
            "title": "Two Sum",
            "problem_statement": "Given an array of integers nums and an integer target, return indices of the two numbers.",
            "difficulty": "EASY",
            "constraints": "2 <= nums.length <= 10^4",
            "examples": [
                {"input": "[2,7,11,15]\n9", "output": "[0,1]", "explanation": "nums[0] + nums[1] == 9"}
            ],
            "test_cases": [
                {"name": "Sample 1", "input": "[2,7,11,15]\n9", "output": "[0,1]", "points": 5, "is_hidden": False},
                {"name": "Hidden 1", "input": "[3,2,4]\n6", "output": "[1,2]", "points": 5, "is_hidden": True}
            ]
        }

        prev_res = admin_client.post('/api/v1/admin/questions/platform-import/preview/', {
            'source': 'LEETCODE_MANUAL',
            'data': lc_data
        }, format='json')
        assert prev_res.status_code == 200
        preview = prev_res.data['data']
        assert preview['source'] == "LEETCODE_MANUAL"
        assert preview['title'] == "Two Sum"

        conf_res = admin_client.post('/api/v1/admin/questions/platform-import/confirm/', {
            'normalized_payload': preview['normalized_payload']
        }, format='json')
        assert conf_res.status_code == 201
        assert conf_res.data['data']['status'] == 'DRAFT'

    def test_leetcode_url_scraping_attempt_rejected(self, admin_client):
        response = admin_client.post('/api/v1/admin/questions/platform-import/preview/', {
            'source': 'LEETCODE',
            'data': {'url': 'https://leetcode.com/problems/two-sum/'}
        }, format='json')
        assert response.status_code == 400
        assert 'leetcode' in response.data['error']['details'] or 'leetcode' in response.data['error']['message']

    def test_zip_package_import(self, admin_client):
        # Create an in-memory zip file
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zf:
            question_data = {
                "title": "Package Matrix Search",
                "problem_statement": "Search for a target value in an m x n integer matrix.",
                "difficulty": "MEDIUM",
                "test_cases": [
                    {"name": "Sample", "input": "3 3\n1 2 3\n4 5 6\n7 8 9\n5", "output": "true", "points": 5, "is_hidden": False},
                    {"name": "Hidden", "input": "1 1\n10\n5", "output": "false", "points": 5, "is_hidden": True}
                ]
            }
            zf.writestr('question.json', json.dumps(question_data))
        zip_buffer.seek(0)

        prev_res = admin_client.post('/api/v1/admin/questions/platform-import/preview/', {
            'source': 'CODEGUARD_ZIP',
            'file': zip_buffer
        }, format='multipart')
        assert prev_res.status_code == 200
        preview = prev_res.data['data']
        assert preview['title'] == "Package Matrix Search"
        assert preview['test_case_count'] == 2

        conf_res = admin_client.post('/api/v1/admin/questions/platform-import/confirm/', {
            'normalized_payload': preview['normalized_payload']
        }, format='json')
        assert conf_res.status_code == 201
        assert conf_res.data['data']['status'] == 'DRAFT'

    def test_question_version_health_endpoint(self, admin_client):
        # Create draft coding question
        from apps.questions.services import QuestionService
        q, v = QuestionService.create_question(
            question_type=QuestionType.CODING,
            title="Health Check Test Problem",
            description="Testing health endpoint",
            points=10,
            coding_config_data={
                "problem_statement": "Solve this problem",
                "allowed_languages": [CodingLanguage.PYTHON],
                "starter_codes": {"PYTHON": "# starter\n"}
            },
            test_cases_data=[
                {"name": "T1", "input_data": "1", "expected_output": "1", "points": 5, "is_hidden": False, "is_verified": False},
                {"name": "T2", "input_data": "2", "expected_output": "2", "points": 5, "is_hidden": True, "is_verified": False},
            ],
            actor=admin_client.handler._force_user
        )

        res = admin_client.get(f'/api/v1/admin/questions/{q.id}/versions/{v.version_number}/health/')
        assert res.status_code == 200
        health = res.data['data']
        assert 'is_ready' in health
        assert 'status' in health
        assert health['is_ready'] is False  # Because test cases are unverified!
        assert len(health['checks']) == 12

    def test_supported_languages_registry_endpoint(self, admin_client):
        res = admin_client.get('/api/v1/admin/questions/languages/')
        assert res.status_code == 200
        langs = res.data['data']['languages']
        assert len(langs) >= 3
        keys = [l['key'] for l in langs]
        assert 'PYTHON' in keys
        assert 'CPP' in keys
        assert 'JAVA' in keys
