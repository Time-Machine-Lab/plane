/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { RequestHandlerExtra } from "@modelcontextprotocol/sdk/shared/protocol.js";
import type { ServerNotification, ServerRequest } from "@modelcontextprotocol/sdk/types.js";
import { PlaneError } from "@/errors";

export type ToolRequestExtra = RequestHandlerExtra<ServerRequest, ServerNotification>;
type RequestHeaders = Record<string, string | string[] | undefined>;

export const getHeader = (headers: RequestHeaders | undefined, name: string): string | undefined => {
  if (!headers) return undefined;
  const match = Object.entries(headers).find(([key]) => key.toLowerCase() === name.toLowerCase());
  const value = match?.[1];
  return Array.isArray(value) ? value[0] : value;
};

export const extractPlaneToken = (extra: ToolRequestExtra): string => {
  const authorization = getHeader(extra.requestInfo?.headers, "authorization");
  if (!authorization) throw new PlaneError("authentication", "A Plane API token is required.");

  const match = /^Bearer\s+([^\s]+)$/i.exec(authorization.trim());
  if (!match?.[1] || match[1].length > 4096) {
    throw new PlaneError("authentication", "The Plane API token is invalid.");
  }
  return match[1];
};

export const resolveWorkspace = (workspaceSlug: string | undefined, extra: ToolRequestExtra): string => {
  const resolved = workspaceSlug ?? getHeader(extra.requestInfo?.headers, "x-plane-workspace")?.trim();
  if (!resolved) {
    throw new PlaneError("validation", "workspace_slug is required when X-Plane-Workspace is not configured.");
  }
  return resolved;
};
