# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import uuid

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from plane.app.services import ProjectPageHierarchyError, ProjectPageHierarchyService
from plane.app.services.page_hierarchy import HierarchyContext, MAX_HIERARCHY_DEPTH
from plane.bgtasks.copy_s3_object import _finish_hierarchy_copy
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
        name=f"Knowledge {suffix}",
        identifier=f"K{suffix}"[:12],
        workspace=workspace,
    )


def _page(workspace, owner, name, access=Page.PUBLIC_ACCESS):
    return Page.objects.create(workspace=workspace, owned_by=owner, name=name, access=access)


def _link(workspace, project, page, *, parent=None, order=0, archived_at=None, archive_batch_id=None):
    return ProjectPage.objects.create(
        workspace=workspace,
        project=project,
        page=page,
        parent=parent,
        sort_order=order,
        archived_at=archived_at,
        archive_batch_id=archive_batch_id,
    )


def _service(project, user, role=20):
    return ProjectPageHierarchyService(
        HierarchyContext(
            project_id=str(project.id),
            workspace_id=str(project.workspace_id),
            user_id=str(user.id),
            project_role=role,
        )
    )


@pytest.mark.unit
@pytest.mark.django_db
class TestProjectPageHierarchyReads:
    def test_lazy_reads_paths_and_pagination_are_stable(self, workspace, create_user):
        project = _project(workspace, "READ")
        ProjectMember.objects.create(workspace=workspace, project=project, member=create_user, role=20)
        first = _link(workspace, project, _page(workspace, create_user, "Duplicate"), order=10)
        second = _link(workspace, project, _page(workspace, create_user, "Duplicate"), order=10)
        child = _link(workspace, project, _page(workspace, create_user, "Child"), parent=first, order=5)
        ProjectPageHierarchyState.objects.create(workspace=workspace, project=project, revision=7)

        first_page = _service(project, create_user).list_children(None, offset=0, limit=1)
        second_page = _service(project, create_user).list_children(None, offset=1, limit=1)

        expected = sorted([first, second], key=lambda item: (item.sort_order, str(item.id)))
        assert first_page["results"][0]["id"] == str(expected[0].page_id)
        assert second_page["results"][0]["id"] == str(expected[1].page_id)
        assert first_page["next_offset"] == 1
        assert second_page["next_offset"] is None
        assert first_page["revision"] == 7
        assert "description_html" not in first_page["results"][0]

        path = _service(project, create_user).path(str(child.page_id))
        assert [item["id"] for item in path["path"]] == [str(first.page_id), str(child.page_id)]
        assert path["depth"] == 2

    def test_effective_visibility_hides_private_branch_and_child_presence(self, workspace, create_user):
        project = _project(workspace, "VIS")
        other = User.objects.create(email=f"other-{uuid.uuid4().hex[:8]}@plane.so")
        root = _link(workspace, project, _page(workspace, other, "Public root"))
        private = _link(
            workspace,
            project,
            _page(workspace, other, "Private", access=Page.PRIVATE_ACCESS),
            parent=root,
        )
        _link(workspace, project, _page(workspace, other, "Hidden descendant"), parent=private)

        response = _service(project, create_user, role=15).list_children(None)

        assert [item["id"] for item in response["results"]] == [str(root.page_id)]
        assert response["results"][0]["has_children"] is False
        assert response["results"][0]["child_count"] == 0
        with pytest.raises(ProjectPageHierarchyError, match="Page not found"):
            _service(project, create_user, role=15).path(str(private.page_id))

    def test_active_child_below_archived_parent_is_not_promoted_to_root(self, workspace, create_user):
        project = _project(workspace, "ARCH")
        root = _link(workspace, project, _page(workspace, create_user, "Archived root"))
        child = _link(workspace, project, _page(workspace, create_user, "Corrupt active child"), parent=root)
        ProjectPage.objects.filter(id=root.id).update(archived_at="2026-01-01T00:00:00Z")

        response = _service(project, create_user).list_children(None)

        assert response["results"] == []
        with pytest.raises(ProjectPageHierarchyError):
            _service(project, create_user).path(str(child.page_id))

    def test_all_pages_builds_deep_paths_with_bounded_queries(self, workspace, create_user):
        project = _project(workspace, "QUERY")
        parent = None
        expected_names = []
        for index in range(MAX_HIERARCHY_DEPTH):
            name = f"Level {index + 1}"
            expected_names.append(name)
            parent = _link(workspace, project, _page(workspace, create_user, name), parent=parent, order=index)

        with CaptureQueriesContext(connection) as queries:
            results = _service(project, create_user).all_pages(include_archived=True)

        deepest = next(item for item in results if item["id"] == str(parent.page_id))
        assert [item["name"] for item in deepest["path"]] == expected_names
        assert deepest["depth"] == MAX_HIERARCHY_DEPTH
        assert len(queries) <= 2

    def test_all_pages_pagination_filters_and_sorting_are_stable(self, workspace, create_user):
        project = _project(workspace, "ALL")
        first = _link(workspace, project, _page(workspace, create_user, "Alpha"), order=20)
        second = _link(workspace, project, _page(workspace, create_user, "Beta"), order=10)
        private = _link(
            workspace,
            project,
            _page(workspace, create_user, "Private", access=Page.PRIVATE_ACCESS),
            parent=first,
            order=5,
        )
        ProjectPage.objects.filter(id=second.id).update(archived_at="2026-01-01T00:00:00Z")
        ProjectPageHierarchyState.objects.create(workspace=workspace, project=project)
        service = _service(project, create_user)

        with CaptureQueriesContext(connection) as queries:
            first_page = service.all_pages_paginated(limit=1, sort_by="name", sort_order="asc")
        second_page = service.all_pages_paginated(offset=1, limit=1, sort_by="name", sort_order="asc")
        private_only = service.all_pages_paginated(access=Page.PRIVATE_ACCESS, sort_by="path", sort_order="asc")
        path_search = service.all_pages_paginated(search="Alpha / Private", sort_by="path", sort_order="asc")
        archived_only = service.all_pages_paginated(archive_state="archived")

        assert first_page["results"][0]["id"] == str(first.page_id)
        assert second_page["results"][0]["id"] == str(second.page_id)
        assert first_page["next_offset"] == 1
        assert private_only["results"][0]["id"] == str(private.page_id)
        assert [item["name"] for item in private_only["results"][0]["path"]] == ["Alpha", "Private"]
        assert [item["id"] for item in path_search["results"]] == [str(private.page_id)]
        assert [item["id"] for item in archived_only["results"]] == [str(second.page_id)]
        assert len(queries) <= 5


