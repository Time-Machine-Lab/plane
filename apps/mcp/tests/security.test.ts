import { describe, expect, it } from "vitest";
import { redact } from "@/logger";
import { getHeader } from "@/request-context";

describe("credential handling", () => {
  it("redacts credential fields and credential-shaped strings", () => {
    const serialized = JSON.stringify(
      redact({
        authorization: "Bearer top-secret",
        nested: { "X-Api-Key": "another-secret", message: "X-Api-Key: third-secret" },
      })
    );
    expect(serialized).not.toContain("top-secret");
    expect(serialized).not.toContain("another-secret");
    expect(serialized).not.toContain("third-secret");
    expect(serialized).toContain("[REDACTED]");
  });

  it("resolves request headers case-insensitively", () => {
    expect(getHeader({ "X-Plane-Workspace": "engineering" }, "x-plane-workspace")).toBe("engineering");
  });
});
