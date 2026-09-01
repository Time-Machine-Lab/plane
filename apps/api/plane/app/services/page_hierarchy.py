# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import copy
import os
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any

from django.db import connection, transaction
from django.db.models import F
from django.utils import timezone

from plane.db.models import (
    Page,
    PageLabel,
    ProjectPage,
    ProjectPageHierarchyMutation,
    ProjectPageHierarchyState,
    UserFavorite,
    UserRecentVisit,
)
from plane.license.utils.instance_value import get_configuration_value


MAX_HIERARCHY_DEPTH = 20
ORDER_STEP = 10000.0


def is_project_page_hierarchy_enabled() -> bool:
    (enabled,) = get_configuration_value(
        [
            {
                "key": "ENABLE_PROJECT_PAGE_HIERARCHY",
                "default": os.environ.get("ENABLE_PROJECT_PAGE_HIERARCHY", "1"),
            }
        ]
    )
    return enabled == "1"


class ProjectPageHierarchyError(Exception):
    def __init__(self, code: str, message: str, *, status_code: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code

    def as_dict(self) -> dict[str, str]:
        return {"error": self.message, "code": self.code}


@dataclass(frozen=True)
class HierarchyContext:
    project_id: str
    workspace_id: str
    user_id: str
    project_role: int | None = None


class ProjectPageHierarchyService:
    """Project-scoped hierarchy reads and atomic mutations.

    Only navigation metadata is selected here. Page bodies deliberately stay
    outside this service so tree reads cannot accidentally become content loads.
    """

    node_page_fields = (
        "id",
        "name",
        "logo_props",
        "access",
        "is_locked",
        "owned_by_id",
        "created_at",
        "updated_at",
    )

    def __init__(self, context: HierarchyContext):
        self.context = context

    @property
    def is_project_admin(self) -> bool:
        return self.context.project_role == 20

    def _links(self, *, include_archived: bool = False):
        queryset = ProjectPage.objects.filter(
            project_id=self.context.project_id,
            workspace_id=self.context.workspace_id,
            deleted_at__isnull=True,
        )
        if not include_archived:
            queryset = queryset.filter(archived_at__isnull=True)
        return queryset.select_related("page", "parent").only(
            "id",
            "project_id",
            "workspace_id",
            "page_id",
            "parent_id",
            "sort_order",
            "archived_at",
            "archive_batch_id",
            "parent__page_id",
            *[f"page__{field}" for field in self.node_page_fields],
        )

    @staticmethod
    def _page_visible(link: ProjectPage, user_id: str) -> bool:
        return link.page.access == Page.PUBLIC_ACCESS or str(link.page.owned_by_id) == str(user_id)

    def _visible_map(self, *, include_archived: bool = False) -> tuple[dict[str, ProjectPage], set[str]]:
        links = list(self._links(include_archived=include_archived))
        by_id = {str(link.id): link for link in links}
        visible: set[str] = set()

        def is_visible(link: ProjectPage) -> bool:
            link_id = str(link.id)
            if link_id in visible:
                return True
            chain: list[ProjectPage] = []
            cursor: ProjectPage | None = link
            seen: set[str] = set()
            while cursor is not None:
                cursor_id = str(cursor.id)
                if cursor_id in visible:
                    visible.update(str(item.id) for item in chain)
                    return True
                if cursor_id in seen or not self._page_visible(cursor, self.context.user_id):
                    return False
                seen.add(cursor_id)
                chain.append(cursor)
                if cursor.parent_id:
                    cursor = by_id.get(str(cursor.parent_id))
                    if cursor is None:
                        return False
                else:
                    cursor = None
            visible.update(str(item.id) for item in chain)
            return True

        for link in links:
            is_visible(link)
        return by_id, visible

    def _state_revision(self) -> int:
        state, _ = ProjectPageHierarchyState.objects.get_or_create(
            project_id=self.context.project_id,
            defaults={"workspace_id": self.context.workspace_id},
        )
        return state.revision

    def _serialize_node(
        self,
        link: ProjectPage,
        *,
        visible_ids: set[str],
        children_by_parent: dict[str | None, list[ProjectPage]],
        depth: int | None = None,
        path: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        visible_children = [child for child in children_by_parent.get(str(link.id), []) if str(child.id) in visible_ids]
        can_manage = self.is_project_admin or str(link.page.owned_by_id) == str(self.context.user_id)
        return {
            "id": str(link.page_id),
            "project_page_id": str(link.id),
            "name": link.page.name,
            "logo_props": link.page.logo_props,
            "access": link.page.access,
            "is_locked": link.page.is_locked,
            "owned_by": str(link.page.owned_by_id),
            "parent_id": str(link.parent.page_id) if getattr(link, "parent", None) else None,
            "sort_order": link.sort_order,
            "archived_at": link.archived_at,
            "has_children": bool(visible_children),
            "child_count": len(visible_children),
            "depth": depth,
            "path": path,
            "created_at": link.page.created_at,
            "updated_at": link.page.updated_at,
            "permissions": {
                "can_create_child": not link.archived_at and self.context.project_role in {15, 20},
                "can_move": not link.archived_at and can_manage,
                "can_archive": not link.archived_at and can_manage,
                "can_restore": bool(link.archived_at) and can_manage,
            },
        }

    def list_children(
        self,
        parent_page_id: str | None,
        *,
        include_archived: bool = False,
        offset: int = 0,
        limit: int = 100,
    ) -> dict[str, Any]:
        by_id, visible_ids = self._visible_map(include_archived=include_archived)
        children_by_parent: dict[str | None, list[ProjectPage]] = defaultdict(list)
        page_to_link = {str(link.page_id): link for link in by_id.values()}
        for link in by_id.values():
            children_by_parent[str(link.parent_id) if link.parent_id else None].append(link)
        for children in children_by_parent.values():
            children.sort(key=lambda item: (item.sort_order, str(item.id)))

        parent_link = None
        parent_key = None
        if parent_page_id:
            parent_link = page_to_link.get(str(parent_page_id))
            if parent_link is None or str(parent_link.id) not in visible_ids:
                raise ProjectPageHierarchyError("page_not_found", "Page not found", status_code=404)
            parent_key = str(parent_link.id)

        children = [item for item in children_by_parent.get(parent_key, []) if str(item.id) in visible_ids]
        total = len(children)
        selected = children[offset : offset + min(max(limit, 1), 200)]
        return {
            "results": [
                self._serialize_node(item, visible_ids=visible_ids, children_by_parent=children_by_parent)
                for item in selected
            ],
            "total_count": total,
            "next_offset": offset + len(selected) if offset + len(selected) < total else None,
            "revision": self._state_revision(),
        }

    def path(self, page_id: str, *, include_archived: bool = False) -> dict[str, Any]:
        active_clause = "AND project_page.archived_at IS NULL" if not include_archived else ""
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                    WITH RECURSIVE ancestors AS (
                        SELECT project_page.id, project_page.parent_id, 1 AS distance
                        FROM project_pages project_page
                        WHERE project_page.page_id = %s
                            AND project_page.project_id = %s
                            AND project_page.workspace_id = %s
                            AND project_page.deleted_at IS NULL
                            {active_clause}

                        UNION ALL

                        SELECT project_page.id, project_page.parent_id, ancestors.distance + 1
                        FROM project_pages project_page
                        INNER JOIN ancestors ON ancestors.parent_id = project_page.id
                        WHERE project_page.project_id = %s
                            AND project_page.workspace_id = %s
                            AND project_page.deleted_at IS NULL
                            AND ancestors.distance < %s
                            {active_clause}
                    )
                    SELECT id, parent_id, distance FROM ancestors ORDER BY distance DESC
                """,
                [
                    page_id,
                    self.context.project_id,
                    self.context.workspace_id,
                    self.context.project_id,
                    self.context.workspace_id,
                    MAX_HIERARCHY_DEPTH,
                ],
            )
            rows = cursor.fetchall()
        if not rows or rows[0][1] is not None:
            raise ProjectPageHierarchyError("page_not_found", "Page not found", status_code=404)
        ordered_link_ids = [str(row[0]) for row in rows]
        if len(set(ordered_link_ids)) != len(ordered_link_ids):
            raise ProjectPageHierarchyError("page_not_found", "Page not found", status_code=404)
        links = {
            str(link.id): link
            for link in self._links(include_archived=include_archived).filter(id__in=ordered_link_ids)
        }
        if len(links) != len(ordered_link_ids):
            raise ProjectPageHierarchyError("page_not_found", "Page not found", status_code=404)
        chain = []
        for link_id in ordered_link_ids:
            link = links[link_id]
            if not self._page_visible(link, self.context.user_id):
                raise ProjectPageHierarchyError("page_not_found", "Page not found", status_code=404)
            chain.append({"id": str(link.page_id), "name": link.page.name, "logo_props": link.page.logo_props})
        return {"path": chain, "depth": len(chain), "revision": self._state_revision()}

    def all_pages(self, *, include_archived: bool = True) -> list[dict[str, Any]]:
        by_id, visible_ids = self._visible_map(include_archived=include_archived)
        children_by_parent: dict[str | None, list[ProjectPage]] = defaultdict(list)
        for link in by_id.values():
            children_by_parent[str(link.parent_id) if link.parent_id else None].append(link)

        path_cache: dict[str, list[dict[str, Any]]] = {}

        def build_path(link: ProjectPage) -> list[dict[str, Any]]:
            link_id = str(link.id)
            cached = path_cache.get(link_id)
            if cached is not None:
                return cached
            lineage: list[ProjectPage] = []
            cursor: ProjectPage | None = link
            while cursor is not None and str(cursor.id) not in path_cache:
                lineage.append(cursor)
                cursor = by_id.get(str(cursor.parent_id)) if cursor.parent_id else None
            prefix = list(path_cache.get(str(cursor.id), [])) if cursor is not None else []
            for item in reversed(lineage):
                prefix = [
                    *prefix,
                    {"id": str(item.page_id), "name": item.page.name, "logo_props": item.page.logo_props},
                ]
                path_cache[str(item.id)] = prefix
            return path_cache[link_id]

        results = []
        for link in by_id.values():
            if str(link.id) not in visible_ids:
                continue
            path = build_path(link)
            results.append(
                self._serialize_node(
                    link,
                    visible_ids=visible_ids,
                    children_by_parent=children_by_parent,
                    depth=len(path),
                    path=path,
                )
            )
        return sorted(results, key=lambda item: (item["sort_order"], item["id"]))

    def all_pages_paginated(
        self,
        *,
        include_archived: bool = True,
        offset: int = 0,
        limit: int = 50,
        search: str = "",
        access: int | None = None,
        locked: bool | None = None,
        owner_id: str | None = None,
        archive_state: str = "all",
        sort_by: str = "updated_at",
        sort_order: str = "desc",
    ) -> dict[str, Any]:
        allowed_sort_fields = {"name", "created_at", "updated_at", "depth", "path", "sort_order"}
        if sort_by not in allowed_sort_fields or sort_order not in {"asc", "desc"}:
            raise ProjectPageHierarchyError("invalid_sort", "Unsupported All Pages sorting")
        if archive_state not in {"all", "active", "archived"}:
            raise ProjectPageHierarchyError("invalid_archive_filter", "Unsupported archive filter")

        active_clause = "AND pp.archived_at IS NULL" if not include_archived else ""
        hierarchy_cte = f"""
            WITH RECURSIVE hierarchy AS (
                SELECT
                    pp.id AS link_id,
                    pp.page_id,
                    pp.parent_id,
                    pp.sort_order,
                    pp.archived_at,
                    p.name,
                    p.access,
                    p.is_locked,
                    p.owned_by_id,
                    p.created_at,
                    p.updated_at,
                    CAST(pp.id AS TEXT) AS path_link_ids,
                    p.name AS path_text,
                    1 AS depth,
                    (p.access = 0 OR p.owned_by_id = %s) AS is_visible
                FROM project_pages pp
                INNER JOIN pages p ON p.id = pp.page_id AND p.deleted_at IS NULL
                WHERE pp.project_id = %s
                    AND pp.workspace_id = %s
                    AND pp.deleted_at IS NULL
                    AND pp.parent_id IS NULL
                    {active_clause}

                UNION ALL

                SELECT
                    pp.id AS link_id,
                    pp.page_id,
                    pp.parent_id,
                    pp.sort_order,
                    pp.archived_at,
                    p.name,
                    p.access,
                    p.is_locked,
                    p.owned_by_id,
                    p.created_at,
                    p.updated_at,
                    hierarchy.path_link_ids || ',' || CAST(pp.id AS TEXT),
                    hierarchy.path_text || ' / ' || p.name,
                    hierarchy.depth + 1,
                    (hierarchy.is_visible AND (p.access = 0 OR p.owned_by_id = %s))
                FROM project_pages pp
                INNER JOIN pages p ON p.id = pp.page_id AND p.deleted_at IS NULL
                INNER JOIN hierarchy ON hierarchy.link_id = pp.parent_id
                WHERE pp.project_id = %s
                    AND pp.workspace_id = %s
                    AND pp.deleted_at IS NULL
                    AND hierarchy.depth < %s
                    {active_clause}
            )
        """
        cte_params = [
            self.context.user_id,
            self.context.project_id,
            self.context.workspace_id,
            self.context.user_id,
            self.context.project_id,
            self.context.workspace_id,
            MAX_HIERARCHY_DEPTH,
        ]
        where_clauses = ["hierarchy.is_visible"]
        filter_params: list[Any] = []
        normalized_search = search.strip().lower()
        if normalized_search:
            where_clauses.append("(LOWER(hierarchy.name) LIKE %s OR LOWER(hierarchy.path_text) LIKE %s)")
            search_pattern = f"%{normalized_search}%"
            filter_params.extend([search_pattern, search_pattern])
        if access is not None:
            where_clauses.append("hierarchy.access = %s")
            filter_params.append(access)
        if locked is not None:
            where_clauses.append("hierarchy.is_locked = %s")
            filter_params.append(locked)
        if owner_id:
            where_clauses.append("hierarchy.owned_by_id = %s")
            filter_params.append(owner_id)
        if archive_state == "active":
            where_clauses.append("hierarchy.archived_at IS NULL")
        elif archive_state == "archived":
            where_clauses.append("hierarchy.archived_at IS NOT NULL")

        where_sql = " AND ".join(where_clauses)
        sort_expressions = {
            "name": "LOWER(hierarchy.name)",
            "created_at": "hierarchy.created_at",
            "updated_at": "hierarchy.updated_at",
            "depth": "hierarchy.depth",
            "path": "LOWER(hierarchy.path_text)",
            "sort_order": "hierarchy.sort_order",
        }
        direction = "ASC" if sort_order == "asc" else "DESC"
        page_limit = min(max(limit, 1), 200)
        with connection.cursor() as cursor:
            cursor.execute(
                f"{hierarchy_cte} SELECT COUNT(*) FROM hierarchy WHERE {where_sql}",
                [*cte_params, *filter_params],
            )
            total = cursor.fetchone()[0]
            cursor.execute(
                f"""
                    {hierarchy_cte}
                    SELECT link_id, page_id, path_link_ids, depth
                    FROM hierarchy
                    WHERE {where_sql}
                    ORDER BY {sort_expressions[sort_by]} {direction}, page_id {direction}
                    LIMIT %s OFFSET %s
                """,
                [*cte_params, *filter_params, page_limit, offset],
            )
            rows = cursor.fetchall()

        selected_link_ids = [str(row[0]) for row in rows]
        path_link_ids_by_selected = {
            str(row[0]): str(row[2]).split(",") if row[2] else [] for row in rows
        }
        depth_by_selected = {str(row[0]): int(row[3]) for row in rows}
        required_link_ids = {
            link_id for path_link_ids in path_link_ids_by_selected.values() for link_id in path_link_ids
        }
        links = list(self._links(include_archived=include_archived).filter(id__in=required_link_ids))
        links_by_id = {str(link.id): link for link in links}
        selected_links = [links_by_id[link_id] for link_id in selected_link_ids if link_id in links_by_id]

        child_links = list(
            self._links(include_archived=include_archived).filter(parent_id__in=[link.id for link in selected_links])
        )
        visible_children = [child for child in child_links if self._page_visible(child, self.context.user_id)]
        children_by_parent: dict[str | None, list[ProjectPage]] = defaultdict(list)
        for child in visible_children:
            children_by_parent[str(child.parent_id)].append(child)
        visible_ids = {*required_link_ids, *[str(child.id) for child in visible_children]}
        selected = []
        for link in selected_links:
            path = [
                {
                    "id": str(links_by_id[path_link_id].page_id),
                    "name": links_by_id[path_link_id].page.name,
                    "logo_props": links_by_id[path_link_id].page.logo_props,
                }
                for path_link_id in path_link_ids_by_selected[str(link.id)]
                if path_link_id in links_by_id
            ]
            selected.append(
                self._serialize_node(
                    link,
                    visible_ids=visible_ids,
                    children_by_parent=children_by_parent,
                    depth=depth_by_selected[str(link.id)],
                    path=path,
                )
            )
        return {
            "results": selected,
            "total_count": total,
            "next_offset": offset + len(rows) if offset + len(rows) < total else None,
            "revision": self._state_revision(),
        }

    def descendants(self, root: ProjectPage, *, include_archived: bool = True) -> list[ProjectPage]:
        links = list(self._links(include_archived=include_archived))
        children: dict[str, list[ProjectPage]] = defaultdict(list)
        for link in links:
            if link.parent_id:
                children[str(link.parent_id)].append(link)
        result = []
        queue = deque(children.get(str(root.id), []))
        while queue:
            item = queue.popleft()
            result.append(item)
            queue.extend(children.get(str(item.id), []))
        return result

    def preview(self, page_id: str, operation: str) -> dict[str, Any]:
        return self.preview_bulk([page_id], "remove" if operation == "delete" else operation)

    def _resolve_selection(
        self,
        page_ids: list[str],
        *,
        include_archived: bool = True,
        lock: bool = False,
    ) -> list[ProjectPage]:
        normalized = [str(page_id) for page_id in page_ids]
        if not normalized:
            raise ProjectPageHierarchyError("empty_selection", "Select at least one page")
        if len(set(normalized)) != len(normalized):
            raise ProjectPageHierarchyError("duplicate_selection", "The selection contains duplicate pages")
        roots = [self._resolve_link(page_id, include_archived=include_archived, lock=lock) for page_id in normalized]
        selected_link_ids = {str(root.id) for root in roots}
        for root in roots:
            descendant_ids = {str(item.id) for item in self.descendants(root)}
            if descendant_ids & (selected_link_ids - {str(root.id)}):
                raise ProjectPageHierarchyError(
                    "overlapping_selection",
                    "Select either a parent page or its descendant, not both",
                )
        return roots

    def preview_bulk(
        self,
        page_ids: list[str],
        operation: str,
        *,
        parent_page_id: str | None = None,
        position: str = "last",
        relative_page_id: str | None = None,
    ) -> dict[str, Any]:
        if operation not in {"move", "archive", "restore", "copy", "remove"}:
            raise ProjectPageHierarchyError("invalid_operation", "Unsupported hierarchy operation")
        include_archived = operation in {"archive", "restore", "remove"}
        roots = self._resolve_selection(page_ids, include_archived=include_archived)
        selected_ids = {root.id for root in roots}
        if operation == "copy" and self.context.project_role not in {15, 20}:
            raise ProjectPageHierarchyError("insufficient_permission", "Page creation permission is required", status_code=403)
        for root in roots:
            if operation != "copy":
                self._validate_manage_permission(root)
            if operation == "archive" and root.archived_at:
                raise ProjectPageHierarchyError("already_archived", "The selection contains an archived page")
            if operation == "restore":
                if root.archived_at is None or root.archive_batch_id is None:
                    raise ProjectPageHierarchyError("not_archived", "The selection contains a page that cannot be restored")
                if root.parent_id and root.parent_id not in selected_ids:
                    parent = ProjectPage.objects.filter(id=root.parent_id, deleted_at__isnull=True).first()
                    if parent and parent.archived_at:
                        raise ProjectPageHierarchyError("archived_ancestor", "Restore the highest archived ancestor first")
            if operation == "remove":
                if root.archived_at is None:
                    raise ProjectPageHierarchyError("not_archived", "Pages must be archived before permanent removal")
                if any(link.archived_at is None for link in self.descendants(root)):
                    raise ProjectPageHierarchyError(
                        "active_descendant",
                        "Archive the complete subtree before permanent removal",
                    )

        if operation == "move":
            parent = self._resolve_link(parent_page_id) if parent_page_id else None
            for root in roots:
                descendants = self.descendants(root)
                if parent and (parent.id == root.id or parent.id in {item.id for item in descendants}):
                    raise ProjectPageHierarchyError("hierarchy_cycle", "A page cannot be moved below its subtree")
                self._validate_visibility(root, parent)
                parent_depth = self._depth(parent) if parent else 0
                if parent_depth + self._subtree_height(root) > MAX_HIERARCHY_DEPTH:
                    raise ProjectPageHierarchyError(
                        "maximum_depth_exceeded",
                        f"The maximum hierarchy depth is {MAX_HIERARCHY_DEPTH}",
                    )
            if position in {"before", "after"}:
                if not relative_page_id:
                    raise ProjectPageHierarchyError("relative_page_required", "A relative page is required")
                relative = self._resolve_link(relative_page_id)
                if relative.id in selected_ids or relative.parent_id != (parent.id if parent else None):
                    raise ProjectPageHierarchyError(
                        "invalid_relative_page",
                        "The relative page is not a destination sibling",
                    )
            elif position not in {"first", "inside", "last"}:
                raise ProjectPageHierarchyError("invalid_position", "Unsupported placement position")

        affected: list[ProjectPage] = []
        seen: set[str] = set()
        for root in roots:
            for link in [root, *self.descendants(root)]:
                if operation == "archive" and link.archived_at is not None:
                    continue
                if operation == "restore" and link.archive_batch_id != root.archive_batch_id:
                    continue
                if str(link.id) not in seen:
                    affected.append(link)
                    seen.add(str(link.id))
        return {
            "operation": operation,
            "root_page_ids": [str(root.page_id) for root in roots],
            "descendant_count": len(affected) - len(roots),
            "affected_count": len(affected),
            "page_ids": [str(item.page_id) for item in affected],
            "revision": self._state_revision(),
        }

    def _resolve_link(self, page_id: str, *, include_archived: bool = False, lock: bool = False) -> ProjectPage:
        queryset = self._links(include_archived=include_archived)
        if lock:
            queryset = queryset.select_for_update(of=("self",))
        link = queryset.filter(page_id=page_id).first()
        _, visible_ids = self._visible_map(include_archived=include_archived)
        if link is None or str(link.id) not in visible_ids:
            raise ProjectPageHierarchyError("page_not_found", "Page not found", status_code=404)
        return link

    def validate_access_change(self, page_id: str, access: int) -> None:
        links = list(
            ProjectPage.objects.filter(
                page_id=page_id,
                workspace_id=self.context.workspace_id,
                deleted_at__isnull=True,
            ).select_related("page", "parent__page")
        )
        if not links:
            raise ProjectPageHierarchyError("page_not_found", "Page not found", status_code=404)
        if access == Page.PUBLIC_ACCESS:
            for link in links:
                if link.parent_id and link.parent.page.access == Page.PRIVATE_ACCESS:
                    raise ProjectPageHierarchyError(
                        "visibility_inheritance",
                        "A child page cannot be more visible than its parent",
                    )
            return

        owner_id = links[0].page.owned_by_id
        project_ids = {link.project_id for link in links}
        project_links = list(
            ProjectPage.objects.filter(
                project_id__in=project_ids,
                workspace_id=self.context.workspace_id,
                deleted_at__isnull=True,
            ).select_related("page")
        )
        children_by_parent: dict[str, list[ProjectPage]] = defaultdict(list)
        for project_link in project_links:
            if project_link.parent_id:
                children_by_parent[str(project_link.parent_id)].append(project_link)
        for root in links:
            queue = deque(children_by_parent.get(str(root.id), []))
            while queue:
                descendant = queue.popleft()
                if descendant.page.access != Page.PRIVATE_ACCESS:
                    raise ProjectPageHierarchyError(
                        "visibility_inheritance",
                        "Make descendant pages private before making this page private",
                    )
                if descendant.page.owned_by_id != owner_id:
                    raise ProjectPageHierarchyError(
                        "private_owner_mismatch",
                        "Private pages in the same branch must have the same owner",
                    )
                queue.extend(children_by_parent.get(str(descendant.id), []))

    def _validate_manage_permission(self, link: ProjectPage) -> None:
        if not self.is_project_admin and str(link.page.owned_by_id) != str(self.context.user_id):
            raise ProjectPageHierarchyError(
                "insufficient_permission",
                "Only the page owner or a project administrator can change this hierarchy",
                status_code=403,
            )

    def _lock_state(self) -> ProjectPageHierarchyState:
        ProjectPageHierarchyState.objects.get_or_create(
            project_id=self.context.project_id,
            defaults={"workspace_id": self.context.workspace_id},
        )
        return ProjectPageHierarchyState.objects.select_for_update().get(project_id=self.context.project_id)

    def _record(
        self,
        *,
        operation_id: uuid.UUID,
        operation: str,
        root: ProjectPage | None,
        revision: int,
        result: dict[str, Any],
        old_parent_id: str | None = None,
        new_parent_id: str | None = None,
        descendant_count: int = 0,
        outcome: str = "success",
    ) -> None:
        ProjectPageHierarchyMutation.objects.create(
            project_id=self.context.project_id,
            workspace_id=self.context.workspace_id,
            actor_id=self.context.user_id,
            operation_id=operation_id,
            operation=operation,
            outcome=outcome,
            root_page_id=root.page_id if root else None,
            old_parent_page_id=old_parent_id,
            new_parent_page_id=new_parent_id,
            descendant_count=descendant_count,
            revision=revision,
            result=result,
        )

    def record_failure(
        self,
        *,
        operation_id: uuid.UUID,
        operation: str,
        error: ProjectPageHierarchyError,
        root_page_id: str | None = None,
    ) -> None:
        ProjectPageHierarchyMutation.objects.update_or_create(
            project_id=self.context.project_id,
            actor_id=self.context.user_id,
            operation_id=operation_id,
            defaults={
                "workspace_id": self.context.workspace_id,
                "operation": operation,
                "outcome": "validation_failure",
                "root_page_id": root_page_id,
                "descendant_count": 0,
                "revision": self._state_revision(),
                "result": {"code": error.code, "status_code": error.status_code},
            },
        )

    def _idempotent_result(self, operation_id: uuid.UUID) -> dict[str, Any] | None:
        mutation = ProjectPageHierarchyMutation.objects.filter(
            project_id=self.context.project_id,
            actor_id=self.context.user_id,
            operation_id=operation_id,
        ).first()
        if mutation is None:
            return None
        if mutation.outcome == "validation_failure":
            raise ProjectPageHierarchyError(
                mutation.result.get("code", "validation_failed"),
                "The hierarchy operation was previously rejected",
                status_code=mutation.result.get("status_code", 400),
            )
        return mutation.result

    @staticmethod
    def _validate_visibility(child: ProjectPage, parent: ProjectPage | None) -> None:
        if parent is None:
            return
        if parent.page.access == Page.PRIVATE_ACCESS:
            if child.page.access != Page.PRIVATE_ACCESS:
                raise ProjectPageHierarchyError(
                    "visibility_inheritance",
                    "A child page cannot be more visible than its parent",
                )
            if child.page.owned_by_id != parent.page.owned_by_id:
                raise ProjectPageHierarchyError(
                    "private_owner_mismatch",
                    "Private pages in the same branch must have the same owner",
                )

    def _depth(self, link: ProjectPage) -> int:
        depth = 1
        cursor = link
        seen = {str(link.id)}
        while cursor.parent_id:
            cursor = ProjectPage.objects.filter(
                id=cursor.parent_id,
                project_id=self.context.project_id,
                workspace_id=self.context.workspace_id,
                deleted_at__isnull=True,
            ).only("id", "parent_id").first()
            if cursor is None or str(cursor.id) in seen:
                raise ProjectPageHierarchyError("invalid_hierarchy", "The hierarchy is invalid")
            seen.add(str(cursor.id))
            depth += 1
            if depth > MAX_HIERARCHY_DEPTH:
                break
        return depth

    def _subtree_height(self, root: ProjectPage) -> int:
        descendants = self.descendants(root)
        parent_by_id = {str(item.id): str(item.parent_id) if item.parent_id else None for item in descendants}
        parent_by_id[str(root.id)] = None
        maximum = 1
        for item in descendants:
            height = 1
            cursor = parent_by_id[str(item.id)]
            while cursor and cursor != str(root.id):
                height += 1
                cursor = parent_by_id.get(cursor)
            maximum = max(maximum, height + 1)
        return maximum

    @staticmethod
    def _bump_locked_state(state: ProjectPageHierarchyState) -> int:
        state.revision = F("revision") + 1
        state.save(update_fields=["revision", "updated_at"])
        state.refresh_from_db(fields=["revision"])
        return state.revision

    def _compact_parent(self, parent_id: uuid.UUID | None, *, exclude_ids: set[uuid.UUID] | None = None) -> None:
        siblings = list(
            ProjectPage.objects.select_for_update()
            .filter(
                project_id=self.context.project_id,
                workspace_id=self.context.workspace_id,
                parent_id=parent_id,
                archived_at__isnull=True,
                deleted_at__isnull=True,
            )
            .exclude(id__in=exclude_ids or set())
            .order_by("sort_order", "id")
        )
        now = timezone.now()
        for index, sibling in enumerate(siblings, start=1):
            sibling.sort_order = index * ORDER_STEP
            sibling.updated_at = now
        if siblings:
            ProjectPage.objects.bulk_update(siblings, ["sort_order", "updated_at"], batch_size=500)

    @transaction.atomic
    def move(
        self,
        page_id: str,
        *,
        parent_page_id: str | None,
        position: str = "last",
        relative_page_id: str | None = None,
        operation_id: uuid.UUID,
        base_revision: int | None = None,
        audit_operation: str = "move",
    ) -> dict[str, Any]:
        replay = self._idempotent_result(operation_id)
        if replay is not None:
            return replay
        state = self._lock_state()
        root = self._resolve_link(page_id, lock=True)
        self._validate_manage_permission(root)
        if root.archived_at:
            raise ProjectPageHierarchyError("archived_node", "Archived pages cannot be moved")
        old_parent_page_id = str(root.parent.page_id) if root.parent_id else None
        parent = self._resolve_link(parent_page_id, lock=True) if parent_page_id else None
        if parent and parent.archived_at:
            raise ProjectPageHierarchyError("archived_parent", "Pages cannot be moved below an archived parent")
        if parent and parent.id == root.id:
            raise ProjectPageHierarchyError("hierarchy_cycle", "A page cannot be its own parent")
        descendants = self.descendants(root)
        if parent and parent.id in {item.id for item in descendants}:
            raise ProjectPageHierarchyError("hierarchy_cycle", "A page cannot be moved below its descendant")
        self._validate_visibility(root, parent)

        parent_depth = self._depth(parent) if parent else 0
        if parent_depth + self._subtree_height(root) > MAX_HIERARCHY_DEPTH:
            raise ProjectPageHierarchyError(
                "maximum_depth_exceeded",
                f"The maximum hierarchy depth is {MAX_HIERARCHY_DEPTH}",
            )

        siblings = list(
            ProjectPage.objects.select_for_update()
            .filter(
                project_id=self.context.project_id,
                workspace_id=self.context.workspace_id,
                parent_id=parent.id if parent else None,
                archived_at__isnull=True,
                deleted_at__isnull=True,
            )
            .exclude(id=root.id)
            .order_by("sort_order", "id")
        )
        insert_at = len(siblings)
        if position in {"before", "after"}:
            if not relative_page_id:
                raise ProjectPageHierarchyError("relative_page_required", "A relative page is required")
            relative_index = next(
                (index for index, item in enumerate(siblings) if str(item.page_id) == str(relative_page_id)),
                None,
            )
            if relative_index is None:
                raise ProjectPageHierarchyError("invalid_relative_page", "The relative page is not a destination sibling")
            insert_at = relative_index + (1 if position == "after" else 0)
        elif position == "first":
            insert_at = 0
        elif position not in {"inside", "last"}:
            raise ProjectPageHierarchyError("invalid_position", "Unsupported placement position")

        siblings.insert(insert_at, root)
        root.parent_id = parent.id if parent else None
        updated_at = timezone.now()
        for index, sibling in enumerate(siblings, start=1):
            sibling.sort_order = index * ORDER_STEP
            sibling.updated_at = updated_at
        ProjectPage.objects.bulk_update(siblings, ["parent", "sort_order", "updated_at"], batch_size=500)

        self._bump_locked_state(state)
        result = {
            "page_id": str(root.page_id),
            "parent_id": str(parent.page_id) if parent else None,
            "revision": state.revision,
            "base_revision": base_revision,
            "siblings": [
                {"id": str(item.page_id), "sort_order": item.sort_order}
                for item in siblings
            ],
        }
        self._record(
            operation_id=operation_id,
            operation=audit_operation,
            root=root,
            revision=state.revision,
            result=result,
            old_parent_id=old_parent_page_id,
            new_parent_id=str(parent.page_id) if parent else None,
            descendant_count=len(descendants),
        )
        return result

    @transaction.atomic
    def archive(self, page_id: str, *, operation_id: uuid.UUID) -> dict[str, Any]:
        replay = self._idempotent_result(operation_id)
        if replay is not None:
            return replay
        state = self._lock_state()
        root = self._resolve_link(page_id, include_archived=True, lock=True)
        self._validate_manage_permission(root)
        if root.archived_at:
            raise ProjectPageHierarchyError("already_archived", "Page is already archived")
        active = [root, *[item for item in self.descendants(root) if item.archived_at is None]]
        now = timezone.now()
        batch_id = uuid.uuid4()
        ProjectPage.objects.filter(id__in=[item.id for item in active]).update(
            archived_at=now,
            archive_batch_id=batch_id,
            updated_at=now,
        )
        self._bump_locked_state(state)
        result = {
            "page_id": str(root.page_id),
            "archived_at": now,
            "archive_batch_id": str(batch_id),
            "affected_count": len(active),
            "revision": state.revision,
        }
        self._record(
            operation_id=operation_id,
            operation="archive",
            root=root,
            revision=state.revision,
            result={**result, "archived_at": now.isoformat()},
            descendant_count=len(active) - 1,
        )
        return result

    @transaction.atomic
    def restore(self, page_id: str, *, operation_id: uuid.UUID) -> dict[str, Any]:
        replay = self._idempotent_result(operation_id)
        if replay is not None:
            return replay
        state = self._lock_state()
        root = self._resolve_link(page_id, include_archived=True, lock=True)
        self._validate_manage_permission(root)
        if root.archived_at is None or root.archive_batch_id is None:
            raise ProjectPageHierarchyError("not_archived", "Page is not part of a restorable archive batch")
        if root.parent_id:
            parent = ProjectPage.objects.filter(id=root.parent_id, deleted_at__isnull=True).first()
            if parent and parent.archived_at:
                raise ProjectPageHierarchyError(
                    "archived_ancestor",
                    "Restore the highest archived ancestor first",
                )
        batch_id = root.archive_batch_id
        restorable = [root, *self.descendants(root)]
        restorable_ids = [item.id for item in restorable if item.archive_batch_id == batch_id]
        now = timezone.now()
        ProjectPage.objects.filter(id__in=restorable_ids).update(
            archived_at=None,
            archive_batch_id=None,
            updated_at=now,
        )
        self._bump_locked_state(state)
        result = {
            "page_id": str(root.page_id),
            "affected_count": len(restorable_ids),
            "revision": state.revision,
        }
        self._record(
            operation_id=operation_id,
            operation="restore",
            root=root,
            revision=state.revision,
            result=result,
            descendant_count=max(len(restorable_ids) - 1, 0),
        )
        return result

    @transaction.atomic
    def bulk_move(
        self,
        page_ids: list[str],
        *,
        parent_page_id: str | None,
        position: str,
        relative_page_id: str | None,
        operation_id: uuid.UUID,
        base_revision: int | None = None,
    ) -> dict[str, Any]:
        replay = self._idempotent_result(operation_id)
        if replay is not None:
            return replay
        state = self._lock_state()
        roots = self._resolve_selection(page_ids, include_archived=False, lock=True)
        for root in roots:
            self._validate_manage_permission(root)
        parent = self._resolve_link(parent_page_id, lock=True) if parent_page_id else None
        if parent and parent.archived_at:
            raise ProjectPageHierarchyError("archived_parent", "Pages cannot be moved below an archived parent")

        selected_ids = {root.id for root in roots}
        old_parent_ids = {root.parent_id for root in roots}
        for root in roots:
            descendants = self.descendants(root)
            if parent and (parent.id == root.id or parent.id in {item.id for item in descendants}):
                raise ProjectPageHierarchyError("hierarchy_cycle", "A page cannot be moved below its subtree")
            self._validate_visibility(root, parent)
            parent_depth = self._depth(parent) if parent else 0
            if parent_depth + self._subtree_height(root) > MAX_HIERARCHY_DEPTH:
                raise ProjectPageHierarchyError(
                    "maximum_depth_exceeded",
                    f"The maximum hierarchy depth is {MAX_HIERARCHY_DEPTH}",
                )

        destination_parent_id = parent.id if parent else None
        siblings = list(
            ProjectPage.objects.select_for_update()
            .filter(
                project_id=self.context.project_id,
                workspace_id=self.context.workspace_id,
                parent_id=destination_parent_id,
                archived_at__isnull=True,
                deleted_at__isnull=True,
            )
            .exclude(id__in=selected_ids)
            .order_by("sort_order", "id")
        )
        insert_at = len(siblings)
        if position in {"before", "after"}:
            if not relative_page_id:
                raise ProjectPageHierarchyError("relative_page_required", "A relative page is required")
            relative_index = next(
                (index for index, item in enumerate(siblings) if str(item.page_id) == str(relative_page_id)),
                None,
            )
            if relative_index is None:
                raise ProjectPageHierarchyError("invalid_relative_page", "The relative page is not a destination sibling")
            insert_at = relative_index + (1 if position == "after" else 0)
        elif position == "first":
            insert_at = 0
        elif position not in {"inside", "last"}:
            raise ProjectPageHierarchyError("invalid_position", "Unsupported placement position")

        ordered_roots = sorted(roots, key=lambda item: (item.sort_order, str(item.id)))
        siblings[insert_at:insert_at] = ordered_roots
        now = timezone.now()
        for index, sibling in enumerate(siblings, start=1):
            sibling.parent_id = destination_parent_id
            sibling.sort_order = index * ORDER_STEP
            sibling.updated_at = now
        ProjectPage.objects.bulk_update(siblings, ["parent", "sort_order", "updated_at"], batch_size=500)
        for old_parent_id in old_parent_ids - {destination_parent_id}:
            self._compact_parent(old_parent_id, exclude_ids=selected_ids)

        revision = self._bump_locked_state(state)
        result = {
            "operation": "move",
            "root_page_ids": [str(root.page_id) for root in ordered_roots],
            "parent_id": str(parent.page_id) if parent else None,
            "revision": revision,
            "base_revision": base_revision,
            "siblings": [{"id": str(item.page_id), "sort_order": item.sort_order} for item in siblings],
        }
        self._record(
            operation_id=operation_id,
            operation="bulk_move",
            root=ordered_roots[0],
            revision=revision,
            result=result,
            new_parent_id=str(parent.page_id) if parent else None,
            descendant_count=sum(len(self.descendants(root)) for root in ordered_roots),
        )
        return result

    @transaction.atomic
    def bulk_archive(self, page_ids: list[str], *, operation_id: uuid.UUID) -> dict[str, Any]:
        replay = self._idempotent_result(operation_id)
        if replay is not None:
            return replay
        state = self._lock_state()
        roots = self._resolve_selection(page_ids, include_archived=True, lock=True)
        active: list[ProjectPage] = []
        seen: set[uuid.UUID] = set()
        for root in roots:
            self._validate_manage_permission(root)
            if root.archived_at:
                raise ProjectPageHierarchyError("already_archived", "The selection contains an archived page")
            for link in [root, *self.descendants(root)]:
                if link.archived_at is None and link.id not in seen:
                    active.append(link)
                    seen.add(link.id)
        now = timezone.now()
        batch_id = uuid.uuid4()
        ProjectPage.objects.filter(id__in=seen).update(
            archived_at=now,
            archive_batch_id=batch_id,
            updated_at=now,
        )
        revision = self._bump_locked_state(state)
        result = {
            "operation": "archive",
            "root_page_ids": [str(root.page_id) for root in roots],
            "affected_count": len(active),
            "archive_batch_id": str(batch_id),
            "archived_at": now.isoformat(),
            "revision": revision,
        }
        self._record(
            operation_id=operation_id,
            operation="bulk_archive",
            root=roots[0],
            revision=revision,
            result=result,
            descendant_count=len(active) - len(roots),
        )
        return result

    @transaction.atomic
    def bulk_restore(self, page_ids: list[str], *, operation_id: uuid.UUID) -> dict[str, Any]:
        replay = self._idempotent_result(operation_id)
        if replay is not None:
            return replay
        state = self._lock_state()
        roots = self._resolve_selection(page_ids, include_archived=True, lock=True)
        restorable_ids: set[uuid.UUID] = set()
        for root in roots:
            self._validate_manage_permission(root)
            if root.archived_at is None or root.archive_batch_id is None:
                raise ProjectPageHierarchyError("not_archived", "The selection contains a page that cannot be restored")
            if root.parent_id and root.parent_id not in {item.id for item in roots}:
                parent = ProjectPage.objects.filter(id=root.parent_id, deleted_at__isnull=True).first()
                if parent and parent.archived_at:
                    raise ProjectPageHierarchyError("archived_ancestor", "Restore the highest archived ancestor first")
            for link in [root, *self.descendants(root)]:
                if link.archive_batch_id == root.archive_batch_id:
                    restorable_ids.add(link.id)
        now = timezone.now()
        ProjectPage.objects.filter(id__in=restorable_ids).update(
            archived_at=None,
            archive_batch_id=None,
            updated_at=now,
        )
        revision = self._bump_locked_state(state)
        result = {
            "operation": "restore",
            "root_page_ids": [str(root.page_id) for root in roots],
            "affected_count": len(restorable_ids),
            "revision": revision,
        }
        self._record(
            operation_id=operation_id,
            operation="bulk_restore",
            root=roots[0],
            revision=revision,
            result=result,
            descendant_count=len(restorable_ids) - len(roots),
        )
        return result

    @transaction.atomic
    def copy_subtrees(self, page_ids: list[str], *, operation_id: uuid.UUID) -> dict[str, Any]:
        replay = self._idempotent_result(operation_id)
        if replay is not None:
            return replay
        if self.context.project_role not in {15, 20}:
            raise ProjectPageHierarchyError("insufficient_permission", "Page creation permission is required", status_code=403)
        state = self._lock_state()
        roots = self._resolve_selection(page_ids, include_archived=False, lock=True)
        ordered_sources: list[ProjectPage] = []
        for root in roots:
            ordered_sources.extend([root, *self.descendants(root, include_archived=False)])

        pending_at = timezone.now()
        source_to_copy: dict[uuid.UUID, ProjectPage] = {}
        created_pages: list[Page] = []
        created_links: list[ProjectPage] = []
        for source in ordered_sources:
            source_page = source.page
            copied_page = Page.objects.create(
                workspace_id=self.context.workspace_id,
                name=f"{source_page.name} (Copy)" if source in roots else source_page.name,
                description_json=copy.deepcopy(source_page.description_json),
                description_html=source_page.description_html,
                description_binary=None,
                owned_by_id=self.context.user_id,
                access=source_page.access,
                color=source_page.color,
                is_locked=False,
                view_props=copy.deepcopy(source_page.view_props),
                logo_props=copy.deepcopy(source_page.logo_props),
                created_by_id=self.context.user_id,
            )
            copied_parent = source_to_copy.get(source.parent_id)
            copied_link = ProjectPage.objects.create(
                workspace_id=self.context.workspace_id,
                project_id=self.context.project_id,
                page=copied_page,
                parent=copied_parent,
                sort_order=source.sort_order,
                archived_at=pending_at,
                archive_batch_id=operation_id,
                created_by_id=self.context.user_id,
            )
            source_to_copy[source.id] = copied_link
            created_pages.append(copied_page)
            created_links.append(copied_link)
            source_labels = list(PageLabel.objects.filter(page=source_page).values_list("label_id", flat=True))
            PageLabel.objects.bulk_create(
                [
                    PageLabel(
                        workspace_id=self.context.workspace_id,
                        page=copied_page,
                        label_id=label_id,
                        created_by_id=self.context.user_id,
                    )
                    for label_id in source_labels
                ]
            )

        revision = self._bump_locked_state(state)
        copied_root_ids = [str(source_to_copy[root.id].page_id) for root in roots]
        result = {
            "operation": "copy",
            "root_page_ids": copied_root_ids,
            "created_page_ids": [str(page.id) for page in created_pages],
            "project_page_ids": [str(link.id) for link in created_links],
            "affected_count": len(created_links),
            "asset_copy_state": "pending",
            "pending_asset_copies": len(created_pages),
            "revision": revision,
        }
        self._record(
            operation_id=operation_id,
            operation="copy_subtree" if len(roots) == 1 else "bulk_copy",
            root=roots[0],
            revision=revision,
            result=result,
            descendant_count=len(created_links) - len(roots),
            outcome="pending",
        )
        mutation = ProjectPageHierarchyMutation.objects.get(
            project_id=self.context.project_id,
            actor_id=self.context.user_id,
            operation_id=operation_id,
        )

        def schedule_asset_copies():
            from plane.bgtasks.copy_s3_object import copy_s3_objects_of_description_and_assets

            for page in created_pages:
                copy_s3_objects_of_description_and_assets.delay(
                    entity_name="PAGE",
                    entity_identifier=str(page.id),
                    project_id=str(self.context.project_id),
                    slug=None,
                    user_id=str(self.context.user_id),
                    hierarchy_mutation_id=str(mutation.id),
                )

        transaction.on_commit(schedule_asset_copies)
        return result

    @transaction.atomic
    def remove_subtrees(self, page_ids: list[str], *, operation_id: uuid.UUID) -> dict[str, Any]:
        replay = self._idempotent_result(operation_id)
        if replay is not None:
            return replay
        state = self._lock_state()
        roots = self._resolve_selection(page_ids, include_archived=True, lock=True)
        affected: list[ProjectPage] = []
        affected_ids: set[uuid.UUID] = set()
        for root in roots:
            self._validate_manage_permission(root)
            if root.archived_at is None:
                raise ProjectPageHierarchyError("not_archived", "Pages must be archived before permanent removal")
            for link in [root, *self.descendants(root)]:
                if link.archived_at is None:
                    raise ProjectPageHierarchyError(
                        "active_descendant",
                        "Archive the complete subtree before permanent removal",
                    )
                if link.id not in affected_ids:
                    affected.append(link)
                    affected_ids.add(link.id)

        now = timezone.now()
        page_ids_to_check = [link.page_id for link in affected]
        ProjectPage.objects.filter(id__in=affected_ids).update(deleted_at=now, updated_at=now)
        deleted_page_ids: list[str] = []
        for page in Page.objects.filter(id__in=page_ids_to_check):
            if not ProjectPage.objects.filter(page_id=page.id, deleted_at__isnull=True).exists():
                deleted_page_ids.append(str(page.id))
                page.delete()
        UserFavorite.objects.filter(
            project_id=self.context.project_id,
            workspace_id=self.context.workspace_id,
            entity_type="page",
            entity_identifier__in=page_ids_to_check,
        ).delete(soft=False)
        UserRecentVisit.objects.filter(
            workspace_id=self.context.workspace_id,
            entity_name="page",
            entity_identifier__in=deleted_page_ids,
        ).delete(soft=False)
        revision = self._bump_locked_state(state)
        result = {
            "operation": "remove",
            "root_page_ids": [str(root.page_id) for root in roots],
            "affected_count": len(affected),
            "deleted_page_ids": deleted_page_ids,
            "preserved_page_ids": [str(page_id) for page_id in page_ids_to_check if str(page_id) not in deleted_page_ids],
            "revision": revision,
        }
        self._record(
            operation_id=operation_id,
            operation="permanent_remove" if len(roots) == 1 else "bulk_permanent_remove",
            root=roots[0],
            revision=revision,
            result=result,
            descendant_count=len(affected) - len(roots),
        )
        return result
