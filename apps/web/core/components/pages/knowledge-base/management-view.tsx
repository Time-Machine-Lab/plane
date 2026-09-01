/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useMemo, useState } from "react";
import { observer } from "mobx-react";
import { useParams, useSearchParams } from "next/navigation";
import { Archive, ArrowDownAZ, ArrowUpAZ, Copy, LockKeyhole, Move, RotateCcw, Search, Trash2, X } from "lucide-react";
import { EPageAccess } from "@plane/constants";
import { useTranslation } from "@plane/i18n";
import { PageIcon } from "@plane/propel/icons";
import { Avatar } from "@plane/ui";
import type { TPageHierarchyAllPagesQuery, TPageHierarchyBulkOperation, TPageHierarchyBulkPayload } from "@plane/types";
import {
  getFileURL,
  getInvalidPageHierarchyDestinationIds,
  getPageHierarchyArchiveStateFromType,
  getPageName,
  renderFormattedDate,
} from "@plane/utils";
import { EPageStoreType, usePageStore } from "@/hooks/store";
import { useMember } from "@/hooks/store/use-member";
import { useAppRouter } from "@/hooks/use-app-router";
import { MovePageDialog } from "./move-dialog";

type PendingBulkAction = {
  operation: TPageHierarchyBulkOperation;
  placement?: Partial<Pick<TPageHierarchyBulkPayload, "parent_id" | "position" | "relative_page_id">>;
};

