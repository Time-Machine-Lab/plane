# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import uuid

from rest_framework import serializers, status
from rest_framework.response import Response

from plane.app.permissions import ProjectPagePermission
from plane.app.services import ProjectPageHierarchyError, ProjectPageHierarchyService
from plane.app.services.page_hierarchy import HierarchyContext, is_project_page_hierarchy_enabled
from plane.db.models import Project, ProjectMember, ProjectUserProperty

from ..base import BaseViewSet


class HierarchyMoveSerializer(serializers.Serializer):
    parent_id = serializers.UUIDField(required=False, allow_null=True)
    position = serializers.ChoiceField(choices=["first", "last", "inside", "before", "after"], default="last")
    relative_page_id = serializers.UUIDField(required=False, allow_null=True)
    operation_id = serializers.UUIDField(required=False, default=uuid.uuid4)
    base_revision = serializers.IntegerField(required=False, allow_null=True, min_value=0)


class HierarchyPreferenceSerializer(serializers.Serializer):
    version = serializers.IntegerField(min_value=1, max_value=1)
    expanded_ids = serializers.ListField(child=serializers.UUIDField(), max_length=200)


class AllPagesQuerySerializer(serializers.Serializer):
    offset = serializers.IntegerField(required=False, default=0, min_value=0)
    limit = serializers.IntegerField(required=False, default=50, min_value=1, max_value=200)
    search = serializers.CharField(required=False, default="", allow_blank=True, max_length=255)
    access = serializers.ChoiceField(required=False, choices=[0, 1])
    locked = serializers.BooleanField(required=False)
    owner_id = serializers.UUIDField(required=False)
    archived = serializers.ChoiceField(required=False, default="all", choices=["all", "active", "archived"])
    sort_by = serializers.ChoiceField(
        required=False,
        default="updated_at",
        choices=["name", "created_at", "updated_at", "depth", "path", "sort_order"],
    )
    sort_order = serializers.ChoiceField(required=False, default="desc", choices=["asc", "desc"])


class BulkHierarchySerializer(serializers.Serializer):
    page_ids = serializers.ListField(child=serializers.UUIDField(), min_length=1, max_length=100)
    operation = serializers.ChoiceField(choices=["move", "archive", "restore", "copy", "remove"])
    parent_id = serializers.UUIDField(required=False, allow_null=True)
    position = serializers.ChoiceField(
        required=False,
        default="last",
        choices=["first", "last", "inside", "before", "after"],
    )
    relative_page_id = serializers.UUIDField(required=False, allow_null=True)
    operation_id = serializers.UUIDField(required=False, default=uuid.uuid4)
    base_revision = serializers.IntegerField(required=False, allow_null=True, min_value=0)


class CopySubtreeSerializer(serializers.Serializer):
    operation_id = serializers.UUIDField(required=False, default=uuid.uuid4)


