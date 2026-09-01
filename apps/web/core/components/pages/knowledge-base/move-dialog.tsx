/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ArrowDown, ArrowDownToLine, ArrowUp, ArrowUpToLine, Check, ChevronRight, X } from "lucide-react";
import { useTranslation } from "@plane/i18n";
import { PageIcon } from "@plane/propel/icons";
import type { TPageHierarchyMovePayload, TPageHierarchyNode } from "@plane/types";
import { filterPageHierarchyMoveDestinations, getPageName } from "@plane/utils";

type MovePlacement = Pick<TPageHierarchyMovePayload, "parent_id" | "position" | "relative_page_id">;

type Props = {
  nodes: TPageHierarchyNode[];
  invalidDestinationIds: Set<string>;
  onSearch?: (query: string) => Promise<TPageHierarchyNode[]>;
  onLoadSiblings?: (parentId: string | null) => Promise<TPageHierarchyNode[]>;
  onClose: () => void;
  onMove: (placement: MovePlacement) => Promise<void>;
};

export function MovePageDialog(props: Props) {
  const { nodes, invalidDestinationIds, onSearch, onLoadSiblings, onClose, onMove } = props;
  const { t } = useTranslation();
  const loadErrorMessage = t("wiki_collections.add_existing_page_modal.error_message");
  const searchInputRef = useRef<HTMLInputElement | null>(null);
  const [query, setQuery] = useState("");
  const [parentId, setParentId] = useState<string | null | undefined>(undefined);
  const [moving, setMoving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [destinationNodes, setDestinationNodes] = useState(nodes);
  const [siblingNodes, setSiblingNodes] = useState<TPageHierarchyNode[]>([]);
  const [loadingDestinations, setLoadingDestinations] = useState(false);
  const [loadingSiblings, setLoadingSiblings] = useState(false);
  const searchSequence = useRef(0);
  const siblingSequence = useRef(0);

  useEffect(() => searchInputRef.current?.focus(), []);
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  useEffect(() => {
    if (!onSearch) return;
    const sequence = ++searchSequence.current;
    setError(null);
    if (!query.trim()) {
      setLoadingDestinations(false);
      return;
    }
    setLoadingDestinations(true);
    const timer = window.setTimeout(() => {
      const search = async () => {
        try {
          const results = await onSearch(query);
          if (searchSequence.current === sequence) setDestinationNodes(results);
        } catch (cause) {
          if (searchSequence.current === sequence) setError((cause as { error?: string })?.error ?? loadErrorMessage);
        } finally {
          if (searchSequence.current === sequence) setLoadingDestinations(false);
        }
      };
      void search();
    }, 200);
    return () => {
      window.clearTimeout(timer);
      if (searchSequence.current === sequence) searchSequence.current += 1;
    };
  }, [loadErrorMessage, onSearch, query]);

  useEffect(() => {
    if (query.trim() === "") setDestinationNodes(nodes);
  }, [nodes, query]);

  useEffect(() => {
    if (!onSearch) {
      setDestinationNodes(nodes);
      setLoadingDestinations(false);
    }
  }, [nodes, onSearch]);

  useEffect(() => {
    if (parentId === undefined || !onLoadSiblings) {
      setLoadingSiblings(false);
      return;
    }
    const sequence = ++siblingSequence.current;
    setLoadingSiblings(true);
    setError(null);
    const loadSiblings = async () => {
      try {
        const results = await onLoadSiblings(parentId);
        if (siblingSequence.current === sequence) setSiblingNodes(results);
      } catch (cause) {
        if (siblingSequence.current === sequence) setError((cause as { error?: string })?.error ?? loadErrorMessage);
      } finally {
        if (siblingSequence.current === sequence) setLoadingSiblings(false);
      }
    };
    void loadSiblings();
    return () => {
      if (siblingSequence.current === sequence) siblingSequence.current += 1;
    };
  }, [loadErrorMessage, onLoadSiblings, parentId]);

  useEffect(() => {
    if (!onLoadSiblings && parentId !== undefined) setSiblingNodes(nodes.filter((node) => node.parent_id === parentId));
  }, [nodes, onLoadSiblings, parentId]);

  const isInvalidDestination = useCallback(
    (node: TPageHierarchyNode) =>
      invalidDestinationIds.has(node.id) ||
      Boolean(node.path?.some((pathItem) => invalidDestinationIds.has(pathItem.id))),
    [invalidDestinationIds]
  );

  const destinations = useMemo(
    () => filterPageHierarchyMoveDestinations(destinationNodes, query, invalidDestinationIds),
    [destinationNodes, invalidDestinationIds, query]
  );
  const siblings = useMemo(
    () =>
      siblingNodes
        .filter((node) => !isInvalidDestination(node) && !node.archived_at)
        .sort((a, b) => a.sort_order - b.sort_order || a.id.localeCompare(b.id)),
    [isInvalidDestination, siblingNodes]
  );

  const move = async (placement: MovePlacement) => {
    setMoving(true);
    setError(null);
    try {
      await onMove(placement);
      onClose();
    } catch (cause) {
      setError((cause as { error?: string })?.error ?? loadErrorMessage);
    } finally {
      setMoving(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 grid place-items-center bg-backdrop p-4"
      role="presentation"
      onMouseDown={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="move-page-title"
        className="shadow-xl flex max-h-[min(40rem,calc(100vh-2rem))] w-full max-w-2xl flex-col overflow-hidden rounded-md border border-subtle bg-surface-1"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="flex h-12 items-center justify-between border-b border-subtle px-4">
          <h2 id="move-page-title" className="text-14 font-medium">
            {t("wiki_collections.add_existing_page_modal.submit")}
          </h2>
          <button
            type="button"
            onClick={onClose}
            aria-label={t("common.close")}
            className="grid size-8 place-items-center"
          >
            <X className="size-4" />
          </button>
        </div>
        <div className="grid min-h-0 flex-1 grid-cols-1 md:grid-cols-2">
          <div className="flex min-h-0 flex-col border-b border-subtle md:border-r md:border-b-0">
            <div className="p-3">
              <input
                ref={searchInputRef}
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder={t("wiki_collections.add_existing_page_modal.search_placeholder")}
                className="focus:ring-accent h-9 w-full rounded border border-subtle bg-transparent px-3 text-13 outline-none focus:ring-2"
              />
            </div>
            <div className="min-h-40 flex-1 overflow-y-auto px-2 pb-2">
              <button
                type="button"
                disabled={moving}
                onClick={() => setParentId(null)}
                className="flex h-9 w-full items-center gap-2 rounded px-2 text-left text-13 hover:bg-layer-1 disabled:opacity-50"
              >
                <PageIcon className="size-4" />
                <span className="min-w-0 flex-1 truncate">{t("knowledge_base")}</span>
                {parentId === null && <Check className="size-4 text-accent-primary" />}
              </button>
              {loadingDestinations && <div className="px-2 py-3 text-12 text-tertiary">{t("common.loading")}</div>}
              {destinations.map((node) => (
                <button
                  key={node.id}
                  type="button"
                  disabled={moving}
                  onClick={() => setParentId(node.id)}
                  className="flex h-9 w-full min-w-0 items-center gap-2 rounded px-2 text-left text-13 hover:bg-layer-1 disabled:opacity-50"
                >
                  <PageIcon className="size-4 shrink-0" />
                  <span className="min-w-0 flex-1 truncate">{getPageName(node.name)}</span>
                  {parentId === node.id ? (
                    <Check className="size-4 text-accent-primary" />
                  ) : (
                    <ChevronRight className="size-4" />
                  )}
                </button>
              ))}
            </div>
          </div>
          <div className="min-h-48 overflow-y-auto p-2">
            {parentId === undefined ? (
              <div className="grid h-full min-h-40 place-items-center text-13 text-tertiary">
                {t("wiki_collections.add_existing_page_modal.no_pages_available")}
              </div>
            ) : (
              <>
                <div className="grid grid-cols-2 gap-2 pb-2">
                  <button
                    type="button"
                    disabled={moving}
                    onClick={() => void move({ parent_id: parentId, position: "first", relative_page_id: null })}
                    className="flex h-9 items-center justify-center gap-2 rounded border border-subtle text-13 hover:bg-layer-1 disabled:opacity-50"
                    aria-label={`↑ ${t("wiki_collections.add_existing_page_modal.submit")}`}
                  >
                    <ArrowUpToLine className="size-4" />
                  </button>
                  <button
                    type="button"
                    disabled={moving}
                    onClick={() => void move({ parent_id: parentId, position: "last", relative_page_id: null })}
                    className="flex h-9 items-center justify-center gap-2 rounded border border-subtle text-13 hover:bg-layer-1 disabled:opacity-50"
                    aria-label={`↓ ${t("wiki_collections.add_existing_page_modal.submit")}`}
                  >
                    <ArrowDownToLine className="size-4" />
                  </button>
                </div>
                {loadingSiblings && <div className="px-2 py-3 text-12 text-tertiary">{t("common.loading")}</div>}
                {siblings.map((sibling) => (
                  <div key={sibling.id} className="flex h-10 min-w-0 items-center gap-1 border-t border-subtle px-1">
                    <PageIcon className="size-4 shrink-0 text-tertiary" />
                    <span className="min-w-0 flex-1 truncate text-13">{getPageName(sibling.name)}</span>
                    <button
                      type="button"
                      disabled={moving}
                      onClick={() =>
                        void move({ parent_id: parentId, position: "before", relative_page_id: sibling.id })
                      }
                      className="grid size-8 shrink-0 place-items-center rounded hover:bg-layer-1 disabled:opacity-50"
                      aria-label={`↑ ${getPageName(sibling.name)}`}
                    >
                      <ArrowUp className="size-4" />
                    </button>
                    <button
                      type="button"
                      disabled={moving}
                      onClick={() =>
                        void move({ parent_id: parentId, position: "after", relative_page_id: sibling.id })
                      }
                      className="grid size-8 shrink-0 place-items-center rounded hover:bg-layer-1 disabled:opacity-50"
                      aria-label={`↓ ${getPageName(sibling.name)}`}
                    >
                      <ArrowDown className="size-4" />
                    </button>
                  </div>
                ))}
              </>
            )}
          </div>
        </div>
        {error && (
          <div role="alert" className="border-t border-subtle px-4 py-2 text-12 text-danger-primary">
            {error}
          </div>
        )}
      </div>
    </div>
  );
}
