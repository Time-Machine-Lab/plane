/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { unset, set } from "lodash-es";
import { makeObservable, observable, runInAction, action, reaction, computed } from "mobx";
import { computedFn } from "mobx-utils";
// types
import { EUserPermissions } from "@plane/constants";
import type {
  TPage,
  TPageFilters,
  TPageHierarchyAllPagesQuery,
  TPageHierarchyBranchState,
  TPageHierarchyBulkOperation,
  TPageHierarchyBulkPayload,
  TPageHierarchyBulkResponse,
  TPageHierarchyMovePayload,
  TPageHierarchyNode,
  TPageHierarchyPathItem,
  TPageHierarchyRow,
  TPageHierarchyPreview,
  TPageNavigationTabs,
} from "@plane/types";
import { EUserProjectRoles } from "@plane/types";
// helpers
import {
  deriveVisiblePageHierarchyRows,
  filterPagesByPageType,
  getPageName,
  mergePageHierarchyNodePageMetadata,
  orderPages,
  PAGE_HIERARCHY_ROOT,
  planOptimisticPageHierarchyMove,
  pruneExpandedPageHierarchyIds,
  reconcilePageHierarchyRevision,
  restoreOptimisticPageHierarchyMove,
  shouldFilterPage,
  togglePageHierarchySelection,
} from "@plane/utils";
// plane web constants
// plane web store
// services
import { ProjectPageService } from "@/services/page";
// store
import type { CoreRootStore } from "../root.store";
import type { TProjectPage } from "./project-page";
import { ProjectPage } from "./project-page";

type TLoader = "init-loader" | "mutation-loader" | undefined;

type TError = { title: string; description: string };

export const ROLE_PERMISSIONS_TO_CREATE_PAGE = [
  EUserPermissions.ADMIN,
  EUserPermissions.MEMBER,
  EUserProjectRoles.ADMIN,
  EUserProjectRoles.MEMBER,
];

export interface IProjectPageStore {
  // observables
  loader: TLoader;
  data: Record<string, TProjectPage>; // pageId => Page
  error: TError | undefined;
  filters: TPageFilters;
  hierarchyNodes: Record<string, TPageHierarchyNode>;
  hierarchyChildren: Record<string, string[]>;
  hierarchyBranchState: Record<string, TPageHierarchyBranchState>;
  hierarchyPaths: Record<string, TPageHierarchyPathItem[]>;
  hierarchyRevision: number;
  expandedHierarchyIds: string[];
  pendingTitleEditPageId: string | null;
  allPagesNodes: TPageHierarchyNode[];
  allPagesTotal: number;
  allPagesNextOffset: number | null;
  allPagesState: TPageHierarchyBranchState;
  allPagesError: string | null;
  selectedAllPageIds: string[];
  bulkPreview: TPageHierarchyPreview | null;
  // computed
  isAnyPageAvailable: boolean;
  canCurrentUserCreatePage: boolean;
  visibleHierarchyRows: TPageHierarchyRow[];
  // helper actions
  getCurrentProjectPageIdsByTab: (pageType: TPageNavigationTabs) => string[] | undefined;
  getCurrentProjectPageIds: (projectId: string) => string[];
  getCurrentProjectFilteredPageIdsByTab: (pageType: TPageNavigationTabs) => string[] | undefined;
  getPageById: (pageId: string) => TProjectPage | undefined;
  updateFilters: <T extends keyof TPageFilters>(filterKey: T, filterValue: TPageFilters[T]) => void;
  clearAllFilters: () => void;
  // actions
  fetchPagesList: (
    workspaceSlug: string,
    projectId: string,
    pageType?: TPageNavigationTabs
  ) => Promise<TPage[] | undefined>;
  fetchPageDetails: (
    workspaceSlug: string,
    projectId: string,
    pageId: string,
    options?: { trackVisit?: boolean }
  ) => Promise<TPage | undefined>;
  createPage: (pageData: Partial<TPage>) => Promise<TPage | undefined>;
  removePage: (params: { pageId: string; shouldSync?: boolean }) => Promise<void>;
  movePage: (workspaceSlug: string, projectId: string, pageId: string, newProjectId: string) => Promise<void>;
  fetchHierarchyBranch: (parentId?: string | null, force?: boolean) => Promise<void>;
  loadHierarchyPath: (pageId: string) => Promise<TPageHierarchyPathItem[]>;
  toggleHierarchyNode: (pageId: string) => Promise<void>;
  movePageInHierarchy: (pageId: string, payload: Omit<TPageHierarchyMovePayload, "operation_id">) => Promise<void>;
  createChildPage: (parentId: string | null, pageData?: Partial<TPage>) => Promise<TPage | undefined>;
  completePendingTitleEdit: (pageId: string, didFocus: boolean) => boolean;
  cancelPendingTitleEdit: (pageId: string) => boolean;
  loadHierarchyPreferences: () => Promise<void>;
  loadAllPages: (query?: TPageHierarchyAllPagesQuery, append?: boolean) => Promise<void>;
  searchHierarchyDestinations: (query: string) => Promise<TPageHierarchyNode[]>;
  loadHierarchySiblings: (parentId: string | null) => Promise<TPageHierarchyNode[]>;
  toggleAllPageSelection: (pageId: string) => void;
  clearAllPageSelection: () => void;
  previewAllPagesBulk: (
    operation: TPageHierarchyBulkOperation,
    placement?: Partial<Pick<TPageHierarchyBulkPayload, "parent_id" | "position" | "relative_page_id">>
  ) => Promise<TPageHierarchyPreview>;
  executeAllPagesBulk: (
    operation: TPageHierarchyBulkOperation,
    placement?: Partial<Pick<TPageHierarchyBulkPayload, "parent_id" | "position" | "relative_page_id">>
  ) => Promise<TPageHierarchyBulkResponse>;
}

