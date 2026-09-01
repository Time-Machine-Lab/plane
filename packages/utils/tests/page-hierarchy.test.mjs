/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import assert from "node:assert/strict";
import test from "node:test";

import {
  PAGE_HIERARCHY_ROOT,
  canDropPageHierarchyPlacement,
  deriveVisiblePageHierarchyRows,
  filterPageHierarchyMoveDestinations,
  getInvalidPageHierarchyDestinationIds,
  getPageHierarchyArchiveStateFromType,
  getPageHierarchyDropPlacement,
  mergePageHierarchyNodePageMetadata,
  normalizePageHierarchy,
  planOptimisticPageHierarchyMove,
  pruneExpandedPageHierarchyIds,
  reconcilePageHierarchyRevision,
  restoreOptimisticPageHierarchyMove,
  togglePageHierarchySelection,
} from "../dist/index.js";

const node = (id, parentId, sortOrder, overrides = {}) => ({
  id,
  project_page_id: `link-${id}`,
  name: id,
  access: 0,
  is_locked: false,
  owned_by: "owner",
  parent_id: parentId,
  sort_order: sortOrder,
  archived_at: null,
  has_children: false,
  child_count: 0,
  depth: null,
  path: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
  permissions: {
    can_create_child: true,
    can_move: true,
    can_archive: true,
    can_restore: false,
  },
  ...overrides,
});

test("normalizes nodes into deterministic sibling lists", () => {
  const input = [
    node("second", null, 10),
    node("first-b", null, 5),
    node("first-a", null, 5),
    node("child", "first-a", 1),
  ];

  const normalized = normalizePageHierarchy(input);

  assert.deepEqual(normalized.childIdsByParent[PAGE_HIERARCHY_ROOT], ["first-a", "first-b", "second"]);
  assert.deepEqual(normalized.childIdsByParent["first-a"], ["child"]);
  assert.equal(normalized.nodesById.child.parent_id, "first-a");
});

test("derives only expanded visible branches without duplicating cyclic rows", () => {
  const nodesById = {
    root: node("root", null, 1, { has_children: true }),
    child: node("child", "root", 1, { has_children: true }),
    leaf: node("leaf", "child", 1),
  };
  const childIdsByParent = {
    [PAGE_HIERARCHY_ROOT]: ["root"],
    root: ["child"],
    child: ["leaf", "root"],
  };

  assert.deepEqual(
    deriveVisiblePageHierarchyRows(nodesById, childIdsByParent, new Set()).map((row) => row.id),
    ["root"]
  );
  const expanded = deriveVisiblePageHierarchyRows(nodesById, childIdsByParent, new Set(["root", "child", "leaf"]));
  assert.deepEqual(
    expanded.map((row) => [row.id, row.depth]),
    [
      ["root", 1],
      ["child", 2],
      ["leaf", 3],
    ]
  );
});

test("marks a complete subtree as invalid move destinations", () => {
  const invalid = getInvalidPageHierarchyDestinationIds("parent", {
    parent: ["child-a", "child-b"],
    "child-a": ["grandchild"],
    grandchild: ["parent"],
  });

  assert.deepEqual([...invalid].toSorted(), ["child-a", "child-b", "grandchild", "parent"]);
});

test("maps pointer position to explicit before, inside, and after drop zones", () => {
  const bounds = { top: 100, height: 40 };

  assert.equal(getPageHierarchyDropPlacement(100, bounds), "before");
  assert.equal(getPageHierarchyDropPlacement(109.9, bounds), "before");
  assert.equal(getPageHierarchyDropPlacement(110, bounds), "inside");
  assert.equal(getPageHierarchyDropPlacement(130, bounds), "inside");
  assert.equal(getPageHierarchyDropPlacement(130.1, bounds), "after");
  assert.equal(getPageHierarchyDropPlacement(140, bounds), "after");
});

test("validates drop placement using source, destination, and destination-parent permissions", () => {
  const nodesById = {
    source: node("source", null, 1),
    immovable: node("immovable", null, 2, {
      permissions: { ...node("unused", null, 0).permissions, can_move: false },
    }),
    parent: node("parent", null, 3),
    restrictedParent: node("restricted-parent", null, 4, {
      permissions: { ...node("unused", null, 0).permissions, can_create_child: false },
    }),
    movableTarget: node("movable-target", "parent", 1),
    fixedTarget: node("fixed-target", "parent", 2, {
      permissions: { ...node("unused", null, 0).permissions, can_move: false },
    }),
    restrictedSibling: node("restricted-sibling", "restricted-parent", 1),
    archived: node("archived", null, 5, { archived_at: "2026-01-01T00:00:00Z" }),
    descendant: node("descendant", "source", 1),
  };
  const invalid = new Set(["source", "descendant"]);

  assert.equal(canDropPageHierarchyPlacement("source", nodesById.fixedTarget, "inside", nodesById, invalid), true);
  assert.equal(canDropPageHierarchyPlacement("source", nodesById.fixedTarget, "before", nodesById, invalid), true);
  assert.equal(
    canDropPageHierarchyPlacement("source", nodesById.restrictedSibling, "after", nodesById, invalid),
    false
  );
  assert.equal(canDropPageHierarchyPlacement("immovable", nodesById.parent, "inside", nodesById, new Set()), false);
  assert.equal(canDropPageHierarchyPlacement("source", nodesById.archived, "inside", nodesById, invalid), false);
  assert.equal(canDropPageHierarchyPlacement("source", nodesById.source, "inside", nodesById, invalid), false);
  assert.equal(canDropPageHierarchyPlacement("source", nodesById.descendant, "inside", nodesById, invalid), false);
});