export const KnowledgeBaseManagementView = observer(function KnowledgeBaseManagementView() {
  const { workspaceSlug, projectId } = useParams();
  const router = useAppRouter();
  const searchParams = useSearchParams();
  const { t } = useTranslation();
  const { getUserDetails } = useMember();
  const store = usePageStore(EPageStoreType.PROJECT);
  const {
    allPagesNodes,
    allPagesTotal,
    allPagesNextOffset,
    allPagesState,
    allPagesError,
    selectedAllPageIds,
    bulkPreview,
    hierarchyNodes,
    hierarchyChildren,
    loadAllPages,
    toggleAllPageSelection,
    clearAllPageSelection,
    previewAllPagesBulk,
    executeAllPagesBulk,
    searchHierarchyDestinations,
    loadHierarchySiblings,
  } = store;
  const [query, setQuery] = useState("");
  const archiveStateFromUrl = getPageHierarchyArchiveStateFromType(searchParams.get("type"));
  const [archiveState, setArchiveState] = useState<TPageHierarchyAllPagesQuery["archived"]>(archiveStateFromUrl);
  const [sortBy, setSortBy] = useState<TPageHierarchyAllPagesQuery["sort_by"]>("updated_at");
  const [sortOrder, setSortOrder] = useState<TPageHierarchyAllPagesQuery["sort_order"]>("desc");
  const [pendingAction, setPendingAction] = useState<PendingBulkAction | null>(null);
  const [showMove, setShowMove] = useState(false);
  const [mutating, setMutating] = useState(false);
  const [bulkError, setBulkError] = useState<string | null>(null);

  const currentQuery = useMemo<TPageHierarchyAllPagesQuery>(
    () => ({ search: query, archived: archiveState, sort_by: sortBy, sort_order: sortOrder, limit: 50 }),
    [archiveState, query, sortBy, sortOrder]
  );
  useEffect(() => {
    const timer = window.setTimeout(() => void loadAllPages(currentQuery), 200);
    return () => window.clearTimeout(timer);
  }, [currentQuery, loadAllPages]);
  useEffect(() => setArchiveState(archiveStateFromUrl), [archiveStateFromUrl]);

  const updateArchiveState = (nextState: NonNullable<TPageHierarchyAllPagesQuery["archived"]>) => {
    setArchiveState(nextState);
    const nextSearchParams = new URLSearchParams(searchParams.toString());
    if (nextState === "all") nextSearchParams.delete("type");
    else nextSearchParams.set("type", nextState);
    const queryString = nextSearchParams.toString();
    router.replace(`/${workspaceSlug}/projects/${projectId}/pages${queryString ? `?${queryString}` : ""}`);
  };

  const requestBulk = async (operation: TPageHierarchyBulkOperation, placement?: PendingBulkAction["placement"]) => {
    setBulkError(null);
    try {
      await previewAllPagesBulk(operation, placement);
      setPendingAction({ operation, placement });
      setShowMove(false);
    } catch (cause) {
      setBulkError((cause as { error?: string })?.error ?? t("wiki_collections.add_existing_page_modal.error_message"));
    }
  };
  const confirmBulk = async () => {
    if (!pendingAction) return;
    setMutating(true);
    setBulkError(null);
    try {
      await executeAllPagesBulk(pendingAction.operation, pendingAction.placement);
      setPendingAction(null);
    } catch (cause) {
      setBulkError((cause as { error?: string })?.error ?? t("wiki_collections.add_existing_page_modal.error_message"));
    } finally {
      setMutating(false);
    }
  };
  const invalidMoveIds = useMemo(() => {
    const invalid = new Set<string>();
    for (const pageId of selectedAllPageIds) {
      for (const id of getInvalidPageHierarchyDestinationIds(pageId, hierarchyChildren)) invalid.add(id);
    }
    return invalid;
  }, [hierarchyChildren, selectedAllPageIds]);
  const selectedNodes = useMemo(
    () => allPagesNodes.filter((node) => selectedAllPageIds.includes(node.id)),
    [allPagesNodes, selectedAllPageIds]
  );
  const canMoveSelection = selectedNodes.length > 0 && selectedNodes.every((node) => node.permissions.can_move);
  const canArchiveSelection = selectedNodes.length > 0 && selectedNodes.every((node) => node.permissions.can_archive);
  const canRestoreSelection = selectedNodes.length > 0 && selectedNodes.every((node) => node.permissions.can_restore);
  const canCopySelection = selectedNodes.length > 0 && selectedNodes.every((node) => node.permissions.can_create_child);

  return (
    <div className="flex h-full min-h-0 flex-col bg-surface-1">
      <div className="flex min-h-12 flex-wrap items-center gap-2 border-b border-subtle px-3 py-2">
        <button
          type="button"
          onClick={() => router.push(`/${workspaceSlug}/projects/${projectId}/pages`)}
          className="focus-visible:ring-accent grid size-8 place-items-center rounded hover:bg-layer-1 focus-visible:ring-2"
          aria-label={t("common.close")}
        >
          <X className="size-4" />
        </button>
        <h1 className="mr-auto text-14 font-medium">{t("common.all_pages")}</h1>
        <label className="relative min-w-48 flex-1 md:max-w-80">
          <Search className="pointer-events-none absolute top-2.5 left-2.5 size-4 text-tertiary" />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder={t("wiki_collections.add_existing_page_modal.search_placeholder")}
            className="focus:ring-accent h-9 w-full rounded border border-subtle bg-transparent pr-3 pl-8 text-13 outline-none focus:ring-2"
          />
        </label>
        <select
          value={archiveState}
          onChange={(event) =>
            updateArchiveState(event.target.value as NonNullable<TPageHierarchyAllPagesQuery["archived"]>)
          }
          className="h-9 rounded border border-subtle bg-transparent px-2 text-13"
        >
          <option value="all">{t("common.all_pages")}</option>
          <option value="active">{t("common.pages")}</option>
          <option value="archived">{t("wiki_collections.predefined.archived")}</option>
        </select>
        <select
          value={sortBy}
          onChange={(event) => setSortBy(event.target.value as TPageHierarchyAllPagesQuery["sort_by"])}
          className="h-9 rounded border border-subtle bg-transparent px-2 text-13"
          aria-label={t("project.project_view.sort_by.name")}
        >
          <option value="updated_at">{t("project.project_view.sort_by.updated_at")}</option>
          <option value="created_at">{t("project.project_view.sort_by.created_at")}</option>
          <option value="name">{t("common.name")}</option>
          <option value="depth">{t("wiki_collections.list.columns.nested_pages")}</option>
          <option value="path">{t("common.knowledge_base")}</option>
        </select>
        <button
          type="button"
          onClick={() => setSortOrder(sortOrder === "asc" ? "desc" : "asc")}
          className="grid size-9 place-items-center rounded border border-subtle hover:bg-layer-1"
          aria-label={t("project.project_view.sort_by.name")}
        >
          {sortOrder === "asc" ? <ArrowDownAZ className="size-4" /> : <ArrowUpAZ className="size-4" />}
        </button>
      </div>

      {selectedAllPageIds.length > 0 && (
        <div className="flex h-11 shrink-0 items-center gap-1 border-b border-subtle bg-layer-1 px-3">
          <span className="mr-2 min-w-6 text-center text-12 tabular-nums">{selectedAllPageIds.length}</span>
          <button
            type="button"
            disabled={!canMoveSelection}
            onClick={() => setShowMove(true)}
            className="grid size-8 place-items-center rounded hover:bg-layer-2 disabled:opacity-40"
            title={t("wiki_collections.add_existing_page_modal.submit")}
          >
            <Move className="size-4" />
          </button>
          <button
            type="button"
            disabled={!canArchiveSelection}
            onClick={() => void requestBulk("archive")}
            className="grid size-8 place-items-center rounded hover:bg-layer-2 disabled:opacity-40"
            title={t("common.archive")}
          >
            <Archive className="size-4" />
          </button>
          <button
            type="button"
            disabled={!canRestoreSelection}
            onClick={() => void requestBulk("restore")}
            className="grid size-8 place-items-center rounded hover:bg-layer-2 disabled:opacity-40"
            title={t("common.restore")}
          >
            <RotateCcw className="size-4" />
          </button>
          <button
            type="button"
            disabled={!canCopySelection}
            onClick={() => void requestBulk("copy")}
            className="grid size-8 place-items-center rounded hover:bg-layer-2 disabled:opacity-40"
            title={t("common.copy_link")}
          >
            <Copy className="size-4" />
          </button>
          <button
            type="button"
            disabled={!canRestoreSelection}
            onClick={() => void requestBulk("remove")}
            className="grid size-8 place-items-center rounded text-danger-primary hover:bg-layer-2 disabled:opacity-40"
            title={t("common.delete")}
          >
            <Trash2 className="size-4" />
          </button>
          <button
            type="button"
            onClick={clearAllPageSelection}
            className="ml-auto grid size-8 place-items-center rounded hover:bg-layer-2"
            aria-label={t("common.close")}
          >
            <X className="size-4" />
          </button>
        </div>
      )}

      {bulkError && (
        <div role="alert" className="border-b border-subtle px-3 py-2 text-12 text-danger-primary">
          {bulkError}
        </div>
      )}
      <div className="min-h-0 flex-1 overflow-auto">
        {allPagesState === "loading" && allPagesNodes.length === 0 && (
          <div className="p-4 text-13 text-tertiary">{t("common.loading")}</div>
        )}
        {allPagesState === "error" && allPagesNodes.length === 0 && (
          <button
            type="button"
            onClick={() => void loadAllPages(currentQuery)}
            className="m-4 text-13 text-accent-primary"
          >
            {allPagesError ?? t("common.retry")}
          </button>
        )}
        {allPagesState === "loaded" && allPagesNodes.length === 0 && (
          <div className="p-4 text-13 text-tertiary">{t("wiki_collections.list.no_pages_title")}</div>
        )}
        {allPagesNodes.map((node) => {
          const owner = getUserDetails(node.owned_by);
          const ownerName = owner?.display_name ?? t("common.none");
          return (
            <div
              key={node.id}
              className="flex min-h-12 min-w-[60rem] items-center gap-3 border-b border-subtle px-3 hover:bg-layer-1"
            >
              <input
                type="checkbox"
                checked={selectedAllPageIds.includes(node.id)}
                onChange={() => toggleAllPageSelection(node.id)}
                aria-label={getPageName(node.name)}
                className="size-4"
              />
              <button
                type="button"
                onClick={() => router.push(`/${workspaceSlug}/projects/${projectId}/pages/${node.id}`)}
                className="flex min-w-0 flex-1 items-center gap-2 text-left"
              >
                <PageIcon className="size-4 shrink-0 text-tertiary" />
                <span className="max-w-64 min-w-36 flex-1 truncate text-13 font-medium">{getPageName(node.name)}</span>
                <span className="min-w-0 flex-1 truncate text-12 text-tertiary">
                  {node.path?.map((item) => getPageName(item.name)).join(" / ")}
                </span>
              </button>
              <span className="w-10 shrink-0 text-right text-12 text-tertiary tabular-nums">L{node.depth}</span>
              <span
                className="flex w-40 shrink-0 items-center gap-2 text-12 text-secondary"
                aria-label={`${t("wiki_collections.list.columns.owner")}: ${ownerName}`}
              >
                <Avatar size="sm" src={getFileURL(owner?.avatar_url ?? "")} name={ownerName} />
                <span className="min-w-0 truncate">{ownerName}</span>
              </span>
              <time
                dateTime={node.updated_at}
                className="w-28 shrink-0 text-12 text-tertiary"
                aria-label={`${t("common.updated_at")}: ${renderFormattedDate(node.updated_at)}`}
              >
                {renderFormattedDate(node.updated_at)}
              </time>
              <span className="flex w-20 shrink-0 items-center justify-end gap-1 text-tertiary">
                {node.access === EPageAccess.PRIVATE && (
                  <LockKeyhole className="size-4" aria-label={t("common.access.private")} />
                )}
                {node.is_locked && (
                  <LockKeyhole className="size-4" aria-label={t("wiki_collections.list.restricted_access")} />
                )}
                {node.archived_at && (
                  <Archive className="size-4" aria-label={t("wiki_collections.predefined.archived")} />
                )}
              </span>
            </div>
          );
        })}
      </div>
      <div className="flex h-11 shrink-0 items-center justify-between border-t border-subtle px-3 text-12 text-tertiary">
        <span className="tabular-nums">
          {allPagesNodes.length} / {allPagesTotal}
        </span>
        {allPagesNextOffset !== null && (
          <button
            type="button"
            disabled={allPagesState === "loading"}
            onClick={() => void loadAllPages({ ...currentQuery, offset: allPagesNextOffset }, true)}
            className="rounded px-3 py-1.5 text-accent-primary hover:bg-layer-1 disabled:opacity-50"
          >
            {t("common.load_more")}
          </button>
        )}
      </div>

      {showMove && (
        <MovePageDialog
          nodes={Object.values(hierarchyNodes).length > 0 ? Object.values(hierarchyNodes) : allPagesNodes}
          invalidDestinationIds={invalidMoveIds}
          onSearch={searchHierarchyDestinations}
          onLoadSiblings={loadHierarchySiblings}
          onClose={() => setShowMove(false)}
          onMove={(placement) => requestBulk("move", placement)}
        />
      )}
      {pendingAction && bulkPreview && (
        <div
          className="fixed inset-0 z-50 grid place-items-center bg-backdrop p-4"
          role="presentation"
          onMouseDown={() => !mutating && setPendingAction(null)}
        >
          <div
            role="dialog"
            aria-modal="true"
            className="shadow-xl w-full max-w-sm rounded-md border border-subtle bg-surface-1 p-4"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <div className="mb-4 flex items-center gap-3">
              <PageIcon className="size-5 text-tertiary" />
              <span className="text-14 font-medium tabular-nums">{bulkPreview.affected_count}</span>
            </div>
            <div className="flex justify-end gap-2">
              <button
                type="button"
                disabled={mutating}
                onClick={() => setPendingAction(null)}
                className="h-9 rounded px-3 text-13 hover:bg-layer-1 disabled:opacity-50"
              >
                {t("common.cancel")}
              </button>
              <button
                type="button"
                disabled={mutating}
                onClick={() => void confirmBulk()}
                className="h-9 rounded bg-accent-primary px-3 text-13 text-on-color disabled:opacity-50"
              >
                {t("common.confirm")}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
});
