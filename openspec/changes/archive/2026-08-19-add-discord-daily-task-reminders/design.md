## Context

The existing Discord integration stores one selected workspace, one encrypted Incoming Webhook, enabled event keys, and explicit Plane-to-Discord member mappings. Work-item activity handlers produce single-event notifications, a shared payload builder constrains mentions, and the transport performs one bounded Webhook attempt without retry or delivery history.

Daily reminders differ from those event-driven notifications in three ways: they start from a schedule rather than one activity, collect many work items at once, and can exceed one Discord payload. Plane already has Celery Beat, Redis-backed cache, workspace timezones, and an approved task-brief card in `docs/spec/discord-card-design.md`. This change extends those existing boundaries without turning Discord delivery into a general scheduler or durable notification system.

## Goals / Non-Goals

**Goals:**

- Generate a daily 08:00 task brief for the one workspace already selected in God Mode.
- Select active work that started on or before the workspace-local date and group it by every assignee plus an unassigned group.
- Render one task per Embed with clear Chinese hierarchy, task metadata, risk styling, links, and reminders ending in `喵~`.
- Mention only the mapped owner of a group and only once, even when the group is split across payloads.
- Keep payloads inside Discord limits without dropping tasks.
- Prevent duplicate daily processing while preserving the existing no-retry, no-history delivery policy.

**Non-Goals:**

- Configurable send time, per-member timezone, or per-member opt-out.
- Reminders for work items without a start date.
- A persistent delivery ledger, retry queue, catch-up job after the 08:00 hour, or exactly-once delivery guarantee across Redis data loss.
- Multiple workspaces, Webhooks, or channels per instance.
- Mention and comment event notifications.
- Reworking the existing single-event card formatters.

## Decisions

### 1. Add a scheduled collector beside the event registry

`work_item.daily_reminder` will be a supported configuration key but not an activity-registry handler. A dedicated Celery task will own the scheduled flow:

```text
Celery Beat tick
  -> load Discord configuration
  -> resolve configured workspace and local time
  -> verify enabled + daily event + local 08:00 hour
  -> claim workspace/date execution key
  -> collect and group eligible work items
  -> build bounded task-brief payloads
  -> send each payload once
```

The Beat entry will run at a small fixed interval, such as every five minutes, because the configured workspace can use any supported timezone, including non-whole-hour offsets. Only ticks in the workspace's local 08:00 hour can claim the date. The first eligible tick claims it, so ordinary scheduler duplication or delay within that hour does not duplicate messages.

This scheduled collector will live in a Discord-focused background-task module and call cohesive integration helpers for selection, grouping, formatting, and transport. It will not add a synthetic work-item activity or force batch behavior into the existing single-event registry.

**Alternative considered:** one fixed UTC cron cannot represent every workspace timezone and daylight-saving transition. A database-created per-workspace periodic task would make the time explicit but adds lifecycle synchronization for a single configured workspace.

### 2. Use a transient workspace/date claim before outbound delivery

The collector will atomically add a namespaced cache key containing the configured workspace ID and local ISO date with a bounded expiry beyond the next local reminder window. Only the invocation that creates the key proceeds. The key is claimed before querying or sending so that a partial Webhook failure cannot cause later Beat ticks to retry already attempted payloads.

This is an execution/idempotency guard, not delivery history: it stores no recipient, task, content, response, or Webhook data and expires automatically. If the cache cannot provide an atomic claim, the invocation sends nothing and logs a sanitized operational failure. Loss of transient cache state can theoretically allow a duplicate; a database ledger is deliberately outside this scope.

**Alternative considered:** storing `last_sent_date` in instance configuration would survive cache eviction but introduces durable delivery state, concurrent write coordination, and a migration/rollout contract inconsistent with the requested lightweight behavior.

### 3. Evaluate dates in the configured workspace timezone

The collector converts the current aware timestamp to the selected workspace's IANA timezone and derives one local date. That same date drives the 08:00 eligibility check, `start_date <= local_date` filter, due-risk classification, displayed summary date, and cache key. It does not depend on the server timezone, an administrator's timezone, or an assignee's timezone.

The work-item query uses the normal active manager and explicit filters for the configured workspace, non-null start date on or before the local date, and state groups other than completed or cancelled. It uses `select_related`/`prefetch_related` for project, state, and assignees so formatting does not issue a query per task. Normal manager behavior excludes drafts, triage, archived work, and archived projects; tests pin those assumptions at the reminder boundary.

**Alternative considered:** using UTC's calendar date is simpler but produces incorrect inclusion and due status around local midnight. Per-assignee dates would fragment one workspace brief and require new configuration.

