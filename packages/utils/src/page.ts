/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { sortBy } from "lodash-es";
// plane imports
import type {
  TPage,
  TPageFilterProps,
  TPageFiltersSortBy,
  TPageFiltersSortKey,
  TPageNavigationTabs,
  TPageHierarchyNode,
  TPageHierarchyRow,
  TPageHierarchyAllPagesQuery,
} from "@plane/types";
// local imports
import { getDate } from "./datetime";
import { satisfiesDateFilter } from "./filter";

/**
 * @description filters pages based on the page type
 * @param {TPageNavigationTabs} pageType
 * @param {TPage[]} pages
 * @returns {TPage[]}
 */
export const filterPagesByPageType = (pageType: TPageNavigationTabs, pages: TPage[]): TPage[] =>
  pages.filter((page) => {
    if (pageType === "public") return page.access === 0 && !page.archived_at;
    if (pageType === "private") return page.access === 1 && !page.archived_at;
    if (pageType === "archived") return page.archived_at;
    return true;
  });

/**
 * @description orders pages based on their status
 * @param {TPage[]} pages
 * @param {TPageFiltersSortKey | undefined} sortByKey
 * @param {TPageFiltersSortBy} sortByOrder
 * @returns {TPage[]}
 */
export const orderPages = (
  pages: TPage[],
  sortByKey: TPageFiltersSortKey | undefined,
  sortByOrder: TPageFiltersSortBy
): TPage[] => {
  let orderedPages: TPage[] = [];
  if (pages.length === 0 || !sortByKey) return [];

  if (sortByKey === "name") {
    orderedPages = sortBy(pages, [(m) => m.name?.toLowerCase()]);
    if (sortByOrder === "desc") orderedPages = orderedPages.toReversed();
  }
  if (sortByKey === "created_at") {
    orderedPages = sortBy(pages, [(m) => m.created_at]);
    if (sortByOrder === "desc") orderedPages = orderedPages.toReversed();
  }
  if (sortByKey === "updated_at") {
    orderedPages = sortBy(pages, [(m) => m.updated_at]);
    if (sortByOrder === "desc") orderedPages = orderedPages.toReversed();
  }

  return orderedPages;
};

/**
 * @description filters pages based on the filters
 * @param {TPage} page
 * @param {TPageFilterProps | undefined} filters
 * @returns {boolean}
 */
export const shouldFilterPage = (page: TPage, filters: TPageFilterProps | undefined): boolean => {
  let fallsInFilters = true;
  Object.keys(filters ?? {}).forEach((key) => {
    const filterKey = key as keyof TPageFilterProps;
    if (filterKey === "created_by" && filters?.created_by && filters.created_by.length > 0)
      fallsInFilters = fallsInFilters && filters.created_by.includes(`${page.owned_by}`);
    if (filterKey === "created_at" && filters?.created_at && filters.created_at.length > 0) {
      const createdDate = getDate(page.created_at);
      filters?.created_at.forEach((dateFilter) => {
        fallsInFilters = fallsInFilters && !!createdDate && satisfiesDateFilter(createdDate, dateFilter);
      });
    }
  });
  if (filters?.favorites && !page.is_favorite) fallsInFilters = false;

  return fallsInFilters;
};

/**
 * @description returns the name of the project after checking for untitled page
 * @param {string | undefined} name
 * @returns {string}
 */
export const getPageName = (name: string | undefined) => {
  if (name === undefined) return "";
  if (!name || name.trim() === "") return "Untitled";
  return name;
};

export const PAGE_HIERARCHY_ROOT = "__root__";

export const normalizePageHierarchy = (
  nodes: TPageHierarchyNode[]
): { nodesById: Record<string, TPageHierarchyNode>; childIdsByParent: Record<string, string[]> } => {
  const nodesById: Record<string, TPageHierarchyNode> = {};
  const childIdsByParent: Record<string, string[]> = {};
  for (const node of nodes) {
    nodesById[node.id] = node;
    const parentKey = node.parent_id ?? PAGE_HIERARCHY_ROOT;
    childIdsByParent[parentKey] = [...(childIdsByParent[parentKey] ?? []), node.id];
  }
  for (const [parentId, childIds] of Object.entries(childIdsByParent)) {
    childIdsByParent[parentId] = childIds.toSorted((leftId, rightId) => {
      const left = nodesById[leftId];
      const right = nodesById[rightId];
      return left.sort_order - right.sort_order || left.id.localeCompare(right.id);
    });
  }
  return { nodesById, childIdsByParent };
};

export const deriveVisiblePageHierarchyRows = (
  nodesById: Record<string, TPageHierarchyNode>,
  childIdsByParent: Record<string, string[]>,
  expandedIds: ReadonlySet<string>,
  maxDepth = 20
): TPageHierarchyRow[] => {
  const rows: TPageHierarchyRow[] = [];
  const visit = (parentKey: string, depth: number, ancestry: ReadonlySet<string>) => {
    for (const id of childIdsByParent[parentKey] ?? []) {
      if (ancestry.has(id) || depth > maxDepth) continue;
      const node = nodesById[id];
      if (!node) continue;
      rows.push({ id, depth, node });
      if (expandedIds.has(id)) visit(id, depth + 1, new Set([...ancestry, id]));
    }
  };
  visit(PAGE_HIERARCHY_ROOT, 1, new Set());
  return rows;
};

export const getInvalidPageHierarchyDestinationIds = (
  pageId: string,
  childIdsByParent: Record<string, string[]>
): Set<string> => {
  const invalid = new Set<string>([pageId]);
  const queue = [pageId];
  while (queue.length > 0) {
    const current = queue.shift();
    if (!current) continue;
    for (const childId of childIdsByParent[current] ?? []) {
      if (!invalid.has(childId)) {
        invalid.add(childId);
        queue.push(childId);
      }
    }
  }
  return invalid;
};

