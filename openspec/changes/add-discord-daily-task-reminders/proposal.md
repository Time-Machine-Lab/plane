## Why

Plane members currently receive Discord notifications only when individual work-item events occur, so overdue and already-started work can disappear from attention when nobody updates it. A concise daily task brief at the start of the workday gives each responsible member, and the team for unassigned work, one actionable view of tasks that should already be underway.

## What Changes

- Add `work_item.daily_reminder` as an optional Discord event in God Mode, using the existing configured workspace, Incoming Webhook, and member mappings.
- At 08:00 in the configured workspace's timezone, collect active work items whose start date is on or before the local date and whose state is neither completed nor cancelled.
- Exclude work items without a start date, drafts, triage items, archived work items, and work items in archived projects.
- Group matching work items by each current assignee and place unassigned work items in a separate group. A work item with multiple assignees appears in every applicable assignee group.
- Send one logical Chinese task brief per non-empty group. Mention the group's assignee only when an explicit Plane-to-Discord mapping exists; still send an unmapped member's brief without a mention, and never mention anyone for the unassigned group.
- Present every task using the task-brief card from `docs/spec/discord-card-design.md`, including linked identifier/name, project, priority, state, start/target dates, risk styling, and a context-sensitive reminder ending in `喵~`.
- Order tasks by overdue, due today, future due date, and no target date, then by priority. Split oversized groups across safe Discord payloads while preserving the group summary and mentioning the member only once.
- Send nothing when no work item matches the reminder conditions.
- Prevent duplicate briefs for the same workspace and local date while retaining the existing bounded, single-attempt Webhook delivery behavior. Do not add delivery retries or delivery history.

Non-goals are administrator-configurable reminder time or timezone, reminders for work without a start date, per-user reminder preferences, additional Discord destinations, retry or delivery-history infrastructure, and the separate mention/comment notification events discussed for later iterations.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `discord-work-item-notifications`: Add the configurable daily task-reminder event, workspace-local scheduling, task selection/grouping, safe brief pagination, mapped member mentions, and no-op behavior for empty results.

## Impact

- **API and background tasks:** extend the Discord integration in `apps/api` with task collection, grouping, sorting, task-brief payload generation, once-per-local-day execution protection, and a Celery Beat entry or equivalent existing scheduling hook.
- **Admin application and shared contracts:** add the daily-reminder event option to the existing God Mode Discord configuration UI and update the corresponding shared event-key type. No new configuration screen or time input is introduced.
- **Existing Discord behavior:** the saved Webhook, workspace, member mappings, constrained `allowed_mentions`, outbound URL protection, timeout, sanitized logging, and no-retry transport remain unchanged.
- **Compatibility:** existing installations do not send daily reminders unless an administrator explicitly enables the new event key. Existing event keys and API payload fields remain compatible.
- **Data and migration:** no database schema or data migration is required. The new event key is stored in the existing enabled-events configuration; the daily execution guard is transient operational state, not delivery history.
- **Authorization and isolation:** only an authorized God Mode administrator can enable the event through the existing configuration API. Collection is restricted to the configured workspace and active objects visible to the normal work-item manager.
- **Deployment and verification:** scheduling, asynchronous execution, grouping, time-boundary behavior, mention safety, and Discord limits warrant focused automated coverage. Independent Tester verification should prefer offline payload and scheduled-task inspection; a test-environment deployment or real Discord call is used only when necessary and explicitly authorized.
- **Licensing:** no new entitlement or licensing tier is introduced; the reminder follows the existing Discord God Mode availability.
- **Applicable standards:** `docs/spec/general-development.md`, `docs/spec/backend-development.md`, `docs/spec/frontend-development.md`, `docs/spec/module-structure.md`, `docs/spec/testing-quality.md`, `docs/spec/test-environment.md`, and `docs/spec/discord-card-design.md`.
