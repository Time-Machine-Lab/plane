/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { z } from "zod";

const booleanValue = z
  .enum(["true", "false", "1", "0"])
  .default("true")
  .transform((value) => value === "true" || value === "1");

const integerValue = (defaultValue: number, minimum: number, maximum: number) =>
  z.coerce.number().int().min(minimum).max(maximum).default(defaultValue);

const configSchema = z.object({
  MCP_ENABLED: booleanValue,
  MCP_HOST: z.string().min(1).default("0.0.0.0"),
  MCP_PORT: integerValue(3100, 1, 65_535),
  MCP_PATH: z
    .string()
    .regex(/^\/[A-Za-z0-9/_-]*$/)
    .default("/mcp"),
  MCP_REQUEST_BODY_LIMIT_BYTES: integerValue(2_097_152, 1_024, 10_485_760),
  PLANE_API_BASE_URL: z.string().url().default("http://localhost:8000/api/v1"),
  PLANE_BASE_URL: z.string().url().optional(),
  PLANE_API_TIMEOUT_MS: integerValue(10_000, 100, 120_000),
  PLANE_API_RESPONSE_LIMIT_BYTES: integerValue(1_048_576, 1_024, 10_485_760),
  LOG_LEVEL: z.enum(["debug", "info", "warn", "error"]).default("info"),
});

export type McpConfig = {
  enabled: boolean;
  host: string;
  port: number;
  path: string;
  requestBodyLimitBytes: number;
  planeApiBaseUrl: string;
  planeBaseUrl: string;
  planeApiTimeoutMs: number;
  planeApiResponseLimitBytes: number;
  logLevel: "debug" | "info" | "warn" | "error";
};

const trimTrailingSlash = (value: string) => value.replace(/\/+$/, "");

export const loadConfig = (source: NodeJS.ProcessEnv = process.env): McpConfig => {
  const parsed = configSchema.parse(source);
  const planeApiBaseUrl = trimTrailingSlash(parsed.PLANE_API_BASE_URL);
  const derivedPlaneBaseUrl = planeApiBaseUrl.replace(/\/api\/v1$/, "");

  return {
    enabled: parsed.MCP_ENABLED,
    host: parsed.MCP_HOST,
    port: parsed.MCP_PORT,
    path: parsed.MCP_PATH,
    requestBodyLimitBytes: parsed.MCP_REQUEST_BODY_LIMIT_BYTES,
    planeApiBaseUrl,
    planeBaseUrl: trimTrailingSlash(parsed.PLANE_BASE_URL ?? derivedPlaneBaseUrl),
    planeApiTimeoutMs: parsed.PLANE_API_TIMEOUT_MS,
    planeApiResponseLimitBytes: parsed.PLANE_API_RESPONSE_LIMIT_BYTES,
    logLevel: parsed.LOG_LEVEL,
  };
};
