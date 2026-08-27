import { describe, expect, it, vi } from "vitest";
import { PlaneApiClient } from "@/plane-api";
import { attachmentProjection, paginatedProjection, workItemProjection } from "@/projections";
import { testConfig } from "./helpers";

describe("Plane API adapter", () => {
  it("preserves pagination metadata while projecting compact work items", () => {
    const result = paginatedProjection(
      {
        total_count: 2,
        next_cursor: "50:50:0",
        next_page_results: true,
        count: 1,
        results: [{ id: "item-1", name: "First", sequence_id: 1, description_binary: "excluded" }],
      },
      workItemProjection
    );
    expect(result).toEqual({
      items: [{ id: "item-1", name: "First", sequence_id: 1 }],
      pagination: { total_count: 2, next_cursor: "50:50:0", next_page_results: true, count: 1 },
    });
  });

  it("includes sanitized description while excluding binary description data", () => {
    expect(
      workItemProjection({
        id: "item-1",
        name: "First",
        description_html: "<p>Current context</p>",
        description_binary: "secret-binary",
      })
    ).toEqual({ id: "item-1", name: "First", description_html: "<p>Current context</p>" });
  });

  it("projects only bounded attachment metadata and authorized access path", () => {
    expect(
      attachmentProjection({
        id: "asset-1",
        attributes: { name: "brief.pdf", type: "application/pdf", private: "excluded" },
        size: 1200,
        asset_url: "/api/assets/v2/workspaces/acme/projects/p/issues/i/attachments/asset-1/",
        asset: "private/storage/key",
        storage_metadata: { bucket: "secret" },
      })
    ).toEqual({
      id: "asset-1",
      name: "brief.pdf",
      media_type: "application/pdf",
      size: 1200,
      download_path: "/api/assets/v2/workspaces/acme/projects/p/issues/i/attachments/asset-1/",
    });
  });

  it.each([
    [400, "validation"],
    [401, "authentication"],
    [403, "authorization"],
    [404, "not_found"],
    [409, "conflict"],
    [429, "throttled"],
    [500, "upstream"],
  ] as const)("maps Plane status %s to %s", async (status, code) => {
    const fetchImplementation = vi.fn(async () =>
      Response.json({ detail: "upstream detail" }, { status, headers: status === 429 ? { "Retry-After": "10" } : {} })
    );
    const client = new PlaneApiClient("secret", testConfig(), fetchImplementation);
    await expect(client.request("users/me/")).rejects.toMatchObject({ code });
  });

  it("maps Plane's invalid-token 403 response to authentication", async () => {
    const fetchImplementation = vi.fn(async () =>
      Response.json({ detail: "Given API token is not valid" }, { status: 403 })
    );
    const client = new PlaneApiClient("secret", testConfig(), fetchImplementation);
    await expect(client.request("users/me/")).rejects.toMatchObject({ code: "authentication" });
  });

  it("keeps other Plane 403 responses as authorization failures", async () => {
    const fetchImplementation = vi.fn(async () => Response.json({ detail: "Permission denied" }, { status: 403 }));
    const client = new PlaneApiClient("secret", testConfig(), fetchImplementation);
    await expect(client.request("users/me/")).rejects.toMatchObject({ code: "authorization" });
  });

  it("stops oversized upstream responses", async () => {
    const fetchImplementation = vi.fn(async () => new Response(JSON.stringify({ data: "x".repeat(200) })));
    const client = new PlaneApiClient("secret", testConfig({ planeApiResponseLimitBytes: 50 }), fetchImplementation);
    await expect(client.request("users/me/")).rejects.toMatchObject({ code: "upstream" });
  });
});
