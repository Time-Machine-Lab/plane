## Why

Current Discord work-item notifications compress the event, task context, and metadata into a flat English message, making the subject difficult to identify and the supporting attributes hard to scan. The confirmed Discord card visual baseline provides a clearer Chinese hierarchy that should now replace the existing payload presentation without changing notification behavior.

## What Changes

- Restyle the existing `work_item.created`, `work_item.assignee_added`, and `work_item.completed` Discord messages using the single-event card defined in `docs/spec/discord-card-design.md`.
- Replace fixed English notification text with concise Chinese event titles and action descriptions while preserving user-entered task, project, and member names.
- Make the work-item identifier and name the linked card title, add a low-emphasis Plane/project source, and move supporting data into a compact property bar.
- Use the confirmed property style: icon labels plus inline-code badge values, with semantic color dots for state, priority, and time risk.
- Apply stable event colors, real event timestamps, and concise footer actions without duplicating title information.
- Restyle the God Mode Discord connection-test message with the same lightweight hierarchy so administrators preview the production visual language.
- Preserve the existing explicit Discord mention behavior and `allowed_mentions` restrictions.
- Do not add new Discord event types, scheduling, notification configuration, delivery retries, message history, or destination behavior.
- Do not add new automated test cases for this visual-only optimization. Existing test assertions may be updated only where the payload contract changes.
- During implementation, CI checks, deployment, and acceptance, do not send any message to the previously supplied Discord Webhook or test subarea. Those credentials and identifiers must not be copied into source code, fixtures, OpenSpec evidence, or configuration.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `discord-work-item-notifications`: Replace the observable card presentation for the connection test and three existing work-item events while preserving their current triggers, recipients, security, and delivery behavior.

## Impact

- **API integration:** update the Discord notification representation, event formatters, and shared payload builder in `apps/api/plane/integrations/discord.py` and directly related code.
- **Existing automated coverage:** update only payload expectations that no longer match the new structure; no new test scenarios or test harness are introduced.
- **Admin application:** no God Mode UI or configuration contract changes are required; only the message produced by the existing test action changes.
- **Compatibility:** no public Plane API, Discord configuration, event key, member mapping, or delivery contract breaks. Discord recipients receive a new presentation for the same events.
- **Data and migration:** no model, migration, stored configuration, or data backfill changes.
- **Authorization and security:** existing God Mode authorization, encrypted Webhook storage, workspace isolation, and constrained user mentions remain unchanged.
- **Verification and rollout:** generated payload inspection is sufficient acceptance for this message-format change, so no test-environment deployment or real Discord smoke is required. The API change follows the normal release rollout, and the prior Webhook and test subarea remain prohibited targets.
- **Licensing:** no licensing or entitlement change.
- **Applicable standards:** `docs/spec/general-development.md`, `docs/spec/backend-development.md`, `docs/spec/testing-quality.md`, `docs/spec/test-environment.md`, and `docs/spec/discord-card-design.md`.