@pytest.mark.unit
@pytest.mark.django_db
class TestProjectPageHierarchyMutations:
    def test_validation_failure_audit_is_bounded_and_idempotent(self, workspace, create_user):
        project = _project(workspace, "AUDIT")
        root = _link(workspace, project, _page(workspace, create_user, "Sensitive title"))
        ProjectPageHierarchyState.objects.create(workspace=workspace, project=project, revision=3)
        service = _service(project, create_user)
        operation_id = uuid.uuid4()
        error = ProjectPageHierarchyError("hierarchy_cycle", "Sensitive title must not be stored")

        service.record_failure(
            operation_id=operation_id,
            operation="move",
            error=error,
            root_page_id=str(root.page_id),
        )
        service.record_failure(
            operation_id=operation_id,
            operation="move",
            error=error,
            root_page_id=str(root.page_id),
        )

        mutation = ProjectPageHierarchyMutation.objects.get(operation_id=operation_id)
        assert mutation.outcome == "validation_failure"
        assert mutation.revision == 3
        assert mutation.result == {"code": "hierarchy_cycle", "status_code": 400}
        assert "Sensitive" not in str(mutation.result)

    def test_non_owner_member_cannot_move_public_page(self, workspace, create_user):
        project = _project(workspace, "AUTH")
        owner = User.objects.create(email=f"owner-{uuid.uuid4().hex[:8]}@plane.so")
        root = _link(workspace, project, _page(workspace, owner, "Owned by someone else"))
        ProjectPageHierarchyState.objects.create(workspace=workspace, project=project)

        with pytest.raises(ProjectPageHierarchyError) as error:
            _service(project, create_user, role=15).move(
                str(root.page_id),
                parent_page_id=None,
                operation_id=uuid.uuid4(),
            )

        assert error.value.code == "insufficient_permission"
        root.refresh_from_db()
        assert root.parent_id is None

    def test_move_preserves_subtree_rejects_cycle_and_is_idempotent(self, workspace, create_user):
        project = _project(workspace, "MOVE")
        root = _link(workspace, project, _page(workspace, create_user, "Root"), order=1)
        child = _link(workspace, project, _page(workspace, create_user, "Child"), parent=root, order=1)
        grandchild = _link(workspace, project, _page(workspace, create_user, "Grandchild"), parent=child, order=1)
        destination = _link(workspace, project, _page(workspace, create_user, "Destination"), order=2)
        state = ProjectPageHierarchyState.objects.create(workspace=workspace, project=project)
        service = _service(project, create_user)

        with pytest.raises(ProjectPageHierarchyError) as error:
            service.move(
                str(root.page_id),
                parent_page_id=str(grandchild.page_id),
                operation_id=uuid.uuid4(),
            )
        assert error.value.code == "hierarchy_cycle"

        operation_id = uuid.uuid4()
        result = service.move(
            str(root.page_id),
            parent_page_id=str(destination.page_id),
            operation_id=operation_id,
        )
        replay = service.move(
            str(root.page_id),
            parent_page_id=None,
            operation_id=operation_id,
        )

        root.refresh_from_db()
        child.refresh_from_db()
        grandchild.refresh_from_db()
        state.refresh_from_db()
        assert root.parent_id == destination.id
        assert child.parent_id == root.id
        assert grandchild.parent_id == child.id
        assert replay == result
        assert state.revision == 1
        assert ProjectPageHierarchyMutation.objects.filter(operation_id=operation_id).count() == 1

    def test_stale_revision_is_revalidated_and_invalid_relative_move_is_atomic(self, workspace, create_user):
        project = _project(workspace, "STALE")
        first = _link(workspace, project, _page(workspace, create_user, "First"), order=10)
        second = _link(workspace, project, _page(workspace, create_user, "Second"), order=20)
        state = ProjectPageHierarchyState.objects.create(workspace=workspace, project=project, revision=4)
        service = _service(project, create_user)

        with pytest.raises(ProjectPageHierarchyError) as error:
            service.move(
                str(first.page_id),
                parent_page_id=None,
                position="before",
                relative_page_id=str(uuid.uuid4()),
                operation_id=uuid.uuid4(),
                base_revision=1,
            )

        assert error.value.code == "invalid_relative_page"
        first.refresh_from_db()
        second.refresh_from_db()
        state.refresh_from_db()
        assert (first.parent_id, first.sort_order) == (None, 10)
        assert (second.parent_id, second.sort_order) == (None, 20)
        assert state.revision == 4

        result = service.move(
            str(second.page_id),
            parent_page_id=None,
            position="first",
            operation_id=uuid.uuid4(),
            base_revision=1,
        )
        assert result["base_revision"] == 1
        assert result["revision"] == 5

    def test_move_rejects_a_subtree_that_would_exceed_maximum_depth(self, workspace, create_user):
        project = _project(workspace, "DEPTH")
        parent = None
        for index in range(MAX_HIERARCHY_DEPTH):
            parent = _link(
                workspace,
                project,
                _page(workspace, create_user, f"Level {index + 1}"),
                parent=parent,
                order=index,
            )
        moving_root = _link(workspace, project, _page(workspace, create_user, "Moving root"))
        moving_child = _link(
            workspace,
            project,
            _page(workspace, create_user, "Moving child"),
            parent=moving_root,
        )
        state = ProjectPageHierarchyState.objects.create(workspace=workspace, project=project)

        with pytest.raises(ProjectPageHierarchyError) as error:
            _service(project, create_user).move(
                str(moving_root.page_id),
                parent_page_id=str(parent.page_id),
                operation_id=uuid.uuid4(),
            )

        assert error.value.code == "maximum_depth_exceeded"
        moving_root.refresh_from_db()
        moving_child.refresh_from_db()
        state.refresh_from_db()
        assert moving_root.parent_id is None
        assert moving_child.parent_id == moving_root.id
        assert state.revision == 0

    def test_cross_project_parent_is_non_disclosing(self, workspace, create_user):
        project = _project(workspace, "ONE")
        other_project = _project(workspace, "TWO")
        root = _link(workspace, project, _page(workspace, create_user, "Root"))
        foreign = _link(workspace, other_project, _page(workspace, create_user, "Foreign"))
        ProjectPageHierarchyState.objects.create(workspace=workspace, project=project)

        with pytest.raises(ProjectPageHierarchyError) as error:
            _service(project, create_user).move(
                str(root.page_id),
                parent_page_id=str(foreign.page_id),
                operation_id=uuid.uuid4(),
            )

        assert error.value.code == "page_not_found"

    def test_access_tightening_checks_all_descendants_in_every_project(self, workspace, create_user):
        first_project = _project(workspace, "ACCA")
        second_project = _project(workspace, "ACCB")
        root_page = _page(workspace, create_user, "Shared root")
        first_root = _link(workspace, first_project, root_page)
        second_root = _link(workspace, second_project, root_page)
        private_child = _page(workspace, create_user, "Private child", access=Page.PRIVATE_ACCESS)
        _link(workspace, first_project, private_child, parent=first_root)
        public_grandchild = _page(workspace, create_user, "Public grandchild")
        private_link = ProjectPage.objects.get(project=first_project, page=private_child)
        _link(workspace, first_project, public_grandchild, parent=private_link)
        _link(workspace, second_project, _page(workspace, create_user, "Other public child"), parent=second_root)

        with pytest.raises(ProjectPageHierarchyError) as error:
            _service(first_project, create_user).validate_access_change(str(root_page.id), Page.PRIVATE_ACCESS)

        assert error.value.code == "visibility_inheritance"
        root_page.refresh_from_db()
        assert root_page.access == Page.PUBLIC_ACCESS

    def test_archive_restore_batch_keeps_pre_archived_descendant_and_other_project_link(
        self, workspace, create_user
    ):
        project = _project(workspace, "LIFE")
        other_project = _project(workspace, "OTHER")
        root = _link(workspace, project, _page(workspace, create_user, "Root"))
        child_page = _page(workspace, create_user, "Child")
        child = _link(workspace, project, child_page, parent=root)
        pre_archived = _link(workspace, project, _page(workspace, create_user, "Old archive"), parent=child)
        old_batch = uuid.uuid4()
        ProjectPage.objects.filter(id=pre_archived.id).update(
            archived_at="2026-01-01T00:00:00Z", archive_batch_id=old_batch
        )
        other_link = _link(workspace, other_project, child_page)
        ProjectPageHierarchyState.objects.create(workspace=workspace, project=project)
        service = _service(project, create_user)

        service.archive(str(root.page_id), operation_id=uuid.uuid4())
        service.restore(str(root.page_id), operation_id=uuid.uuid4())

        root.refresh_from_db()
        child.refresh_from_db()
        pre_archived.refresh_from_db()
        other_link.refresh_from_db()
        assert root.archived_at is None
        assert child.archived_at is None
        assert pre_archived.archived_at is not None
        assert pre_archived.archive_batch_id == old_batch
        assert other_link.archived_at is None

    def test_bulk_selection_rejects_overlap_before_writes(self, workspace, create_user):
        project = _project(workspace, "OVERLAP")
        root = _link(workspace, project, _page(workspace, create_user, "Root"))
        child = _link(workspace, project, _page(workspace, create_user, "Child"), parent=root)
        state = ProjectPageHierarchyState.objects.create(workspace=workspace, project=project)
        service = _service(project, create_user)

        with pytest.raises(ProjectPageHierarchyError) as error:
            service.bulk_archive([str(root.page_id), str(child.page_id)], operation_id=uuid.uuid4())

        assert error.value.code == "overlapping_selection"
        root.refresh_from_db()
        child.refresh_from_db()
        state.refresh_from_db()
        assert root.archived_at is None
        assert child.archived_at is None
        assert state.revision == 0

    def test_bulk_move_keeps_roots_contiguous_and_subtrees_intact(self, workspace, create_user):
        project = _project(workspace, "BULKMOVE")
        first = _link(workspace, project, _page(workspace, create_user, "First"), order=10)
        first_child = _link(workspace, project, _page(workspace, create_user, "First child"), parent=first)
        second = _link(workspace, project, _page(workspace, create_user, "Second"), order=20)
        destination = _link(workspace, project, _page(workspace, create_user, "Destination"), order=30)
        existing = _link(workspace, project, _page(workspace, create_user, "Existing"), parent=destination, order=10)
        ProjectPageHierarchyState.objects.create(workspace=workspace, project=project)

        result = _service(project, create_user).bulk_move(
            [str(second.page_id), str(first.page_id)],
            parent_page_id=str(destination.page_id),
            position="before",
            relative_page_id=str(existing.page_id),
            operation_id=uuid.uuid4(),
        )

        first.refresh_from_db()
        second.refresh_from_db()
        first_child.refresh_from_db()
        assert [item["id"] for item in result["siblings"]] == [
            str(first.page_id),
            str(second.page_id),
            str(existing.page_id),
        ]
        assert first.parent_id == destination.id
        assert second.parent_id == destination.id
        assert first_child.parent_id == first.id

    def test_copy_subtree_is_hidden_until_asset_copy_finishes(self, workspace, create_user):
        project = _project(workspace, "COPY")
        root = _link(workspace, project, _page(workspace, create_user, "Root"), order=10)
        child = _link(workspace, project, _page(workspace, create_user, "Child"), parent=root, order=20)
        ProjectPageHierarchyState.objects.create(workspace=workspace, project=project)
        operation_id = uuid.uuid4()

        result = _service(project, create_user).copy_subtrees([str(root.page_id)], operation_id=operation_id)

        copied_links = list(
            ProjectPage.objects.filter(id__in=result["project_page_ids"]).select_related("page").order_by("sort_order")
        )
        copied_root = next(link for link in copied_links if link.parent_id is None)
        copied_child = next(link for link in copied_links if link.parent_id is not None)
        mutation = ProjectPageHierarchyMutation.objects.get(operation_id=operation_id)
        assert result["asset_copy_state"] == "pending"
        assert copied_root.page.name == "Root (Copy)"
        assert copied_child.page.name == "Child"
        assert copied_child.parent_id == copied_root.id
        assert all(link.archived_at is not None for link in copied_links)
        assert mutation.outcome == "pending"

    def test_copy_subtree_is_published_only_after_every_asset_copy_succeeds(self, workspace, create_user):
        project = _project(workspace, "COPYSUCCESS")
        root = _link(workspace, project, _page(workspace, create_user, "Root"))
        _link(workspace, project, _page(workspace, create_user, "Child"), parent=root)
        state = ProjectPageHierarchyState.objects.create(workspace=workspace, project=project)
        operation_id = uuid.uuid4()

        result = _service(project, create_user).copy_subtrees([str(root.page_id)], operation_id=operation_id)
        mutation = ProjectPageHierarchyMutation.objects.get(operation_id=operation_id)

        _finish_hierarchy_copy(mutation.id, failed=False)
        mutation.refresh_from_db()
        assert mutation.outcome == "pending"
        assert mutation.result["pending_asset_copies"] == 1
        assert ProjectPage.objects.filter(id__in=result["project_page_ids"], archived_at__isnull=True).count() == 0

        _finish_hierarchy_copy(mutation.id, failed=False)
        mutation.refresh_from_db()
        state.refresh_from_db()
        assert mutation.outcome == "success"
        assert mutation.result["asset_copy_state"] == "ready"
        assert mutation.result["pending_asset_copies"] == 0
        assert ProjectPage.objects.filter(id__in=result["project_page_ids"], archived_at__isnull=True).count() == 2
        assert state.revision == 2

    def test_copy_subtree_failure_is_recoverable_and_never_publishes_partial_tree(self, workspace, create_user):
        project = _project(workspace, "COPYFAIL")
        root = _link(workspace, project, _page(workspace, create_user, "Root"))
        _link(workspace, project, _page(workspace, create_user, "Child"), parent=root)
        ProjectPageHierarchyState.objects.create(workspace=workspace, project=project)
        operation_id = uuid.uuid4()

        result = _service(project, create_user).copy_subtrees([str(root.page_id)], operation_id=operation_id)
        mutation = ProjectPageHierarchyMutation.objects.get(operation_id=operation_id)
        _finish_hierarchy_copy(mutation.id, failed=True)
        _finish_hierarchy_copy(mutation.id, failed=False)

        mutation.refresh_from_db()
        assert mutation.outcome == "recoverable_failure"
        assert mutation.result["asset_copy_state"] == "failed"
        assert mutation.result["pending_asset_copies"] == 0
        assert ProjectPage.objects.filter(id__in=result["project_page_ids"], archived_at__isnull=True).count() == 0

    def test_remove_subtree_preserves_pages_with_other_active_project_links(self, workspace, create_user):
        project = _project(workspace, "REMOVE")
        other_project = _project(workspace, "SURVIVE")
        batch_id = uuid.uuid4()
        root_page = _page(workspace, create_user, "Exclusive root")
        child_page = _page(workspace, create_user, "Shared child")
        root = _link(
            workspace,
            project,
            root_page,
            archived_at="2026-01-01T00:00:00Z",
            archive_batch_id=batch_id,
        )
        child = _link(
            workspace,
            project,
            child_page,
            parent=root,
            archived_at="2026-01-01T00:00:00Z",
            archive_batch_id=batch_id,
        )
        other_link = _link(workspace, other_project, child_page)
        exclusive_recent = UserRecentVisit.objects.create(
            workspace=workspace,
            user=create_user,
            entity_name="page",
            entity_identifier=root_page.id,
        )
        shared_recent = UserRecentVisit.objects.create(
            workspace=workspace,
            user=create_user,
            entity_name="page",
            entity_identifier=child_page.id,
        )
        ProjectPageHierarchyState.objects.create(workspace=workspace, project=project)

        result = _service(project, create_user).remove_subtrees([str(root.page_id)], operation_id=uuid.uuid4())

        assert str(root_page.id) in result["deleted_page_ids"]
        assert str(child_page.id) in result["preserved_page_ids"]
        assert Page.all_objects.get(id=root_page.id).deleted_at is not None
        assert Page.objects.filter(id=child_page.id).exists()
        assert ProjectPage.all_objects.get(id=root.id).deleted_at is not None
        assert ProjectPage.all_objects.get(id=child.id).deleted_at is not None
        other_link.refresh_from_db()
        assert other_link.deleted_at is None
        assert not UserRecentVisit.objects.filter(id=exclusive_recent.id).exists()
        assert UserRecentVisit.objects.filter(id=shared_recent.id).exists()
