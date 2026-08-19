import { afterEach, describe, expect, it, vi } from "vitest";
import { TOOL_NAMES } from "@/tools";
import { connectClient, startTestServer, testConfig } from "./helpers";

const realFetch = globalThis.fetch;

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("Plane MCP protocol", () => {
  it("initializes and advertises only the approved tool catalog without authentication", async () => {
    const running = await startTestServer();
    const { client, transport } = await connectClient(running.url);
    try {
      const listed = await client.listTools();
      const names = listed.tools.map((tool) => tool.name).toSorted();
      expect(names).toEqual([...TOOL_NAMES].toSorted());
      expect(names.join(" ")).not.toMatch(/delete|archive|restore|export|invite|token|admin/i);
    } finally {
      await transport.close();
      await running.close();
    }
  });

  it("rejects tool calls without a Bearer token before calling Plane", async () => {
    const upstream = vi.fn();
    vi.stubGlobal("fetch", async (input: string | URL | Request, init?: RequestInit) => {
      const url = new URL(input instanceof Request ? input.url : input.toString());
      if (url.hostname === "127.0.0.1") return realFetch(input, init);
      upstream();
      return new Response(null, { status: 500 });
    });
    const running = await startTestServer();
    const { client, transport } = await connectClient(running.url);
    try {
      const result = await client.callTool({ name: "plane_status", arguments: { workspace_slug: "engineering" } });
      expect(result.isError).toBe(true);
      expect(result.structuredContent).toMatchObject({ error: { code: "authentication" } });
      expect(upstream).not.toHaveBeenCalled();
    } finally {
      await transport.close();
      await running.close();
    }
  });

  it("uses the default workspace header and forwards the token only as X-Api-Key", async () => {
    const upstreamRequests: Array<{ url: string; headers: Headers }> = [];
    vi.stubGlobal("fetch", async (input: string | URL | Request, init?: RequestInit) => {
      const url = new URL(input instanceof Request ? input.url : input.toString());
      if (url.hostname === "127.0.0.1") return realFetch(input, init);
      const headers = new Headers(init?.headers);
      upstreamRequests.push({ url: url.toString(), headers });
      const body = url.pathname.endsWith("/users/me/")
        ? { id: "user-1", display_name: "Plane Agent" }
        : { results: [], total_count: 0, count: 0 };
      return Response.json(body);
    });
    const running = await startTestServer();
    const { client, transport } = await connectClient(running.url, {
      Authorization: "Bearer secret-plane-token",
      "X-Plane-Workspace": "engineering",
    });
    try {
      const result = await client.callTool({ name: "plane_status", arguments: {} });
      expect(result.isError).not.toBe(true);
      expect(result.structuredContent).toMatchObject({ available: true, workspace: "engineering" });
      expect(upstreamRequests).toHaveLength(2);
      expect(upstreamRequests[1]?.url).toContain("/workspaces/engineering/projects/");
      for (const request of upstreamRequests) {
        expect(request.headers.get("x-api-key")).toBe("secret-plane-token");
        expect(request.headers.get("authorization")).toBeNull();
      }
    } finally {
      await transport.close();
      await running.close();
    }
  });

  it("rejects unknown write fields without issuing a mutation", async () => {
    const upstream = vi.fn();
    vi.stubGlobal("fetch", async (input: string | URL | Request, init?: RequestInit) => {
      const url = new URL(input instanceof Request ? input.url : input.toString());
      if (url.hostname === "127.0.0.1") return realFetch(input, init);
      upstream();
      return Response.json({});
    });
    const running = await startTestServer();
    const { client, transport } = await connectClient(running.url, { Authorization: "Bearer token" });
    try {
      const result = await client.callTool({
        name: "create_work_item",
        arguments: {
          workspace_slug: "engineering",
          project_id: "11111111-1111-4111-8111-111111111111",
          title: "Test",
          delete_after_create: true,
        },
      });
      expect(result.isError).toBe(true);
      expect(upstream).not.toHaveBeenCalled();
    } finally {
      await transport.close();
      await running.close();
    }
  });

  it("returns not found from the MCP route when disabled", async () => {
    const running = await startTestServer(testConfig({ enabled: false }));
    try {
      const response = await realFetch(running.url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ jsonrpc: "2.0", id: 1, method: "initialize", params: {} }),
      });
      expect(response.status).toBe(404);
    } finally {
      await running.close();
    }
  });
});
