/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { McpConfig } from "@/config";
import { PlaneError } from "@/errors";

type FetchImplementation = typeof fetch;
type QueryValue = string | number | boolean | undefined;

export type PlaneRequestOptions = {
  method?: "GET" | "POST" | "PATCH";
  query?: Record<string, QueryValue>;
  body?: Record<string, unknown>;
};

const extractErrorMessage = (body: unknown, fallback: string): string => {
  if (!body || typeof body !== "object") return fallback;
  const record = body as Record<string, unknown>;
  for (const key of ["detail", "message", "error"]) {
    if (typeof record[key] === "string" && record[key]) return record[key];
  }
  return fallback;
};

const isInvalidApiTokenResponse = (body: unknown): boolean =>
  /api token is not valid/i.test(extractErrorMessage(body, ""));

const errorFromResponse = (response: Response, body: unknown): PlaneError => {
  const fallback = "Plane rejected the request.";
  if (response.status === 400 || response.status === 422) {
    return new PlaneError("validation", extractErrorMessage(body, "Plane rejected the supplied fields."));
  }
  if (response.status === 401) return new PlaneError("authentication", "The Plane API token is invalid or inactive.");
  if (response.status === 403) {
    if (isInvalidApiTokenResponse(body)) {
      return new PlaneError("authentication", "The Plane API token is invalid or inactive.");
    }
    return new PlaneError("authorization", "The Plane account is not allowed to do this.");
  }
  if (response.status === 404) return new PlaneError("not_found", "The requested Plane object was not found.");
  if (response.status === 409)
    return new PlaneError("conflict", extractErrorMessage(body, "The request conflicts with existing Plane data."));
  if (response.status === 429) {
    return new PlaneError(
      "throttled",
      "Plane rate-limited the request.",
      response.headers.get("retry-after") ?? undefined
    );
  }
  return new PlaneError("upstream", fallback);
};

const readJsonWithLimit = async (response: Response, maximumBytes: number): Promise<unknown> => {
  if (response.status === 204) return null;
  const declaredLength = Number(response.headers.get("content-length") ?? 0);
  if (declaredLength > maximumBytes) throw new PlaneError("upstream", "Plane returned a response that is too large.");
  if (!response.body) return null;

  const chunks: Uint8Array[] = [];
  let size = 0;
  const reader = response.body.getReader();
  while (true) {
    // The response stream must be consumed in order so the byte limit can stop it immediately.
    // eslint-disable-next-line no-await-in-loop
    const { done, value } = await reader.read();
    if (done) break;
    size += value.byteLength;
    if (size > maximumBytes) {
      // eslint-disable-next-line no-await-in-loop
      await reader.cancel();
      throw new PlaneError("upstream", "Plane returned a response that is too large.");
    }
    chunks.push(value);
  }

  const bytes = new Uint8Array(size);
  let offset = 0;
  for (const chunk of chunks) {
    bytes.set(chunk, offset);
    offset += chunk.byteLength;
  }
  const text = new TextDecoder().decode(bytes);
  if (!text) return null;
  try {
    return JSON.parse(text) as unknown;
  } catch {
    throw new PlaneError("upstream", "Plane returned an invalid response.");
  }
};

export class PlaneApiClient {
  constructor(
    private readonly token: string,
    private readonly config: McpConfig,
    private readonly fetchImplementation: FetchImplementation = fetch
  ) {}

  async request<T = unknown>(path: string, options: PlaneRequestOptions = {}): Promise<T> {
    const url = new URL(`${this.config.planeApiBaseUrl}/${path.replace(/^\//, "")}`);
    for (const [key, value] of Object.entries(options.query ?? {})) {
      if (value !== undefined) url.searchParams.set(key, String(value));
    }

    let response: Response;
    try {
      response = await this.fetchImplementation(url, {
        method: options.method ?? "GET",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
          "X-Api-Key": this.token,
        },
        body: options.body ? JSON.stringify(options.body) : undefined,
        signal: AbortSignal.timeout(this.config.planeApiTimeoutMs),
      });
    } catch (error) {
      if (error instanceof PlaneError) throw error;
      throw new PlaneError("upstream", "Plane is unavailable or timed out.");
    }

    const body = await readJsonWithLimit(response, this.config.planeApiResponseLimitBytes);
    if (!response.ok) throw errorFromResponse(response, body);
    return body as T;
  }
}
