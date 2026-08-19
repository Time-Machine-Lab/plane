## MODIFIED Requirements

### Requirement: God Mode administrators can configure one Discord destination

The system SHALL provide an authorized God Mode Discord configuration page that lets an instance administrator enable or disable the integration, select exactly one Plane workspace, enter a Discord Incoming Webhook URL, and choose any of the supported event keys. The supported event keys SHALL include `work_item.created`, `work_item.assignee_added`, `work_item.completed`, and `work_item.daily_reminder`.

#### Scenario: Administrator saves a valid configuration

- **WHEN** an authorized instance administrator saves a valid Webhook URL, one workspace, and a set of enabled events
- **THEN** the system stores the configuration and uses it for subsequent matching events and scheduled reminders in that workspace

#### Scenario: Integration is disabled

- **WHEN** an administrator saves the Discord integration as disabled
- **THEN** the system sends no Discord work-item notifications or daily task reminders until it is enabled again

#### Scenario: Unsupported or unselected event occurs

- **WHEN** a work-item activity or scheduled reminder does not match an enabled supported event key
- **THEN** the system sends no Discord notification for that activity or reminder

#### Scenario: Unauthorized user accesses Discord configuration

- **WHEN** a user without God Mode instance-administrator authorization attempts to read, change, or test the Discord configuration
- **THEN** the system rejects the operation without exposing or changing the configuration

## ADDED Requirements

### Requirement: Daily task reminders run once in the workspace morning

When the Discord integration and `work_item.daily_reminder` event are enabled, the system SHALL generate daily task reminders once per local calendar date during the 08:00 hour of the configured workspace's timezone. The system SHALL use the workspace timezone without adding a separate reminder-time or reminder-timezone setting.

#### Scenario: Scheduler reaches the configured workspace morning

- **WHEN** the scheduler first runs at or after 08:00 and before 09:00 on a local date for the configured workspace
- **THEN** the system evaluates and, when applicable, sends that date's task reminders for the workspace

#### Scenario: Scheduler runs again on the same local date

- **WHEN** another scheduler invocation occurs after reminder processing has been claimed for the same workspace and local date
- **THEN** the system sends no additional daily reminder payload for that workspace and date

#### Scenario: Scheduler runs outside the reminder window

- **WHEN** the scheduler runs outside the configured workspace's local 08:00 hour
- **THEN** the system does not process a daily task reminder

#### Scenario: Daily reminder event is not enabled

- **WHEN** the integration is disabled or `work_item.daily_reminder` is not selected
- **THEN** scheduled invocations send no daily task reminder

### Requirement: Daily reminders include active work that should have started

For the configured workspace's local date, the system SHALL include work items whose start date is on or before that date and whose state group is neither completed nor cancelled. The system MUST exclude work items without a start date, drafts, triage items, archived work items, work items in archived projects, and work items from every other workspace.

#### Scenario: Work item started before today

- **WHEN** an active non-completed and non-cancelled work item has a start date before the workspace's local date
- **THEN** the work item is included in the daily reminder collection

#### Scenario: Work item starts today

- **WHEN** an active non-completed and non-cancelled work item has a start date equal to the workspace's local date
- **THEN** the work item is included in the daily reminder collection

#### Scenario: Work item is not eligible

- **WHEN** a work item starts after the local date, has no start date, is completed, is cancelled, is a draft or triage item, is archived, belongs to an archived project, or belongs to another workspace
- **THEN** the work item is excluded from the daily reminder collection

#### Scenario: No work item is eligible

- **WHEN** the daily reminder collection contains no eligible work item
- **THEN** the system sends no Discord message for that local date

### Requirement: Daily reminders are grouped by assignee and unassigned work

The system SHALL create one logical task brief for every assignee who owns at least one eligible work item and one separate logical brief for eligible work items with no assignee. A work item with multiple assignees SHALL appear in every assignee's brief. The system SHALL create an assignee brief even when that member has no Discord mapping.

#### Scenario: Eligible work belongs to multiple assignees

- **WHEN** an eligible work item has two or more assignees
- **THEN** the work item appears once in each assignee's logical brief

#### Scenario: Eligible work has no assignee

- **WHEN** an eligible work item has no assignee
- **THEN** the work item appears once in the unassigned logical brief and in no member brief

#### Scenario: Assignee has no Discord mapping

- **WHEN** an assignee has eligible work but no saved Plane-to-Discord mapping
- **THEN** the system sends that member's brief using the Plane display name without generating a Discord mention

### Requirement: Daily reminder recipients are mentioned safely and only once

