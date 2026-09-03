from django.shortcuts import get_object_or_404
from django.db.models import Q
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination

from apps.accounts.permissions import IsAdmin, IsActiveUser
from apps.core.views import APIResponse
from .models import Question, QuestionVersion, Tag, QuestionStatus, VersionStatus
from .services import QuestionService
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


class AdminQuestionVersionListView(APIView):
    """
    List all versions or create a new Version (N+1) for a Question.
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
        new_version = QuestionService.create_new_version(question=question, actor=request.user, request=request)
        return APIResponse(
            data=QuestionVersionAdminDetailSerializer(new_version).data,
            message=f"Version {new_version.version_number} draft created successfully.",
            status_code=status.HTTP_201_CREATED
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
