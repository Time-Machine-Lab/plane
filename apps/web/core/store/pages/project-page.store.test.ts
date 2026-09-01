/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import assert from "node:assert/strict";
import test from "node:test";
import { observable, runInAction } from "mobx";
import type { TPage, TPageHierarchyNode, TPageHierarchyPreferences, TPageHierarchyResponse } from "@plane/types";
import { PAGE_HIERARCHY_ROOT } from "@plane/utils";
import type { ProjectPageService } from "@/services/page";
import type { CoreRootStore } from "../root.store";
import { ProjectPageStore } from "./project-page.store";

const node = (
  id: string,
  parentId: string | null,
  sortOrder: number,
  overrides: Partial<TPageHierarchyNode> = {}
): TPageHierarchyNode => ({
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

const hierarchyResponse = (results: TPageHierarchyNode[], revision: number): TPageHierarchyResponse => ({
  results,
  total_count: results.length,
  next_offset: null,
  revision,
});

const createStore = () => {
  const rootStore = {
    router: observable({ workspaceSlug: "workspace", projectId: "project" }),
    user: {
      permission: {
        getProjectRoleByWorkspaceSlugAndProjectId: () => 20,
      },
    },
    favorite: {
      entityMap: {},
      removeFavoriteFromStore: () => undefined,
    },
  } as unknown as CoreRootStore;
  return new ProjectPageStore(rootStore);
};

const seedMoveState = (store: ProjectPageStore) => {
  const source = node("source", "old-parent", 1, { has_children: true, child_count: 1 });
  const oldSibling = node("old-sibling", "old-parent", 2);
  const target = node("target", "new-parent", 1);
  const descendant = node("descendant", "source", 1);
  store.hierarchyNodes = {
    "old-parent": node("old-parent", null, 1, { has_children: true, child_count: 2 }),
    "new-parent": node("new-parent", null, 2, { has_children: true, child_count: 1 }),
    source,
    "old-sibling": oldSibling,
    target,
    descendant,
  };
  store.hierarchyChildren = {
    [PAGE_HIERARCHY_ROOT]: ["old-parent", "new-parent"],
    "old-parent": ["source", "old-sibling"],
    "new-parent": ["target"],
    source: ["descendant"],
  };
  store.hierarchyBranchState = {
    [PAGE_HIERARCHY_ROOT]: "loaded",
    "old-parent": "loaded",
    "new-parent": "loaded",
    source: "loaded",
  };
  store.hierarchyRevision = 5;
  const pageContent = { id: "source", description_html: "<p>Unchanged</p>" };
  store.data.source = pageContent as never;
  return { source, oldSibling, target, descendant, pageContent };
};

test("loads a direct-link ancestor chain through the MobX store and persists expanded branches", async () => {
  const store = createStore();
  const root = node("root", null, 1, { has_children: true, child_count: 1 });
  const child = node("child", "root", 1, { has_children: true, child_count: 1 });
  const selected = node("selected", "child", 1);
  const branchCalls: Array<string | null> = [];
  let savedExpandedIds: string[] = [];
  store.service = {
    fetchHierarchyPath: async () => ({
      path: [root, child, selected].map(({ id, name }) => ({ id, name })),
      depth: 3,
      revision: 5,
    }),
    fetchHierarchy: async (_workspaceSlug: string, _projectId: string, parentId: string | null) => {
      branchCalls.push(parentId);
      if (parentId === null) return hierarchyResponse([root], 3);
      if (parentId === "root") return hierarchyResponse([child], 4);
      return hierarchyResponse([selected], 5);
    },
    updateHierarchyPreferences: async (
      _workspaceSlug: string,
      _projectId: string,
      preferences: TPageHierarchyPreferences
    ) => {
      savedExpandedIds = preferences.expanded_ids;
      return preferences;
    },
  } as unknown as ProjectPageService;

  const path = await store.loadHierarchyPath("selected");
  await new Promise((resolve) => setTimeout(resolve, 550));

  assert.deepEqual(
    path.map((item) => item.id),
    ["root", "child", "selected"]
  );
  assert.deepEqual(new Set(branchCalls), new Set([null, "child", "root"]));
  assert.deepEqual(store.expandedHierarchyIds, ["root", "child"]);
  assert.deepEqual(savedExpandedIds, ["root", "child"]);
  assert.deepEqual(
    store.visibleHierarchyRows.map((row) => row.id),
    ["root", "child", "selected"]
  );
  assert.equal(store.hierarchyRevision, 5);
});

test("hydrates saved expanded branches after root loading without loading collapsed branches twice", async () => {
  const store = createStore();
  const root = node("root", null, 1, { has_children: true, child_count: 1 });
  const child = node("child", "root", 1, { has_children: true, child_count: 1 });
  const leaf = node("leaf", "child", 1);
  const collapsed = node("collapsed", null, 2, { has_children: true, child_count: 1 });
  const branchCalls: Array<string | null> = [];
  let savedExpandedIds: string[] = [];
  store.service = {
    fetchHierarchyPreferences: async () => ({
      version: 1,
      expanded_ids: ["root", "child", "stale"],
    }),
    fetchHierarchy: async (_workspaceSlug: string, _projectId: string, parentId: string | null) => {
      branchCalls.push(parentId);
      if (parentId === null) {
        await new Promise((resolve) => setTimeout(resolve, 10));
        return hierarchyResponse([root, collapsed], 3);
      }
      if (parentId === "root") return hierarchyResponse([child], 4);
      if (parentId === "child") return hierarchyResponse([leaf], 5);
      throw new Error(`Unexpected branch ${parentId}`);
    },
    updateHierarchyPreferences: async (
      _workspaceSlug: string,
      _projectId: string,
      preferences: TPageHierarchyPreferences
    ) => {
      savedExpandedIds = preferences.expanded_ids;
      return preferences;
    },
  } as unknown as ProjectPageService;

  await Promise.all([store.fetchHierarchyBranch(null), store.loadHierarchyPreferences()]);
  await new Promise((resolve) => setTimeout(resolve, 550));

  assert.equal(branchCalls.filter((parentId) => parentId === null).length, 1);
  assert.deepEqual(branchCalls, [null, "root", "child"]);
  assert.equal(branchCalls.includes("collapsed"), false);
  assert.deepEqual(store.expandedHierarchyIds, ["root", "child"]);
  assert.deepEqual(savedExpandedIds, ["root", "child"]);
  assert.deepEqual(store.hierarchyChildren.root, ["child"]);
  assert.deepEqual(store.hierarchyChildren.child, ["leaf"]);
  assert.deepEqual(
    store.visibleHierarchyRows.map((row) => row.id),
    ["root", "child", "leaf", "collapsed"]
  );
});

test("keeps a restored branch error retryable without pruning its saved expansion", async () => {
  const store = createStore();
  const root = node("root", null, 1, { has_children: true, child_count: 1 });
  const child = node("child", "root", 1);
  let shouldFail = true;
  store.service = {
    fetchHierarchyPreferences: async () => ({ version: 1, expanded_ids: ["root"] }),
    fetchHierarchy: async (_workspaceSlug: string, _projectId: string, parentId: string | null) => {
      if (parentId === null) return hierarchyResponse([root], 3);
      if (shouldFail) throw new Error("branch unavailable");
      return hierarchyResponse([child], 4);
    },
  } as unknown as ProjectPageService;

  await store.loadHierarchyPreferences();

  assert.equal(store.hierarchyBranchState.root, "error");
  assert.deepEqual(store.expandedHierarchyIds, ["root"]);

  shouldFail = false;
  await store.fetchHierarchyBranch("root", true);

  assert.equal(store.hierarchyBranchState.root, "loaded");
  assert.deepEqual(store.hierarchyChildren.root, ["child"]);
});

test("projects current Page lock metadata into tree rows without changing hierarchy placement", () => {
  const store = createStore();
  const pageNode = node("page", "parent", 3);
  store.hierarchyNodes = {
    parent: node("parent", null, 1, { has_children: true, child_count: 1 }),
    page: pageNode,
  };
  store.hierarchyChildren = {
    [PAGE_HIERARCHY_ROOT]: ["parent"],
    parent: ["page"],
  };
  store.expandedHierarchyIds = ["parent"];
  const pageState = observable({
    name: "Page",
    logo_props: undefined,
    access: 0,
    is_locked: false,
    owned_by: "owner",
    archived_at: null,
    project_archived_at: null,
  });
  store.data.page = pageState as never;

  assert.equal(store.visibleHierarchyRows[1].node.is_locked, false);
  runInAction(() => {
    pageState.is_locked = true;
  });
  assert.equal(store.visibleHierarchyRows[1].node.is_locked, true);
  runInAction(() => {
    pageState.is_locked = false;
  });
  assert.equal(store.visibleHierarchyRows[1].node.is_locked, false);
  assert.equal(store.visibleHierarchyRows[1].node.parent_id, "parent");
  assert.equal(store.visibleHierarchyRows[1].node.sort_order, 3);
});

test("reparents optimistically, reconciles authoritative siblings, and preserves subtree and page content", async () => {
  const store = createStore();
  const { oldSibling, target, pageContent } = seedMoveState(store);
  const refreshCalls: Array<string | null> = [];
  let mutationCount = 0;
  store.service = {
    moveInHierarchy: async () => {
      mutationCount += 1;
      return {
        page_id: "source",
        parent_id: "new-parent",
        revision: 6,
        base_revision: 5,
        siblings: [
          { id: "target", sort_order: 1 },
          { id: "source", sort_order: 2 },
        ],
      };
    },
    fetchHierarchy: async (_workspaceSlug: string, _projectId: string, parentId: string | null) => {
      refreshCalls.push(parentId);
      return hierarchyResponse(parentId === "old-parent" ? [oldSibling] : [target, store.hierarchyNodes.source], 6);
    },
  } as unknown as ProjectPageService;

  const placement = { parent_id: "new-parent", position: "after" as const, relative_page_id: "target" };
  await store.movePageInHierarchy("source", placement);
  await store.movePageInHierarchy("source", placement);

  assert.equal(mutationCount, 2);
  assert.deepEqual(refreshCalls, ["old-parent"]);
  assert.equal(store.hierarchyNodes.source.parent_id, "new-parent");
  assert.deepEqual(store.hierarchyChildren["old-parent"], ["old-sibling"]);
  assert.deepEqual(store.hierarchyChildren["new-parent"], ["target", "source"]);
  assert.equal(store.hierarchyNodes["old-parent"].child_count, 1);
  assert.equal(store.hierarchyNodes["old-parent"].has_children, true);
  assert.equal(store.hierarchyNodes["new-parent"].child_count, 2);
  assert.equal(store.hierarchyNodes["new-parent"].has_children, true);
  assert.deepEqual(store.hierarchyChildren.source, ["descendant"]);
  assert.equal(store.data.source.id, pageContent.id);
  assert.equal(store.data.source.description_html, pageContent.description_html);
  assert.equal(store.hierarchyRevision, 6);
});

test("refreshes both affected branches when the server reports a newer concurrent revision", async () => {
  const store = createStore();
  const { oldSibling, target } = seedMoveState(store);
  const refreshCalls: Array<string | null> = [];
  store.service = {
    moveInHierarchy: async () => ({
      page_id: "source",
      parent_id: "new-parent",
      revision: 8,
      base_revision: 5,
      siblings: [
        { id: "target", sort_order: 1 },
        { id: "source", sort_order: 2 },
      ],
    }),
    fetchHierarchy: async (_workspaceSlug: string, _projectId: string, parentId: string | null) => {
      refreshCalls.push(parentId);
      if (parentId === "old-parent") return hierarchyResponse([oldSibling], 8);
      return hierarchyResponse([target, store.hierarchyNodes.source], 9);
    },
  } as unknown as ProjectPageService;

  await store.movePageInHierarchy("source", {
    parent_id: "new-parent",
    position: "after",
    relative_page_id: "target",
  });

  assert.deepEqual(new Set(refreshCalls), new Set(["new-parent", "old-parent"]));
  assert.equal(store.hierarchyRevision, 9);
  assert.deepEqual(store.hierarchyChildren["old-parent"], ["old-sibling"]);
  assert.deepEqual(store.hierarchyChildren["new-parent"], ["target", "source"]);
});

test("rolls back a rejected reparent, refreshes affected branches, and retains Page content state", async () => {
  const store = createStore();
  const { source, oldSibling, target, pageContent } = seedMoveState(store);
  const refreshCalls: Array<string | null> = [];
  store.service = {
    moveInHierarchy: async () => {
      throw new Error("conflict");
    },
    fetchHierarchy: async (_workspaceSlug: string, _projectId: string, parentId: string | null) => {
      refreshCalls.push(parentId);
      return hierarchyResponse(parentId === "old-parent" ? [source, oldSibling] : [target], 5);
    },
  } as unknown as ProjectPageService;

  await assert.rejects(
    store.movePageInHierarchy("source", {
      parent_id: "new-parent",
      position: "after",
      relative_page_id: "target",
    }),
    /conflict/
  );

  assert.deepEqual(new Set(refreshCalls), new Set(["new-parent", "old-parent"]));
  assert.equal(store.hierarchyNodes.source.parent_id, "old-parent");
  assert.deepEqual(store.hierarchyChildren["old-parent"], ["source", "old-sibling"]);
  assert.deepEqual(store.hierarchyChildren["new-parent"], ["target"]);
  assert.deepEqual(store.hierarchyChildren.source, ["descendant"]);
  assert.equal(store.hierarchyNodes["old-parent"].child_count, 2);
  assert.equal(store.hierarchyNodes["old-parent"].has_children, true);
  assert.equal(store.hierarchyNodes["new-parent"].child_count, 1);
  assert.equal(store.hierarchyNodes["new-parent"].has_children, true);
  assert.equal(store.data.source.id, pageContent.id);
  assert.equal(store.data.source.description_html, pageContent.description_html);
  assert.equal(store.hierarchyRevision, 5);
});

test("makes an unloaded leaf destination expandable immediately and clears the emptied source parent", async () => {
  const store = createStore();
  const source = node("source", "old-parent", 1);
  store.hierarchyNodes = {
    "old-parent": node("old-parent", null, 1, { has_children: true, child_count: 1 }),
    "new-parent": node("new-parent", null, 2),
    source,
  };
  store.hierarchyChildren = {
    [PAGE_HIERARCHY_ROOT]: ["old-parent", "new-parent"],
    "old-parent": ["source"],
  };
  store.hierarchyBranchState = {
    [PAGE_HIERARCHY_ROOT]: "loaded",
    "old-parent": "loaded",
  };
  store.expandedHierarchyIds = ["old-parent"];
  store.hierarchyRevision = 1;
  const branchCalls: Array<string | null> = [];
  store.service = {
    moveInHierarchy: async () => ({
      page_id: "source",
      parent_id: "new-parent",
      revision: 2,
      base_revision: 1,
      siblings: [{ id: "source", sort_order: 1 }],
    }),
    fetchHierarchy: async (_workspaceSlug: string, _projectId: string, parentId: string | null) => {
      branchCalls.push(parentId);
      return hierarchyResponse(parentId === "new-parent" ? [store.hierarchyNodes.source] : [], 2);
    },
    updateHierarchyPreferences: async () => ({ version: 1, expanded_ids: [] }),
  } as unknown as ProjectPageService;

  await store.movePageInHierarchy("source", {
    parent_id: "new-parent",
    position: "last",
    relative_page_id: null,
  });

  assert.equal(store.hierarchyNodes["new-parent"].has_children, true);
  assert.equal(store.hierarchyNodes["new-parent"].child_count, 1);
  assert.equal(store.hierarchyBranchState["new-parent"], undefined);
  assert.equal(store.hierarchyChildren["new-parent"], undefined);
  assert.equal(store.hierarchyNodes["old-parent"].has_children, false);
  assert.equal(store.hierarchyNodes["old-parent"].child_count, 0);
  assert.deepEqual(store.hierarchyChildren["old-parent"], []);
  assert.equal(store.expandedHierarchyIds.includes("old-parent"), false);

  await store.toggleHierarchyNode("new-parent");

  assert.deepEqual(branchCalls, ["old-parent", "new-parent"]);
  assert.equal(store.hierarchyBranchState["new-parent"], "loaded");
  assert.deepEqual(store.hierarchyChildren["new-parent"], ["source"]);
  assert.equal(store.expandedHierarchyIds.includes("new-parent"), true);
});

test("records and consumes title editing once for a newly created child page", async () => {
  const store = createStore();
  const createdPage = { id: "child", project_parent_id: "parent", project_ids: ["project"] } as TPage;
  let submittedParentId: string | null | undefined;
  store.service = {
    create: async (_workspaceSlug: string, _projectId: string, pageData: Partial<TPage>) => {
      submittedParentId = pageData.project_parent_id;
      return createdPage;
    },
    fetchHierarchy: async () => hierarchyResponse([], 1),
    updateHierarchyPreferences: async () => ({ version: 1, expanded_ids: [] }),
  } as unknown as ProjectPageService;

  const result = await store.createChildPage("parent");

  assert.equal(result, createdPage);
  assert.equal(submittedParentId, "parent");
  assert.equal(store.pendingTitleEditPageId, "child");
  assert.equal(store.completePendingTitleEdit("other-page", true), false);
  assert.equal(store.pendingTitleEditPageId, "child");
  assert.equal(store.completePendingTitleEdit("child", false), false);
  assert.equal(store.pendingTitleEditPageId, "child");
  assert.equal(store.completePendingTitleEdit("child", true), true);
  assert.equal(store.pendingTitleEditPageId, null);
  assert.equal(store.completePendingTitleEdit("child", true), false);
});

test("records title editing for a root page and clears it when the project changes", async () => {
  const store = createStore();
  store.service = {
    create: async () => ({ id: "root-page", project_parent_id: null, project_ids: ["project"] }) as TPage,
    fetchHierarchy: async () => hierarchyResponse([], 1),
  } as unknown as ProjectPageService;

  await store.createChildPage(null);

  assert.equal(store.pendingTitleEditPageId, "root-page");
  runInAction(() => {
    store.rootStore.router.projectId = "another-project";
  });
  assert.equal(store.pendingTitleEditPageId, null);
});

test("isolates consecutive title editing intents for pages created in one store lifecycle", async () => {
  const store = createStore();
  const createdIds = ["page-a", "page-b"];
  store.service = {
    create: async () => ({ id: createdIds.shift(), project_parent_id: null, project_ids: ["project"] }) as TPage,
    fetchHierarchy: async () => hierarchyResponse([], 1),
  } as unknown as ProjectPageService;

  await store.createChildPage(null);
  assert.equal(store.pendingTitleEditPageId, "page-a");
  assert.equal(store.completePendingTitleEdit("page-a", true), true);
  assert.equal(store.completePendingTitleEdit("page-a", true), false);

  await store.createChildPage(null);
  assert.equal(store.pendingTitleEditPageId, "page-b");
  assert.equal(store.completePendingTitleEdit("page-a", true), false);
  assert.equal(store.pendingTitleEditPageId, "page-b");
  assert.equal(store.completePendingTitleEdit("page-b", false), false);
  assert.equal(store.pendingTitleEditPageId, "page-b");
  assert.equal(store.completePendingTitleEdit("page-b", true), true);
  assert.equal(store.completePendingTitleEdit("page-b", true), false);
});

test("does not leave a title editing intent when page creation fails", async () => {
  const store = createStore();
  store.service = {
    create: async () => {
      throw new Error("create failed");
    },
  } as unknown as ProjectPageService;

  await assert.rejects(store.createChildPage("parent"), /create failed/);

  assert.equal(store.pendingTitleEditPageId, null);
});
