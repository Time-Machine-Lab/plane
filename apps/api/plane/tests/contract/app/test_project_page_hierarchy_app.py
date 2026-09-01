# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import uuid

import pytest
from rest_framework import status

from plane.app.services import ProjectPageHierarchyError, ProjectPageHierarchyService
from plane.db.models import (
    Page,
    Project,
    ProjectMember,
    ProjectPage,
    ProjectPageHierarchyMutation,
    ProjectPageHierarchyState,
    User,
    UserRecentVisit,
)


def _project(workspace, suffix):
    return Project.objects.create(
        name=f"Hierarchy {suffix}",
        identifier=f"H{suffix}"[:12],
        workspace=workspace,
    )


def _page(workspace, project, owner, name, *, access=Page.PUBLIC_ACCESS, parent=None, order=0):
    page = Page.objects.create(workspace=workspace, owned_by=owner, name=name, access=access)
    link = ProjectPage.objects.create(
        workspace=workspace,
        project=project,
        page=page,
        parent=parent,
        sort_order=order,
    )
    return page, link


def _hierarchy_url(workspace, project, parent_id=None):
    url = f"/api/workspaces/{workspace.slug}/projects/{project.id}/pages/hierarchy/"
    return f"{url}?parent_id={parent_id}" if parent_id else url


