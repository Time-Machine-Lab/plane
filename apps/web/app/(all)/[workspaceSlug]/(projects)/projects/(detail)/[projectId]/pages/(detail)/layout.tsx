/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// component
import { Outlet } from "react-router";
import useSWR from "swr";
import { AppHeader } from "@/components/core/app-header";
import { ContentWrapper } from "@/components/core/content-wrapper";
import { KnowledgeBaseDetailLayout } from "@/components/pages/knowledge-base";
// plane web hooks
import { EPageStoreType, usePageStore } from "@/hooks/store";
import { useInstance } from "@/hooks/store/use-instance";
// local components
import type { Route } from "./+types/layout";
import { PageDetailsHeader } from "./header";

export default function ProjectPageDetailsLayout({ params }: Route.ComponentProps) {
  const { workspaceSlug, projectId } = params;
  const { fetchPagesList } = usePageStore(EPageStoreType.PROJECT);
  const { config: instanceConfig } = useInstance();
  // fetching pages list
  useSWR(`PROJECT_PAGES_${projectId}`, () => fetchPagesList(workspaceSlug, projectId));
  return (
    <>
      <AppHeader header={<PageDetailsHeader />} />
      <ContentWrapper>
        {instanceConfig?.is_project_page_hierarchy_enabled !== false ? (
          <KnowledgeBaseDetailLayout>
            <Outlet />
          </KnowledgeBaseDetailLayout>
        ) : (
          <Outlet />
        )}
      </ContentWrapper>
    </>
  );
}