class PageHierarchyViewSet(BaseViewSet):
    permission_classes = [ProjectPagePermission]

    def _service(self, request, slug, project_id):
        project = Project.objects.only("id", "workspace_id").get(id=project_id, workspace__slug=slug)
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
    def _error_response(error: ProjectPageHierarchyError):
        return Response(error.as_dict(), status=error.status_code)

    @staticmethod
    def _disabled_response():
        return Response({"error": "Not found", "code": "not_found"}, status=status.HTTP_404_NOT_FOUND)

    def list(self, request, slug, project_id):
        try:
            parent_id = request.query_params.get("parent_id") or None
            include_archived = request.query_params.get("archived", "false").lower() == "true"
            offset = max(int(request.query_params.get("offset", 0)), 0)
            limit = min(max(int(request.query_params.get("limit", 100)), 1), 200)
            return Response(
                self._service(request, slug, project_id).list_children(
                    parent_id,
                    include_archived=include_archived,
                    offset=offset,
                    limit=limit,
                )
            )
        except (TypeError, ValueError):
            return Response({"error": "Invalid pagination", "code": "invalid_pagination"}, status=400)
        except ProjectPageHierarchyError as error:
            return self._error_response(error)

    def path(self, request, slug, project_id, page_id):
        try:
            include_archived = request.query_params.get("archived", "false").lower() == "true"
            return Response(
                self._service(request, slug, project_id).path(str(page_id), include_archived=include_archived)
            )
        except ProjectPageHierarchyError as error:
            return self._error_response(error)

    def move(self, request, slug, project_id, page_id):
        if not is_project_page_hierarchy_enabled():
            return self._disabled_response()
        payload = HierarchyMoveSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        service = self._service(request, slug, project_id)
        try:
            result = service.move(
                str(page_id),
                parent_page_id=(str(payload.validated_data["parent_id"]) if payload.validated_data.get("parent_id") else None),
                position=payload.validated_data["position"],
                relative_page_id=(
                    str(payload.validated_data["relative_page_id"])
                    if payload.validated_data.get("relative_page_id")
                    else None
                ),
                operation_id=payload.validated_data["operation_id"],
                base_revision=payload.validated_data.get("base_revision"),
            )
            return Response(result)
        except ProjectPageHierarchyError as error:
            service.record_failure(
                operation_id=payload.validated_data["operation_id"],
                operation="move",
                error=error,
                root_page_id=str(page_id),
            )
            return self._error_response(error)

    def preview(self, request, slug, project_id, page_id):
        operation = request.query_params.get("operation", "move")
        if operation not in {"move", "archive", "restore", "copy", "delete"}:
            return Response({"error": "Unsupported operation", "code": "invalid_operation"}, status=400)
        try:
            return Response(self._service(request, slug, project_id).preview(str(page_id), operation))
        except ProjectPageHierarchyError as error:
            return self._error_response(error)

    def all_pages(self, request, slug, project_id):
        payload = AllPagesQuerySerializer(data=request.query_params)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        try:
            return Response(
                self._service(request, slug, project_id).all_pages_paginated(
                    include_archived=data["archived"] != "active",
                    offset=data["offset"],
                    limit=data["limit"],
                    search=data["search"],
                    access=data.get("access"),
                    locked=data.get("locked"),
                    owner_id=str(data["owner_id"]) if data.get("owner_id") else None,
                    archive_state=data["archived"],
                    sort_by=data["sort_by"],
                    sort_order=data["sort_order"],
                )
            )
        except ProjectPageHierarchyError as error:
            return self._error_response(error)

    def bulk_preview(self, request, slug, project_id):
        payload = BulkHierarchySerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        try:
            return Response(
                self._service(request, slug, project_id).preview_bulk(
                    [str(page_id) for page_id in data["page_ids"]],
                    data["operation"],
                    parent_page_id=str(data["parent_id"]) if data.get("parent_id") else None,
                    position=data["position"],
                    relative_page_id=(str(data["relative_page_id"]) if data.get("relative_page_id") else None),
                )
            )
        except ProjectPageHierarchyError as error:
            return self._error_response(error)

    def bulk_mutate(self, request, slug, project_id):
        if not is_project_page_hierarchy_enabled():
            return self._disabled_response()
        payload = BulkHierarchySerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        service = self._service(request, slug, project_id)
        page_ids = [str(page_id) for page_id in data["page_ids"]]
        operation_id = data["operation_id"]
        try:
            if data["operation"] == "move":
                result = service.bulk_move(
                    page_ids,
                    parent_page_id=str(data["parent_id"]) if data.get("parent_id") else None,
                    position=data["position"],
                    relative_page_id=(str(data["relative_page_id"]) if data.get("relative_page_id") else None),
                    operation_id=operation_id,
                    base_revision=data.get("base_revision"),
                )
            elif data["operation"] == "archive":
                result = service.bulk_archive(page_ids, operation_id=operation_id)
            elif data["operation"] == "restore":
                result = service.bulk_restore(page_ids, operation_id=operation_id)
            elif data["operation"] == "copy":
                result = service.copy_subtrees(page_ids, operation_id=operation_id)
            else:
                result = service.remove_subtrees(page_ids, operation_id=operation_id)
            response_status = status.HTTP_202_ACCEPTED if data["operation"] == "copy" else status.HTTP_200_OK
            return Response(result, status=response_status)
        except ProjectPageHierarchyError as error:
            service.record_failure(
                operation_id=operation_id,
                operation=f"bulk_{data['operation']}",
                error=error,
                root_page_id=page_ids[0],
            )
            return self._error_response(error)

    def copy_subtree(self, request, slug, project_id, page_id):
        if not is_project_page_hierarchy_enabled():
            return self._disabled_response()
        payload = CopySubtreeSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        service = self._service(request, slug, project_id)
        operation_id = payload.validated_data["operation_id"]
        try:
            return Response(
                service.copy_subtrees([str(page_id)], operation_id=operation_id),
                status=status.HTTP_202_ACCEPTED,
            )
        except ProjectPageHierarchyError as error:
            service.record_failure(
                operation_id=operation_id,
                operation="copy_subtree",
                error=error,
                root_page_id=str(page_id),
            )
            return self._error_response(error)

    def retrieve_preferences(self, request, slug, project_id):
        project = Project.objects.only("id", "workspace_id").get(id=project_id, workspace__slug=slug)
        props, _ = ProjectUserProperty.objects.get_or_create(
            project=project,
            user=request.user,
            defaults={"workspace_id": project.workspace_id},
        )
        pages = props.preferences.get("pages", {})
        hierarchy = pages.get("hierarchy", {"version": 1, "expanded_ids": []})
        return Response(hierarchy)

    def update_preferences(self, request, slug, project_id):
        payload = HierarchyPreferenceSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        project = Project.objects.only("id", "workspace_id").get(id=project_id, workspace__slug=slug)
        props, _ = ProjectUserProperty.objects.get_or_create(
            project=project,
            user=request.user,
            defaults={"workspace_id": project.workspace_id},
        )
        preferences = dict(props.preferences)
        pages = dict(preferences.get("pages", {}))
        pages["hierarchy"] = {
            "version": 1,
            "expanded_ids": [str(item) for item in payload.validated_data["expanded_ids"]],
        }
        preferences["pages"] = pages
        props.preferences = preferences
        props.save(update_fields=["preferences", "updated_at"])
        return Response(pages["hierarchy"], status=status.HTTP_200_OK)
