/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { CallToolResult } from "@modelcontextprotocol/sdk/types.js";

export type PlaneErrorCode =
  | "validation"
  | "authentication"
  | "authorization"
  | "not_found"
  | "conflict"
  | "throttled"
  | "upstream";

export class PlaneError extends Error {
  constructor(
    public readonly code: PlaneErrorCode,
    message: string,
    public readonly retryAfter?: string
  ) {
    super(message);
    this.name = "PlaneError";
  }
}

const stableUnexpectedError = new PlaneError("upstream", "Plane could not complete the request.");

export const errorResult = (error: unknown): CallToolResult => {
  const planeError = error instanceof PlaneError ? error : stableUnexpectedError;
  const payload = {
    error: {
      code: planeError.code,
      message: planeError.message,
      ...(planeError.retryAfter ? { retry_after: planeError.retryAfter } : {}),
    },
  };

  return {
    isError: true,
    content: [{ type: "text", text: JSON.stringify(payload) }],
    structuredContent: payload,
  };
};

export const successResult = (payload: Record<string, unknown>): CallToolResult => ({
  content: [{ type: "text", text: JSON.stringify(payload) }],
  structuredContent: payload,
});
