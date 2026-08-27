/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import type { McpConfig } from "@/config";
import { errorResult, PlaneError, successResult } from "@/errors";
import type { Logger } from "@/logger";
import { PlaneApiClient } from "@/plane-api";
import {
  attachmentProjection,
  commentProjection,
  cycleProjection,
  labelProjection,
  memberProjection,
  moduleProjection,
  paginatedProjection,
  projectProjection,
  stateProjection,
  userProjection,
  workItemProjection,
} from "@/projections";
import { extractPlaneToken, resolveWorkspace, type ToolRequestExtra } from "@/request-context";

const workspaceSlug = z
  .string()
  .min(1)
  .max(255)
  .regex(/^[A-Za-z0-9][A-Za-z0-9_-]*$/);
const uuid = z.string().uuid();
const cursor = z.string().min(1).max(500).optional();
const perPage = z.number().int().min(1).max(100).default(50);

const workspaceInput = z.object({ workspace_slug: workspaceSlug.optional() }).strict();
const projectInput = workspaceInput.extend({ project_id: uuid }).strict();
const paginationInput = z.object({ cursor, per_page: perPage }).strict();
const projectPaginationInput = projectInput.merge(paginationInput).strict();

const encode = encodeURIComponent;

const canonicalProjectUrl = (config: McpConfig, workspace: string, projectId: string) =>
  `${config.planeBaseUrl}/${encode(workspace)}/projects/${encode(projectId)}/issues`;

const canonicalWorkItemUrl = (config: McpConfig, workspace: string, projectId: string, workItemId: string) =>
  `${canonicalProjectUrl(config, workspace, projectId)}/${encode(workItemId)}`;

const requestQuery = (args: { cursor?: string; per_page: number }) => ({
  cursor: args.cursor,
  per_page: args.per_page,
});

const requestContext = (
  config: McpConfig,
  extra: ToolRequestExtra,
  explicitWorkspace: string | undefined
): { client: PlaneApiClient; workspace: string } => {
  const token = extractPlaneToken(extra);
  const workspace = resolveWorkspace(explicitWorkspace, extra);
  return { client: new PlaneApiClient(token, config), workspace };
};

const guarded = async (logger: Logger, tool: string, callback: () => Promise<Record<string, unknown>>) => {
  try {
    return successResult(await callback());
  } catch (error) {
    logger.warn("MCP tool failed", {
      tool,
      code: error instanceof PlaneError ? error.code : "unexpected",
    });
    return errorResult(error);
  }
};

export const TOOL_NAMES = [
  "plane_status",
  "list_projects",
  "get_project",
  "list_work_items",
  "search_work_items",
  "get_work_item",
  "create_work_item",
  "update_work_item",
  "list_comments",
  "list_attachments",
  "add_comment",
  "list_states",
  "list_labels",
  "list_cycles",
  "list_modules",
  "list_members",
] as const;

