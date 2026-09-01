# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Python imports
import json
import uuid
from datetime import datetime
from django.core.serializers.json import DjangoJSONEncoder

# Django imports
from django.db import connection, transaction
from django.db.models import (
    Exists,
    OuterRef,
    Q,
    Value,
    UUIDField,
    Count,
    Case,
    When,
    IntegerField,
)
from django.http import StreamingHttpResponse
from django.contrib.postgres.aggregates import ArrayAgg
from django.contrib.postgres.fields import ArrayField
from django.db.models.functions import Coalesce

# Third party imports
from rest_framework import status
from rest_framework.response import Response

# Module imports
from plane.app.permissions import allow_permission, ROLE
from plane.app.serializers import (
    PageSerializer,
    PageDetailSerializer,
    PageBinaryUpdateSerializer,
)
from plane.db.models import (
    Page,
    PageLog,
    UserFavorite,
    ProjectMember,
    ProjectPage,
    Project,
)
from plane.utils.error_codes import ERROR_CODES
from plane.utils.host import base_host

# Local imports
from ..base import BaseAPIView, BaseViewSet
from plane.bgtasks.page_transaction_task import page_transaction
from plane.bgtasks.page_version_task import track_page_version
from plane.bgtasks.recent_visited_task import recent_visited_task
from plane.bgtasks.copy_s3_object import copy_s3_objects_of_description_and_assets
from plane.app.permissions import ProjectPagePermission
from plane.app.services import ProjectPageHierarchyError, ProjectPageHierarchyService
from plane.app.services.page_hierarchy import HierarchyContext, is_project_page_hierarchy_enabled


def unarchive_archive_page_and_descendants(page_id, archived_at):
    # Your SQL query
    sql = """
    WITH RECURSIVE descendants AS (
        SELECT id FROM pages WHERE id = %s
        UNION ALL
        SELECT pages.id FROM pages, descendants WHERE pages.parent_id = descendants.id
    )
    UPDATE pages SET archived_at = %s WHERE id IN (SELECT id FROM descendants);
    """

    # Execute the SQL query
    with connection.cursor() as cursor:
        cursor.execute(sql, [page_id, archived_at])


