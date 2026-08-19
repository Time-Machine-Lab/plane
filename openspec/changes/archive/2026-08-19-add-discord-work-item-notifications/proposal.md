## Why

Plane users currently need to watch the product directly to learn when work items are created, assigned, or completed. A lightweight Discord Incoming Webhook integration lets an instance administrator send those key events to an existing Discord channel and mention the responsible people without introducing a bot, OAuth flow, or delivery subsystem.

## What Changes

- Add a God Mode Discord configuration page where an instance administrator can enable the integration, select one Plane workspace, enter an encrypted-at-rest Discord Webhook URL, choose enabled events, and manage explicit Plane-user-to-Discord-user ID mappings.
- Add a test-message action so the administrator can validate the saved Webhook and target channel.
- Send formatted Discord embed messages with links to the affected Plane work item for these initial events:
  - `work_item.created`
  - `work_item.assignee_added`
  - `work_item.completed`
- Mention mapped current assignees when a work item is created or completed, and mention only newly added mapped assignees when assignees are added. Show unmapped assignees by Plane display name without mentioning them.
- Add a small event registry and normalized Discord notification contract so future event handlers can be added without changing member mapping or Webhook delivery behavior.
- Perform one asynchronous delivery attempt with a bounded HTTP timeout and sanitized error logging. Do not retry or retain delivery history.
- Restrict all configuration and test-message operations to authorized God Mode instance administrators and isolate notifications to the configured workspace.

Non-goals for this change are Discord Bot or OAuth support, multiple workspace or Webhook destinations, inbound Discord actions, assignee-removal notifications, automatic retries, delivery history, fallback delivery, compensation logic, and QQ or WeChat integration.

## Capabilities

### New Capabilities

- `discord-work-item-notifications`: Instance-level Discord Webhook configuration, manual member mapping, test-message delivery, and selected work-item event notifications with controlled user mentions.

### Modified Capabilities

None.

## Impact

- **Admin application:** add the `/god-mode/discord/` route, sidebar entry, configuration form, event controls, member mapping table, save behavior, and test-message action in `apps/admin`.
- **API and background processing:** add authorized configuration endpoints and validation, encrypted secret handling, event matching/formatting, member resolution, and one-attempt Webhook delivery in `apps/api` using existing activity and work-item update paths.
- **Instance configuration:** add keys for enabled state, selected workspace, encrypted Webhook URL, enabled event keys, and Plane-to-Discord user mappings. Existing installations remain disabled until explicitly configured.
- **Compatibility and migration:** no breaking API behavior is introduced. Any schema/configuration migration required for new instance settings must preserve existing instances and default the integration to disabled.
- **Authorization and security:** God Mode authorization applies to reading or changing configuration and sending a test message. The Webhook secret must not be returned in plaintext after storage or written to logs; Discord mentions are limited through explicit `allowed_mentions.users` values derived from configured mappings.
- **Dependencies and external systems:** outbound delivery uses Discord's Incoming Webhook HTTP API. No Discord SDK, Bot token, OAuth application, or new durable queue is required.
- **Deployment and acceptance:** the runtime change follows the repository's single `scripts/test/deploy-test.ps1` deployment path, followed by independent Tester acceptance against the scenarios in this change.
- **Licensing:** this is an instance administration capability and must follow the repository's existing God Mode and instance-configuration availability patterns; it does not introduce a new licensing tier or entitlement.
- **Applicable standards:** `docs/spec/general-development.md`, `docs/spec/frontend-development.md`, `docs/spec/backend-development.md`, `docs/spec/module-structure.md`, `docs/spec/testing-quality.md`, and `docs/spec/test-environment.md`.