export type TPageHierarchyDropPlacement = "before" | "inside" | "after";

export const getPageHierarchyDropPlacement = (
  clientY: number,
  bounds: Pick<DOMRect, "top" | "height">
): TPageHierarchyDropPlacement => {
  const ratio = (clientY - bounds.top) / bounds.height;
  if (ratio < 0.25) return "before";
  if (ratio > 0.75) return "after";
  return "inside";
};

export const canDropPageHierarchyPlacement = (
  sourceId: string,
  target: TPageHierarchyNode,
  placement: TPageHierarchyDropPlacement,
  nodesById: Record<string, TPageHierarchyNode>,
  invalidDestinationIds: ReadonlySet<string>
): boolean => {
  const source = nodesById[sourceId];
  if (!source?.permissions.can_move || source.archived_at) return false;
  if (target.archived_at || sourceId === target.id || invalidDestinationIds.has(target.id)) return false;
  if (placement === "inside") return target.permissions.can_create_child;
  if (target.parent_id === null) return true;
  const parent = nodesById[target.parent_id];
  return Boolean(parent && !parent.archived_at && parent.permissions.can_create_child);
};

export const getPageHierarchyArchiveStateFromType = (
  pageType?: string | null
): NonNullable<TPageHierarchyAllPagesQuery["archived"]> => {
  if (pageType === "archived") return "archived";
  if (pageType === "active") return "active";
  return "all";
};

export const filterPageHierarchyMoveDestinations = (
  nodes: TPageHierarchyNode[],
  query: string,
  invalidDestinationIds: ReadonlySet<string>
): TPageHierarchyNode[] => {
  const normalizedQuery = query.trim().toLowerCase();
  return nodes.filter((node) => {
    if (
      node.archived_at ||
      invalidDestinationIds.has(node.id) ||
      node.path?.some((pathItem) => invalidDestinationIds.has(pathItem.id))
    )
      return false;
    if (!normalizedQuery) return true;
    return [node.name, ...(node.path?.map((pathItem) => pathItem.name) ?? [])].some((name) =>
      getPageName(name).toLowerCase().includes(normalizedQuery)
    );
  });
};

export const mergePageHierarchyNodePageMetadata = (
  node: TPageHierarchyNode,
  page: Partial<TPage> | undefined
): TPageHierarchyNode => {
  if (!page) return node;
  const archivedAt =
    page.project_archived_at !== undefined
      ? page.project_archived_at
      : page.archived_at !== undefined
        ? page.archived_at
        : node.archived_at;
  return {
    ...node,
    name: page.name ?? node.name,
    logo_props: page.logo_props !== undefined ? page.logo_props : node.logo_props,
    access: page.access ?? node.access,
    is_locked: page.is_locked ?? node.is_locked,
    owned_by: page.owned_by ?? node.owned_by,
    archived_at: archivedAt,
  };
};

export const pruneExpandedPageHierarchyIds = (
  expandedIds: Iterable<string>,
  nodesById: Record<string, TPageHierarchyNode>,
  limit = 200
): string[] => [...expandedIds].filter((id) => Boolean(nodesById[id]) && !nodesById[id].archived_at).slice(-limit);

export type TOptimisticPageHierarchyMoveSnapshot = {
  node: TPageHierarchyNode;
  oldParentKey: string;
  newParentKey: string;
  oldChildren: string[];
  newChildren: string[];
};

export const planOptimisticPageHierarchyMove = (
  node: TPageHierarchyNode,
  childIdsByParent: Record<string, string[]>,
  placement: { parent_id?: string | null; position: string; relative_page_id?: string | null }
) => {
  const oldParentKey = node.parent_id ?? PAGE_HIERARCHY_ROOT;
  const newParentKey = placement.parent_id ?? PAGE_HIERARCHY_ROOT;
  const oldChildren = [...(childIdsByParent[oldParentKey] ?? [])];
  const newChildren = [...(childIdsByParent[newParentKey] ?? [])];
  const sourceWithoutNode = oldChildren.filter((id) => id !== node.id);
  const destination = (oldParentKey === newParentKey ? sourceWithoutNode : newChildren).filter((id) => id !== node.id);
  let index = destination.length;
  if (placement.relative_page_id && ["before", "after"].includes(placement.position)) {
    const relativeIndex = destination.indexOf(placement.relative_page_id);
    if (relativeIndex >= 0) index = relativeIndex + (placement.position === "after" ? 1 : 0);
  } else if (placement.position === "first") index = 0;
  destination.splice(index, 0, node.id);
  return {
    snapshot: { node: { ...node }, oldParentKey, newParentKey, oldChildren, newChildren },
    node: { ...node, parent_id: placement.parent_id ?? null },
    oldChildren: oldParentKey === newParentKey ? destination : sourceWithoutNode,
    newChildren: destination,
  };
};

export const restoreOptimisticPageHierarchyMove = (snapshot: TOptimisticPageHierarchyMoveSnapshot) => ({
  node: snapshot.node,
  childIdsByParent:
    snapshot.oldParentKey === snapshot.newParentKey
      ? { [snapshot.oldParentKey]: snapshot.oldChildren }
      : {
          [snapshot.oldParentKey]: snapshot.oldChildren,
          [snapshot.newParentKey]: snapshot.newChildren,
        },
});

export const togglePageHierarchySelection = (selectedIds: string[], pageId: string): string[] =>
  selectedIds.includes(pageId) ? selectedIds.filter((id) => id !== pageId) : [...selectedIds, pageId];

export const reconcilePageHierarchyRevision = (currentRevision: number, incomingRevision: number): number =>
  Math.max(currentRevision, incomingRevision);
