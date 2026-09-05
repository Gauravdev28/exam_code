import re
import mimetypes
from pathlib import Path
from django.shortcuts import get_object_or_404
from django.http import HttpResponse, FileResponse, Http404
from django.db.models import Q
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination

from apps.accounts.permissions import IsAdmin, IsActiveUser
from apps.core.views import APIResponse
from .models import Question, QuestionVersion, Tag, QuestionStatus, VersionStatus
from .services import QuestionService
from .services_ingestion import SpreadsheetQuestionImporter, ImageQuestionExtractor, TEMP_IMAGE_DIR
from .serializers import (
    TagSerializer,
    QuestionListSerializer,
    QuestionDetailSerializer,
    QuestionVersionAdminDetailSerializer,
    QuestionVersionPublicDetailSerializer,
    QuestionVersionSummarySerializer,
    CreateQuestionSerializer,
    UpdateDraftVersionSerializer,
)

class StandardPagination(PageNumberPagination):
    page_size = 15
    page_size_query_param = 'page_size'
    max_page_size = 100

    def get_paginated_response(self, data):
        return APIResponse(
            data={
                'count': self.page.paginator.count,
                'next': self.get_next_link(),
                'previous': self.get_previous_link(),
                'results': data
            }
        )


class AdminQuestionListView(APIView):
    """
    List & Create Questions.
    GET /api/v1/admin/questions/
    POST /api/v1/admin/questions/
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsAdmin]
    pagination_class = StandardPagination

    def get(self, request):
        queryset = Question.objects.prefetch_related('versions__tags', 'created_by').all()

        # Filter by Question Status (ACTIVE vs ARCHIVED)
        q_status = request.query_params.get('status')
        if q_status:
            queryset = queryset.filter(status=q_status.upper())

        # Filter by Question Type
        q_type = request.query_params.get('question_type') or request.query_params.get('type')
        if q_type:
            queryset = queryset.filter(question_type=q_type.upper())

        # Filter by Difficulty (on latest version)
        difficulty = request.query_params.get('difficulty')
        if difficulty:
            queryset = queryset.filter(versions__difficulty=difficulty.upper()).distinct()

        # Filter by Version Status (e.g. DRAFT, PUBLISHED)
        v_status = request.query_params.get('version_status')
        if v_status:
            queryset = queryset.filter(versions__status=v_status.upper()).distinct()

        # Filter by Tag
        tag = request.query_params.get('tag')
        if tag:
            queryset = queryset.filter(versions__tags__name__iexact=tag.strip()).distinct()

        # Search across title, description, tags
        search = request.query_params.get('search')
        if search:
            search_clean = search.strip()
            queryset = queryset.filter(
                Q(versions__title__icontains=search_clean) |
                Q(versions__description__icontains=search_clean) |
                Q(versions__tags__name__icontains=search_clean)
            ).distinct()

        # Ordering
        ordering = request.query_params.get('ordering', '-created_at')
        if ordering in ['created_at', '-created_at', 'updated_at', '-updated_at', 'question_type', '-question_type']:
            queryset = queryset.order_by(ordering)
        else:
            queryset = queryset.order_by('-created_at')

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request)
        serializer = QuestionListSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request):
        serializer = CreateQuestionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        question, version = QuestionService.create_question(
            question_type=data['question_type'],
            title=data['title'],
            description=data['description'],
            instructions=data.get('instructions', ''),
            points=data.get('points', 10),
            negative_marking_enabled=data.get('negative_marking_enabled', False),
            negative_points=data.get('negative_points', 0),
            difficulty=data.get('difficulty', 'MEDIUM'),
            tags=data.get('tags', []),
            type_config=data.get('type_config', {}),
            coding_config_data=data.get('coding_config', {}),
            test_cases_data=data.get('test_cases', []),
            sql_config_data=data.get('sql_config', {}),
            actor=request.user,
            request=request
        )

        return APIResponse(
            data=QuestionVersionAdminDetailSerializer(version).data,
            message="Question created successfully in DRAFT status.",
            status_code=status.HTTP_201_CREATED
        )


class AdminQuestionDetailView(APIView):
    """
    Retrieve or Hard-delete logical Question.
    GET /api/v1/admin/questions/<id>/
    DELETE /api/v1/admin/questions/<id>/
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsAdmin]

    def get(self, request, pk):
        question = get_object_or_404(
            Question.objects.prefetch_related('versions__tags', 'versions__coding_config__test_cases', 'versions__sql_config'),
            id=pk
        )
        return APIResponse(
            data=QuestionDetailSerializer(question).data,
            message="Question details retrieved."
        )

    def delete(self, request, pk):
        question = get_object_or_404(Question, id=pk)
        QuestionService.delete_draft_question(question=question, actor=request.user, request=request)
        return APIResponse(
            message="Question deleted successfully."
        )


