## Context

Plane already records work-item activity and computes field-level changes in the API background-task path. God Mode already exposes instance configuration through the admin application and instance configuration API. This change connects those existing boundaries to Discord's Incoming Webhook API for one configured workspace.

The requested integration is intentionally small: configuration must be manageable in God Mode, messages must be readable and able to mention explicitly mapped people, and future events must be straightforward to add. It does not need the operational characteristics of a durable notification platform. The relevant stakeholders are instance administrators who configure the integration, workspace members whose activity produces messages, and Discord channel members who consume them.

## Goals / Non-Goals

**Goals:**

- Configure one workspace and one Discord Incoming Webhook from `/god-mode/discord/`.
- Store the Webhook secret safely and let administrators manually maintain `Plane User ID -> Discord User ID` mappings.
- Deliver Discord embeds for work-item creation, newly added assignees, and the first transition into completed.
- Restrict generated mentions to the explicitly resolved recipients.
- Keep event-specific matching and formatting separate from common mapping and transport so later events are small additions.
- Preserve the success and latency characteristics of the originating work-item request by delivering asynchronously.

**Non-Goals:**

- Discord Bot users, OAuth installation, slash commands, or inbound Discord interactions.
- More than one workspace, Webhook, or channel per Plane instance.
- Automatic member discovery or identity matching.
- Assignee-removal messages.
- Retries, delivery queues beyond the existing background execution mechanism, delivery history, dead-letter handling, fallback channels, or compensation.
- QQ or WeChat delivery.

## Decisions

### 1. Reuse instance configuration and add a dedicated God Mode page

The integration will use the existing instance-configuration model and API conventions for five logical values: enabled state, selected workspace ID, encrypted Webhook URL, enabled event keys encoded as JSON, and member mappings encoded as JSON. The admin application will add `/god-mode/discord/` and a matching sidebar item with an enable toggle, workspace selector, write-only Webhook field, event checkboxes, mapping table, Save action, and Send test message action.

The mapping table will source Plane members from the selected workspace. Each row contains a member selector, the selected member's read-only Plane User ID, a manually entered Discord User ID, and a remove action. Backend validation remains authoritative and verifies workspace membership, uniqueness, identifier shape, supported event keys, and official Discord Incoming Webhook URL shape. Saving an empty Webhook field retains an already stored secret; replacing it requires submitting a new valid URL.

The Webhook value will use the repository's existing encryption facility for sensitive instance configuration. Read APIs return only a configured/not-configured indicator, never the plaintext URL.

**Alternatives considered:** a new integration database model would make multiple destinations easier later, but adds migrations and abstractions that the one-instance/one-workspace requirement does not need. Environment variables would protect the secret but would not satisfy editable God Mode configuration.

### 2. Add a thin Discord event registry at the existing activity boundary

The background activity path will call a Discord-specific registry after Plane has enough old/new state to identify the event. The registry is a map from a stable event key to a matcher/formatter. It is not a general event bus and does not change existing activity or webhook contracts.

The initial handlers are:

- `work_item.created`: matches creation in the configured workspace and resolves current assignees as recipients.
- `work_item.assignee_added`: computes `new_assignee_ids - old_assignee_ids`; it does not match removals alone and resolves only newly added users as recipients.
- `work_item.completed`: matches only a transition from a non-completed state group to the completed state group and resolves current assignees as recipients.

Each handler emits the same internal contract:

```ts
type DiscordNotification = {
  eventKey: string;
  title: string;
  description: string;
  url: string;
  color: number;
  recipientUserIds: string[];
};
```

The concrete backend language may express this as a typed Python structure, but the fields and responsibilities remain the same. Common code enriches the payload with actor, project, work-item identifier, and assignee display names where required, resolves mappings, and submits it to the transport.

Adding a future event consists of adding its stable key, one matcher/formatter registered under that key, and one God Mode event option. Configuration parsing, mapping resolution, mention policy, and transport do not change.

**Alternatives considered:** embedding Discord calls directly in each work-item view is initially shorter but couples request handling, formatting, and transport and makes each later event repeat sensitive logic. A general cross-product event bus is more flexible but exceeds this change's scope.