export class ProjectPageStore implements IProjectPageStore {
  // observables
  loader: TLoader = "init-loader";
  data: Record<string, TProjectPage> = {}; // pageId => Page
  error: TError | undefined = undefined;
  filters: TPageFilters = {
    searchQuery: "",
    sortKey: "updated_at",
    sortBy: "desc",
  };
  hierarchyNodes: Record<string, TPageHierarchyNode> = {};
  hierarchyChildren: Record<string, string[]> = {};
  hierarchyBranchState: Record<string, TPageHierarchyBranchState> = {};
  hierarchyPaths: Record<string, TPageHierarchyPathItem[]> = {};
  hierarchyRevision = 0;
  expandedHierarchyIds: string[] = [];
  pendingTitleEditPageId: string | null = null;
  allPagesNodes: TPageHierarchyNode[] = [];
  allPagesTotal = 0;
  allPagesNextOffset: number | null = null;
  allPagesState: TPageHierarchyBranchState = "idle";
  allPagesError: string | null = null;
  selectedAllPageIds: string[] = [];
  bulkPreview: TPageHierarchyPreview | null = null;
  private hierarchyBranchRequests = new Map<string, Promise<void>>();
  private hierarchyPreferenceTimer: ReturnType<typeof setTimeout> | undefined;
  private allPagesQuery: TPageHierarchyAllPagesQuery = {};
  // service
  service: ProjectPageService;
  rootStore: CoreRootStore;

  constructor(private store: CoreRootStore) {
    makeObservable(this, {
      // observables
      loader: observable.ref,
      data: observable,
      error: observable,
      filters: observable,
      hierarchyNodes: observable,
      hierarchyChildren: observable,
      hierarchyBranchState: observable,
      hierarchyPaths: observable,
      hierarchyRevision: observable.ref,
      expandedHierarchyIds: observable,
      pendingTitleEditPageId: observable.ref,
      allPagesNodes: observable,
      allPagesTotal: observable.ref,
      allPagesNextOffset: observable.ref,
      allPagesState: observable.ref,
      allPagesError: observable.ref,
      selectedAllPageIds: observable,
      bulkPreview: observable.ref,
      // computed
      isAnyPageAvailable: computed,
      canCurrentUserCreatePage: computed,
      visibleHierarchyRows: computed,
      // helper actions
      updateFilters: action,
      clearAllFilters: action,
      // actions
      fetchPagesList: action,
      fetchPageDetails: action,
      createPage: action,
      removePage: action,
      movePage: action,
      fetchHierarchyBranch: action,
      loadHierarchyPath: action,
      toggleHierarchyNode: action,
      movePageInHierarchy: action,
      createChildPage: action,
      completePendingTitleEdit: action,
      cancelPendingTitleEdit: action,
      loadHierarchyPreferences: action,
      loadAllPages: action,
      searchHierarchyDestinations: action,
      loadHierarchySiblings: action,
      toggleAllPageSelection: action,
      clearAllPageSelection: action,
      previewAllPagesBulk: action,
      executeAllPagesBulk: action,
    });
    this.rootStore = store;
    // service
    this.service = new ProjectPageService();
    // initialize display filters of the current project
    reaction(
      () => this.store.router.projectId,
      (projectId) => {
        if (!projectId) return;
        this.filters.searchQuery = "";
        this.hierarchyNodes = {};
        this.hierarchyChildren = {};
        this.hierarchyBranchState = {};
        this.hierarchyPaths = {};
        this.hierarchyRevision = 0;
        this.expandedHierarchyIds = [];
        this.pendingTitleEditPageId = null;
        this.hierarchyBranchRequests.clear();
        this.allPagesNodes = [];
        this.allPagesTotal = 0;
        this.allPagesNextOffset = null;
        this.allPagesState = "idle";
        this.allPagesError = null;
        this.selectedAllPageIds = [];
        this.bulkPreview = null;
      }
    );
  }

