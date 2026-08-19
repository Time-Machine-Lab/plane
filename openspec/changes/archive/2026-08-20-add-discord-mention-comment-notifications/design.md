## Context

The existing Discord integration has one instance-level destination, one configured workspace, explicit Plane-to-Discord mappings, a typed single-event card contract, safe mention construction, and a bounded no-retry Webhook transport. Work-item activity processing already compares old and new rich text to create Plane mention notifications. Plane Pages separately record embedded components in `PageLog`; a user mention is identifiable by its stable mention-node transaction, but the current Page transaction task does not carry the editing actor or project route context and does not send notifications.

The prerequisite `add-discord-daily-task-reminders` change adds a scheduled batch path and the `work_item.daily_reminder` configuration key. This change must begin after that change is completed and archived. It extends only the immediate single-event path and retains the scheduled reminder's separate representation and collector.

## Goals / Non-Goals

**Goals:**

- Notify mapped assignees about newly created work-item comments without notifying the actor.
- Resolve overlap deterministically: comment mentions of assignees remain comment notifications, while comment mentions of non-assignees become mention notifications.
- Notify only newly mentioned recipients when comments or work-item descriptions are edited.
- Add safe, deduplicated mention notifications for direct edits to public project-linked Plane Pages.
- Produce clear Chinese cards with safe excerpts, accurate work-item/comment/Page links, and exact mapped mention allowlists.
- Reuse the existing configuration, mappings, single-attempt transport, and approved card standard.

**Non-Goals:**

- Discord DMs, multiple Webhooks, per-user preferences, retries, delivery history, or a general notification event bus.
- Private Page messages, global project-update or overview mentions, non-work-item comments, or Page block-level deep links.
- Notifications caused by Page duplication, import, system synchronization, or version restoration.
- Changes to daily reminder collection, schedule, grouping, cards, or execution guard.

## Decisions

### 1. Classify recipients before resolving Discord mappings

A small interaction classifier will operate on Plane user IDs and the event-time assignee snapshot. It will not use Discord mappings to decide semantics. For comment creation:

```text
comment recipients = assignees at event time - actor
mention recipients = newly mentioned users - assignees at event time - actor
```

For comment editing:

```text
comment-update recipients = newly mentioned users intersect current event-time assignees - actor
mention recipients        = newly mentioned users - current event-time assignees - actor
```

Work-item description and Plane Page mentions always use the mention classification, regardless of unrelated assignee status. Each set is deduplicated before event enablement and mapping resolution. An assignee classified as a comment recipient never falls back to `user.mentioned` when the comment event is disabled.

The comment-creation path captures assignee IDs when the activity is scheduled rather than querying them only when Discord delivery executes. This keeps recipients consistent if assignments change before the background task runs.

**Alternatives considered:** sending both event types to a mentioned assignee is literal but noisy. Suppressing the entire comment card whenever any assignee is mentioned would prevent other responsible assignees from learning about the comment. Classifying after mapping would make event meaning depend on administrator configuration.

### 2. Share neutral rich-text mention and excerpt utilities

Mention extraction and old/new diffing will live in a neutral backend helper used by Plane's existing notification task and Discord interaction handling. It parses only validated `mention-component` nodes with `entity_name="user_mention"`, returns stable Plane user IDs, and treats malformed content as having no eligible mention rather than exposing parser failures to the source operation.

The same helper family will create bounded excerpts. It replaces user mention nodes with resolved Plane display names, converts supported block structure to plain text, normalizes whitespace, strips unsupported markup and storage details, escapes Discord Markdown, and truncates to at most 300 characters with an ellipsis. For a description or Page, it prefers the containing block around the newly added mention; for a comment, it uses the bounded comment body. Multiple eligible recipients from the same source operation share one card rather than duplicating the excerpt.

**Alternatives considered:** importing parsing functions from `notification_task.py` would create the wrong dependency direction. Using `comment_stripped` or `description_stripped` alone loses custom mention-node display text and does not reliably select Page context around the mention.

### 3. Extend the immediate Discord notification contexts, not the daily brief model

The existing single-event `DiscordNotification` contract remains the presentation boundary for `user.mentioned` and `work_item.comment_activity`. Source-specific contexts provide actor, recipient Plane IDs, source type, work item or Page identity, excerpt, timestamp, and URL. Common builders apply the mention and comment themes already defined in `docs/spec/discord-card-design.md`.

Work-item comment URLs use the canonical work-item URL plus `#comment-{comment_id}`. Description mentions link to the work item. Plane Page URLs use the configured application base URL and the project context captured by the Page update request; they link to the Page without claiming exact block navigation.