@pytest.mark.contract
@pytest.mark.django_db
class TestProjectPageHierarchyAppAPI:
    def test_lazy_tree_and_breadcrumb_contract(self, session_client, workspace, create_user):
        project = _project(workspace, "READ")
        ProjectMember.objects.create(workspace=workspace, project=project, member=create_user, role=20)
        root, root_link = _page(workspace, project, create_user, "Technical docs")
        child, child_link = _page(workspace, project, create_user, "Backend", parent=root_link)
        leaf, _ = _page(workspace, project, create_user, "Permissions", parent=child_link)

        roots = session_client.get(_hierarchy_url(workspace, project))
        children = session_client.get(_hierarchy_url(workspace, project, root.id))
        path = session_client.get(
            f"/api/workspaces/{workspace.slug}/projects/{project.id}/pages/{leaf.id}/hierarchy-path/"
        )

        assert roots.status_code == status.HTTP_200_OK
        assert [item["id"] for item in roots.json()["results"]] == [str(root.id)]
        assert roots.json()["results"][0]["has_children"] is True
        assert "description_html" not in roots.json()["results"][0]
        assert children.status_code == status.HTTP_200_OK
        assert [item["id"] for item in children.json()["results"]] == [str(child.id)]
        assert path.status_code == status.HTTP_200_OK
        assert [item["name"] for item in path.json()["path"]] == [
            "Technical docs",
            "Backend",
            "Permissions",
        ]

    def test_private_ancestor_hides_descendant_from_tree_path_search_and_favorite(
        self, session_client, workspace, create_user
    ):
        project = _project(workspace, "PRIVATE")
        ProjectMember.objects.create(workspace=workspace, project=project, member=create_user, role=15)
        owner = User.objects.create(email=f"private-{uuid.uuid4().hex[:8]}@plane.so")
        private, private_link = _page(
            workspace,
            project,
            owner,
            "Secret parent",
            access=Page.PRIVATE_ACCESS,
        )
        descendant, _ = _page(workspace, project, owner, "Public-looking descendant", parent=private_link)

        roots = session_client.get(_hierarchy_url(workspace, project))
        path = session_client.get(
            f"/api/workspaces/{workspace.slug}/projects/{project.id}/pages/{descendant.id}/hierarchy-path/"
        )
        search = session_client.get(
            f"/api/workspaces/{workspace.slug}/search/",
            {
                "search": "Public-looking",
                "entities": "page",
                "project_id": str(project.id),
                "workspace_search": "false",
            },
        )
        favorite = session_client.post(
            f"/api/workspaces/{workspace.slug}/projects/{project.id}/favorite-pages/{descendant.id}/"
        )
        detail = session_client.get(
            f"/api/workspaces/{workspace.slug}/projects/{project.id}/pages/{descendant.id}/"
        )
        content = session_client.get(
            f"/api/workspaces/{workspace.slug}/projects/{project.id}/pages/{descendant.id}/description/"
        )

        assert roots.status_code == status.HTTP_200_OK
        assert roots.json()["results"] == []
        assert path.status_code == status.HTTP_404_NOT_FOUND
        assert search.status_code == status.HTTP_200_OK
        assert search.json()["results"]["page"] == []
        assert favorite.status_code in {status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND}
        assert detail.status_code in {status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND}
        assert content.status_code in {status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND}

    def test_search_returns_project_path_for_duplicate_names(self, session_client, workspace, create_user):
        project = _project(workspace, "SEARCH")
        ProjectMember.objects.create(workspace=workspace, project=project, member=create_user, role=20)
        first_root, first_link = _page(workspace, project, create_user, "Backend")
        second_root, second_link = _page(workspace, project, create_user, "Frontend")
        first_leaf, _ = _page(workspace, project, create_user, "Permissions", parent=first_link)
        second_leaf, _ = _page(workspace, project, create_user, "Permissions", parent=second_link)

        response = session_client.get(
            f"/api/workspaces/{workspace.slug}/search/",
            {
                "search": "Permissions",
                "entities": "page",
                "project_id": str(project.id),
                "workspace_search": "false",
            },
        )

        assert response.status_code == status.HTTP_200_OK
        page_results = response.json()["results"]["page"]
        paths = {item["path_text"] for item in page_results}
        assert paths == {
            f"{first_root.name} / {first_leaf.name}",
            f"{second_root.name} / {second_leaf.name}",
        }
        assert {
            tuple(path_item["name"] for path_item in item["path"])
            for item in page_results
        } == {
            (first_root.name, first_leaf.name),
            (second_root.name, second_leaf.name),
        }
        assert all(item["path"][-1]["id"] == item["id"] for item in page_results)

    def test_member_cannot_move_page_owned_by_someone_else(self, session_client, workspace, create_user):
        project = _project(workspace, "MOVE")
        ProjectMember.objects.create(workspace=workspace, project=project, member=create_user, role=15)
        owner = User.objects.create(email=f"owner-{uuid.uuid4().hex[:8]}@plane.so")
        page, _ = _page(workspace, project, owner, "Owner controlled")

        operation_id = uuid.uuid4()
        response = session_client.post(
            f"/api/workspaces/{workspace.slug}/projects/{project.id}/pages/{page.id}/move-in-hierarchy/",
            {
                "parent_id": None,
                "position": "last",
                "operation_id": str(operation_id),
            },
            format="json",
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.json()["code"] == "insufficient_permission"

    def test_cross_project_parent_is_rejected_without_metadata(self, session_client, workspace, create_user):
        project = _project(workspace, "LOCAL")
        foreign_project = _project(workspace, "FOREIGN")
        ProjectMember.objects.create(workspace=workspace, project=project, member=create_user, role=20)
        local, _ = _page(workspace, project, create_user, "Local")
        foreign, _ = _page(workspace, foreign_project, create_user, "Foreign secret")

        operation_id = uuid.uuid4()
        response = session_client.post(
            f"/api/workspaces/{workspace.slug}/projects/{project.id}/pages/{local.id}/move-in-hierarchy/",
            {
                "parent_id": str(foreign.id),
                "position": "inside",
                "operation_id": str(operation_id),
            },
            format="json",
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json() == {"error": "Page not found", "code": "page_not_found"}

        mutation = ProjectPageHierarchyMutation.objects.get(
            project=project,
            operation_id=operation_id,
        )
        assert mutation.outcome == "validation_failure"
        assert mutation.result == {"code": "page_not_found", "status_code": 404}
        assert "Foreign secret" not in str(mutation.result)

    def test_all_pages_and_bulk_preview_contracts(self, session_client, workspace, create_user):
        project = _project(workspace, "MANAGE")
        ProjectMember.objects.create(workspace=workspace, project=project, member=create_user, role=20)
        root, root_link = _page(workspace, project, create_user, "Root", order=10)
        child, _ = _page(workspace, project, create_user, "Child", parent=root_link, order=10)

        first_page = session_client.get(
            f"/api/workspaces/{workspace.slug}/projects/{project.id}/pages/hierarchy/all-pages/",
            {"limit": 1, "sort_by": "name", "sort_order": "asc"},
        )
        preview = session_client.post(
            f"/api/workspaces/{workspace.slug}/projects/{project.id}/pages/hierarchy/bulk-preview/",
            {"page_ids": [str(root.id)], "operation": "archive"},
            format="json",
        )
        overlap = session_client.post(
            f"/api/workspaces/{workspace.slug}/projects/{project.id}/pages/hierarchy/bulk-preview/",
            {"page_ids": [str(root.id), str(child.id)], "operation": "archive"},
            format="json",
        )

        assert first_page.status_code == status.HTTP_200_OK
        assert first_page.json()["total_count"] == 2
        assert first_page.json()["next_offset"] == 1
        assert "description_html" not in first_page.json()["results"][0]
        assert preview.status_code == status.HTTP_200_OK
        assert preview.json()["affected_count"] == 2
        assert overlap.status_code == status.HTTP_400_BAD_REQUEST
        assert overlap.json()["code"] == "overlapping_selection"

    def test_bulk_archive_and_restore_are_atomic(self, session_client, workspace, create_user):
        project = _project(workspace, "BULK")
        ProjectMember.objects.create(workspace=workspace, project=project, member=create_user, role=20)
        first, first_link = _page(workspace, project, create_user, "First")
        child, child_link = _page(workspace, project, create_user, "Child", parent=first_link)
        second, second_link = _page(workspace, project, create_user, "Second")
        ProjectPageHierarchyState.objects.create(workspace=workspace, project=project)

        archived = session_client.post(
            f"/api/workspaces/{workspace.slug}/projects/{project.id}/pages/hierarchy/bulk/",
            {
                "page_ids": [str(first.id), str(second.id)],
                "operation": "archive",
                "operation_id": str(uuid.uuid4()),
            },
            format="json",
        )

        first_link.refresh_from_db()
        child_link.refresh_from_db()
        second_link.refresh_from_db()
        assert archived.status_code == status.HTTP_200_OK
        assert archived.json()["affected_count"] == 3
        assert first_link.archived_at is not None
        assert child_link.archived_at is not None
        assert second_link.archived_at is not None

        restored = session_client.post(
            f"/api/workspaces/{workspace.slug}/projects/{project.id}/pages/hierarchy/bulk/",
            {
                "page_ids": [str(first.id), str(second.id)],
                "operation": "restore",
                "operation_id": str(uuid.uuid4()),
            },
            format="json",
        )
        assert restored.status_code == status.HTTP_200_OK
        assert restored.json()["affected_count"] == 3

    def test_child_create_rolls_back_page_when_hierarchy_placement_fails(
        self, session_client, workspace, create_user, monkeypatch
    ):
        project = _project(workspace, "CREATEFAIL")
        ProjectMember.objects.create(workspace=workspace, project=project, member=create_user, role=20)
        parent, _ = _page(workspace, project, create_user, "Parent")
        operation_id = uuid.uuid4()
        original_page_ids = set(Page.objects.values_list("id", flat=True))

        def reject_placement(*args, **kwargs):
            raise ProjectPageHierarchyError("maximum_depth_exceeded", "Placement rejected")

        monkeypatch.setattr(ProjectPageHierarchyService, "move", reject_placement)
        response = session_client.post(
            f"/api/workspaces/{workspace.slug}/projects/{project.id}/pages/",
            {
                "name": "Must roll back",
                "parent_id": str(parent.id),
                "operation_id": str(operation_id),
            },
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()["code"] == "maximum_depth_exceeded"
        assert set(Page.objects.values_list("id", flat=True)) == original_page_ids
        mutation = ProjectPageHierarchyMutation.objects.get(project=project, operation_id=operation_id)
        assert mutation.outcome == "validation_failure"

    def test_permanent_remove_endpoint_removes_the_complete_archived_subtree(
        self, session_client, workspace, create_user
    ):
        project = _project(workspace, "REMOVEAPI")
        ProjectMember.objects.create(workspace=workspace, project=project, member=create_user, role=20)
        root, root_link = _page(workspace, project, create_user, "Root")
        child, child_link = _page(workspace, project, create_user, "Child", parent=root_link)
        batch_id = uuid.uuid4()
        ProjectPage.objects.filter(id__in=[root_link.id, child_link.id]).update(
            archived_at="2026-01-01T00:00:00Z",
            archive_batch_id=batch_id,
        )
        ProjectPageHierarchyState.objects.create(workspace=workspace, project=project)

        response = session_client.delete(
            f"/api/workspaces/{workspace.slug}/projects/{project.id}/pages/{root.id}/",
            {"operation_id": str(uuid.uuid4())},
            format="json",
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert ProjectPage.all_objects.get(id=root_link.id).deleted_at is not None
        assert ProjectPage.all_objects.get(id=child_link.id).deleted_at is not None
        assert Page.all_objects.get(id=root.id).deleted_at is not None
        assert Page.all_objects.get(id=child.id).deleted_at is not None

    def test_recent_visits_omit_effectively_hidden_page(self, session_client, workspace, create_user):
        project = _project(workspace, "RECENT")
        ProjectMember.objects.create(workspace=workspace, project=project, member=create_user, role=15)
        owner = User.objects.create(email=f"recent-owner-{uuid.uuid4().hex[:8]}@plane.so")
        _, private_link = _page(
            workspace,
            project,
            owner,
            "Hidden parent",
            access=Page.PRIVATE_ACCESS,
        )
        descendant, _ = _page(workspace, project, owner, "Hidden recent", parent=private_link)
        UserRecentVisit.objects.create(
            workspace=workspace,
            user=create_user,
            entity_name="page",
            entity_identifier=descendant.id,
        )

        response = session_client.get(
            f"/api/workspaces/{workspace.slug}/recent-visits/",
            {"entity_name": "page"},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []
