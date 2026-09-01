/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { TLogoProps } from "../common";
import type { EPageAccess } from "../enums";
import type { TPageExtended } from "./extended";

export type TPage = {
  access: EPageAccess | undefined;
  archived_at: string | null | undefined;
  color: string | undefined;
  created_at: Date | undefined;
  created_by: string | undefined;
  description_json: object | undefined;
  description_html: string | undefined;
  id: string | undefined;
  is_favorite: boolean;
  is_locked: boolean;
  label_ids: string[] | undefined;
  name: string | undefined;
  owned_by: string | undefined;
  project_ids?: string[] | undefined;
  updated_at: Date | undefined;
  updated_by: string | undefined;
  workspace: string | undefined;
  logo_props: TLogoProps | undefined;
  deleted_at: Date | undefined;
  project_parent_id?: string | null;
  sort_order?: number;
  project_archived_at?: string | null;
  depth?: number;
  path?: TPageHierarchyPathItem[];
  has_children?: boolean;
  child_count?: number;
  hierarchy_permissions?: TPageHierarchyPermissions;
  hierarchy_revision?: number;
} & TPageExtended;

export type TPageHierarchyPathItem = {
  id: string;
  name: string;
  logo_props?: TLogoProps;
};

export type TPageHierarchyPermissions = {
  can_create_child: boolean;
  can_move: boolean;
  can_archive: boolean;
  can_restore: boolean;
};

export type TPageHierarchyNode = {
  id: string;
  project_page_id: string;
  name: string;
  logo_props?: TLogoProps;
  access: EPageAccess;
  is_locked: boolean;
  owned_by: string;
  parent_id: string | null;
  sort_order: number;
  archived_at: string | null;
  has_children: boolean;
  child_count: number;
  depth: number | null;
  path: TPageHierarchyPathItem[] | null;
  created_at: string;
  updated_at: string;
  permissions: TPageHierarchyPermissions;
};

export type TPageHierarchyResponse = {
  results: TPageHierarchyNode[];
  total_count: number;
  next_offset: number | null;
  revision: number;
};

export type TPageHierarchyAllPagesQuery = {
  offset?: number;
  limit?: number;
  search?: string;
  access?: EPageAccess;
  locked?: boolean;
  owner_id?: string;
  archived?: "all" | "active" | "archived";
  sort_by?: "name" | "created_at" | "updated_at" | "depth" | "path" | "sort_order";
  sort_order?: "asc" | "desc";
};

export type TPageHierarchyBulkOperation = "move" | "archive" | "restore" | "copy" | "remove";

export type TPageHierarchyBulkPayload = {
  page_ids: string[];
  operation: TPageHierarchyBulkOperation;
  parent_id?: string | null;
  position?: TPageHierarchyMovePayload["position"];
  relative_page_id?: string | null;
  operation_id: string;
  base_revision?: number;
};

export type TPageHierarchyPreview = {
  operation: TPageHierarchyBulkOperation;
  root_page_ids: string[];
  descendant_count: number;
  affected_count: number;
  page_ids: string[];
  revision: number;
};

export type TPageHierarchyBulkResponse = {
  operation: TPageHierarchyBulkOperation;
  root_page_ids: string[];
  affected_count?: number;
  parent_id?: string | null;
  archived_at?: string;
  archive_batch_id?: string;
  created_page_ids?: string[];
  deleted_page_ids?: string[];
  preserved_page_ids?: string[];
  asset_copy_state?: "pending" | "ready" | "failed";
  revision: number;
  siblings?: { id: string; sort_order: number }[];
};

export type TPageHierarchyPathResponse = {
  path: TPageHierarchyPathItem[];
  depth: number;
  revision: number;
};

export type TPageHierarchyMovePayload = {
  parent_id: string | null;
  position: "first" | "last" | "inside" | "before" | "after";
  relative_page_id?: string | null;
  operation_id: string;
  base_revision?: number;
};

export type TPageHierarchyMoveResponse = {
  page_id: string;
  parent_id: string | null;
  revision: number;
  base_revision: number | null;
  siblings: { id: string; sort_order: number }[];
};

export type TPageHierarchyPreferences = {
  version: 1;
  expanded_ids: string[];
};

export type TPageHierarchyBranchState = "idle" | "loading" | "loaded" | "error";

export type TPageHierarchyRow = {
  id: string;
  depth: number;
  node: TPageHierarchyNode;
};

// page filters
export type TPageNavigationTabs = "public" | "private" | "archived";

export type TPageFiltersSortKey = "name" | "created_at" | "updated_at" | "opened_at";

export type TPageFiltersSortBy = "asc" | "desc";

export type TPageFilterProps = {
  created_at?: string[] | null;
  created_by?: string[] | null;
  favorites?: boolean;
  labels?: string[] | null;
};

export type TPageFilters = {
  searchQuery: string;
  sortKey: TPageFiltersSortKey;
  sortBy: TPageFiltersSortBy;
  filters?: TPageFilterProps;
};

export type TPageEmbedType = "mention" | "issue";

export type TPageVersion = {
  created_at: string;
  created_by: string;
  deleted_at: string | null;
  description_binary?: string | null;
  description_html?: string | null;
  description_json?: object;
  id: string;
  last_saved_at: string;
  owned_by: string;
  page: string;
  updated_at: string;
  updated_by: string;
  workspace: string;
};

export type TDocumentPayload = {
  description_binary: string;
  description_html: string;
  description_json: object;
};

export type TWebhookConnectionQueryParams = {
  documentType: "project_page" | "team_page" | "workspace_page";
  projectId?: string;
  teamId?: string;
  workspaceSlug: string;
};
