/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { Fragment, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { combine } from "@atlaskit/pragmatic-drag-and-drop/combine";
import { draggable, dropTargetForElements } from "@atlaskit/pragmatic-drag-and-drop/element/adapter";
import { observer } from "mobx-react";
import { useParams } from "next/navigation";
import { Archive, ChevronRight, GripVertical, List, LockKeyhole, Move, Plus, Star } from "lucide-react";
import { EPageAccess } from "@plane/constants";
import { useTranslation } from "@plane/i18n";
import { Logo } from "@plane/propel/emoji-icon-picker";
import { PageIcon } from "@plane/propel/icons";
import type { TPageHierarchyNode, TPageHierarchyRow } from "@plane/types";
import {
  canDropPageHierarchyPlacement,
  getInvalidPageHierarchyDestinationIds,
  getPageHierarchyDropPlacement,
  getPageName,
  PAGE_HIERARCHY_ROOT,
} from "@plane/utils";
import { useAppRouter } from "@/hooks/use-app-router";
import { EPageStoreType, usePageStore } from "@/hooks/store";
import { MovePageDialog } from "./move-dialog";

type DropPlacement = "before" | "inside" | "after";

const focusTreeRow = (index: number) => {
  const rows = Array.from(document.querySelectorAll<HTMLElement>("[data-tree-row]"));
  rows[Math.max(0, Math.min(index, rows.length - 1))]?.focus();
};

type TreeRowProps = {
  row: TPageHierarchyRow;
  index: number;
  selectedId?: string;
  expanded: boolean;
  invalidDestinationIds: Set<string>;
  canAcceptDrop: (sourceId: string, target: TPageHierarchyNode, placement: DropPlacement) => boolean;
  onOpen: (id: string) => void;
  onToggle: (id: string) => void;
  onAddChild: (id: string) => void;
  onMoveCommand: (id: string) => void;
  onDrop: (sourceId: string, target: TPageHierarchyNode, placement: DropPlacement) => void;
  onDragState: (id: string | null) => void;
  onKeyDown: (event: React.KeyboardEvent<HTMLDivElement>, row: TPageHierarchyRow, index: number) => void;
};

const KnowledgeBaseTreeRow = observer(function KnowledgeBaseTreeRow(props: TreeRowProps) {
  const {
    row,
    index,
    selectedId,
    expanded,
    invalidDestinationIds,
    canAcceptDrop,
    onOpen,
    onToggle,
    onAddChild,
    onMoveCommand,
    onDrop,
    onDragState,
    onKeyDown,
  } = props;
  const { t } = useTranslation();
  const rowRef = useRef<HTMLDivElement | null>(null);
  const dragHandleRef = useRef<HTMLButtonElement | null>(null);
  const [dropPlacement, setDropPlacement] = useState<DropPlacement | null>(null);
  const visualDepth = Math.min(row.depth - 1, 6);
  const invalidDestination = invalidDestinationIds.has(row.id);

  useEffect(() => {
    const element = rowRef.current;
    if (!element || row.node.archived_at) return;
    const registrations = [
      dropTargetForElements({
        element,
        canDrop: ({ source, input }) => {
          const placement = getPageHierarchyDropPlacement(input.clientY, element.getBoundingClientRect());
          return source.data.type === "project-page" && canAcceptDrop(String(source.data.pageId), row.node, placement);
        },
        getData: ({ input, element: targetElement }) => ({
          pageId: row.id,
          placement: getPageHierarchyDropPlacement(input.clientY, targetElement.getBoundingClientRect()),
        }),
        onDrag: ({ self }) => setDropPlacement(self.data.placement as DropPlacement),
        onDragLeave: () => setDropPlacement(null),
        onDrop: ({ source, self }) => {
          setDropPlacement(null);
          const placement = self.data.placement as DropPlacement;
          const sourceId = String(source.data.pageId);
          if (canAcceptDrop(sourceId, row.node, placement)) onDrop(sourceId, row.node, placement);
        },
      }),
    ];
    if (row.node.permissions.can_move)
      registrations.push(
        draggable({
          element,
          dragHandle: dragHandleRef.current ?? undefined,
          getInitialData: () => ({ pageId: row.id, type: "project-page" }),
          onDragStart: () => onDragState(row.id),
          onDrop: () => onDragState(null),
        })
      );
    return combine(...registrations);
  }, [canAcceptDrop, onDragState, onDrop, row]);

  return (
    <div
      ref={rowRef}
      role="treeitem"
      aria-level={row.depth}
      aria-expanded={row.node.has_children ? expanded : undefined}
      aria-selected={selectedId === row.id}
      aria-disabled={invalidDestination || undefined}
      data-tree-row={row.id}
      tabIndex={selectedId === row.id || (!selectedId && index === 0) ? 0 : -1}
      onKeyDown={(event) => onKeyDown(event, row, index)}
      className={`group focus-visible:ring-accent relative flex h-9 min-w-0 items-center gap-1 border-y border-transparent pr-1 text-13 outline-none focus-visible:ring-2 ${
        selectedId === row.id ? "bg-layer-2" : "hover:bg-layer-1"
      } ${dropPlacement === "inside" ? "bg-accent-subtle" : ""} ${invalidDestination ? "opacity-50" : ""}`}
      style={{ paddingLeft: `${8 + visualDepth * 16}px` }}
    >
      {dropPlacement === "before" && <span className="absolute inset-x-1 top-0 h-0.5 bg-accent-primary" />}
      {dropPlacement === "after" && <span className="absolute inset-x-1 bottom-0 h-0.5 bg-accent-primary" />}
      <button
        type="button"
        className="focus-visible:ring-accent grid size-6 shrink-0 place-items-center rounded-sm outline-none focus-visible:ring-2"
        onClick={() => row.node.has_children && onToggle(row.id)}
        aria-label={t(expanded ? "wiki_collections.list.collapse_page" : "wiki_collections.list.expand_page")}
        disabled={!row.node.has_children}
      >
        {row.node.has_children && (
          <ChevronRight className={`size-3.5 transition-transform ${expanded ? "rotate-90" : ""}`} />
        )}
      </button>
      <button
        type="button"
        className="focus-visible:ring-accent flex min-w-0 flex-1 items-center gap-2 rounded-sm text-left outline-none focus-visible:ring-2"
        onClick={() => onOpen(row.id)}
      >
        {row.node.logo_props?.in_use ? (
          <Logo logo={row.node.logo_props} size={16} type="lucide" />
        ) : (
          <PageIcon className="size-4 shrink-0 text-tertiary" />
        )}
        <span className="min-w-0 flex-1 truncate">{getPageName(row.node.name)}</span>
        <span className="flex shrink-0 items-center gap-1 text-tertiary">
          {row.node.access === EPageAccess.PRIVATE && (
            <LockKeyhole className="size-3.5" aria-label={t("common.access.private")} />
          )}
          {row.node.is_locked && (
            <LockKeyhole className="size-3.5" aria-label={t("wiki_collections.list.restricted_access")} />
          )}
          {row.node.archived_at && (
            <Archive className="size-3.5" aria-label={t("wiki_collections.predefined.archived")} />
          )}
        </span>
      </button>
      {!row.node.archived_at && (
        <div className="hidden shrink-0 items-center group-focus-within:flex group-hover:flex">
          {row.node.permissions.can_create_child && (
            <button
              type="button"
              data-page-title-focus-source
              className="focus-visible:ring-accent grid size-7 place-items-center rounded-sm hover:bg-layer-2 focus-visible:ring-2"
              onClick={() => onAddChild(row.id)}
              title={t("wiki_collections.header.add_page")}
              aria-label={t("wiki_collections.header.add_page")}
            >
              <Plus className="size-3.5" />
            </button>
          )}
          {row.node.permissions.can_move && (
            <>
              <button
                type="button"
                className="focus-visible:ring-accent grid size-7 place-items-center rounded-sm hover:bg-layer-2 focus-visible:ring-2"
                onClick={() => onMoveCommand(row.id)}
                title={t("wiki_collections.add_existing_page_modal.submit")}
                aria-label={t("wiki_collections.add_existing_page_modal.submit")}
              >
                <Move className="size-3.5" />
              </button>
              <button
                ref={dragHandleRef}
                type="button"
                className="focus-visible:ring-accent grid size-7 cursor-grab place-items-center rounded-sm hover:bg-layer-2 focus-visible:ring-2"
                title={t("common.drag_to_rearrange")}
                aria-label={t("common.drag_to_rearrange")}
              >
                <GripVertical className="size-3.5" />
              </button>
            </>
          )}
        </div>
      )}
    </div>
  );
});

export const KnowledgeBaseTree = observer(function KnowledgeBaseTree() {
  const { workspaceSlug, projectId, pageId } = useParams();
  const router = useAppRouter();
  const { t } = useTranslation();
  const store = usePageStore(EPageStoreType.PROJECT);
  const {
    data,
    hierarchyNodes,
    hierarchyChildren,
    hierarchyBranchState,
    expandedHierarchyIds,
    visibleHierarchyRows,
    fetchHierarchyBranch,
    fetchPagesList,
    loadHierarchyPath,
    loadHierarchyPreferences,
    toggleHierarchyNode,
    createChildPage,
    movePageInHierarchy,
    searchHierarchyDestinations,
    loadHierarchySiblings,
  } = store;
  const [movingPageId, setMovingPageId] = useState<string | null>(null);
  const [draggingPageId, setDraggingPageId] = useState<string | null>(null);
  const [operationError, setOperationError] = useState<string | null>(null);
  const selectedId = pageId?.toString();
  const rootState = hierarchyBranchState[PAGE_HIERARCHY_ROOT] ?? "idle";

  useEffect(() => {
    if (!workspaceSlug || !projectId) return;
    void Promise.allSettled([
      fetchHierarchyBranch(null),
      loadHierarchyPreferences(),
      fetchPagesList(workspaceSlug.toString(), projectId.toString()),
    ]);
  }, [fetchHierarchyBranch, fetchPagesList, loadHierarchyPreferences, projectId, workspaceSlug]);

  useEffect(() => {
    for (const expandedId of expandedHierarchyIds) {
      const node = hierarchyNodes[expandedId];
      const branchState = hierarchyBranchState[expandedId] ?? "idle";
      if (node?.has_children && !node.archived_at && branchState === "idle") {
        void fetchHierarchyBranch(expandedId).catch(() => undefined);
      }
    }
  });

  useEffect(() => {
    if (selectedId) void loadHierarchyPath(selectedId);
  }, [loadHierarchyPath, selectedId]);

  const openPage = useCallback(
    (id: string) => router.push(`/${workspaceSlug}/projects/${projectId}/pages/${id}`),
    [projectId, router, workspaceSlug]
  );
  const createChild = async (parentId: string | null) => {
    setOperationError(null);
    try {
      const page = await createChildPage(parentId);
      if (page?.id) openPage(page.id);
    } catch (cause) {
      setOperationError(
        (cause as { error?: string })?.error ?? t("wiki_collections.add_existing_page_modal.error_message")
      );
    }
  };
  const invalidDestinationIds = useMemo(() => {
    if (!draggingPageId) return new Set<string>();
    const invalid = new Set<string>([draggingPageId]);
    const queue = [draggingPageId];
    while (queue.length > 0) {
      const id = queue.shift();
      if (!id) continue;
      for (const childId of hierarchyChildren[id] ?? []) {
        invalid.add(childId);
        queue.push(childId);
      }
    }
    return invalid;
  }, [draggingPageId, hierarchyChildren]);
  const canAcceptDrop = useCallback(
    (sourceId: string, target: TPageHierarchyNode, placement: DropPlacement) =>
      canDropPageHierarchyPlacement(
        sourceId,
        target,
        placement,
        hierarchyNodes,
        getInvalidPageHierarchyDestinationIds(sourceId, hierarchyChildren)
      ),
    [hierarchyChildren, hierarchyNodes]
  );

  const handleDrop = useCallback(
    async (sourceId: string, target: TPageHierarchyNode, placement: DropPlacement) => {
      setDraggingPageId(sourceId);
      setOperationError(null);
      try {
        await movePageInHierarchy(sourceId, {
          parent_id: placement === "inside" ? target.id : target.parent_id,
          position: placement,
          relative_page_id: placement === "inside" ? null : target.id,
        });
      } catch (cause) {
        setOperationError(
          (cause as { error?: string })?.error ?? t("wiki_collections.add_existing_page_modal.error_message")
        );
      } finally {
        setDraggingPageId(null);
      }
    },
    [movePageInHierarchy, t]
  );

  const handleKeyDown = (event: React.KeyboardEvent<HTMLDivElement>, row: TPageHierarchyRow, index: number) => {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      focusTreeRow(index + 1);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      focusTreeRow(index - 1);
    } else if (event.key === "ArrowRight") {
      event.preventDefault();
      if (row.node.has_children && !expandedHierarchyIds.includes(row.id)) void toggleHierarchyNode(row.id);
      else focusTreeRow(index + 1);
    } else if (event.key === "ArrowLeft") {
      event.preventDefault();
      if (expandedHierarchyIds.includes(row.id)) void toggleHierarchyNode(row.id);
      else if (row.node.parent_id)
        document.querySelector<HTMLElement>(`[data-tree-row="${row.node.parent_id}"]`)?.focus();
    } else if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      openPage(row.id);
    }
  };

  const favorites = Object.values(data).filter((page) => page.is_favorite && !page.archived_at);
  const moveInvalidIds = movingPageId
    ? getInvalidPageHierarchyDestinationIds(movingPageId, hierarchyChildren)
    : new Set<string>();

  return (
    <div className="flex h-full min-h-0 flex-col bg-surface-1" aria-label={t("knowledge_base")}>
      <div className="flex h-11 shrink-0 items-center justify-between border-b border-subtle px-3">
        <h1 className="truncate text-14 font-medium">{t("knowledge_base")}</h1>
        <div className="flex items-center">
          <button
            type="button"
            onClick={() => router.push(`/${workspaceSlug}/projects/${projectId}/pages?view=all`)}
            className="focus-visible:ring-accent grid size-8 place-items-center rounded hover:bg-layer-1 focus-visible:ring-2"
            title={t("common.all_pages")}
            aria-label={t("common.all_pages")}
          >
            <List className="size-4" />
          </button>
          <button
            type="button"
            data-page-title-focus-source
            onClick={() => void createChild(null)}
            className="focus-visible:ring-accent grid size-8 place-items-center rounded hover:bg-layer-1 focus-visible:ring-2"
            title={t("wiki_collections.header.add_page")}
            aria-label={t("wiki_collections.header.add_page")}
          >
            <Plus className="size-4" />
          </button>
        </div>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto py-2">
        {operationError && (
          <div role="alert" className="mx-3 mb-2 text-12 text-danger-primary">
            {operationError}
          </div>
        )}
        {favorites.length > 0 && (
          <section aria-label={t("common.favorites")} className="mb-2 border-b border-subtle pb-2">
            <div className="flex h-7 items-center gap-2 px-3 text-11 font-medium text-tertiary">
              <Star className="size-3.5" /> {t("common.favorites")}
            </div>
            {favorites.map((page) => (
              <button
                key={page.id}
                type="button"
                onClick={() => page.id && openPage(page.id)}
                className="flex h-8 w-full min-w-0 items-center gap-2 px-3 text-left text-13 hover:bg-layer-1"
              >
                <PageIcon className="size-4 shrink-0 text-tertiary" />
                <span className="truncate">{getPageName(page.name)}</span>
              </button>
            ))}
          </section>
        )}
        {rootState === "loading" && <div className="px-3 py-4 text-13 text-tertiary">{t("common.loading")}</div>}
        {rootState === "error" && (
          <button
            type="button"
            onClick={() => void fetchHierarchyBranch(null, true)}
            className="mx-3 text-13 text-accent-primary"
          >
            {t("common.retry")}
          </button>
        )}
        {rootState === "loaded" && visibleHierarchyRows.length === 0 && (
          <div className="px-3 py-4 text-13 text-tertiary">{t("wiki_collections.list.no_pages_title")}</div>
        )}
        <div role="tree" aria-label={t("knowledge_base")}>
          {visibleHierarchyRows.map((row, index) => (
            <Fragment key={row.id}>
              <KnowledgeBaseTreeRow
                row={row}
                index={index}
                selectedId={selectedId}
                expanded={expandedHierarchyIds.includes(row.id)}
                invalidDestinationIds={invalidDestinationIds}
                canAcceptDrop={canAcceptDrop}
                onOpen={openPage}
                onToggle={(id) =>
                  void toggleHierarchyNode(id).catch((cause) =>
                    setOperationError(
                      (cause as { error?: string })?.error ??
                        t("wiki_collections.add_existing_page_modal.error_message")
                    )
                  )
                }
                onAddChild={(id) => void createChild(id)}
                onMoveCommand={setMovingPageId}
                onDrop={(sourceId, target, placement) => void handleDrop(sourceId, target, placement)}
                onDragState={setDraggingPageId}
                onKeyDown={handleKeyDown}
              />
              {expandedHierarchyIds.includes(row.id) && hierarchyBranchState[row.id] === "loading" && (
                <div className="h-7 px-10 text-12 text-tertiary">{t("common.loading")}</div>
              )}
              {expandedHierarchyIds.includes(row.id) && hierarchyBranchState[row.id] === "error" && (
                <button
                  type="button"
                  onClick={() => void fetchHierarchyBranch(row.id, true)}
                  className="h-7 px-10 text-12 text-accent-primary"
                >
                  {t("common.retry")}
                </button>
              )}
            </Fragment>
          ))}
        </div>
      </div>
      {movingPageId && (
        <MovePageDialog
          nodes={Object.values(hierarchyNodes)}
          invalidDestinationIds={moveInvalidIds}
          onSearch={searchHierarchyDestinations}
          onLoadSiblings={loadHierarchySiblings}
          onClose={() => setMovingPageId(null)}
          onMove={(placement) => movePageInHierarchy(movingPageId, placement)}
        />
      )}
    </div>
  );
});