`work_item.daily_reminder` remains outside the immediate event registry and continues to use its separate task-brief representation. The two paths share only stable low-level helpers such as escaping, mappings, explicit allowed mentions, Discord limits, and transport.

**Alternatives considered:** expanding the daily task-brief model to represent interactions would mix batch and single-event constraints. Creating a general product-wide event bus is unnecessary for three known rich-text sources.

### 4. Use PageLog transaction creation as the Page mention idempotency boundary

Direct Page creation and update entry points will pass `actor_id`, `project_id`, and an explicit eligible operation kind to Page transaction processing. For each newly added user mention node, the task will atomically create or claim the `PageLog` row identified by `page + transaction`. Discord dispatch occurs only for the invocation that successfully creates the new transaction record. Repeated autosaves or duplicate task invocations therefore do not resend the mention.

Before dispatch, the task verifies that the Page still belongs to the configured workspace, is public, remains linked through the captured project context, and that the actor and mentioned users are valid workspace members. Calls originating from duplicate, import, synchronization, or version-restore flows omit notification eligibility and continue to maintain Page data without sending Discord messages.

No schema migration is required because the actor and project are transient event context and the existing unique Page/transaction identity provides the durable deduplication boundary.

**Alternatives considered:** adding delivery state to `PageLog` would create a migration and durable delivery history. Diffing the full Page independently in Discord code would duplicate Page transaction semantics and race under repeated saves.

### 5. Keep the shared-channel privacy boundary explicit

Discord Incoming Webhooks publish to one channel and cannot privately address a mapped member. Private Plane Pages are therefore excluded entirely: no title, excerpt, actor, or link is sent. Public project-linked Pages use the same configured-workspace guard as work items. Administrators remain responsible for choosing a Discord channel appropriate for the selected workspace's public project content.

All recipient mentions are emitted only in top-level `content`; embeds contain display names and safe excerpts but no generated Discord mention syntax. `allowed_mentions.parse` remains empty and `allowed_mentions.users` contains exactly the mapped IDs for that card. If mapping removes every classified recipient, the card is not sent.

**Alternatives considered:** sending a generic private-page alert still reveals that a Page and interaction exist and gives a link most channel members cannot open. A Webhook cannot enforce Plane Page authorization within Discord.

### 6. Extend configuration only after the reminder change is archived

The final supported-event union is:

```text
work_item.created
work_item.assignee_added
work_item.completed
work_item.daily_reminder
user.mentioned
work_item.comment_activity
```

God Mode presents localized "提到了你" and "任务收到新评论" options. `user.mentioned` covers work-item descriptions, comment mentions of non-assignees, and public Plane Pages. `work_item.comment_activity` covers new comments to assignees and comment edits that newly mention assignees. Existing configuration JSON remains valid and both new events are disabled until selected.

This change will be rebased or started from the archived daily-reminder result rather than implemented concurrently against the older allowlist. That sequencing avoids losing the reminder event from backend validation, shared TypeScript types, UI options, tests, or the main spec.

## Risks / Trade-offs

- **[A comment produces two cards]** -> Allow at most one comment card and one mention card, only when their independently classified mapped recipient sets are non-empty.
- **[Assignments change around comment creation]** -> Capture the assignee snapshot at event time and use it consistently for routing.
- **[Page autosave or task duplication repeats notifications]** -> Dispatch only from the successful atomic creation of a new Page mention transaction.
- **[A private Page leaks into a shared channel]** -> Recheck Page access immediately before dispatch and send nothing for private Pages.
- **[A copied or restored Page contains many mentions]** -> Carry an explicit operation kind and permit notification only for direct user creation or editing.
- **[Rich content triggers unintended Discord formatting or mentions]** -> Convert through the shared safe excerpt helper and retain an exact empty-parse mention allowlist.
- **[Daily briefs and interactions hit the same Webhook at 08:00]** -> Keep each delivery bounded and independent; accept rate-limit loss under the confirmed no-retry policy rather than adding a queue in this change.
- **[Page links do not jump to the precise mention]** -> Link to the containing Page and state no block-anchor guarantee; deep linking remains future work.

## Migration Plan

1. Complete and archive `add-discord-daily-task-reminders`, then begin this implementation from that resulting main spec and code.
2. Release backend interaction handling, Page transaction context, shared event types, and God Mode options together. No schema or data migration is expected.
3. Existing installations remain unchanged because saved event arrays do not contain the two new keys.
4. Administrators opt in to either event independently. Roll back operationally by clearing those event selections; a code rollback filters the unknown keys as unsupported without affecting existing Discord configuration.

## Open Questions

None for the confirmed scope.