For an assignee group with a saved mapping, the system SHALL place that assignee's `<@DISCORD_USER_ID>` mention only in the first Discord payload of the group and SHALL set `allowed_mentions.users` to exactly that mapped Discord User ID. Continuation payloads, unmapped member groups, and the unassigned group MUST permit no user, role, `@everyone`, or `@here` mention.

#### Scenario: Mapped assignee receives a brief

- **WHEN** a logical brief belongs to an assignee with a saved Discord mapping
- **THEN** only the first payload mentions that mapped user and no payload permits any other mention

#### Scenario: Group must not mention a user

- **WHEN** a logical brief belongs to an unmapped assignee or contains unassigned work
- **THEN** every payload for that group contains no generated mention and has an empty explicit user allowlist

### Requirement: Daily task briefs use the approved Chinese card hierarchy

Each logical brief SHALL follow the task-brief card in `docs/spec/discord-card-design.md`. Its group summary SHALL identify the assignee or unassigned group, local date, total task count, overdue count, due-today count, and remaining in-progress count. Each work item SHALL use a separate Embed with a linked `{identifier} · {name}` title and SHALL display its project, priority, state, and task time from start date through target date or `未设置`. Fixed presentation text SHALL be Chinese, while user-entered names remain unchanged.

Each work-item Embed SHALL use red risk presentation when overdue, yellow when due today, and blue for other eligible work. It SHALL end with a context-sensitive reminder in `footer.text` whose final characters are `喵~`; the unassigned reminder SHALL ask the team to assign or claim the work instead of addressing an owner.

#### Scenario: Assigned task is overdue

- **WHEN** an assigned eligible work item's target date is before the workspace's local date
- **THEN** its Embed uses overdue risk presentation, states how overdue it is, contains all required task information, and ends with an owner-oriented overdue reminder followed by `喵~`

#### Scenario: Assigned task is due today

- **WHEN** an assigned eligible work item's target date equals the workspace's local date
- **THEN** its Embed uses due-today presentation, contains all required task information, and ends with an owner-oriented due-today reminder followed by `喵~`

#### Scenario: Assigned task has a future or missing target date

- **WHEN** an assigned eligible work item's target date is after the local date or is not set
- **THEN** its Embed uses normal pending presentation, displays the future date or `未设置`, and ends with an appropriate progress reminder followed by `喵~`

#### Scenario: Task is unassigned

- **WHEN** an eligible work item belongs to the unassigned group
- **THEN** its Embed contains the same required task information and ends with a reminder to assign or claim the work followed by `喵~`

### Requirement: Tasks are ordered by urgency within each brief

The system SHALL order each group's work items first by target-date risk in this sequence: overdue, due today, future target date, and no target date. Within the same risk category, the system SHALL order work by priority in this sequence: urgent, high, medium, low, and none, using a deterministic final tie-breaker.

#### Scenario: Group contains mixed dates and priorities

- **WHEN** a logical brief contains work items across multiple target-date and priority categories
- **THEN** the rendered task sequence follows target-date risk first, priority second, and remains deterministic for otherwise equal work items

### Requirement: Oversized briefs are split without losing tasks or repeating mentions

The system MUST keep every Discord payload within the platform's supported Embed-count, per-field, per-Embed, and aggregate character limits. When one group cannot fit in one payload, the system SHALL split it into the minimum ordered sequence of continuation payloads needed to include every eligible work item. Every payload SHALL identify the same group and its part number, and only the first payload SHALL contain the mapped assignee mention.

#### Scenario: Group fits in one Discord payload

- **WHEN** every task Embed and the group summary fit within one supported payload
- **THEN** the system sends one payload containing every task in the determined order

#### Scenario: Group exceeds a Discord payload limit

- **WHEN** adding another task Embed would exceed a Discord payload limit
- **THEN** the system starts a continuation payload, preserves task order and group identity, includes every task exactly once, and does not repeat the mapped mention

### Requirement: Reminder delivery remains single-attempt and non-durable

The system SHALL claim the configured workspace and local date before beginning reminder delivery, then make one bounded Webhook attempt for each generated payload. A failed payload SHALL produce a sanitized error without exposing the Webhook URL or task content and SHALL NOT be retried, recorded in delivery history, or cause the same date's reminder to be regenerated by a later scheduler invocation.

#### Scenario: One reminder payload fails

- **WHEN** Discord rejects a reminder payload, the request times out, or a network error occurs
- **THEN** the system records one sanitized failure for that payload, performs no retry, continues independently with any remaining generated payloads, and does not resend the day's brief later

#### Scenario: Reminder payloads succeed

- **WHEN** Discord accepts every generated reminder payload
- **THEN** the daily reminder ends successfully and no later scheduler invocation sends another brief for the same workspace and local date
