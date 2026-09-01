/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { PanelLeft, X } from "lucide-react";
import { useTranslation } from "@plane/i18n";
import { KnowledgeBaseTree } from "./tree";

export function KnowledgeBaseDetailLayout({ children }: { children: React.ReactNode }) {
  const { t } = useTranslation();
  const [drawerOpen, setDrawerOpen] = useState(false);
  return (
    <div className="relative flex h-full min-h-0 w-full overflow-hidden">
      <aside className="hidden h-full w-72 shrink-0 border-r border-subtle lg:block">
        <KnowledgeBaseTree />
      </aside>
      <main className="relative min-w-0 flex-1 overflow-hidden">
        <button
          type="button"
          onClick={() => setDrawerOpen(true)}
          className="shadow-sm focus-visible:ring-accent absolute top-2 left-2 z-20 grid size-9 place-items-center rounded border border-subtle bg-surface-1 focus-visible:ring-2 lg:hidden"
          title={t("knowledge_base")}
          aria-label={t("knowledge_base")}
        >
          <PanelLeft className="size-4" />
        </button>
        {children}
      </main>
      {drawerOpen && (
        <div className="fixed inset-0 z-50 lg:hidden" role="presentation">
          <button
            type="button"
            className="absolute inset-0 bg-backdrop"
            onClick={() => setDrawerOpen(false)}
            aria-label={t("common.close")}
          />
          <aside className="shadow-xl absolute inset-y-0 left-0 w-[min(22rem,calc(100vw-2rem))] bg-surface-1">
            <button
              type="button"
              onClick={() => setDrawerOpen(false)}
              className="focus-visible:ring-accent absolute top-1.5 right-2 z-10 grid size-8 place-items-center rounded hover:bg-layer-1 focus-visible:ring-2"
              aria-label={t("common.close")}
            >
              <X className="size-4" />
            </button>
            <KnowledgeBaseTree />
          </aside>
        </div>
      )}
    </div>
  );
}