  /**
   * @description check if any page is available
   */
  get isAnyPageAvailable() {
    if (this.loader) return true;
    return Object.keys(this.data).length > 0;
  }

  /**
   * @description returns true if the current logged in user can create a page
   */
  get canCurrentUserCreatePage() {
    const { workspaceSlug, projectId } = this.store.router;
    const currentUserProjectRole = this.store.user.permission.getProjectRoleByWorkspaceSlugAndProjectId(
      workspaceSlug?.toString() || "",
      projectId?.toString() || ""
    );
    return !!currentUserProjectRole && ROLE_PERMISSIONS_TO_CREATE_PAGE.includes(currentUserProjectRole);
  }

  get visibleHierarchyRows() {
    const rows = deriveVisiblePageHierarchyRows(
      this.hierarchyNodes,
      this.hierarchyChildren,
      new Set(this.expandedHierarchyIds)
    );
    for (const row of rows) row.node = mergePageHierarchyNodePageMetadata(row.node, this.data[row.id]);
    return rows;
  }

  /**
   * @description get the current project page ids based on the pageType
   * @param {TPageNavigationTabs} pageType
   */
  getCurrentProjectPageIdsByTab = computedFn((pageType: TPageNavigationTabs) => {
    const { projectId } = this.store.router;
    if (!projectId) return undefined;
    // helps to filter pages based on the pageType
    let pagesByType = filterPagesByPageType(pageType, Object.values(this?.data || {}));
    pagesByType = pagesByType.filter((p) => p.project_ids?.includes(projectId));

    const pages = (pagesByType.map((page) => page.id) as string[]) || undefined;

    return pages ?? undefined;
  });

  /**
   * @description get the current project page ids
   * @param {string} projectId
   */
  getCurrentProjectPageIds = computedFn((projectId: string) => {
    if (!projectId) return [];
    const pages = Object.values(this?.data || {}).filter((page) => page.project_ids?.includes(projectId));
    return pages.map((page) => page.id) as string[];
  });

  /**
   * @description get the current project filtered page ids based on the pageType
   * @param {TPageNavigationTabs} pageType
   */
  getCurrentProjectFilteredPageIdsByTab = computedFn((pageType: TPageNavigationTabs) => {
    const { projectId } = this.store.router;
    if (!projectId) return undefined;

    // helps to filter pages based on the pageType
    const pagesByType = filterPagesByPageType(pageType, Object.values(this?.data || {}));
    let filteredPages = pagesByType.filter(
      (p) =>
        p.project_ids?.includes(projectId) &&
        getPageName(p.name).toLowerCase().includes(this.filters.searchQuery.toLowerCase()) &&
        shouldFilterPage(p, this.filters.filters)
    );
    filteredPages = orderPages(filteredPages, this.filters.sortKey, this.filters.sortBy);

    const pages = (filteredPages.map((page) => page.id) as string[]) || undefined;

    return pages ?? undefined;
  });

  /**
   * @description get the page store by id
   * @param {string} pageId
   */
  getPageById = computedFn((pageId: string) => this.data?.[pageId] || undefined);

  updateFilters = <T extends keyof TPageFilters>(filterKey: T, filterValue: TPageFilters[T]) => {
    runInAction(() => {
      set(this.filters, [filterKey], filterValue);
    });
  };

  /**
   * @description clear all the filters
   */
  clearAllFilters = () =>
    runInAction(() => {
      set(this.filters, ["filters"], {});
    });

