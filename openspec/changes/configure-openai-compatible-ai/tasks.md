## 1. Shared Configuration Contracts

- [ ] 1.1 Expand `@plane/types` with `LLM_BASE_URL`, `LLM_MODELS`, and `LLM_REASONING_EFFORT` plus the minimal configured-secret response metadata; preserve all existing exports and consumers. Complete L1 with `pnpm turbo run check:format check:lint check:types --filter=@plane/types`, `pnpm turbo run build --filter=@plane/types`, and the direct admin type check `pnpm turbo run check:types --filter=admin` before marking this task complete.
- [ ] 1.2 Follow the repository `translate` skill, add synchronized `@plane/i18n` keys for the OpenAI-compatible form, validation, configured-key state, and save feedback, and avoid changing unrelated locale strings. Complete L1 with `pnpm --filter=@plane/i18n check:sync` and the package's configured format, lint, type, and build commands before marking this task complete.

## 2. API Configuration and Persistence

- [ ] 2.1 Add `LLM_BASE_URL`, `LLM_MODELS`, and `LLM_REASONING_EFFORT` to the existing instance configuration definitions, parse optional `LLM_ALLOWED_HOSTS`/`LLM_ALLOWED_IPS` operator environment values with sanitized warnings, and document placeholder-only examples. Preserve existing values and require no Django schema migration.
- [ ] 2.2 Implement one server-side AI configuration parser/validator that merges submitted and stored values, derives a legacy model list from `LLM_MODEL`, validates URL/model/default/effort consistency, and reports structured field errors.
- [ ] 2.3 Make AI PATCH updates atomic, implement omitted/replace/explicit-clear API-key semantics, and redact `LLM_API_KEY` with configured metadata in authorized responses without changing serialization for unrelated encrypted settings.
- [ ] 2.4 Add API unit and app-contract tests for new defaults, JSON parsing, legacy fallback, valid and invalid model/default/effort values, atomic rollback, secret redaction/preservation/clear, instance-admin access, and non-admin rejection. Complete L1 for tasks 2.1-2.4 with `ruff format --check apps/api`, `ruff check apps/api`, and `docker compose -f docker-compose-test.yml run --rm --build api-tests pytest plane/tests/unit/license/test_ai_configuration.py plane/tests/contract/app/test_instance_ai_configuration.py` before marking them complete.

## 3. AI Runtime and Outbound Safety

- [ ] 3.1 Replace the tuple configuration helper with one typed effective configuration consumed by both workspace and project completion endpoints; remove the fixed model allowlist as a runtime gate while retaining the existing provider/default compatibility behavior.
- [ ] 3.2 Configure the OpenAI client with the custom Base URL only when present, preserve Base URL path prefixes, disable automatic redirects, apply bounded timeouts/retries, send the selected model, and omit `reasoning_effort` unless configured.
- [ ] 3.3 Validate a custom target before persistence and immediately before use, block unsafe/unresolved targets without sending credentials or content, and allow only operator-trusted hosts/networks from the dedicated allowlists.
- [ ] 3.4 Preserve completion success response shapes and sanitized failure behavior for invalid configuration, authentication, rate limits, timeouts, incompatible protocols, and upstream outages; ensure runtime failures never mutate settings or log secrets.
- [ ] 3.5 Add focused unit/contract tests using synthetic keys and mocked DNS/HTTP/OpenAI transports for official fallback, custom URL/path, arbitrary models including a synthetic GPT-5.6 Sol identifier, effort present/omitted, redirects, public/blocked/allowlisted targets, both completion endpoints, error mapping, configuration preservation, and log redaction. Complete L1 for tasks 3.1-3.5 with `ruff format --check apps/api`, `ruff check apps/api`, and `docker compose -f docker-compose-test.yml run --rm --build api-tests pytest plane/tests/unit/app/test_openai_compatible_provider.py plane/tests/contract/app/test_ai_completion_configuration.py` before marking them complete.

## 4. God Mode Administration UI

