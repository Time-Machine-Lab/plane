## Context

Plane's God Mode AI page currently edits only `LLM_API_KEY` and `LLM_MODEL`. The backend stores those values through the generic instance-configuration endpoint, validates the selected model against a provider class's fixed list, and constructs `OpenAI(api_key=...)`, which always uses the SDK endpoint. The same helper serves both workspace and project AI completion endpoints.

The change crosses `apps/admin`, `apps/api`, `packages/types`, and `packages/i18n`. It must retain existing installations, keep instance-level authorization intact, avoid returning a plaintext API key, and prevent an administrator-entered URL from becoming an unrestricted server-side request target. The user-visible contract is defined by `specs/openai-compatible-ai-configuration/spec.md`.

## Goals / Non-Goals

**Goals:**

- Let an instance administrator configure an OpenAI-compatible Base URL, arbitrary model catalog, default model, and optional reasoning effort in the existing God Mode AI page.
- Preserve the current `LLM_API_KEY` and `LLM_MODEL` settings and official OpenAI behavior by default.
- Validate multi-field updates as one configuration and apply them consistently to both existing completion endpoints.
- Keep secrets redacted and custom outbound targets constrained by an explicit URL-security policy.
- Keep the implementation localized to existing configuration/provider boundaries for manageable upstream merges.

**Non-Goals:**

- Add provider-native Anthropic or Gemini request paths, automatic `/models` discovery, per-workspace settings, usage accounting, credential testing, prompt changes, or the Responses API.
- Change successful workspace/project completion response payloads.
- Generalize the complete instance-configuration API or redesign all encrypted settings.
- Allow untrusted private, loopback, link-local, or metadata endpoints.

## Decisions

### 1. Extend the existing instance configuration contract

Use the existing `InstanceConfiguration` text storage and add the following recognized keys through the current seed/configuration mechanism:

| Key                    | Storage and default       | Purpose                                                                       |
| ---------------------- | ------------------------- | ----------------------------------------------------------------------------- |
| `LLM_API_KEY`          | Existing encrypted text   | Credential sent only to the selected endpoint                                 |
| `LLM_BASE_URL`         | Text, empty by default    | OpenAI-compatible base URL; empty means SDK default                           |
| `LLM_MODELS`           | JSON string array         | Editable ordered catalog of unique model identifiers                          |
| `LLM_MODEL`            | Existing text             | Selected default; must exist in `LLM_MODELS`                                  |
| `LLM_REASONING_EFFORT` | Text, empty by default    | Optional effort value sent only when non-empty                                |
| `LLM_PROVIDER`         | Existing `openai` default | Retained for compatibility; this change does not add other provider protocols |

`packages/types` expands `TInstanceAIConfigurationKeys` for the new persisted keys and adds the minimal response metadata needed to distinguish an omitted/redacted API key from an unconfigured key. It remains a pure type contract and does not own parsing or runtime state.

`LLM_MODELS` uses a JSON array rather than comma-separated text so model identifiers are unambiguous. The API owns serialization and parsing. For a legacy installation with no usable `LLM_MODELS`, the read/runtime adapter derives `[LLM_MODEL]`; the implementation does not need to rewrite existing rows during rollout.

Alternatives considered:

- Continue using only free-text `LLM_MODEL`: rejected because it does not provide the requested editable model list or a reliable default-selection contract.
- Create a relational model table: rejected because the list is instance configuration, does not require querying, and would add migration/rollback cost.
- Hard-code current models including GPT-5.6 Sol: rejected because compatible gateways use different identifiers and the list would become stale again.

### 2. Use one validated candidate configuration for atomic updates

When a PATCH contains any AI key, `apps/api` loads the currently effective AI values, overlays only submitted fields, parses the candidate model list, normalizes surrounding whitespace, and validates the complete candidate before writing. Validation includes:

- Base URL is empty or an absolute HTTP(S) URL with a host and without embedded credentials.
- Model list contains at least one distinct non-empty identifier; identifiers are length-bounded and contain no control characters.
- `LLM_MODEL` is one of the configured identifiers.
- Reasoning effort is empty or a length-bounded value without control characters. The UI offers common presets (`none`, `minimal`, `low`, `medium`, `high`, `xhigh`, `max`, `ultra`) but accepts a valid custom value for compatible gateways.
- API key update semantics distinguish omitted (preserve), non-empty (replace), and explicit clear. The form does not resubmit a redaction marker as a credential.

All requested AI rows are updated inside one database transaction only after the candidate passes validation. A structured HTTP 400 response maps errors to configuration keys. Unrelated configuration keys retain their current generic update behavior.

Alternatives considered:

- Validate each field independently in the React form only: rejected because direct API clients could bypass it and model/default consistency requires the merged server-side state.
- Partially save valid fields: rejected because it can leave the default model outside the catalog or pair a credential with the wrong endpoint.

### 3. Redact the AI credential without changing other secret forms

