/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

const REDACTED = "[REDACTED]";
const sensitiveKey = /^(authorization|cookie|set-cookie|x-api-key|api[_-]?key|access[_-]?token|token)$/i;

const redactString = (value: string): string =>
  value
    .replace(/\bBearer\s+[A-Za-z0-9._~+/=-]+/gi, `Bearer ${REDACTED}`)
    .replace(/(X-Api-Key\s*[:=]\s*)[^\s,;]+/gi, `$1${REDACTED}`);

export const redact = (value: unknown): unknown => {
  if (typeof value === "string") return redactString(value);
  if (value instanceof Error) {
    return { name: value.name, message: redactString(value.message) };
  }
  if (Array.isArray(value)) return value.map(redact);
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value).map(([key, entry]) => [key, sensitiveKey.test(key) ? REDACTED : redact(entry)])
    );
  }
  return value;
};

type LogLevel = "debug" | "info" | "warn" | "error";

const levelPriority: Record<LogLevel, number> = { debug: 10, info: 20, warn: 30, error: 40 };

export class Logger {
  constructor(private readonly minimumLevel: LogLevel) {}

  debug(message: string, details?: unknown) {
    this.write("debug", message, details);
  }

  info(message: string, details?: unknown) {
    this.write("info", message, details);
  }

  warn(message: string, details?: unknown) {
    this.write("warn", message, details);
  }

  error(message: string, details?: unknown) {
    this.write("error", message, details);
  }

  private write(level: LogLevel, message: string, details?: unknown) {
    if (levelPriority[level] < levelPriority[this.minimumLevel]) return;
    const entry = {
      timestamp: new Date().toISOString(),
      level,
      service: "plane-mcp",
      message,
      ...(details === undefined ? {} : { details: redact(details) }),
    };
    const serialized = JSON.stringify(entry);
    if (level === "error") console.error(serialized);
    else if (level === "warn") console.warn(serialized);
    else console.log(serialized);
  }
}