class AdminQuestionArchiveView(APIView):
    """
    Logically archive a Question.
    POST /api/v1/admin/questions/<id>/archive/
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsAdmin]

    def post(self, request, pk):
        question = get_object_or_404(Question, id=pk)
        archived_question = QuestionService.archive_question(question=question, actor=request.user, request=request)
        return APIResponse(
            data=QuestionDetailSerializer(archived_question).data,
            message="Question archived successfully."
        )


class AdminQuestionUsageView(APIView):
    """
    Dependency-aware question usage check.
    GET /api/v1/admin/questions/<uuid:pk>/usage/
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsAdmin]

    def get(self, request, pk):
        question = get_object_or_404(Question, id=pk)
        usage = QuestionService.get_question_usage(question)
        return APIResponse(
            data=usage,
            message="Question usage details retrieved successfully."
        )


class AdminQuestionRunSandboxView(APIView):
    """
    Safely executes admin test code against Judge0 external sandbox.
    POST /api/v1/admin/questions/run-sandbox/

    Strict fail-closed architecture:
    - Never uses exec(), eval(), compile(), or host subprocesses.
    - Uses external Judge0 CE adapter with bounded limits.
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsAdmin]

    def post(self, request):
        from apps.evaluator.services import Judge0Adapter, OutputComparisonService

        source_code = request.data.get('source_code', '')
        language = request.data.get('language', 'PYTHON')
        stdin_data = request.data.get('stdin', '')
        expected_output = request.data.get('expected_output', '')
        cpu_time_limit_ms = min(int(request.data.get('cpu_time_limit_ms', 2000)), 5000)
        memory_limit_mb = min(int(request.data.get('memory_limit_mb', 256)), 256)

        if not source_code.strip():
            return APIResponse(
                error={"message": "Source code cannot be blank."},
                status_code=status.HTTP_400_BAD_REQUEST
            )

        # Execute strictly in external isolated sandbox
        result = Judge0Adapter.execute_in_sandbox(
            source_code=source_code,
            language=language,
            stdin_data=stdin_data,
            expected_output=expected_output,
            cpu_time_limit_ms=cpu_time_limit_ms,
            memory_limit_mb=memory_limit_mb,
        )

        passed = None
        if expected_output.strip() and result.get('stdout') is not None:
            passed = OutputComparisonService.compare(
                result.get('stdout') or '',
                expected_output,
                policy={'mode': 'EXACT_STRIPPED', 'ignore_trailing_whitespace': True, 'ignore_trailing_empty_lines': True}
            )

        return APIResponse(
            data={
                "status_id": result.get("status_id"),
                "status_description": result.get("status_description"),
                "stdout": result.get("stdout"),
                "stderr": result.get("stderr"),
                "compile_output": result.get("compile_output"),
                "time": result.get("time"),
                "memory": result.get("memory"),
                "passed": passed,
                "expected_output": expected_output
            },
            message="Sandbox execution completed."
        )


class AdminQuestionVersionListView(APIView):
    """
    List all versions or create/reuse a draft Version (N+1) for a Question.
    GET /api/v1/admin/questions/<id>/versions/
    POST /api/v1/admin/questions/<id>/versions/
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsAdmin]

    def get(self, request, pk):
        question = get_object_or_404(Question, id=pk)
        versions = question.versions.order_by('version_number')
        return APIResponse(
            data=QuestionVersionSummarySerializer(versions, many=True).data,
            message="Version history retrieved."
        )

    def post(self, request, pk):
        question = get_object_or_404(Question, id=pk)
        new_version = QuestionService.get_or_create_draft_version(question=question, actor=request.user, request=request)
        return APIResponse(
            data=QuestionVersionAdminDetailSerializer(new_version).data,
            message=f"Version {new_version.version_number} draft ready.",
            status_code=status.HTTP_200_OK if new_version.status == VersionStatus.DRAFT else status.HTTP_201_CREATED
        )


