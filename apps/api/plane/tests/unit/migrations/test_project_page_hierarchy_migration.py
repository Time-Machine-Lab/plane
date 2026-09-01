# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import importlib
from types import SimpleNamespace

import pytest
from django.apps import apps
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone

from plane.db.models import Page, Project, ProjectPage, ProjectPageHierarchyState


migration = importlib.import_module("plane.db.migrations.0124_project_page_hierarchy")


def _project(workspace, suffix):
    return Project.objects.create(
        name=f"Migration {suffix}",
        identifier=f"M{suffix}"[:12],
        workspace=workspace,
    )


def _page(workspace, owner, name, *, parent=None, order=0, archived_at=None):
    return Page.objects.create(
        workspace=workspace,
        owned_by=owner,
        name=name,
        description_html=f"<p>{name} content</p>",
        parent=parent,
        sort_order=order,
        archived_at=archived_at,
    )


def _link(workspace, project, page):
    return ProjectPage.objects.create(workspace=workspace, project=project, page=page)


def _run_backfill():
    migration.backfill_project_page_hierarchy(apps, SimpleNamespace(connection=connection))


def _depth(link):
    seen = set()
    value = 1
    while link.parent_id:
        assert link.id not in seen
        seen.add(link.id)
        link = ProjectPage.objects.get(id=link.parent_id)
        value += 1
    return value


@pytest.mark.unit
@pytest.mark.django_db
class TestProjectPageHierarchyMigration:
    def test_backfill_preserves_valid_nesting_order_archive_content_and_ids(self, workspace, create_user, caplog):
        project = _project(workspace, "VALID")
        archived_at = timezone.now()
        root = _page(workspace, create_user, "Root", order=10)
        child = _page(workspace, create_user, "Child", parent=root, order=20, archived_at=archived_at)
        root_link = _link(workspace, project, root)
        child_link = _link(workspace, project, child)
        original = {page.id: page.description_html for page in (root, child)}

        with caplog.at_level("INFO", logger="plane.migrations.project_page_hierarchy"):
            _run_backfill()

        root_link.refresh_from_db()
        child_link.refresh_from_db()
        assert root_link.parent_id is None
        assert child_link.parent_id == root_link.id
        assert root_link.sort_order == root.sort_order
        assert child_link.sort_order == child.sort_order
        assert child_link.archived_at == archived_at
        assert ProjectPageHierarchyState.objects.filter(project=project).count() == 1
        assert {page.id: page.description_html for page in Page.objects.filter(id__in=original)} == original
        assert "Project Page hierarchy backfill complete" in caplog.text

    def test_backfill_repairs_missing_cross_project_and_cyclic_parents_deterministically(
        self, workspace, create_user
    ):
        first_project = _project(workspace, "FIRST")
        second_project = _project(workspace, "SECOND")
        foreign_parent = _page(workspace, create_user, "Foreign")
        cross_project_child = _page(workspace, create_user, "Cross project", parent=foreign_parent)
        missing_parent = _page(workspace, create_user, "Missing parent")
        missing_child = _page(workspace, create_user, "Missing child", parent=missing_parent)
        cycle_a = _page(workspace, create_user, "Cycle A")
        cycle_b = _page(workspace, create_user, "Cycle B", parent=cycle_a)
        Page.objects.filter(id=cycle_a.id).update(parent=cycle_b)
        _link(workspace, second_project, foreign_parent)
        repaired = [
            _link(workspace, first_project, cross_project_child),
            _link(workspace, first_project, missing_child),
            _link(workspace, first_project, cycle_a),
            _link(workspace, first_project, cycle_b),
        ]

        _run_backfill()
        first_result = list(
            ProjectPage.objects.filter(id__in=[item.id for item in repaired])
            .order_by("id")
            .values_list("id", "parent_id")
        )
        _run_backfill()
        second_result = list(
            ProjectPage.objects.filter(id__in=[item.id for item in repaired])
            .order_by("id")
            .values_list("id", "parent_id")
        )

        assert first_result == second_result
        cross_link = ProjectPage.objects.get(project=first_project, page=cross_project_child)
        missing_link = ProjectPage.objects.get(project=first_project, page=missing_child)
        assert cross_link.parent_id is None
        assert missing_link.parent_id is None
        assert max(_depth(ProjectPage.objects.get(id=item.id)) for item in repaired) <= 2

    def test_backfill_caps_legacy_depth_and_keeps_multi_project_placements_independent(
        self, workspace, create_user
    ):
        first_project = _project(workspace, "DEEPA")
        second_project = _project(workspace, "DEEPB")
        parent = None
        pages = []
        for index in range(migration.MAX_DEPTH + 3):
            parent = _page(workspace, create_user, f"Level {index}", parent=parent, order=index)
            pages.append(parent)
            _link(workspace, first_project, parent)
        shared = pages[-1]
        second_link = _link(workspace, second_project, shared)

        _run_backfill()

        first_links = list(ProjectPage.objects.filter(project=first_project))
        assert max(_depth(item) for item in first_links) <= migration.MAX_DEPTH
        second_link.refresh_from_db()
        assert second_link.parent_id is None
        assert ProjectPageHierarchyState.objects.filter(project__in=[first_project, second_project]).count() == 2

    def test_reverse_callback_never_changes_legacy_page_data(self, workspace, create_user, caplog):
        project = _project(workspace, "REVERSE")
        page = _page(workspace, create_user, "Durable", order=42)
        original_id = page.id
        original_content = page.description_html
        _link(workspace, project, page)
        _run_backfill()

        with caplog.at_level("INFO", logger="plane.migrations.project_page_hierarchy"):
            migration.reverse_backfill(apps, SimpleNamespace(connection=connection))

        page.refresh_from_db()
        assert page.id == original_id
        assert page.description_html == original_content
        assert page.sort_order == 42
        assert "legacy Page hierarchy and content remain unchanged" in caplog.text


def _column_names(table_name):
    with connection.cursor() as cursor:
        return {column.name for column in connection.introspection.get_table_description(cursor, table_name)}


@pytest.mark.unit
@pytest.mark.django_db(transaction=True)
def test_schema_reverse_and_reapply_preserve_legacy_page_hierarchy_columns():
    previous = [("db", "0123_mutica_agent_delegation")]
    target = [("db", "0124_project_page_hierarchy")]
    try:
        MigrationExecutor(connection).migrate(previous)
        tables = set(connection.introspection.table_names())
        project_page_columns = _column_names("project_pages")
        page_columns = _column_names("pages")

        assert "project_page_hierarchy_states" not in tables
        assert "project_page_hierarchy_mutations" not in tables
        assert {"parent_id", "sort_order", "archived_at", "archive_batch_id"}.isdisjoint(project_page_columns)
        assert {"parent_id", "sort_order", "archived_at"}.issubset(page_columns)
    finally:
        MigrationExecutor(connection).migrate(target)

    tables = set(connection.introspection.table_names())
    project_page_columns = _column_names("project_pages")
    assert "project_page_hierarchy_states" in tables
    assert "project_page_hierarchy_mutations" in tables
    assert {"parent_id", "sort_order", "archived_at", "archive_batch_id"}.issubset(project_page_columns)
