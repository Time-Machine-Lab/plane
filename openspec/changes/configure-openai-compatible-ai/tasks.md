## 1. Shared Configuration Contracts

- [ ] 1.1 Expand `@plane/types` with `LLM_BASE_URL`, `LLM_MODELS`, and `LLM_REASONING_EFFORT` plus the minimal configured-secret response metadata; preserve existing exports and consumers.
- [ ] 1.2 Follow the repository `translate` skill and add synchronized `@plane/i18n` keys for the form, validation, configured-key state, and save feedback without changing unrelated locale strings.

## 2. API Configuration and Persistence

- [ ] 2.1 Add `LLM_BASE_URL`, `LLM_MODELS`, and `LLM_REASONING_EFFORT` to the existing instance configuration definitions, parse optional operator `LLM_ALLOWED_HOSTS`/`LLM_ALLOWED_IPS`, and document placeholder-only examples. Require no Django schema migration.
- [ ] 2.2 Implement one server-side AI configuration parser/validator that merges submitted and stored values, derives a legacy model list from `LLM_MODEL`, validates URL/model/default/effort consistency, and reports structured field errors.
- [ ] 2.3 Make AI PATCH updates atomic, implement omitted/replace/explicit-clear API-key semantics, and redact `LLM_API_KEY` with configured metadata in authorized responses without changing unrelated encrypted settings.
- [ ] 2.4 Add focused API unit and contract tests for parsing/defaults, atomic rollback, secret semantics, instance-admin authorization, and non-admin rejection.

## 3. AI Runtime and Outbound Safety

- [ ] 3.1 Replace the tuple configuration helper with one typed effective configuration consumed by both workspace and project completion endpoints; remove the fixed model allowlist as a runtime gate while preserving compatibility behavior.
- [ ] 3.2 Configure the OpenAI client with a custom Base URL only when present, preserve path prefixes, disable automatic redirects, apply bounded timeouts/retries, send the selected model, and omit `reasoning_effort` unless configured.
- [ ] 3.3 Validate a custom target before persistence and immediately before use, block unsafe/unresolved targets without sending credentials or content, and allow only operator-trusted hosts/networks from dedicated allowlists.
- [ ] 3.4 Preserve completion success response shapes and sanitized failure behavior; runtime failures must not mutate settings or log secrets.
- [ ] 3.5 Add focused mocked unit/contract tests for official fallback, custom URL/path/model/effort, redirects, public/blocked/allowlisted targets, both completion endpoints, error mapping, configuration preservation, and log redaction.

## 4. God Mode Administration UI

- [ ] 4.1 Extend the existing OpenAI form with a labeled Base URL input, accessible editable model list, default-model selector, preset-capable/custom reasoning-effort control, and configured/replace/clear API-key interaction using existing Admin patterns.
- [ ] 4.2 Parse and serialize the model catalog through a typed form adapter, omit an unchanged secret, map server field errors without losing attempted values, and preserve submitting, disabled, success, and failure states.
- [ ] 4.3 Verify responsive layout, keyboard/focus behavior, accessible names, dynamic text fit, and clean console behavior while keeping new copy localized.
- [ ] 4.4 Do not introduce an Admin test harness solely for this screen. Keep serialization and validation mechanics covered by API tests and use the runtime configuration journey for the user-visible interaction.

## 5. Verification and Acceptance

- [ ] 5.1 Confirm affected CI checks and existing automated tests pass. CI owns lint, types, builds, and automated test evidence; the Tester does not rerun these commands.
- [ ] 5.2 Deploy the affected `admin` and `api` services once with `scripts/test/deploy-test.ps1 -Services admin,api`. The deploy script owns migration, startup, and health evidence.
- [ ] 5.3 Have an independent Tester preflight the required accounts, controlled compatible endpoint, synthetic credential, and observation channel. Record `blocked` rather than `fail` when a prerequisite is unavailable.
- [ ] 5.4 Have the Tester execute a minimal set of journeys covering: Admin save/reload and validation recovery; key preserve/replace/clear and non-admin rejection; custom endpoint/model/effort through both completion entry points; official fallback; and safe, blocked, and explicitly trusted endpoint policy. One journey may cover multiple spec scenarios, and only one real third-party connectivity smoke is required.
- [ ] 5.5 Record sanitized `pass`/`fail`/`blocked` journey evidence in `verification.md`. Mocked tests own timeout/DNS/upstream-error permutations. After a defect fix and redeployment, the same Tester retests only the failed journey and one necessary nearby regression.

## Acceptance Record

- Tester: Pending independent Tester
- Verification report: [verification.md](./verification.md) (to be created after implementation)
- Verdict: pending
- Residual risks: pending final Tester assessment; the design records the remaining DNS resolution-to-connect interval for custom SDK requests