test("allows root sibling placement without requiring the target itself to be movable", () => {
  const source = node("source", null, 1);
  const fixedRoot = node("fixed-root", null, 2, {
    permissions: { ...source.permissions, can_move: false, can_create_child: false },
  });
  const nodesById = { source, "fixed-root": fixedRoot };

  assert.equal(canDropPageHierarchyPlacement("source", fixedRoot, "before", nodesById, new Set()), true);
  assert.equal(canDropPageHierarchyPlacement("source", fixedRoot, "after", nodesById, new Set()), true);
  assert.equal(canDropPageHierarchyPlacement("source", fixedRoot, "inside", nodesById, new Set()), false);
});

test("maps legacy page type query values to All Pages archive state", () => {
  assert.equal(getPageHierarchyArchiveStateFromType("archived"), "archived");
  assert.equal(getPageHierarchyArchiveStateFromType("active"), "active");
  assert.equal(getPageHierarchyArchiveStateFromType("public"), "all");
  assert.equal(getPageHierarchyArchiveStateFromType(null), "all");
});

test("filters move destinations by name or path while excluding invalid and archived nodes", () => {
  const shared = node("shared", null, 1, { name: "Shared Platform" });
  const nested = node("nested", "shared", 1, {
    name: "Permissions",
    path: [{ id: "shared", name: "Shared Platform" }],
  });
  const invalid = node("invalid", null, 2, { name: "Shared Invalid" });
  const archived = node("archived", null, 3, {
    name: "Shared Archive",
    archived_at: "2026-01-01T00:00:00Z",
  });

  assert.deepEqual(
    filterPageHierarchyMoveDestinations([shared, nested, invalid, archived], "shared", new Set(["invalid"])).map(
      (item) => item.id
    ),
    ["shared", "nested"]
  );
  assert.deepEqual(
    filterPageHierarchyMoveDestinations([shared, nested, invalid, archived], "", new Set(["invalid"])).map(
      (item) => item.id
    ),
    ["shared", "nested"]
  );
});

test("merges current Page display metadata without changing hierarchy placement", () => {
  const hierarchyNode = node("page", "parent", 7, { has_children: true, child_count: 2 });

  const merged = mergePageHierarchyNodePageMetadata(hierarchyNode, {
    name: "Renamed",
    access: 1,
    is_locked: true,
    project_archived_at: null,
  });

  assert.equal(merged.name, "Renamed");
  assert.equal(merged.access, 1);
  assert.equal(merged.is_locked, true);
  assert.equal(merged.parent_id, "parent");
  assert.equal(merged.sort_order, 7);
  assert.equal(merged.has_children, true);
  assert.equal(merged.child_count, 2);
});

test("prunes stale and archived expansion preferences and keeps the newest bounded values", () => {
  const nodesById = {
    active1: node("active1", null, 1),
    active2: node("active2", null, 2),
    active3: node("active3", null, 3),
    archived: node("archived", null, 4, { archived_at: "2026-01-01T00:00:00Z" }),
  };

  assert.deepEqual(
    pruneExpandedPageHierarchyIds(["stale", "active1", "archived", "active2", "active3"], nodesById, 2),
    ["active2", "active3"]
  );
});

test("plans optimistic reparenting and restores both affected branches after failure", () => {
  const source = node("source", "old-parent", 10);
  const children = {
    "old-parent": ["before", "source", "after"],
    "new-parent": ["target-a", "target-b"],
  };
  const plan = planOptimisticPageHierarchyMove(source, children, {
    parent_id: "new-parent",
    position: "before",
    relative_page_id: "target-b",
  });

  assert.equal(plan.node.parent_id, "new-parent");
  assert.deepEqual(plan.oldChildren, ["before", "after"]);
  assert.deepEqual(plan.newChildren, ["target-a", "source", "target-b"]);
  assert.deepEqual(restoreOptimisticPageHierarchyMove(plan.snapshot), {
    node: source,
    childIdsByParent: children,
  });
});

test("reorders within one parent without duplicating a node", () => {
  const source = node("source", null, 10);
  const plan = planOptimisticPageHierarchyMove(
    source,
    { [PAGE_HIERARCHY_ROOT]: ["a", "source", "b"] },
    {
      parent_id: null,
      position: "after",
      relative_page_id: "b",
    }
  );

  assert.deepEqual(plan.newChildren, ["a", "b", "source"]);
  assert.deepEqual(restoreOptimisticPageHierarchyMove(plan.snapshot).childIdsByParent, {
    [PAGE_HIERARCHY_ROOT]: ["a", "source", "b"],
  });
});

test("selection toggles are immutable and revisions never move backward", () => {
  const selected = ["first"];
  assert.deepEqual(togglePageHierarchySelection(selected, "second"), ["first", "second"]);
  assert.deepEqual(togglePageHierarchySelection(selected, "first"), []);
  assert.deepEqual(selected, ["first"]);
  assert.equal(reconcilePageHierarchyRevision(8, 5), 8);
  assert.equal(reconcilePageHierarchyRevision(8, 11), 11);
});