### 3. Use Discord embeds with a shared payload builder

One shared builder translates `DiscordNotification` plus resolved Plane context into a Discord Webhook payload. Each message uses an embed with a concise event title, work-item identifier/name, project, actor, assignee names, event-appropriate color, and the canonical Plane work-item URL. Human-readable Plane names are always retained even when a user has no Discord mapping.

Mapped recipients are rendered as `<@DISCORD_USER_ID>`. The payload sets `allowed_mentions.parse` to an empty list and `allowed_mentions.users` to the exact deduplicated mapped Discord User IDs for that event. This prevents work-item text, names, or other content from triggering role, `@everyone`, `@here`, or unintended user mentions.

**Alternatives considered:** plain text is simpler but is harder to scan and produces inconsistent formatting as events grow. Discord Block-like custom composition is unnecessary because embeds cover the required structure and links.

### 4. Make one asynchronous, bounded delivery attempt

The originating work-item operation will enqueue or invoke delivery through Plane's existing background-task mechanism after the activity data is available. The Discord transport performs exactly one HTTP POST with a short configured-in-code timeout. A successful Discord response ends the task. HTTP errors, timeouts, and network errors are logged once with the event key, relevant Plane object identifiers, and a coarse failure category; the URL, Webhook token, full payload, and other secrets are excluded.

Failure never changes or rolls back the Plane work-item operation. No retry policy, delivery record, fallback, or compensation is added. The test-message endpoint uses the same payload builder and transport synchronously enough to return accepted/failed status to God Mode, while still making only one attempt.

**Alternatives considered:** retries and durable delivery records improve reliability but require persistence, idempotency, operational UI, and retention choices that are explicitly outside the requested first version. Sending inside the work-item HTTP request would expose users to Discord latency and failures.

### 5. Keep configuration and delivery workspace-scoped

Before event matching, the integration checks that it is enabled, the event key is selected, and the activity workspace ID equals the configured workspace ID. Mapping validation and member selection are also scoped to that workspace. A workspace change requires revalidating the submitted mapping set; mappings that do not belong to the newly selected workspace are rejected rather than silently applied.

God Mode's existing instance-administrator permission checks protect all read, update, and test operations. Runtime delivery reads configuration internally and exposes no new public unauthenticated endpoint.

## Risks / Trade-offs

- **[Discord or the network is temporarily unavailable]** -> The one attempt can be lost by design; record a sanitized error so operators can diagnose recurring failures, while keeping retry infrastructure out of v1.
- **[An administrator enters the wrong Discord User ID]** -> Validate identifier shape and constrain `allowed_mentions`, but rely on the explicit mapping as the source of truth. The test action validates the Webhook, not every identity.
- **[Discord changes Webhook URL or payload rules]** -> Centralize URL validation and payload construction in the Discord integration module so compatibility changes are localized.
- **[Activity tasks are emitted more than once upstream]** -> This version has no durable deduplication and can mirror upstream duplicates; completion matching prevents repeated messages for ordinary updates while already completed.
- **[JSON configuration becomes awkward at larger scale]** -> The selected-workspace mapping is expected to remain small for v1. Move to a dedicated model only if multi-destination or large mapping requirements are approved later.
- **[Encrypted secret rotation or key loss]** -> Follow the existing instance-secret encryption lifecycle; administrators can replace the Webhook URL from God Mode if necessary.

## Migration Plan

1. Add the new instance configuration definitions and any required migration/default records with the integration disabled, no selected workspace, no enabled events, no mappings, and no Webhook value.
2. Deploy the API/background-task changes and admin UI together through the repository's normal deployment flow. Existing instances remain behaviorally unchanged until an administrator explicitly configures and enables Discord.
3. After configuration, use Send test message before enabling production events, then verify each enabled event in the configured workspace.
4. To roll back behavior without a code rollback, disable the integration in God Mode. A code rollback may leave inert configuration values in storage; they contain no active behavior and can be removed by a later explicit migration if required.

## Open Questions

None for the proposed v1 scope.