For `LLM_API_KEY`, configuration responses return an empty/redacted value plus a boolean indicating whether a value exists. The update contract preserves the stored key when the key field is omitted, replaces it only when a new value is submitted, and supports an explicit clear action. The admin form shows a configured state rather than hydrating plaintext into the password input.

This is intentionally scoped to the AI key. Changing serialization for every encrypted instance setting would affect authentication and email forms and is outside this change. Completion errors remain sanitized, and logs include endpoint/model context only after removing credentials, query secrets, and request content.

### 4. Keep UI state in the existing admin form boundary

`apps/admin` continues to use the existing instance store/service update path. The page parses `LLM_MODELS` into an editable model-list control, uses a select/combobox for the default model, and uses a preset-capable combobox for reasoning effort. The Base URL and password controls reuse existing Propel/common inputs. No new shared UI component is introduced unless implementation proves an existing reusable control is missing.

The layout retains the current OpenAI section and responsive God Mode visual language. It must provide labels, keyboard access, visible focus, disabled/submitting state, field-level server validation, save success/failure feedback, and stable small-screen layout. New user-visible strings use `@plane/i18n`; implementation must follow the repository `translate` workflow before editing locale JSON.

Failure direction is API -> service/store -> form: the service returns typed validation errors, the store preserves the last fetched values, and the form keeps the attempted values so the administrator can correct them. A failed save must not show success or overwrite stored state.

### 5. Build requests from one backend runtime configuration

Replace the tuple-style configuration helper with a typed backend value object or equivalent validated structure containing `api_key`, `base_url`, `models`, `model`, and `reasoning_effort`. Both workspace and project completion endpoints consume that same helper.

For an empty Base URL, instantiate the SDK without `base_url` so its official endpoint behavior remains authoritative. For a custom URL, pass the normalized Base URL while preserving any path prefix such as `/v1`. Build the chat-completion request with the configured model and add `reasoning_effort` only when non-empty; prompt construction and response mapping stay unchanged. Disable automatic redirects for custom endpoints so a validated origin cannot redirect credentials to another target. Apply explicit connection/read timeouts and retain bounded SDK retry behavior.

The fixed provider model list is no longer an authorization source. Runtime validation checks the selected model against the configured catalog. Provider names and unsupported native protocols remain unchanged.

Failure behavior:

- Missing/invalid effective configuration returns the existing sanitized client-facing configuration error without making an outbound request.
- Authentication, rate-limit, timeout, connection, or compatible-protocol errors are logged without secrets and mapped to the established generic completion failure response.
- Runtime failures never mutate persisted configuration.

### 6. Apply outbound URL safety with an explicit private-gateway escape hatch

At save time and immediately before a custom endpoint is used, validate the URL with Plane's existing IP/URL security primitives. Reject embedded credentials, non-HTTP(S) schemes, unresolved hosts, loopback, link-local, reserved, metadata, and private addresses by default. Automatic redirects are disabled.

Introduce operator-only environment contracts `LLM_ALLOWED_HOSTS` and `LLM_ALLOWED_IPS`, parsed with the same normalization and CIDR validation conventions as existing outbound allowlists. Exact allowlisted hosts or allowed networks may resolve to private addresses; no God Mode user can alter the allowlist. Invalid allowlist entries are ignored with sanitized startup warnings. These values are optional and empty by default, so public gateways require no deployment change. Environment examples/documentation contain placeholders only.

Save-time plus immediate pre-request validation reduces stale-DNS exposure while retaining the OpenAI SDK. A custom endpoint remains an administrator-controlled integration; redirect blocking and per-request revalidation are mandatory. A future shared pinned `httpx` transport can eliminate the remaining resolution-to-connect interval if the provider surface expands, but building that transport is outside this focused change.

Alternatives considered:

- Permit every administrator-entered URL: rejected because it enables credential-bearing SSRF into instance infrastructure.
- Block every private address with no escape hatch: rejected because self-hosted operators commonly run compatible gateways on private service networks.
- Reuse webhook-specific allowlist variables: rejected because LLM gateway trust and webhook trust are separate operator decisions.

## Cross-Module Contracts

```text
God Mode form (apps/admin)
        |
        | typed PATCH /api/instances/configurations/
        v
configuration validation/persistence (apps/api)
        |
        | validated effective AI configuration
        v
workspace/project completion endpoints (apps/api)
        |
        | OpenAI-compatible request
        v
official OpenAI endpoint or configured gateway
```

- **API**: Existing endpoint path and methods remain. AI PATCH validation gains structured 400 field errors and atomic semantics. AI key reads gain redaction/configured metadata. Completion success payloads do not change.
- **Data**: Existing table and encryption remain. New rows are text values created by the current configuration seeding mechanism; no schema migration.
- **Environment**: Optional `LLM_ALLOWED_HOSTS` and `LLM_ALLOWED_IPS`; existing `LLM_API_KEY`, `LLM_MODEL`, `LLM_PROVIDER`, and `SKIP_ENV_VAR` behavior remains. The new instance values also honor environment defaults when database configuration is disabled.
- **Events/realtime/workers**: No changed contract.
- **Public packages**: `@plane/types` expands configuration key/response metadata types without removing existing exports; `@plane/i18n` adds synchronized keys without changing existing message contracts.