class PageViewSet(BaseViewSet):
    serializer_class = PageSerializer
    model = Page
    permission_classes = [ProjectPagePermission]
    search_fields = ["name"]

    def _hierarchy_service(self, request, slug, project_id):
        project = Project.objects.only("id", "workspace_id").get(pk=project_id, workspace__slug=slug)
        project_role = (
            ProjectMember.objects.filter(project=project, member=request.user, is_active=True)
            .values_list("role", flat=True)
            .first()
        )
        return ProjectPageHierarchyService(
            HierarchyContext(
                project_id=str(project.id),
                workspace_id=str(project.workspace_id),
                user_id=str(request.user.id),
                project_role=project_role,
            )
        )

    @staticmethod
    def _merge_hierarchy(page_data, node):
        page_data.update(
            {
                "parent": node["parent_id"],
                "project_parent_id": node["parent_id"],
                "sort_order": node["sort_order"],
                "archived_at": node["archived_at"],
                "project_archived_at": node["archived_at"],
                "depth": node["depth"],
                "path": node["path"],
                "has_children": node["has_children"],
                "child_count": node["child_count"],
                "hierarchy_permissions": node["permissions"],
            }
        )
        return page_data

    def get_queryset(self):
        subquery = UserFavorite.objects.filter(
            user=self.request.user,
            entity_type="page",
            entity_identifier=OuterRef("pk"),
            workspace__slug=self.kwargs.get("slug"),
        )
        return self.filter_queryset(
            super()
            .get_queryset()
            .filter(workspace__slug=self.kwargs.get("slug"))
            .filter(
                projects__project_projectmember__member=self.request.user,
                projects__project_projectmember__is_active=True,
                projects__archived_at__isnull=True,
            )
            .filter(Q(owned_by=self.request.user) | Q(access=0))
            .prefetch_related("projects")
            .select_related("workspace")
            .select_related("owned_by")
            .annotate(is_favorite=Exists(subquery))
            .order_by(self.request.GET.get("order_by", "-created_at"))
            .prefetch_related("labels")
            .order_by("-is_favorite", "-created_at")
            .annotate(
                project=Exists(
                    ProjectPage.objects.filter(
                        page_id=OuterRef("id"),
                        project_id=self.kwargs.get("project_id"),
                        deleted_at__isnull=True,
                    )
                )
            )
            .annotate(
                label_ids=Coalesce(
                    ArrayAgg(
                        "page_labels__label_id",
                        distinct=True,
                        filter=~Q(page_labels__label_id__isnull=True),
                    ),
                    Value([], output_field=ArrayField(UUIDField())),
                ),
                project_ids=Coalesce(
                    ArrayAgg("projects__id", distinct=True, filter=~Q(projects__id=True)),
                    Value([], output_field=ArrayField(UUIDField())),
                ),
            )
            .filter(project=True)
            .distinct()
        )

    @transaction.atomic
    def create(self, request, slug, project_id):
        data = request.data.copy()
        parent_id = data.pop("parent_id", None)
        if isinstance(parent_id, list):
            parent_id = parent_id[0] if parent_id else None
        operation_id = data.pop("operation_id", None)
        if isinstance(operation_id, list):
            operation_id = operation_id[0] if operation_id else None
        operation_uuid = uuid.UUID(str(operation_id)) if operation_id else uuid.uuid4()
        service = self._hierarchy_service(request, slug, project_id)
        hierarchy_enabled = is_project_page_hierarchy_enabled()
        if parent_id and not hierarchy_enabled:
            return Response({"error": "Page not found", "code": "page_not_found"}, status=status.HTTP_404_NOT_FOUND)
        if parent_id:
            try:
                parent_link = ProjectPage.objects.select_related("page").get(
                    page_id=parent_id,
                    project_id=project_id,
                    workspace__slug=slug,
                    deleted_at__isnull=True,
                    archived_at__isnull=True,
                )
            except ProjectPage.DoesNotExist:
                service.record_failure(
                    operation_id=operation_uuid,
                    operation="create",
                    error=ProjectPageHierarchyError("page_not_found", "Page not found", status_code=404),
                )
                return Response({"error": "Page not found", "code": "page_not_found"}, status=404)
            if parent_link.page.access == Page.PRIVATE_ACCESS:
                if parent_link.page.owned_by_id != request.user.id:
                    service.record_failure(
                        operation_id=operation_uuid,
                        operation="create",
                        error=ProjectPageHierarchyError("page_not_found", "Page not found", status_code=404),
                    )
                    return Response({"error": "Page not found", "code": "page_not_found"}, status=404)
                data["access"] = Page.PRIVATE_ACCESS
        # Project placement is authoritative; never write a project parent to the legacy global field.
        data.pop("parent", None)
        serializer = PageSerializer(
            data=data,
            context={
                "project_id": project_id,
                "owned_by_id": request.user.id,
                "description_json": request.data.get("description_json", {}),
                "description_binary": request.data.get("description_binary", None),
                "description_html": request.data.get("description_html", "<p></p>"),
            },
        )

        if serializer.is_valid():
            try:
                with transaction.atomic():
                    serializer.save()
                    placement = (
                        service.move(
                            str(serializer.data["id"]),
                            parent_page_id=str(parent_id) if parent_id else None,
                            position="last",
                            operation_id=operation_uuid,
                            audit_operation="create",
                        )
                        if hierarchy_enabled
                        else None
                    )
            except ProjectPageHierarchyError as error:
                service.record_failure(
                    operation_id=operation_uuid,
                    operation="create",
                    error=error,
                )
                return Response(error.as_dict(), status=error.status_code)
            # capture the page transaction
            page_transaction.delay(
                new_description_html=request.data.get("description_html", "<p></p>"),
                old_description_html=None,
                page_id=serializer.data["id"],
                actor_id=str(request.user.id),
                project_id=str(project_id),
                operation_kind="direct_create",
                origin=base_host(request=request, is_app=True),
            )
            page = self.get_queryset().get(pk=serializer.data["id"])
            serializer = PageDetailSerializer(page)
            node = next(
                item for item in service.all_pages(include_archived=True) if item["id"] == str(page.id)
            )
            response_data = self._merge_hierarchy(dict(serializer.data), node)
            response_data["hierarchy_revision"] = (
                placement["revision"]
                if placement is not None
                else service.path(str(page.id), include_archived=True)["revision"]
            )
            return Response(response_data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def partial_update(self, request, slug, project_id, page_id):
        try:
            page = Page.objects.get(
                pk=page_id,
                workspace__slug=slug,
                projects__id=project_id,
                project_pages__deleted_at__isnull=True,
            )

            if page.is_locked:
                return Response({"error": "Page is locked"}, status=status.HTTP_400_BAD_REQUEST)

            # Only update access if the page owner is the requesting  user
            if page.access != request.data.get("access", page.access) and page.owned_by_id != request.user.id:
                return Response(
                    {"error": "Access cannot be updated since this page is owned by someone else"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            data = request.data.copy()
            data.pop("parent", None)
            if page.access != data.get("access", page.access):
                try:
                    self._hierarchy_service(request, slug, project_id).validate_access_change(
                        str(page_id), data["access"]
                    )
                except ProjectPageHierarchyError as error:
                    return Response(error.as_dict(), status=error.status_code)

            serializer = PageDetailSerializer(page, data=data, partial=True)
            page_description = page.description_html
            if serializer.is_valid():
                serializer.save()
                # capture the page transaction
                if request.data.get("description_html"):
                    page_transaction.delay(
                        new_description_html=request.data.get("description_html", "<p></p>"),
                        old_description_html=page_description,
                        page_id=page_id,
                        actor_id=str(request.user.id),
                        project_id=str(project_id),
                        operation_kind="direct_edit",
                        origin=base_host(request=request, is_app=True),
                    )

                return Response(serializer.data, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Page.DoesNotExist:
            return Response(
                {"error": "Access cannot be updated since this page is owned by someone else"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    def retrieve(self, request, slug, project_id, page_id=None):
        page = self.get_queryset().filter(pk=page_id).first()
        project = Project.objects.get(pk=project_id)
        track_visit = request.query_params.get("track_visit", "true").lower() == "true"

        if page is None:
            return Response({"error": "Page not found"}, status=status.HTTP_404_NOT_FOUND)

        """
        if the role is guest and guest_view_all_features is false and owned by is not
        the requesting user then dont show the page
        """

        if (
            ProjectMember.objects.filter(
                workspace__slug=slug,
                project_id=project_id,
                member=request.user,
                role=5,
                is_active=True,
            ).exists()
            and not project.guest_view_all_features
            and page.owned_by != request.user
        ):
            return Response(
                {"error": "You are not allowed to view this page"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        else:
            issue_ids = PageLog.objects.filter(page_id=page_id, entity_name="issue").values_list(
                "entity_identifier", flat=True
            )
            data = PageDetailSerializer(page).data
            try:
                service = self._hierarchy_service(request, slug, project_id)
                node = next(item for item in service.all_pages(include_archived=True) if item["id"] == str(page.id))
                data = self._merge_hierarchy(dict(data), node)
                data["hierarchy_revision"] = service.path(str(page.id), include_archived=True)["revision"]
            except (ProjectPageHierarchyError, StopIteration):
                return Response({"error": "Page not found"}, status=status.HTTP_404_NOT_FOUND)
            data["issue_ids"] = issue_ids
            if track_visit:
                recent_visited_task.delay(
                    slug=slug,
                    entity_name="page",
                    entity_identifier=page_id,
                    user_id=request.user.id,
                    project_id=project_id,
                )
            return Response(data, status=status.HTTP_200_OK)

    def lock(self, request, slug, project_id, page_id):
        page = Page.objects.get(
            pk=page_id,
            workspace__slug=slug,
            projects__id=project_id,
            project_pages__deleted_at__isnull=True,
        )

        page.is_locked = True
        page.save()
        return Response(status=status.HTTP_204_NO_CONTENT)

    def unlock(self, request, slug, project_id, page_id):
        page = Page.objects.get(
            pk=page_id,
            workspace__slug=slug,
            projects__id=project_id,
            project_pages__deleted_at__isnull=True,
        )

        page.is_locked = False
        page.save()

        return Response(status=status.HTTP_204_NO_CONTENT)

    def access(self, request, slug, project_id, page_id):
        access = request.data.get("access", 0)
        page = Page.objects.get(
            pk=page_id,
            workspace__slug=slug,
            projects__id=project_id,
            project_pages__deleted_at__isnull=True,
        )

        # Only update access if the page owner is the requesting user
        if page.access != request.data.get("access", page.access) and page.owned_by_id != request.user.id:
            return Response(
                {"error": "Access cannot be updated since this page is owned by someone else"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            self._hierarchy_service(request, slug, project_id).validate_access_change(str(page_id), access)
        except ProjectPageHierarchyError as error:
            return Response(error.as_dict(), status=error.status_code)
        page.access = access
        page.save()
        return Response(status=status.HTTP_204_NO_CONTENT)

    def list(self, request, slug, project_id):
        queryset = self.get_queryset()
        project = Project.objects.get(pk=project_id)
        if (
            ProjectMember.objects.filter(
                workspace__slug=slug,
                project_id=project_id,
                member=request.user,
                role=5,
                is_active=True,
            ).exists()
            and not project.guest_view_all_features
        ):
            queryset = queryset.filter(owned_by=request.user)
        service = self._hierarchy_service(request, slug, project_id)
        hierarchy_nodes = {item["id"]: item for item in service.all_pages(include_archived=True)}
        pages = [
            self._merge_hierarchy(dict(PageSerializer(page).data), hierarchy_nodes[str(page.id)])
            for page in queryset
            if str(page.id) in hierarchy_nodes
        ]
        return Response(pages, status=status.HTTP_200_OK)

    def archive(self, request, slug, project_id, page_id):
        page = Page.objects.get(
            pk=page_id,
            workspace__slug=slug,
            projects__id=project_id,
            project_pages__deleted_at__isnull=True,
        )

        # only the owner or admin can archive the page
        if (
            ProjectMember.objects.filter(
                project_id=project_id, member=request.user, is_active=True, role__lte=15
            ).exists()
            and request.user.id != page.owned_by_id
        ):
            return Response(
                {"error": "Only the owner or admin can archive the page"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        service = self._hierarchy_service(request, slug, project_id)
        operation_id = uuid.UUID(str(request.data.get("operation_id", uuid.uuid4())))
        try:
            result = service.archive(str(page_id), operation_id=operation_id)
            return Response(result, status=status.HTTP_200_OK)
        except ProjectPageHierarchyError as error:
            service.record_failure(
                operation_id=operation_id,
                operation="archive",
                error=error,
                root_page_id=str(page_id),
            )
            return Response(error.as_dict(), status=error.status_code)

    def unarchive(self, request, slug, project_id, page_id):
        page = Page.objects.get(
            pk=page_id,
            workspace__slug=slug,
            projects__id=project_id,
            project_pages__deleted_at__isnull=True,
        )

        # only the owner or admin can un archive the page
        if (
            ProjectMember.objects.filter(
                project_id=project_id, member=request.user, is_active=True, role__lte=15
            ).exists()
            and request.user.id != page.owned_by_id
        ):
            return Response(
                {"error": "Only the owner or admin can un archive the page"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        service = self._hierarchy_service(request, slug, project_id)
        operation_id = uuid.UUID(str(request.data.get("operation_id", uuid.uuid4())))
        try:
            result = service.restore(str(page_id), operation_id=operation_id)
            return Response(result, status=status.HTTP_200_OK)
        except ProjectPageHierarchyError as error:
            service.record_failure(
                operation_id=operation_id,
                operation="restore",
                error=error,
                root_page_id=str(page_id),
            )
            return Response(error.as_dict(), status=error.status_code)

    def destroy(self, request, slug, project_id, page_id):
        service = self._hierarchy_service(request, slug, project_id)
        operation_id = uuid.UUID(str(request.data.get("operation_id", uuid.uuid4())))
        try:
            service.remove_subtrees([str(page_id)], operation_id=operation_id)
            return Response(status=status.HTTP_204_NO_CONTENT)
        except ProjectPageHierarchyError as error:
            service.record_failure(
                operation_id=operation_id,
                operation="permanent_remove",
                error=error,
                root_page_id=str(page_id),
            )
            return Response(error.as_dict(), status=error.status_code)

    def summary(self, request, slug, project_id):
        queryset = (
            Page.objects.filter(workspace__slug=slug)
            .filter(
                projects__project_projectmember__member=self.request.user,
                projects__project_projectmember__is_active=True,
                projects__archived_at__isnull=True,
            )
            .filter(Q(owned_by=request.user) | Q(access=0))
            .annotate(
                project=Exists(
                    ProjectPage.objects.filter(page_id=OuterRef("id"), project_id=self.kwargs.get("project_id"))
                )
            )
            .filter(project=True)
            .distinct()
        )

        project = Project.objects.get(pk=project_id)
        if (
            ProjectMember.objects.filter(
                workspace__slug=slug,
                project_id=project_id,
                member=request.user,
                role=ROLE.GUEST.value,
                is_active=True,
            ).exists()
            and not project.guest_view_all_features
        ):
            queryset = queryset.filter(owned_by=request.user)

        stats = queryset.aggregate(
            public_pages=Count(
                Case(
                    When(access=Page.PUBLIC_ACCESS, archived_at__isnull=True, then=1),
                    output_field=IntegerField(),
                )
            ),
            private_pages=Count(
                Case(
                    When(access=Page.PRIVATE_ACCESS, archived_at__isnull=True, then=1),
                    output_field=IntegerField(),
                )
            ),
            archived_pages=Count(Case(When(archived_at__isnull=False, then=1), output_field=IntegerField())),
        )

        return Response(stats, status=status.HTTP_200_OK)


class PageFavoriteViewSet(BaseViewSet):
    model = UserFavorite

    @staticmethod
    def _hierarchy_service(request, slug, project_id):
        project = Project.objects.only("id", "workspace_id").get(pk=project_id, workspace__slug=slug)
        project_role = (
            ProjectMember.objects.filter(project=project, member=request.user, is_active=True)
            .values_list("role", flat=True)
            .first()
        )
        return ProjectPageHierarchyService(
            HierarchyContext(
                project_id=str(project.id),
                workspace_id=str(project.workspace_id),
                user_id=str(request.user.id),
                project_role=project_role,
            )
        )

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    def create(self, request, slug, project_id, page_id):
        try:
            self._hierarchy_service(request, slug, project_id).path(str(page_id))
        except ProjectPageHierarchyError as error:
            return Response(error.as_dict(), status=error.status_code)
        _ = UserFavorite.objects.create(
            project_id=project_id,
            entity_identifier=page_id,
            entity_type="page",
            user=request.user,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    def destroy(self, request, slug, project_id, page_id):
        page_favorite = UserFavorite.objects.get(
            project=project_id,
            user=request.user,
            workspace__slug=slug,
            entity_identifier=page_id,
            entity_type="page",
        )
        page_favorite.delete(soft=False)
        return Response(status=status.HTTP_204_NO_CONTENT)


class PagesDescriptionViewSet(BaseViewSet):
    permission_classes = [ProjectPagePermission]

    def retrieve(self, request, slug, project_id, page_id):
        page = Page.objects.get(
            Q(owned_by=self.request.user) | Q(access=0),
            pk=page_id,
            workspace__slug=slug,
            projects__id=project_id,
            project_pages__deleted_at__isnull=True,
        )
        binary_data = page.description_binary

        def stream_data():
            if binary_data:
                yield binary_data
            else:
                yield b""

        response = StreamingHttpResponse(stream_data(), content_type="application/octet-stream")
        response["Content-Disposition"] = 'attachment; filename="page_description.bin"'
        return response

    def partial_update(self, request, slug, project_id, page_id):
        page = Page.objects.get(
            Q(owned_by=self.request.user) | Q(access=0),
            pk=page_id,
            workspace__slug=slug,
            projects__id=project_id,
            project_pages__deleted_at__isnull=True,
        )

        if page.is_locked:
            return Response(
                {
                    "error_code": ERROR_CODES["PAGE_LOCKED"],
                    "error_message": "PAGE_LOCKED",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if page.archived_at:
            return Response(
                {
                    "error_code": ERROR_CODES["PAGE_ARCHIVED"],
                    "error_message": "PAGE_ARCHIVED",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Store the old description_html before saving (needed for both tasks)
        old_description_html = page.description_html

        # Serialize the existing instance
        existing_instance = json.dumps({"description_html": old_description_html}, cls=DjangoJSONEncoder)

        # Use serializer for validation and update
        serializer = PageBinaryUpdateSerializer(page, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()

            # Capture the page transaction
            if request.data.get("description_html"):
                page_transaction.delay(
                    new_description_html=request.data.get("description_html", "<p></p>"),
                    old_description_html=old_description_html,
                    page_id=page_id,
                    actor_id=str(request.user.id),
                    project_id=str(project_id),
                    operation_kind="direct_edit",
                    origin=base_host(request=request, is_app=True),
                )

            # Run background tasks
            track_page_version.delay(
                page_id=page_id,
                existing_instance=existing_instance,
                user_id=request.user.id,
            )
            return Response({"message": "Updated successfully"})
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PageDuplicateEndpoint(BaseAPIView):
    permission_classes = [ProjectPagePermission]

    def post(self, request, slug, project_id, page_id):
        page = Page.objects.get(
            pk=page_id,
            workspace__slug=slug,
            projects__id=project_id,
            project_pages__deleted_at__isnull=True,
        )

        # check for permission
        if page.access == Page.PRIVATE_ACCESS and page.owned_by_id != request.user.id:
            return Response({"error": "Permission denied"}, status=status.HTTP_403_FORBIDDEN)

        page.pk = None
        page.name = f"{page.name} (Copy)"
        page.description_binary = None
        page.parent = None
        page.sort_order = Page.DEFAULT_SORT_ORDER
        page.archived_at = None
        page.deleted_at = None
        page.owned_by = request.user
        page.created_by = request.user
        page.updated_by = request.user
        page.save()

        # A standard duplicate is intentionally a root Page in the requested
        # project. It must not inherit either a source hierarchy parent or the
        # source Page's links to other projects.
        ProjectPage.objects.create(
            workspace_id=page.workspace_id,
            project_id=project_id,
            page_id=page.id,
            parent=None,
            sort_order=Page.DEFAULT_SORT_ORDER,
            created_by_id=page.created_by_id,
            updated_by_id=page.updated_by_id,
        )

        page_transaction.delay(
            new_description_html=page.description_html,
            old_description_html=None,
            page_id=page.id,
        )

        # Copy the s3 objects uploaded in the page
        copy_s3_objects_of_description_and_assets.delay(
            entity_name="PAGE",
            entity_identifier=page.id,
            project_id=project_id,
            slug=slug,
            user_id=request.user.id,
        )

        page = (
            Page.objects.filter(pk=page.id)
            .annotate(
                project_ids=Coalesce(
                    ArrayAgg("projects__id", distinct=True, filter=~Q(projects__id=True)),
                    Value([], output_field=ArrayField(UUIDField())),
                )
            )
            .first()
        )
        serializer = PageDetailSerializer(page)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