  /**
   * @description fetch all the pages
   */
  fetchPagesList = async (workspaceSlug: string, projectId: string, pageType?: TPageNavigationTabs) => {
    try {
      if (!workspaceSlug || !projectId) return undefined;

      const currentPageIds = pageType ? this.getCurrentProjectPageIdsByTab(pageType) : undefined;
      runInAction(() => {
        this.loader = currentPageIds && currentPageIds.length > 0 ? `mutation-loader` : `init-loader`;
        this.error = undefined;
      });

      const pages = await this.service.fetchAll(workspaceSlug, projectId);
      runInAction(() => {
        for (const page of pages) {
          if (page?.id) {
            const existingPage = this.getPageById(page.id);
            if (existingPage) {
              // If page already exists, update all fields except name

              const { name, ...otherFields } = page;
              existingPage.mutateProperties(otherFields, false);
            } else {
              // If new page, create a new instance with all data
              set(this.data, [page.id], new ProjectPage(this.store, page));
            }
          }
        }
        this.loader = undefined;
      });

      return pages;
    } catch (error) {
      runInAction(() => {
        this.loader = undefined;
        this.error = {
          title: "Failed",
          description: "Failed to fetch the pages, Please try again later.",
        };
      });
      throw error;
    }
  };

  /**
   * @description fetch the details of a page
   * @param {string} pageId
   */
  fetchPageDetails = async (...args: Parameters<IProjectPageStore["fetchPageDetails"]>) => {
    const [workspaceSlug, projectId, pageId, options] = args;
    const { trackVisit } = options || {};
    try {
      if (!workspaceSlug || !projectId || !pageId) return undefined;

      const currentPageId = this.getPageById(pageId);
      runInAction(() => {
        this.loader = currentPageId ? `mutation-loader` : `init-loader`;
        this.error = undefined;
      });

      const page = await this.service.fetchById(workspaceSlug, projectId, pageId, trackVisit ?? true);

      runInAction(() => {
        if (page?.id) {
          const pageInstance = this.getPageById(page.id);
          if (pageInstance) {
            pageInstance.mutateProperties(page, false);
          } else {
            set(this.data, [page.id], new ProjectPage(this.store, page));
          }
        }
        this.loader = undefined;
      });

      return page;
    } catch (error) {
      runInAction(() => {
        this.loader = undefined;
        this.error = {
          title: "Failed",
          description: "Failed to fetch the page, Please try again later.",
        };
      });
      throw error;
    }
  };

  /**
   * @description create a page
   * @param {Partial<TPage>} pageData
   */
  createPage = async (pageData: Partial<TPage>) => {
    try {
      const { workspaceSlug, projectId } = this.store.router;
      if (!workspaceSlug || !projectId) return undefined;

      runInAction(() => {
        this.loader = "mutation-loader";
        this.error = undefined;
      });

      const payload = {
        ...pageData,
        parent_id: pageData.project_parent_id,
        operation_id: crypto.randomUUID(),
      };
      const page = await this.service.create(workspaceSlug, projectId, payload);
      runInAction(() => {
        if (page?.id) set(this.data, [page.id], new ProjectPage(this.store, page));
        if (page?.id) {
          const parentKey = page.project_parent_id ?? PAGE_HIERARCHY_ROOT;
          this.hierarchyChildren[parentKey] = [...(this.hierarchyChildren[parentKey] ?? []), page.id];
        }
        this.loader = undefined;
      });

      return page;
    } catch (error) {
      runInAction(() => {
        this.loader = undefined;
        this.error = {
          title: "Failed",
          description: "Failed to create a page, Please try again later.",
        };
      });
      throw error;
    }
  };

  /**
   * @description delete a page
   * @param {string} pageId
   */
  removePage = async ({ pageId, shouldSync: _shouldSync = true }: { pageId: string; shouldSync?: boolean }) => {
    try {
      const { workspaceSlug, projectId } = this.store.router;
      if (!workspaceSlug || !projectId || !pageId) return undefined;

      await this.service.remove(workspaceSlug, projectId, pageId);
      runInAction(() => {
        unset(this.data, [pageId]);
        if (this.rootStore.favorite.entityMap[pageId]) this.rootStore.favorite.removeFavoriteFromStore(pageId);
      });
    } catch (error) {
      runInAction(() => {
        this.loader = undefined;
        this.error = {
          title: "Failed",
          description: "Failed to delete a page, Please try again later.",
        };
      });
      throw error;
    }
  };

