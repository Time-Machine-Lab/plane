# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Third party imports
from rest_framework import status
from rest_framework.response import Response

from plane.app.services import ProjectPageHierarchyService
from plane.app.services.page_hierarchy import HierarchyContext
from plane.db.models import ProjectMember, ProjectPage, UserRecentVisit
from plane.app.serializers import WorkspaceRecentVisitSerializer

# Modules imports
from ..base import BaseViewSet
from plane.app.permissions import allow_permission, ROLE


class UserRecentVisitViewSet(BaseViewSet):
    model = UserRecentVisit
    use_read_replica = True

    def get_serializer_class(self):
        return WorkspaceRecentVisitSerializer

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST], level="WORKSPACE")
    def list(self, request, slug):
        user_recent_visits = UserRecentVisit.objects.filter(workspace__slug=slug, user=request.user)

        entity_name = request.query_params.get("entity_name")

        if entity_name:
            user_recent_visits = user_recent_visits.filter(entity_name=entity_name)

        user_recent_visits = user_recent_visits.filter(entity_name__in=["issue", "page", "project"])

        candidates = list(user_recent_visits[:100])
        recent_page_ids = {
            str(visit.entity_identifier) for visit in candidates if visit.entity_name == "page" and visit.entity_identifier
        }
        visible_page_ids: set[str] = set()
        if recent_page_ids:
            memberships = {
                str(project_id): role
                for project_id, role in ProjectMember.objects.filter(
                    workspace__slug=slug,
                    member=request.user,
                    is_active=True,
                    project__project_pages__page_id__in=recent_page_ids,
                    project__project_pages__deleted_at__isnull=True,
                )
                .values_list("project_id", "role")
                .distinct()
            }
            projects = ProjectPage.objects.filter(
                workspace__slug=slug,
                project_id__in=memberships,
                page_id__in=recent_page_ids,
                deleted_at__isnull=True,
            ).values_list("project_id", "workspace_id").distinct()
            for project_id, workspace_id in projects:
                service = ProjectPageHierarchyService(
                    HierarchyContext(
                        project_id=str(project_id),
                        workspace_id=str(workspace_id),
                        user_id=str(request.user.id),
                        project_role=memberships[str(project_id)],
                    )
                )
                visible_page_ids.update(
                    item["id"] for item in service.all_pages(include_archived=False) if item["id"] in recent_page_ids
                )
        filtered_visits = [
            visit
            for visit in candidates
            if visit.entity_name != "page" or str(visit.entity_identifier) in visible_page_ids
        ][:20]
        serializer = WorkspaceRecentVisitSerializer(filtered_visits, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
