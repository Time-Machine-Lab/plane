/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { Server as HttpServer } from "node:http";
import { randomUUID } from "node:crypto";
import { createMcpExpressApp } from "@modelcontextprotocol/sdk/server/express.js";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";
import express, { type Request, type Response } from "express";
import type { McpConfig } from "@/config";
import type { Logger } from "@/logger";
import { registerPlaneTools } from "@/tools";

const methodNotAllowed = (res: Response): void => {
  res.status(405).json({
    jsonrpc: "2.0",
    error: { code: -32_000, message: "Method not allowed." },
    id: null,
  });
};

export const createPlaneMcpServer = (config: McpConfig, logger: Logger): McpServer => {
  const server = new McpServer({ name: "plane", version: "1.0.0" });
  registerPlaneTools(server, config, logger);
  return server;
};

export class PlaneMcpHttpServer {
  private readonly app;
  private httpServer: HttpServer | undefined;

  constructor(
    private readonly config: McpConfig,
    private readonly logger: Logger
  ) {
    this.app = createMcpExpressApp({ host: config.host });
    this.app.disable("x-powered-by");
    this.app.use(express.json({ limit: config.requestBodyLimitBytes }));
    this.registerRoutes();
  }

  get expressApp() {
    return this.app;
  }

  listen(): Promise<void> {
    return new Promise((resolve, reject) => {
      this.httpServer = this.app.listen(this.config.port, this.config.host, () => {
        this.logger.info("Plane MCP server started", {
          host: this.config.host,
          port: this.config.port,
          path: this.config.path,
          enabled: this.config.enabled,
        });
        resolve();
      });
      this.httpServer.once("error", reject);
    });
  }

  close(): Promise<void> {
    if (!this.httpServer) return Promise.resolve();
    return new Promise((resolve, reject) => {
      this.httpServer?.close((error) => {
        if (error) reject(error);
        else resolve();
      });
    });
  }

  private registerRoutes(): void {
    this.app.get("/health", (_req, res) => {
      res.status(200).json({ status: this.config.enabled ? "ok" : "disabled" });
    });

    this.app.post(this.config.path, (req: Request, res: Response) => {
      void this.handleMcpRequest(req, res);
    });

    this.app.get(this.config.path, (_req, res) => {
      if (!this.config.enabled) res.status(404).json({ message: "Not Found" });
      else methodNotAllowed(res);
    });

    this.app.delete(this.config.path, (_req, res) => {
      if (!this.config.enabled) res.status(404).json({ message: "Not Found" });
      else methodNotAllowed(res);
    });

    this.app.use((_req, res) => res.status(404).json({ message: "Not Found" }));
  }

  private async handleMcpRequest(req: Request, res: Response): Promise<void> {
    if (!this.config.enabled) {
      res.status(404).json({ message: "Not Found" });
      return;
    }

    const requestId = randomUUID();
    const server = createPlaneMcpServer(this.config, this.logger);
    const transport = new StreamableHTTPServerTransport({
      sessionIdGenerator: undefined,
      enableJsonResponse: true,
    });
    res.once("close", () => {
      void transport.close();
      void server.close();
    });

    try {
      await server.connect(transport);
      await transport.handleRequest(req, res, req.body);
      this.logger.debug("MCP request completed", { request_id: requestId, method: req.method, path: req.path });
    } catch (error) {
      this.logger.error("MCP request failed", { request_id: requestId, error });
      if (!res.headersSent) {
        res.status(500).json({
          jsonrpc: "2.0",
          error: { code: -32_603, message: "Internal server error" },
          id: null,
        });
      }
    }
  }
}
