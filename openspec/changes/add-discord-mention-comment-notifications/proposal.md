## Why

Plane's Discord integration reports work-item lifecycle changes and is adding scheduled task briefs, but it does not yet surface the conversations that need a person's attention. Adding recipient-aware comment and mention notifications lets mapped members respond promptly while avoiding duplicate cards when a work-item assignee is also mentioned in the same comment.

## What Changes

- Add two opt-in Discord event choices in God Mode: `user.mentioned` ("提到了你") and `work_item.comment_activity` ("任务收到新评论"), using the existing configured workspace, Incoming Webhook, and Plane-to-Discord member mappings.
- Send a Chinese single-event comment card when a work-item comment is created, mentioning every mapped assignee who was responsible at event time except the comment actor.
- Classify newly mentioned comment recipients by responsibility: a mentioned current assignee remains a comment recipient and does not receive a second mention card; a mentioned non-assignee receives a mention card. A mixed comment can produce at most one card per event type, with recipients grouped and deduplicated.
- When a comment edit adds mentions, notify only the newly mentioned mapped recipients: newly mentioned assignees receive a comment-update card and newly mentioned non-assignees receive a mention card. Other assignees are not notified again.
- Send a Chinese mention card for new mentions in a work-item description, regardless of assignee status, excluding the actor and unmapped users.
- Send a Chinese mention card for new mentions introduced by direct creation or editing of a public Plane Page. Include the actor, Page name, a bounded plain-text excerpt around the mention, and a link to the Page. Do not notify for private Pages, Page duplication, imports, system synchronization, or version restoration.
- Use the approved single-event hierarchy in `docs/spec/discord-card-design.md`, constrain Discord mentions to explicit mapped recipients, and make one bounded Webhook attempt without retry or delivery history.
- Keep the daily task reminder behavior unchanged. This change depends on `add-discord-daily-task-reminders` being completed and archived first so the final event allowlist and main capability specification contain all events.

Non-goals are Discord direct messages, per-member notification preferences, notifications for unmapped recipients, private Page mentions, exact Page-block deep links, project updates or project overview mentions, comments outside work items, notification retries or history, and changes to the daily reminder schedule or grouping.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `discord-work-item-notifications`: Extend the configured Discord destination with recipient-aware work-item comment notifications and new-mention notifications from work-item descriptions, work-item comments, and public Plane Pages.

## Impact

- **API and background tasks:** extend the existing Discord single-event pipeline and work-item activity notification path; share mention-diff and safe excerpt logic; pass actor and project context into Page transaction processing; dispatch only after a newly inserted Page mention transaction is known.
- **Page behavior:** reuse existing `PageLog` mention transaction identity for deduplication. Direct public Page creation and edits can emit mention notifications; private or non-interactive Page operations remain silent. No database schema migration is expected.
- **Admin application and shared contracts:** add two localized event options and extend the shared Discord event-key type. Existing saved configurations remain opt-in and compatible.
- **Existing Discord behavior:** preserve the encrypted Webhook, selected workspace, manual mappings, constrained `allowed_mentions`, bounded transport, sanitized errors, and no-retry policy. Daily briefs may still share the same Webhook with immediate notifications; no new rate-limit queue is introduced.
- **Authorization and isolation:** only events from the configured workspace are eligible. Work-item and Page source access continues to use their existing authorization paths; private Pages are explicitly excluded to avoid publishing protected content to a shared Discord channel.
- **Compatibility and sequencing:** there is no breaking API behavior. Implementation begins from the archived result of `add-discord-daily-task-reminders`, and the supported-event requirement must retain `work_item.daily_reminder` alongside the two new keys.
- **Deployment and verification:** the behavior can primarily be verified with focused automated and offline payload checks; deploy affected services only if independent verification cannot establish the event routing and Page transaction behavior locally.
- **Licensing:** no new entitlement or licensing tier is introduced; the events follow the existing Discord God Mode availability.
- **Applicable standards:** `docs/spec/general-development.md`, `docs/spec/backend-development.md`, `docs/spec/frontend-development.md`, `docs/spec/module-structure.md`, `docs/spec/testing-quality.md`, `docs/spec/test-environment.md`, and `docs/spec/discord-card-design.md`.