- [ ] 4.1 Extend the existing OpenAI form with a labeled Base URL input, accessible editable model-list control, default-model selector, preset-capable/custom reasoning-effort combobox, and configured/replace/clear API-key interaction using existing admin and Propel patterns.
- [ ] 4.2 Parse and serialize the model catalog through a typed form adapter, omit an unchanged secret, map server field errors without losing attempted values, and preserve submitting, disabled, success, and failure states in the existing service/store flow.
- [ ] 4.3 Verify responsive layout, keyboard/focus behavior, accessible names, dynamic text fit, and no console/hydration errors at desktop and mobile widths; keep new copy localized through the keys from task 1.2.
- [ ] 4.4 Add the admin's focused Vitest setup/script if still absent and cover model-list editing/default consistency, legacy initialization, effort presets/custom values, secret omission/replace/clear, payload serialization, and server error recovery. Complete L1 for tasks 4.1-4.4 with `pnpm --filter=admin test`, `pnpm turbo run check:format check:lint check:types --filter=admin`, and `pnpm turbo run build --filter=admin` before marking them complete.

## 5. Runtime Acceptance and Independent Verification

- [ ] 5.1 Execute L2 on Windows with `Get-Help .\scripts\test\start-local.ps1 -Detailed` and `.\scripts\test\start-local.ps1 -Apps admin -Wait`; through the reported local URL/tunnel, verify instance-admin save/reload, arbitrary model/default changes, reasoning presets/custom values, key configured/replace/clear, validation recovery, mobile/desktop layout, keyboard access, and clean browser console/network behavior. Record only redacted screenshots and observable results.
- [ ] 5.2 Execute L3 with `Get-Help .\scripts\test\deploy-test.ps1 -Detailed` and `.\scripts\test\deploy-test.ps1 -Services admin,api`; through the script-reported configured-port URL and a controlled non-production OpenAI-compatible fixture, verify custom URL/path/model/effort, official fallback, both completion endpoints, non-admin rejection, public/blocked/allowlisted targets, upstream failure recovery, persistence, container health, and absence of secrets in responses/logs. Keep all hosts, accounts, tokens, cookies, and private configuration in ignored `.secrets/plane-test.env`, never in artifacts.
- [ ] 5.3 Execute the L4 pre-merge/release gate with `pnpm check`, `pnpm build`, and `docker compose -f docker-compose-test.yml up --build --abort-on-container-exit --exit-code-from api-tests`; repeat the critical God Mode save and configured completion smoke path on the isolated test instance, then clean only the dedicated local API test stack with `docker compose -f docker-compose-test.yml down -v` after validating its target project.
- [ ] 5.4 After implementation and all implementation-Agent L1 checks pass, create a new Tester sub-agent with only `openspec/changes/configure-openai-compatible-ai/`, `docs/spec/testing-quality.md`, `docs/spec/test-environment.md`, `docs/spec/frontend-development.md`, `docs/spec/backend-development.md`, and `docs/spec/shared-packages-development.md`. The Tester must independently read all artifacts, leave product code unchanged, rerun the required L1-L4 scenarios, and write `openspec/changes/configure-openai-compatible-ai/verification.md` with pass/fail/unverified evidence for every mandatory scenario. Tester/implementation separation is responsibility independence, not process, credential, or security isolation, because Agents share the worktree.
- [ ] 5.5 If verification fails or is unverified, return the evidence to the implementation Agent for fixes and create a different new Tester sub-agent for the next cycle; never reuse the previous Tester to declare success. Accept the change only when the final new Tester report marks every mandatory scenario pass.

## Acceptance Record

- Tester: Pending new independent Tester sub-agent
- Verification report: [verification.md](./verification.md) (to be created after implementation)
- Selected level: L1 + L2 + L3, with L4 required before merge/release
- Verdict: pending
- Evidence: pending sanitized command output, deployment ID, API/page observations, and redacted screenshots
- Residual risks: pending final Tester assessment; the design records the remaining DNS resolution-to-connect interval for custom SDK requests