  /**
   * @description move a page to a new project
   * @param {string} workspaceSlug
   * @param {string} projectId
   * @param {string} pageId
   * @param {string} newProjectId
   */
  movePage = async (workspaceSlug: string, projectId: string, pageId: string, newProjectId: string) => {
    try {
      await this.service.move(workspaceSlug, projectId, pageId, newProjectId);
      runInAction(() => {
        unset(this.data, [pageId]);
      });
    } catch (error) {
      console.error("Unable to move page", error);
      throw error;
    }
  };

  fetchHierarchyBranch = (parentId: string | null = null, force = false): Promise<void> => {
    const { workspaceSlug, projectId } = this.store.router;
    if (!workspaceSlug || !projectId) return Promise.resolve();
    const branchKey = parentId ?? PAGE_HIERARCHY_ROOT;
    const pendingRequest = this.hierarchyBranchRequests.get(branchKey);
    if (pendingRequest) {
      // A forced refresh must run after an in-flight request. Otherwise its older
      // response can overwrite an optimistic create or move made meanwhile.
      return force
        ? pendingRequest.then(
            () => this.fetchHierarchyBranch(parentId, true),
            () => this.fetchHierarchyBranch(parentId, true)
          )
        : pendingRequest;
    }
    if (!force && this.hierarchyBranchState[branchKey] === "loaded") return Promise.resolve();

    const request = (async () => {
      runInAction(() => {
        this.hierarchyBranchState[branchKey] = "loading";
      });
      try {
        const response = await this.service.fetchHierarchy(workspaceSlug, projectId, parentId);
        runInAction(() => {
          this.hierarchyChildren[branchKey] = response.results.map((node) => node.id);
          for (const node of response.results) this.hierarchyNodes[node.id] = node;
          if (parentId) {
            const parent = this.hierarchyNodes[parentId];
            if (parent) {
              parent.child_count = response.total_count;
              parent.has_children = response.total_count > 0;
              if (!parent.has_children)
                this.expandedHierarchyIds = this.expandedHierarchyIds.filter((id) => id !== parentId);
            }
          }
          if (response.revision > this.hierarchyRevision) this.hierarchyRevision = response.revision;
          this.hierarchyBranchState[branchKey] = "loaded";
        });
      } catch (error) {
        runInAction(() => {
          this.hierarchyBranchState[branchKey] = "error";
        });
        throw error;
      }
    })();

    this.hierarchyBranchRequests.set(branchKey, request);
    return request.finally(() => {
      if (this.hierarchyBranchRequests.get(branchKey) === request) this.hierarchyBranchRequests.delete(branchKey);
    });
  };

  loadHierarchyPath = async (pageId: string) => {
    const { workspaceSlug, projectId } = this.store.router;
    if (!workspaceSlug || !projectId) return [];
    const response = await this.service.fetchHierarchyPath(workspaceSlug, projectId, pageId);
    await this.fetchHierarchyBranch(null);
    await Promise.all(response.path.slice(0, -1).map((item) => this.fetchHierarchyBranch(item.id)));
    runInAction(() => {
      this.hierarchyPaths[pageId] = response.path;
      this.hierarchyRevision = reconcilePageHierarchyRevision(this.hierarchyRevision, response.revision);
      this.expandedHierarchyIds = Array.from(
        new Set([...this.expandedHierarchyIds, ...response.path.slice(0, -1).map((item) => item.id)])
      );
    });
    this.scheduleHierarchyPreferenceSave();
    return response.path;
  };

  toggleHierarchyNode = async (pageId: string) => {
    const isExpanded = this.expandedHierarchyIds.includes(pageId);
    if (!isExpanded && this.hierarchyBranchState[pageId] !== "loaded") await this.fetchHierarchyBranch(pageId);
    runInAction(() => {
      this.expandedHierarchyIds = isExpanded
        ? this.expandedHierarchyIds.filter((id) => id !== pageId)
        : [...this.expandedHierarchyIds, pageId];
    });
    this.scheduleHierarchyPreferenceSave();
  };