class AdminQuestionVersionDetailView(APIView):
    """
    Retrieve or Update a specific QuestionVersion.
    GET /api/v1/admin/questions/<id>/versions/<version_number>/
    PATCH /api/v1/admin/questions/<id>/versions/<version_number>/
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsAdmin]

    def get(self, request, pk, version_number):
        version = get_object_or_404(
            QuestionVersion.objects.select_related('question', 'coding_config', 'sql_config').prefetch_related('tags', 'coding_config__test_cases'),
            question_id=pk,
            version_number=version_number
        )
        return APIResponse(
            data=QuestionVersionAdminDetailSerializer(version).data,
            message=f"Version {version_number} details retrieved."
        )

    def patch(self, request, pk, version_number):
        version = get_object_or_404(
            QuestionVersion.objects.select_related('question', 'coding_config', 'sql_config'),
            question_id=pk,
            version_number=version_number
        )
        serializer = UpdateDraftVersionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        updated_version = QuestionService.update_draft_version(
            version=version,
            title=data.get('title'),
            description=data.get('description'),
            instructions=data.get('instructions'),
            points=data.get('points'),
            negative_marking_enabled=data.get('negative_marking_enabled'),
            negative_points=data.get('negative_points'),
            difficulty=data.get('difficulty'),
            tags=data.get('tags'),
            type_config=data.get('type_config'),
            coding_config_data=data.get('coding_config'),
            test_cases_data=data.get('test_cases'),
            sql_config_data=data.get('sql_config'),
            actor=request.user,
            request=request
        )

        return APIResponse(
            data=QuestionVersionAdminDetailSerializer(updated_version).data,
            message=f"Version {version_number} updated successfully."
        )


class AdminQuestionVersionPublishView(APIView):
    """
    Validate and Publish a QuestionVersion.
    POST /api/v1/admin/questions/<id>/versions/<version_number>/publish/
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsAdmin]

    def post(self, request, pk, version_number):
        version = get_object_or_404(
            QuestionVersion.objects.select_related('question', 'coding_config', 'sql_config').prefetch_related('coding_config__test_cases'),
            question_id=pk,
            version_number=version_number
        )
        published_version = QuestionService.publish_version(version=version, actor=request.user, request=request)
        return APIResponse(
            data=QuestionVersionAdminDetailSerializer(published_version).data,
            message=f"Version {version_number} published successfully and locked permanently."
        )


class AdminQuestionVersionArchiveView(APIView):
    """
    Archive a published QuestionVersion.
    POST /api/v1/admin/questions/<id>/versions/<version_number>/archive/
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsAdmin]

    def post(self, request, pk, version_number):
        version = get_object_or_404(
            QuestionVersion.objects.select_related('question'),
            question_id=pk,
            version_number=version_number
        )
        archived_version = QuestionService.archive_version(version=version, actor=request.user, request=request)
        return APIResponse(
            data=QuestionVersionAdminDetailSerializer(archived_version).data,
            message=f"Version {version_number} archived."
        )


class AdminQuestionVersionPreviewView(APIView):
    """
    Student-perspective Preview of a QuestionVersion (hiding hidden test cases).
    GET /api/v1/admin/questions/<id>/versions/<version_number>/preview/
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsAdmin]

    def get(self, request, pk, version_number):
        version = get_object_or_404(
            QuestionVersion.objects.select_related('question', 'coding_config', 'sql_config').prefetch_related('tags', 'coding_config__test_cases'),
            question_id=pk,
            version_number=version_number
        )
        return APIResponse(
            data=QuestionVersionPublicDetailSerializer(version).data,
            message=f"Version {version_number} preview retrieved."
        )


