## Why

God Mode currently stores only an API key and one model name, while the API always connects to OpenAI's default endpoint and rejects models outside a stale built-in allowlist. Self-hosted Plane instances therefore cannot use their own OpenAI-compatible gateway, newer models such as GPT-5.6 Sol, or model-specific reasoning effort settings.

## What Changes

- Extend the God Mode AI form with an optional OpenAI-compatible Base URL, an editable model list, a selected default model, and an optional reasoning effort setting while retaining the encrypted API key field.
- Replace the backend's fixed model allowlist with validation against the administrator-configured model list, and use the selected model for AI requests.
- Route AI requests through the configured Base URL, falling back to the official OpenAI endpoint when the field is empty.
- Send reasoning effort only when configured so endpoints and models that do not use the option remain compatible.
- Validate configuration atomically and return actionable errors without overwriting the last valid settings. Restrict reads and writes to the existing instance-administrator authorization boundary.
- Validate outbound HTTP(S) targets against Plane's URL-security rules. Public endpoints work directly; trusted private endpoints require an explicit operator allowlist so arbitrary internal or metadata access remains blocked by default.
- Preserve existing `LLM_API_KEY` and `LLM_MODEL` installations without a database schema migration. Existing installations continue to use the official OpenAI endpoint and their current model until an administrator opts into the new settings.

## Capabilities

### New Capabilities

- `openai-compatible-ai-configuration`: Instance administrators can configure and safely use an OpenAI-compatible endpoint, model catalog, default model, and reasoning effort from God Mode.

### Modified Capabilities

None. The repository currently has no main spec governing instance AI configuration.

## Impact

- **Runtime modules**: `apps/admin` for the God Mode form and interaction states; `apps/api` for configuration validation, persistence, URL safety, and OpenAI client/request construction.
- **Shared packages**: `packages/types` for the expanded instance AI configuration key contract and `packages/i18n` for new user-visible settings and validation copy. Existing service and store update paths remain the transport boundary unless implementation discovers a missing validation contract.
- **API contract**: The existing instance configuration read/update endpoint gains recognized AI configuration keys and validation errors; endpoint paths and authentication semantics do not change. Workspace/project AI completion response shapes remain unchanged.
- **Authorization**: Only instance administrators may read or update these settings. Existing workspace/project member access to invoke configured AI features is unchanged and never exposes the API key.
- **Data and migration**: New `InstanceConfiguration` entries use the existing text-backed configuration mechanism. No Django schema migration or destructive data migration is expected. Rollback ignores/removes the new values and restores official-endpoint behavior.
- **Deployment**: No mandatory deployment topology change. An optional operator allowlist is required only for trusted private-network model gateways; no secret or private endpoint value is committed.
- **Realtime and events**: No realtime protocol, event, worker, or public package behavior changes.
- **Dependencies and licensing**: Reuse the installed OpenAI SDK and existing Plane UI/security utilities; no new dependency or AGPL licensing impact is expected.
- **Upstream compatibility**: Keep changes within existing AI configuration and provider extension points, preserve current keys, and avoid broad provider abstractions so future Plane upstream merges remain focused.

## Applicable Standards

- `docs/spec/README.md`
- `docs/spec/general-development.md`
- `docs/spec/testing-quality.md`
- `docs/spec/frontend-development.md`
- `docs/spec/backend-development.md`
- `docs/spec/shared-packages-development.md`
- `docs/spec/module-structure.md`
- `docs/spec/test-environment.md`

## Acceptance

- **L1, Windows local**: Run focused format, lint, type, build, and automated tests for `admin`, `@plane/types`, and `apps/api`. Unit and contract tests cover parsing, defaults, invalid values, authorization, URL blocking/allowlisting, request construction, and redaction.
- **L2, Windows local frontend plus isolated test API**: Start `admin` with `scripts/test/start-local.ps1`; verify an instance administrator can edit the Base URL, model list, default model, API key, and reasoning effort, sees validation and saving states, and reloads the persisted non-secret values without layout, accessibility, console, or network errors.
- **L3, isolated test server**: Deploy only affected `admin` and `api` services with `scripts/test/deploy-test.ps1`; use a non-production OpenAI-compatible fixture endpoint and synthetic credentials to verify the selected endpoint, model, and optional reasoning effort are used, official-endpoint fallback remains compatible, non-administrators are rejected, blocked targets cannot be saved or called, failures do not erase the last valid configuration, and secrets never appear in responses or logs.
- **L4, pre-merge/release**: Run the repository-wide checks, build, and isolated API suite because this is a security-sensitive cross-module/public-type contract change; repeat the critical God Mode save and completion smoke path on the test instance.
- The change is accepted only after a newly created Tester sub-agent independently records pass evidence for every mandatory scenario in `verification.md`; any failed or unavailable mandatory scenario keeps the change incomplete.

## Non-Goals

- Adding Anthropic, Gemini, or other native provider-specific configuration screens or request protocols.
- Discovering models automatically from `/models`, testing credentials from the form, usage/cost reporting, per-workspace overrides, or per-request model selection.
- Changing prompts, AI feature UX outside God Mode, completion response payloads, or adopting the OpenAI Responses API as part of this change.
- Allowing unrestricted access to loopback, link-local, cloud metadata, or other internal targets without an explicit operator trust configuration.