  movePageInHierarchy = async (pageId: string, payload: Omit<TPageHierarchyMovePayload, "operation_id">) => {
    const { workspaceSlug, projectId } = this.store.router;
    if (!workspaceSlug || !projectId) return;
    const node = this.hierarchyNodes[pageId];
    if (!node) return;
    const submittedRevision = this.hierarchyRevision;
    const plannedMove = planOptimisticPageHierarchyMove(node, this.hierarchyChildren, payload);
    const { snapshot } = plannedMove;
    const oldBranchLoaded = this.hierarchyBranchState[snapshot.oldParentKey] === "loaded";
    const newBranchLoaded = this.hierarchyBranchState[snapshot.newParentKey] === "loaded";
    const parentSnapshots = new Map<string, TPageHierarchyNode>();
    for (const parentKey of new Set([snapshot.oldParentKey, snapshot.newParentKey])) {
      if (parentKey !== PAGE_HIERARCHY_ROOT && this.hierarchyNodes[parentKey])
        parentSnapshots.set(parentKey, { ...this.hierarchyNodes[parentKey] });
    }
    const expandedIdsSnapshot = [...this.expandedHierarchyIds];
    runInAction(() => {
      if (oldBranchLoaded) this.hierarchyChildren[snapshot.oldParentKey] = plannedMove.oldChildren;
      if (newBranchLoaded) this.hierarchyChildren[snapshot.newParentKey] = plannedMove.newChildren;
      this.hierarchyNodes[pageId] = plannedMove.node;
      if (snapshot.oldParentKey !== snapshot.newParentKey) {
        const oldParent = this.hierarchyNodes[snapshot.oldParentKey];
        if (oldParent) {
          oldParent.child_count = oldBranchLoaded
            ? plannedMove.oldChildren.length
            : Math.max(0, oldParent.child_count - 1);
          oldParent.has_children = oldParent.child_count > 0;
          if (!oldParent.has_children)
            this.expandedHierarchyIds = this.expandedHierarchyIds.filter((id) => id !== oldParent.id);
        }
        const newParent = this.hierarchyNodes[snapshot.newParentKey];
        if (newParent) {
          newParent.child_count = newBranchLoaded ? plannedMove.newChildren.length : newParent.child_count + 1;
          newParent.has_children = true;
        }
      }
    });
    if (this.expandedHierarchyIds.length !== expandedIdsSnapshot.length) this.scheduleHierarchyPreferenceSave();
    try {
      const result = await this.service.moveInHierarchy(workspaceSlug, projectId, pageId, {
        ...payload,
        operation_id: crypto.randomUUID(),
        base_revision: this.hierarchyRevision,
      });
      runInAction(() => {
        this.hierarchyRevision = reconcilePageHierarchyRevision(this.hierarchyRevision, result.revision);
        if (newBranchLoaded) this.hierarchyChildren[snapshot.newParentKey] = result.siblings.map((item) => item.id);
        for (const item of result.siblings) {
          if (this.hierarchyNodes[item.id]) this.hierarchyNodes[item.id].sort_order = item.sort_order;
        }
      });
      const branchesToRefresh = new Set<string | null>();
      if (snapshot.oldParentKey !== snapshot.newParentKey) {
        branchesToRefresh.add(snapshot.node.parent_id);
        branchesToRefresh.add(payload.parent_id);
      }
      if (result.revision > submittedRevision + 1) {
        branchesToRefresh.add(snapshot.node.parent_id);
        branchesToRefresh.add(payload.parent_id);
      }
      await Promise.all([...branchesToRefresh].map((parentId) => this.fetchHierarchyBranch(parentId, true)));
    } catch (error) {
      const restored = restoreOptimisticPageHierarchyMove(snapshot);
      const didExpandedIdsChange =
        this.expandedHierarchyIds.length !== expandedIdsSnapshot.length ||
        this.expandedHierarchyIds.some((id, index) => id !== expandedIdsSnapshot[index]);
      runInAction(() => {
        this.hierarchyNodes[pageId] = restored.node;
        for (const [parentKey, childIds] of Object.entries(restored.childIdsByParent)) {
          if (this.hierarchyBranchState[parentKey] === "loaded") this.hierarchyChildren[parentKey] = childIds;
        }
        for (const [parentKey, parent] of parentSnapshots) this.hierarchyNodes[parentKey] = parent;
        this.expandedHierarchyIds = expandedIdsSnapshot;
      });
      if (didExpandedIdsChange) this.scheduleHierarchyPreferenceSave();
      await Promise.all([
        this.fetchHierarchyBranch(snapshot.node.parent_id, true),
        this.fetchHierarchyBranch(payload.parent_id, true),
      ]);
      throw error;
    }
  };