## Standards Compliance

- `docs/spec/README.md` and `docs/spec/module-structure.md`: work stays in the existing admin, API, and shared-types owners; no new top-level or runtime module is introduced.
- `docs/spec/general-development.md`: preserve existing keys and upstream boundaries, validate external input server-side, use project logging, and avoid secret exposure or unrelated refactors.
- `docs/spec/frontend-development.md`: reuse existing service/store and Propel controls, maintain typed React form state, accessibility, responsive behavior, and actionable errors.
- `docs/spec/backend-development.md`: keep request orchestration in views and validation/runtime configuration in focused serializers/helpers, preserve permissions, use transactions, enforce outbound URL safety, timeouts, and sanitized logging.
- `docs/spec/shared-packages-development.md`: `@plane/types` remains dependency-free, `@plane/i18n` keeps locale keys synchronized, and both are verified with the direct admin consumer.
- `docs/spec/testing-quality.md`: CI owns focused automated evidence while the independent Tester owns only the minimal user-visible journeys.
- `docs/spec/test-environment.md`: deploy only affected services to the isolated test server and keep all credentials and private endpoints in ignored test configuration.

## Test Environment and Evidence

- CI runs affected Admin/shared-package checks and focused API unit/contract pytest. Tests use synthetic keys and mocked DNS/HTTP transports, assert request URLs and fields without printing credentials, and own failure permutations that do not need real-network injection.
- Deploy `admin` and `api` once with `scripts/test/deploy-test.ps1 -Services admin,api`. A controlled non-production compatible endpoint and synthetic token come only from ignored `.secrets/plane-test.env` or fixtures.
- An independent Tester preflights the required account, credential, fixture endpoint, and observation channel, then executes a minimal set of journeys covering Admin save/reload, authorization and secret semantics, custom/official completion behavior, and outbound endpoint policy. One journey may satisfy multiple spec scenarios.
- The Tester performs one real compatible-endpoint connectivity smoke, does not rerun CI commands, and does not inspect normal-success logs. Evidence records only sanitized observable results.
- Missing prerequisites are `blocked`; incorrect deployed behavior is `fail`. After a defect fix and redeployment, the same Tester retests only the failed journey and one necessary nearby regression.

## Migration Plan

1. Add new configuration definitions and optional allowlist parsing. Running the existing instance configuration command creates missing rows without changing current values.
2. Deploy API and admin together because the new redacted-key response metadata and form behavior are one cross-module contract.
3. On first read, derive the model list from the existing `LLM_MODEL` when `LLM_MODELS` is absent/invalid; keep the Base URL and reasoning effort empty.
4. Observe sanitized validation counts and provider error categories, not configuration values. Verify container health and both completion endpoint paths in the test environment.
5. Roll back application code to the previous release if needed. The old release ignores new rows and continues using `LLM_API_KEY`/`LLM_MODEL`; no schema rollback is required. Operators may remove optional allowlist variables after rollback. New configuration rows can remain inert.

Backup is limited to the normal instance database backup before deployment; no special data transformation is required. Rollback cannot make a model supported by the custom endpoint work through an older Plane version if that older version's fixed allowlist rejects it.

## Risks / Trade-offs

- **Compatible endpoints differ in request options** -> Omit reasoning effort when blank, allow gateway-specific values, and surface sanitized upstream errors when a gateway rejects a configured option.
- **Custom endpoint enables SSRF or credential exfiltration** -> Enforce HTTP(S), reject embedded credentials and unsafe resolution, disable redirects, revalidate before use, and require operator-only allowlists for private targets.
- **DNS can change between validation and SDK connection** -> Validate again immediately before each request and disable redirects; record the small remaining interval as residual risk rather than claiming transport pinning.
- **Redacting the key changes current admin behavior** -> Ship API and admin together, use explicit configured metadata, and preserve omitted-key semantics.
- **JSON model data can be malformed from legacy/manual edits** -> Parse fail-closed for updates and derive a compatibility catalog from `LLM_MODEL` for reads/runtime without destructive rewriting.
- **Reasoning presets evolve** -> Presets are UI conveniences, while the validated custom value keeps the backend forward-compatible.
- **Cross-module changes increase merge surface** -> Limit shared changes to types and keep provider/runtime logic within the existing API file area.

## Open Questions

- Confirm the exact model identifier exposed by the target gateway for the GPT-5.6 Sol display name during implementation/test setup; the product contract intentionally stores the endpoint's identifier rather than assuming one.
- Confirm whether the current OpenAI SDK version accepts all target gateway reasoning values through `chat.completions.create`; if its generated typing blocks a gateway-specific value while the wire protocol supports it, update the design before implementation rather than bypassing types silently.