class AdminTagListView(APIView):
    """
    List & Create Tags.
    GET /api/v1/admin/tags/
    POST /api/v1/admin/tags/
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsAdmin]

    def get(self, request):
        tags = Tag.objects.all()
        return APIResponse(data=TagSerializer(tags, many=True).data)

    def post(self, request):
        serializer = TagSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tag = serializer.save()
        return APIResponse(data=TagSerializer(tag).data, status_code=status.HTTP_201_CREATED)


class AdminQuestionTemplateDownloadView(APIView):
    """
    Download official Question Bank ingestion template (CSV or XLSX).
    GET /api/v1/admin/questions/import/template/?format=csv|xlsx
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsAdmin]

    def perform_content_negotiation(self, request, force=False):
        # Prevent DRF format-suffix negotiation from intercepting ?format=csv or ?format=xlsx
        return (None, None)

    def get(self, request):
        fmt = request.GET.get('format', 'csv').lower()
        if fmt in ('xlsx', 'excel'):
            content = SpreadsheetQuestionImporter.generate_template_xlsx()
            filename = "codeguard_questions_template.xlsx"
            content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        else:
            content = SpreadsheetQuestionImporter.generate_template_csv()
            filename = "codeguard_questions_template.csv"
            content_type = "text/csv; charset=utf-8"

        response = HttpResponse(content, content_type=content_type)
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response


class AdminQuestionSpreadsheetPreviewView(APIView):
    """
    Upload and parse Excel/CSV question file, producing row-level validation preview.
    POST /api/v1/admin/questions/import/preview/
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsAdmin]

    def post(self, request):
        upload = request.FILES.get('file')
        if not upload:
            return APIResponse(
                error={"message": "No file uploaded. Please upload a valid .csv or .xlsx spreadsheet."},
                status_code=status.HTTP_400_BAD_REQUEST
            )

        preview_data = SpreadsheetQuestionImporter.parse_and_validate_spreadsheet(
            upload,
            upload.name
        )
        return APIResponse(
            data=preview_data,
            message="Spreadsheet validated and preview generated successfully."
        )


class AdminQuestionSpreadsheetConfirmView(APIView):
    """
    Commit validated spreadsheet rows into DRAFT questions.
    POST /api/v1/admin/questions/import/confirm/
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsAdmin]

    def post(self, request):
        rows = request.data.get('rows')
        if not rows or not isinstance(rows, list):
            return APIResponse(
                error={"message": "Expected a list of row items to import."},
                status_code=status.HTTP_400_BAD_REQUEST
            )

        result = SpreadsheetQuestionImporter.commit_imported_rows(
            rows,
            actor=request.user,
            request=request
        )
        return APIResponse(
            data=result,
            message=f"Successfully imported {result['created_count']} questions as drafts.",
            status_code=status.HTTP_201_CREATED if result['created_count'] > 0 else status.HTTP_200_OK
        )


class AdminQuestionImageExtractView(APIView):
    """
    Upload an image/screenshot and extract structured question configuration via OCR.
    POST /api/v1/admin/questions/extract-image/
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsAdmin]

    def post(self, request):
        image_file = request.FILES.get('image')
        if not image_file:
            return APIResponse(
                error={"message": "No image file provided. Please upload a PNG, JPG, or WEBP screenshot."},
                status_code=status.HTTP_400_BAD_REQUEST
            )

        unique_name, dest_path = ImageQuestionExtractor.validate_and_store_image(
            image_file,
            image_file.name
        )

        lines = ImageQuestionExtractor.extract_text_from_image(dest_path)
        extracted_data = ImageQuestionExtractor.map_extracted_lines_to_question_structure(
            lines,
            unique_name
        )
        extracted_data['image_url'] = f"/api/v1/admin/questions/temp-image/{unique_name}/"

        return APIResponse(
            data=extracted_data,
            message="Question extracted successfully. Please review the extracted content before saving."
        )


class AdminQuestionTempImageView(APIView):
    """
    Authenticated retrieval of temporary uploaded question screenshot for the review interface.
    GET /api/v1/admin/questions/temp-image/<str:image_id>/
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsAdmin]

    def get(self, request, image_id: str):
        # Strict filename sanitization to prevent path traversal
        clean_id = Path(image_id).name
        if not re.match(r'^[a-f0-9]{32}\.(png|jpe?g|webp)$', clean_id, re.IGNORECASE):
            return APIResponse(
                error={"message": "Image not found."},
                status_code=status.HTTP_404_NOT_FOUND
            )

        file_path = TEMP_IMAGE_DIR / clean_id
        if not file_path.exists() or not file_path.is_file():
            return APIResponse(
                error={"message": "Image not found or has expired."},
                status_code=status.HTTP_404_NOT_FOUND
            )

        mime, _ = mimetypes.guess_type(str(file_path))
        return FileResponse(open(file_path, 'rb'), content_type=mime or 'application/octet-stream')