  createChildPage = async (parentId: string | null, pageData: Partial<TPage> = {}) => {
    const page = await this.createPage({ ...pageData, project_parent_id: parentId });
    if (parentId && page?.id) {
      await this.fetchHierarchyBranch(parentId, true);
      if (!this.expandedHierarchyIds.includes(parentId)) {
        runInAction(() => {
          this.expandedHierarchyIds.push(parentId);
        });
      }
      this.scheduleHierarchyPreferenceSave();
    } else if (page?.id) await this.fetchHierarchyBranch(null, true);
    if (page?.id) {
      const createdPageId = page.id;
      runInAction(() => {
        this.pendingTitleEditPageId = createdPageId;
      });
    }
    return page;
  };

  completePendingTitleEdit = (pageId: string, didFocus: boolean) => {
    if (!didFocus || this.pendingTitleEditPageId !== pageId) return false;
    this.pendingTitleEditPageId = null;
    return true;
  };

  cancelPendingTitleEdit = (pageId: string) => {
    if (this.pendingTitleEditPageId !== pageId) return false;
    this.pendingTitleEditPageId = null;
    return true;
  };

  loadHierarchyPreferences = async () => {
    const { workspaceSlug, projectId } = this.store.router;
    if (!workspaceSlug || !projectId) return;
    const preferences = await this.service.fetchHierarchyPreferences(workspaceSlug, projectId);
    runInAction(() => {
      this.expandedHierarchyIds = preferences.expanded_ids.slice(-200);
    });
    try {
      await this.fetchHierarchyBranch(null);
    } catch {
      return;
    }
    await this.hydrateExpandedHierarchyBranches();
  };

  private hydrateExpandedHierarchyBranches = async () => {
    const restoredIds = new Set(this.expandedHierarchyIds);
    const hydratedIds = new Set<string>();
    let hasBranchError = false;

    const hydrateChildren = async (parentId: string | null): Promise<void> => {
      const branchKey = parentId ?? PAGE_HIERARCHY_ROOT;
      const expandedChildren = (this.hierarchyChildren[branchKey] ?? []).filter((id) => restoredIds.has(id));
      await Promise.all(
        expandedChildren.map(async (pageId) => {
          const node = this.hierarchyNodes[pageId];
          if (!node || node.archived_at || !node.has_children) return;
          hydratedIds.add(pageId);
          try {
            await this.fetchHierarchyBranch(pageId);
            await hydrateChildren(pageId);
          } catch {
            hasBranchError = true;
          }
        })
      );
    };

    await hydrateChildren(null);
    if (hasBranchError) return;

    const prunedIds = this.expandedHierarchyIds.filter((id) => hydratedIds.has(id));
    if (
      prunedIds.length !== this.expandedHierarchyIds.length ||
      prunedIds.some((id, index) => id !== this.expandedHierarchyIds[index])
    ) {
      runInAction(() => {
        this.expandedHierarchyIds = prunedIds;
      });
      this.scheduleHierarchyPreferenceSave();
    }
  };

  private scheduleHierarchyPreferenceSave = () => {
    if (this.hierarchyPreferenceTimer) clearTimeout(this.hierarchyPreferenceTimer);
    this.hierarchyPreferenceTimer = setTimeout(() => {
      const { workspaceSlug, projectId } = this.store.router;
      if (!workspaceSlug || !projectId) return;
      const expandedIds = pruneExpandedPageHierarchyIds(this.expandedHierarchyIds, this.hierarchyNodes);
      void this.service.updateHierarchyPreferences(workspaceSlug, projectId, {
        version: 1,
        expanded_ids: expandedIds,
      });
    }, 500);
  };

  loadAllPages = async (query: TPageHierarchyAllPagesQuery = {}, append = false) => {
    const { workspaceSlug, projectId } = this.store.router;
    if (!workspaceSlug || !projectId) return;
    runInAction(() => {
      this.allPagesState = "loading";
      this.allPagesError = null;
      if (!append) {
        this.allPagesQuery = query;
        this.selectedAllPageIds = [];
        this.bulkPreview = null;
      }
    });
    try {
      const response = await this.service.fetchAllPages(workspaceSlug, projectId, query);
      runInAction(() => {
        this.allPagesNodes = append ? [...this.allPagesNodes, ...response.results] : response.results;
        this.allPagesTotal = response.total_count;
        this.allPagesNextOffset = response.next_offset;
        this.hierarchyRevision = reconcilePageHierarchyRevision(this.hierarchyRevision, response.revision);
        for (const node of response.results) this.hierarchyNodes[node.id] = node;
        this.allPagesState = "loaded";
      });
    } catch (error) {
      runInAction(() => {
        this.allPagesState = "error";
        this.allPagesError = (error as { error?: string })?.error ?? "Unable to load pages";
      });
      throw error;
    }
  };