### 4. Group in memory after one workspace-scoped query

Each eligible work item is added once to every current assignee's group. Items without assignees are added once to a distinct unassigned group. Assignee group identity uses the immutable Plane user ID; display names are presentation only. This deliberately duplicates a multi-assignee task across member briefs so each person receives a complete view of their responsibilities.

Within each group, a stable sort key contains:

1. Target-date category: overdue, today, future, missing.
2. Priority rank: urgent, high, medium, low, none.
3. Target date where present.
4. Project identifier and work-item sequence ID as deterministic tie-breakers.

No group is produced for an assignee without eligible work, and an empty overall result produces no payload.

### 5. Introduce a task-brief model instead of expanding the single-event contract

The existing `DiscordNotification` intentionally supports a compact single-event card with at most three fields. A separate typed task-brief representation will model group identity, summary counts, mapped recipient, local date, ordered task presentation, and generated payload parts. It will reuse the existing canonical work-item URL, escaping, badge, member-mapping resolution, mention policy, and Webhook transport helpers where their contracts fit.

Each task becomes one Embed following `docs/spec/discord-card-design.md`:

- `author.name`: `Plane · {project}`.
- Linked title: `{identifier} · {name}`.
- Risk line: overdue days, due today, or normal progress context.
- Fields: priority, state, and task time (`start date -> target date/未设置`).
- Embed color: red for overdue, yellow for due today, blue otherwise.
- Footer: an assigned-owner or unassigned reminder ending exactly in `喵~`.

User-entered names are escaped and truncated at the presentation boundary. Fixed copy is Chinese. Scheduled links use the existing application base URL settings because there is no originating HTTP request.

**Alternative considered:** representing all tasks as fields in one Embed is more compact but violates the approved card hierarchy, becomes hard to scan, and reaches field/value limits unpredictably.

### 6. Pack ordered task Embeds against Discord limits

The builder will centralize Discord's relevant limits: Embeds per message, title/description/field/footer limits, and aggregate Embed characters. It greedily adds already bounded task Embeds in sorted order until the next Embed would exceed a limit, then starts a continuation payload. This produces the minimum number of payloads for the chosen Embed representations and never silently drops a task.

Every payload identifies the group and `part/total`; the first contains the full summary and the mapped top-level mention when available. Continuations repeat enough group context for channel readability but use empty `content` and empty `allowed_mentions.users`. The unassigned and unmapped paths always use an empty allowlist. Each payload is sent independently once; one failure does not prevent attempts for later already-generated payloads.

**Alternative considered:** truncating the task list and linking to Plane avoids pagination but violates the requirement that every eligible task and its key information appear in the brief.

### 7. Extend the existing event configuration without new settings

The shared event-key type, backend allowlist, and God Mode event options will include `work_item.daily_reminder`. Existing saved JSON remains valid and does not contain the new key, so reminders are opt-in. The UI describes the fixed 08:00 schedule using the selected workspace's timezone; it adds no time picker, timezone selector, API endpoint, secret, or model.

## Risks / Trade-offs

- **[Redis state is lost after a brief is sent]** -> A duplicate is possible because the guard is intentionally transient; keep the key namespaced and long-lived enough for normal operations, while avoiding durable delivery history.
- **[Scheduler is unavailable for the entire local 08:00 hour]** -> That date's reminder is missed; no catch-up or retry is added in this lightweight version.
- **[A group contains many tasks]** -> Build bounded Embeds and split into ordered continuation payloads, mentioning the owner only once.
- **[One payload fails among several]** -> Log only sanitized identifiers and failure category, continue remaining single attempts, and retain the date claim so no accidental retry occurs.
- **[The query grows with a very large workspace]** -> Restrict it to one configured workspace and eligible indexed relations, eagerly load formatting data, and avoid N+1 queries; dedicated batching can be proposed if real scale requires it.
- **[Date presentation differs from a member's personal timezone]** -> Use the workspace timezone consistently and state it in God Mode because the brief represents shared workspace planning.
- **[Fixed playful copy is not suitable for every instance]** -> Treat Chinese `喵~` reminders as confirmed scope; template or language configuration remains a separate change.

## Migration Plan

1. Release the backend support, scheduled task, shared event-key contract, and God Mode option together. No schema or data migration is required.
2. Existing instances remain unchanged because their enabled-event JSON does not contain `work_item.daily_reminder`.
3. An administrator opts in by selecting the event and saving the existing Discord configuration.
4. Roll back operationally by disabling the event. A code rollback leaves the unknown saved key inert because the previous backend filters unsupported event keys; administrators can save the configuration again to remove it.

## Open Questions

None for the confirmed scope.
