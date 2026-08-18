## 1. MCP Runtime

- [ ] 1.1 Add the `apps/mcp` runtime, official MCP SDK dependency, strict TypeScript configuration, and local service entry point.
- [ ] 1.2 Implement the Streamable HTTP `/mcp` transport, initialization lifecycle, health behavior, and enablement configuration.
- [ ] 1.3 Add typed configuration for the Plane API base URL, request timeouts, response limits, and redacted structured logging.

## 2. Authentication And Plane API Adapter

- [ ] 2.1 Implement Bearer API-token extraction, credential redaction, and forwarding to `/api/v1` as `X-Api-Key`.
- [ ] 2.2 Implement explicit and default-header workspace context resolution without server-side user session storage.
- [ ] 2.3 Build the typed Plane API client with pagination preservation and stable authentication, authorization, validation, not-found, conflict, throttling, and upstream error mapping.
- [ ] 2.4 Add or adjust focused `/api/v1` contracts and OpenAPI examples only where the approved MCP tools cannot use an existing safe external endpoint.

## 3. Plane MCP Tools

- [ ] 3.1 Implement `plane_status` and project read tools with compact structured outputs.
- [ ] 3.2 Implement paginated work-item list, search, detail, and comment-list tools.
- [ ] 3.3 Implement work-item create and update tools with strict schemas and no partial mutation on invalid input.
- [ ] 3.4 Implement comment creation and supporting state, label, cycle, module, and suitable member read tools.
- [ ] 3.5 Verify `tools/list` excludes deletion, administration, token-management, export, archive, and restore operations.

## 4. Deployment And Documentation

- [ ] 4.1 Add proxy routing and local, test, and supported self-hosted deployment definitions for the optional MCP runtime.
- [ ] 4.2 Document `/mcp`, Bearer API-token configuration, workspace context options, supported tools, dedicated-account guidance, and rollback behavior.

## 5. Verification

- [ ] 5.1 Add focused MCP protocol, tool-schema, API mapping, credential-redaction, pagination, and workspace/project isolation tests.
- [ ] 5.2 Deploy the completed change once with `scripts/test/deploy-test.ps1`.
- [ ] 5.3 Have an independent Tester execute the required MCP access and tool scenarios with persistent test accounts and record pass/fail evidence in `verification.md`.