  searchHierarchyDestinations = async (query: string) => {
    const { workspaceSlug, projectId } = this.store.router;
    if (!workspaceSlug || !projectId) return [];
    const response = await this.service.fetchAllPages(workspaceSlug, projectId, {
      search: query,
      archived: "active",
      sort_by: "path",
      sort_order: "asc",
      limit: 100,
    });
    runInAction(() => {
      this.hierarchyRevision = reconcilePageHierarchyRevision(this.hierarchyRevision, response.revision);
      for (const node of response.results) this.hierarchyNodes[node.id] = node;
    });
    return response.results;
  };

  loadHierarchySiblings = async (parentId: string | null) => {
    const { workspaceSlug, projectId } = this.store.router;
    if (!workspaceSlug || !projectId) return [];
    const results: TPageHierarchyNode[] = [];
    let offset = 0;
    let revision = this.hierarchyRevision;
    let nextOffset: number | null = 0;
    while (nextOffset !== null) {
      // Cursor pages must be requested in order because each response supplies the next offset.
      // oxlint-disable-next-line no-await-in-loop
      const response = await this.service.fetchHierarchy(workspaceSlug, projectId, parentId, false, offset, 200);
      results.push(...response.results);
      revision = reconcilePageHierarchyRevision(revision, response.revision);
      nextOffset = response.next_offset;
      offset = nextOffset ?? offset;
    }
    const branchKey = parentId ?? PAGE_HIERARCHY_ROOT;
    runInAction(() => {
      this.hierarchyRevision = revision;
      this.hierarchyChildren[branchKey] = results.map((node) => node.id);
      this.hierarchyBranchState[branchKey] = "loaded";
      for (const node of results) this.hierarchyNodes[node.id] = node;
    });
    return results;
  };

  toggleAllPageSelection = (pageId: string) => {
    this.selectedAllPageIds = togglePageHierarchySelection(this.selectedAllPageIds, pageId);
    this.bulkPreview = null;
  };

  clearAllPageSelection = () => {
    this.selectedAllPageIds = [];
    this.bulkPreview = null;
  };

  previewAllPagesBulk = async (
    operation: TPageHierarchyBulkOperation,
    placement: Partial<Pick<TPageHierarchyBulkPayload, "parent_id" | "position" | "relative_page_id">> = {}
  ) => {
    const { workspaceSlug, projectId } = this.store.router;
    if (!workspaceSlug || !projectId) throw new Error("Project context is required");
    runInAction(() => {
      this.bulkPreview = null;
    });
    const preview = await this.service.previewBulkHierarchy(workspaceSlug, projectId, {
      page_ids: this.selectedAllPageIds,
      operation,
      ...placement,
    });
    runInAction(() => {
      this.bulkPreview = preview;
    });
    return preview;
  };

  executeAllPagesBulk = async (
    operation: TPageHierarchyBulkOperation,
    placement: Partial<Pick<TPageHierarchyBulkPayload, "parent_id" | "position" | "relative_page_id">> = {}
  ) => {
    const { workspaceSlug, projectId } = this.store.router;
    if (!workspaceSlug || !projectId) throw new Error("Project context is required");
    const result = await this.service.mutateBulkHierarchy(workspaceSlug, projectId, {
      page_ids: this.selectedAllPageIds,
      operation,
      operation_id: crypto.randomUUID(),
      base_revision: this.hierarchyRevision,
      ...placement,
    });
    runInAction(() => {
      this.hierarchyRevision = reconcilePageHierarchyRevision(this.hierarchyRevision, result.revision);
      this.selectedAllPageIds = [];
      this.bulkPreview = null;
      this.hierarchyBranchState = {};
    });
    await Promise.all([this.loadAllPages(this.allPagesQuery), this.fetchHierarchyBranch(null, true)]);
    return result;
  };
}
