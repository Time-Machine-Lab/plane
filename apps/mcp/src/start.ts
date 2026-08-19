/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { loadConfig } from "@/config";
import { Logger } from "@/logger";
import { PlaneMcpHttpServer } from "@/server";

const config = loadConfig();
const logger = new Logger(config.logLevel);
const server = new PlaneMcpHttpServer(config, logger);

const shutdown = async (signal: string): Promise<void> => {
  logger.info("Plane MCP server stopping", { signal });
  try {
    await server.close();
    process.exit(0);
  } catch (error) {
    logger.error("Plane MCP server shutdown failed", { error });
    process.exit(1);
  }
};

server.listen().catch((error: unknown) => {
  logger.error("Plane MCP server failed to start", { error });
  process.exit(1);
});

process.on("SIGTERM", () => void shutdown("SIGTERM"));
process.on("SIGINT", () => void shutdown("SIGINT"));

process.on("unhandledRejection", (error: unknown) => {
  logger.error("Unhandled rejection", { error });
});

process.on("uncaughtException", (error: Error) => {
  logger.error("Uncaught exception", { error });
  process.exit(1);
});
