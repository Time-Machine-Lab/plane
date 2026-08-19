import type { Server } from "node:http";
import type { AddressInfo } from "node:net";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StreamableHTTPClientTransport } from "@modelcontextprotocol/sdk/client/streamableHttp.js";
import type { McpConfig } from "@/config";
import { Logger } from "@/logger";
import { PlaneMcpHttpServer } from "@/server";

export const testConfig = (overrides: Partial<McpConfig> = {}): McpConfig => ({
  enabled: true,
  host: "127.0.0.1",
  port: 3100,
  path: "/mcp",
  requestBodyLimitBytes: 2_097_152,
  planeApiBaseUrl: "https://plane.example.test/api/v1",
  planeBaseUrl: "https://plane.example.test",
  planeApiTimeoutMs: 1_000,
  planeApiResponseLimitBytes: 1_048_576,
  logLevel: "error",
  ...overrides,
});

export const startTestServer = async (config = testConfig()) => {
  const service = new PlaneMcpHttpServer(config, new Logger("error"));
  const server = await new Promise<Server>((resolve) => {
    const listening = service.expressApp.listen(0, "127.0.0.1", () => resolve(listening));
  });
  const address = server.address() as AddressInfo;
  const url = new URL(`http://127.0.0.1:${address.port}${config.path}`);

  return {
    server,
    url,
    close: () =>
      new Promise<void>((resolve, reject) =>
        server.close((error) => {
          if (error) reject(error);
          else resolve();
        })
      ),
  };
};

export const connectClient = async (url: URL, headers: Record<string, string> = {}) => {
  const transport = new StreamableHTTPClientTransport(url, { requestInit: { headers } });
  const client = new Client({ name: "plane-mcp-test", version: "1.0.0" });
  await client.connect(transport);
  return { client, transport };
};