export const registerPlaneTools = (server: McpServer, config: McpConfig, logger: Logger): void => {
  server.registerTool(
    "plane_status",
    {
      description: "Verify the Plane API token and access to a workspace without changing data.",
      inputSchema: workspaceInput,
      annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false },
    },
    async ({ workspace_slug }, extra) =>
      guarded(logger, "plane_status", async () => {
        const { client, workspace } = requestContext(config, extra, workspace_slug);
        const user = await client.request("users/me/");
        await client.request(`workspaces/${encode(workspace)}/projects/`, { query: { per_page: 1 } });
        return {
          available: true,
          plane_origin: config.planeBaseUrl,
          workspace,
          user: userProjection(user),
        };
      })
  );

  server.registerTool(
    "list_projects",
    {
      description: "List projects accessible to the Plane account in a workspace.",
      inputSchema: workspaceInput.merge(paginationInput).strict(),
      annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false },
    },
    async ({ workspace_slug, ...page }, extra) =>
      guarded(logger, "list_projects", async () => {
        const { client, workspace } = requestContext(config, extra, workspace_slug);
        const response = await client.request(`workspaces/${encode(workspace)}/projects/`, {
          query: requestQuery(page),
        });
        const result = paginatedProjection(response, projectProjection);
        for (const project of result.items) {
          if (typeof project.id === "string") project.url = canonicalProjectUrl(config, workspace, project.id);
        }
        return {
          workspace,
          ...result,
        };
      })
  );

  server.registerTool(
    "get_project",
    {
      description: "Get one project by UUID in an accessible workspace.",
      inputSchema: projectInput,
      annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false },
    },
    async ({ workspace_slug, project_id }, extra) =>
      guarded(logger, "get_project", async () => {
        const { client, workspace } = requestContext(config, extra, workspace_slug);
        const response = await client.request(`workspaces/${encode(workspace)}/projects/${encode(project_id)}/`);
        return {
          workspace,
          project: { ...projectProjection(response), url: canonicalProjectUrl(config, workspace, project_id) },
        };
      })
  );

  server.registerTool(
    "list_work_items",
    {
      description: "List a bounded page of work items in a project.",
      inputSchema: projectPaginationInput.extend({ order_by: z.string().min(1).max(100).optional() }).strict(),
      annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false },
    },
    async ({ workspace_slug, project_id, order_by, ...page }, extra) =>
      guarded(logger, "list_work_items", async () => {
        const { client, workspace } = requestContext(config, extra, workspace_slug);
        const response = await client.request(
          `workspaces/${encode(workspace)}/projects/${encode(project_id)}/work-items/`,
          { query: { ...requestQuery(page), order_by } }
        );
        const result = paginatedProjection(response, workItemProjection);
        for (const item of result.items) {
          if (typeof item.id === "string") item.url = canonicalWorkItemUrl(config, workspace, project_id, item.id);
        }
        return {
          workspace,
          project_id,
          ...result,
        };
      })
  );

  server.registerTool(
    "search_work_items",
    {
      description: "Search accessible work items by name, sequence, or project identifier.",
      inputSchema: workspaceInput
        .extend({
          query: z.string().trim().min(1).max(200),
          project_id: uuid.optional(),
          limit: z.number().int().min(1).max(50).default(10),
        })
        .strict(),
      annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false },
    },
    async ({ workspace_slug, query, project_id, limit }, extra) =>
      guarded(logger, "search_work_items", async () => {
        const { client, workspace } = requestContext(config, extra, workspace_slug);
        const response = await client.request<Record<string, unknown>>(
          `workspaces/${encode(workspace)}/work-items/search/`,
          {
            query: { search: query, project_id, workspace_search: !project_id, limit },
          }
        );
        const items = Array.isArray(response.issues) ? response.issues.map(workItemProjection) : [];
        return { workspace, items, count: items.length };
      })
  );

  server.registerTool(
    "get_work_item",
    {
      description: "Get one work item by UUID in a project.",
      inputSchema: projectInput.extend({ work_item_id: uuid }).strict(),
      annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false },
    },
    async ({ workspace_slug, project_id, work_item_id }, extra) =>
      guarded(logger, "get_work_item", async () => {
        const { client, workspace } = requestContext(config, extra, workspace_slug);
        const response = await client.request(
          `workspaces/${encode(workspace)}/projects/${encode(project_id)}/work-items/${encode(work_item_id)}/`
        );
        return {
          workspace,
          project_id,
          work_item: {
            ...workItemProjection(response),
            url: canonicalWorkItemUrl(config, workspace, project_id, work_item_id),
          },
        };
      })
  );

  const supportedWorkItemFields = {
    description_html: z.string().max(200_000).nullable().optional(),
    priority: z.enum(["urgent", "high", "medium", "low", "none"]).optional(),
    state_id: uuid.optional(),
    assignee_ids: z.array(uuid).max(100).optional(),
    label_ids: z.array(uuid).max(100).optional(),
    start_date: z.string().date().nullable().optional(),
    target_date: z.string().date().nullable().optional(),
    parent_id: uuid.nullable().optional(),
  };

  server.registerTool(
    "create_work_item",
    {
      description: "Create one work item with a strict set of supported fields.",
      inputSchema: projectInput
        .extend({ title: z.string().trim().min(1).max(255), ...supportedWorkItemFields })
        .strict(),
      annotations: { readOnlyHint: false, destructiveHint: false, idempotentHint: false, openWorldHint: false },
    },
    async ({ workspace_slug, project_id, title, state_id, assignee_ids, label_ids, parent_id, ...fields }, extra) =>
      guarded(logger, "create_work_item", async () => {
        const { client, workspace } = requestContext(config, extra, workspace_slug);
        const response = await client.request(
          `workspaces/${encode(workspace)}/projects/${encode(project_id)}/work-items/`,
          {
            method: "POST",
            body: {
              name: title,
              ...fields,
              ...(state_id === undefined ? {} : { state: state_id }),
              ...(assignee_ids === undefined ? {} : { assignees: assignee_ids }),
              ...(label_ids === undefined ? {} : { labels: label_ids }),
              ...(parent_id === undefined ? {} : { parent: parent_id }),
            },
          }
        );
        const item = workItemProjection(response);
        return {
          workspace,
          project_id,
          work_item: {
            ...item,
            url: typeof item.id === "string" ? canonicalWorkItemUrl(config, workspace, project_id, item.id) : undefined,
          },
        };
      })
  );

  server.registerTool(
    "update_work_item",
    {
      description: "Update one work item with a strict set of supported fields.",
      inputSchema: projectInput
        .extend({
          work_item_id: uuid,
          title: z.string().trim().min(1).max(255).optional(),
          ...supportedWorkItemFields,
        })
        .strict()
        .refine(
          ({ workspace_slug: _workspace, project_id: _project, work_item_id: _item, ...changes }) =>
            Object.values(changes).some((value) => value !== undefined),
          { message: "At least one supported change is required." }
        ),
      annotations: { readOnlyHint: false, destructiveHint: false, idempotentHint: true, openWorldHint: false },
    },
    async (
      { workspace_slug, project_id, work_item_id, title, state_id, assignee_ids, label_ids, parent_id, ...fields },
      extra
    ) =>
      guarded(logger, "update_work_item", async () => {
        const { client, workspace } = requestContext(config, extra, workspace_slug);
        const response = await client.request(
          `workspaces/${encode(workspace)}/projects/${encode(project_id)}/work-items/${encode(work_item_id)}/`,
          {
            method: "PATCH",
            body: {
              ...fields,
              ...(title === undefined ? {} : { name: title }),
              ...(state_id === undefined ? {} : { state: state_id }),
              ...(assignee_ids === undefined ? {} : { assignees: assignee_ids }),
              ...(label_ids === undefined ? {} : { labels: label_ids }),
              ...(parent_id === undefined ? {} : { parent: parent_id }),
            },
          }
        );
        return {
          workspace,
          project_id,
          work_item: {
            ...workItemProjection(response),
            url: canonicalWorkItemUrl(config, workspace, project_id, work_item_id),
          },
        };
      })
  );

  server.registerTool(
    "list_comments",
    {
      description: "List a bounded page of comments on a work item.",
      inputSchema: projectPaginationInput.extend({ work_item_id: uuid }).strict(),
      annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false },
    },
    async ({ workspace_slug, project_id, work_item_id, ...page }, extra) =>
      guarded(logger, "list_comments", async () => {
        const { client, workspace } = requestContext(config, extra, workspace_slug);
        const response = await client.request(
          `workspaces/${encode(workspace)}/projects/${encode(project_id)}/work-items/${encode(work_item_id)}/comments/`,
          { query: requestQuery(page) }
        );
        return { workspace, project_id, work_item_id, ...paginatedProjection(response, commentProjection) };
      })
  );

  server.registerTool(
    "list_attachments",
    {
      description: "List a bounded page of authorized attachment metadata and current download access.",
      inputSchema: projectPaginationInput.extend({ work_item_id: uuid }).strict(),
      annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false },
    },
    async ({ workspace_slug, project_id, work_item_id, ...page }, extra) =>
      guarded(logger, "list_attachments", async () => {
        const { client, workspace } = requestContext(config, extra, workspace_slug);
        const response = await client.request(
          `workspaces/${encode(workspace)}/projects/${encode(project_id)}/work-items/${encode(work_item_id)}/attachments/`,
          { query: requestQuery(page) }
        );
        const result = paginatedProjection(response, attachmentProjection);
        for (const attachment of result.items) {
          if (typeof attachment.download_path === "string" && attachment.download_path.startsWith("/api/assets/")) {
            attachment.download_url = new URL(attachment.download_path, config.planeBaseUrl).toString();
          }
          delete attachment.download_path;
        }
        return { workspace, project_id, work_item_id, ...result };
      })
  );

  server.registerTool(
    "add_comment",
    {
      description: "Add one non-empty HTML comment to a work item.",
      inputSchema: projectInput
        .extend({ work_item_id: uuid, comment_html: z.string().trim().min(1).max(200_000) })
        .strict(),
      annotations: { readOnlyHint: false, destructiveHint: false, idempotentHint: false, openWorldHint: false },
    },
    async ({ workspace_slug, project_id, work_item_id, comment_html }, extra) =>
      guarded(logger, "add_comment", async () => {
        const { client, workspace } = requestContext(config, extra, workspace_slug);
        const response = await client.request(
          `workspaces/${encode(workspace)}/projects/${encode(project_id)}/work-items/${encode(work_item_id)}/comments/`,
          { method: "POST", body: { comment_html } }
        );
        return { workspace, project_id, work_item_id, comment: commentProjection(response) };
      })
  );

  const metadataTools = [
    ["list_states", "states", stateProjection, "List project workflow states."],
    ["list_labels", "labels", labelProjection, "List project labels."],
    ["list_cycles", "cycles-lite", cycleProjection, "List project cycles."],
    ["list_modules", "modules-lite", moduleProjection, "List project modules."],
  ] as const;

  for (const [name, endpoint, projection, description] of metadataTools) {
    server.registerTool(
      name,
      {
        description,
        inputSchema: projectPaginationInput,
        annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false },
      },
      async ({ workspace_slug, project_id, ...page }, extra) =>
        guarded(logger, name, async () => {
          const { client, workspace } = requestContext(config, extra, workspace_slug);
          const response = await client.request(
            `workspaces/${encode(workspace)}/projects/${encode(project_id)}/${endpoint}/`,
            { query: requestQuery(page) }
          );
          return { workspace, project_id, ...paginatedProjection(response, projection) };
        })
    );
  }

  server.registerTool(
    "list_members",
    {
      description: "List lightweight workspace members or members of one project.",
      inputSchema: workspaceInput.merge(paginationInput).extend({ project_id: uuid.optional() }).strict(),
      annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false },
    },
    async ({ workspace_slug, project_id, ...page }, extra) =>
      guarded(logger, "list_members", async () => {
        const { client, workspace } = requestContext(config, extra, workspace_slug);
        const path = project_id
          ? `workspaces/${encode(workspace)}/projects/${encode(project_id)}/project-members-lite/`
          : `workspaces/${encode(workspace)}/members-lite/`;
        const response = await client.request(path, { query: requestQuery(page) });
        return { workspace, ...(project_id ? { project_id } : {}), ...paginatedProjection(response, memberProjection) };
      })
  );
};
