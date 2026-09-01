## Purpose

Define the expected behavior for Plane's lightweight Discord Incoming Webhook integration for work-item notifications, including administrator configuration, explicit member mapping, controlled user mentions, and single-attempt outbound delivery.

## Requirements

### Requirement: God Mode administrators can configure one Discord destination

The system SHALL provide an authorized God Mode Discord configuration page that lets an instance administrator enable or disable the integration, select exactly one Plane workspace, enter a Discord Incoming Webhook URL, and choose any of the supported event keys. After the prerequisite daily-reminder change is archived, the supported event keys SHALL include `work_item.created`, `work_item.assignee_added`, `work_item.completed`, `work_item.daily_reminder`, `user.mentioned`, and `work_item.comment_activity`.

#### Scenario: Administrator saves a valid configuration

- **WHEN** an authorized instance administrator saves a valid Webhook URL, one workspace, and a set of enabled events
- **THEN** the system stores the configuration and uses it for subsequent matching events and scheduled reminders in that workspace

#### Scenario: Integration is disabled

- **WHEN** an administrator saves the Discord integration as disabled
- **THEN** the system sends no Discord work-item, Plane Page, mention, comment, or daily reminder notification until it is enabled again

#### Scenario: Unsupported or unselected event occurs

- **WHEN** an activity or scheduled reminder does not match an enabled supported event key
- **THEN** the system sends no Discord notification for that activity or reminder

#### Scenario: Unauthorized user accesses Discord configuration

- **WHEN** a user without God Mode instance-administrator authorization attempts to read, change, or test the Discord configuration
- **THEN** the system rejects the operation without exposing or changing the configuration

### Requirement: Discord credentials and configuration input are protected

The system MUST store the Discord Webhook URL encrypted at rest, MUST NOT return the stored URL in plaintext after it has been saved, and MUST NOT include it in application logs. The system SHALL validate that a submitted URL is a supported Discord Incoming Webhook URL before saving or testing it.

#### Scenario: Saved Webhook is redisplayed

- **WHEN** an authorized administrator opens a configuration that already has a Webhook URL
- **THEN** the page indicates that a Webhook is configured without receiving or displaying the plaintext secret

#### Scenario: Administrator retains an existing Webhook

- **WHEN** an authorized administrator saves other configuration changes without entering a replacement Webhook URL
- **THEN** the system retains the existing encrypted Webhook URL

#### Scenario: Invalid Webhook URL is submitted

- **WHEN** an administrator attempts to save or test a value that is not a supported Discord Incoming Webhook URL
- **THEN** the system rejects the operation with a validation error and does not attempt outbound delivery

### Requirement: Administrators manually map Plane members to Discord users

The system SHALL let an authorized administrator maintain an explicit mapping table for members of the selected Plane workspace. Each mapping SHALL pair a selected Plane member and read-only Plane User ID with a manually entered Discord User ID, and the administrator SHALL be able to remove a mapping. The system MUST NOT infer a Discord User ID from names, email addresses, or other profile data.

#### Scenario: Administrator creates a member mapping

- **WHEN** an administrator selects a member of the configured workspace, enters a valid Discord User ID, and saves the configuration
- **THEN** the system stores the explicit `Plane User ID -> Discord User ID` mapping for notification mention resolution

#### Scenario: Administrator removes a member mapping

- **WHEN** an administrator removes an existing mapping and saves the configuration
- **THEN** subsequent notifications no longer mention that Discord user through the removed mapping

#### Scenario: Invalid mapping is submitted

- **WHEN** an administrator submits a missing, duplicate, or invalid Plane User ID or Discord User ID mapping
- **THEN** the system rejects the invalid mapping with a validation error and does not partially save the submitted mapping set

### Requirement: Administrators can send a test message

The system SHALL provide an authorized test-message action that performs one delivery attempt using the configured Discord Webhook and reports whether Discord accepted the request. The test message SHALL use the single-event hierarchy from `docs/spec/discord-card-design.md`, including a Chinese test title, Plane source, concise description, destination link, semantic color, footer action, and event timestamp, so the test represents the production card style without mentioning any member.

#### Scenario: Test message succeeds

- **WHEN** an authorized administrator sends a test message with a valid saved configuration and Discord accepts the Webhook request
- **THEN** a clearly identified Chinese Plane test card using the production visual hierarchy appears in the configured Discord channel and the God Mode page reports success

#### Scenario: Test message fails

- **WHEN** Discord rejects the Webhook request, the request times out, or a network error occurs
- **THEN** the God Mode page reports failure without retrying the request or changing the saved configuration

### Requirement: Work-item creation notifications are delivered

When `work_item.created` is enabled, the integration is enabled, and a work item is created in the configured workspace, the system SHALL asynchronously send one Discord embed containing the event type, work-item name and identifier, project context, actor, current assignee names, and a link to the Plane work item. The card SHALL follow `docs/spec/discord-card-design.md`: use `Plane · {project}` as its source, use the linked Chinese title `🆕 新任务｜{identifier} · {name}`, describe the actor's action in Chinese, display status, priority, and assignee information using icon labels and inline-code badge values, use the creation event color, and include a concise footer and real event timestamp.

#### Scenario: Work item is created with mapped assignees

- **WHEN** a work item is created in the configured workspace and one or more current assignees have saved Discord mappings
- **THEN** the system sends one visually structured Chinese creation card that mentions each mapped current assignee and identifies all current assignees by Plane display name

#### Scenario: Work item is created with unmapped assignees

- **WHEN** a work item is created in the configured workspace and a current assignee has no saved Discord mapping
- **THEN** the structured creation card identifies that assignee by Plane display name without producing a Discord mention for that assignee

### Requirement: Newly assigned members receive assignment notifications

When `work_item.assignee_added` is enabled, the integration is enabled, and a work-item update in the configured workspace adds assignees, the system SHALL compare the previous and new `assignee_ids` values and asynchronously send one Discord embed for the update. The notification SHALL identify all newly added assignees and SHALL mention only newly added assignees that have saved Discord mappings. The card SHALL follow `docs/spec/discord-card-design.md`: use `Plane · {project}` as its source, use the linked Chinese title `👤 分配给你｜{identifier} · {name}`, describe the actor and assignment in Chinese, display status, priority, and deadline using icon labels and inline-code badge values, use semantic dots for urgency, use the assignment event color, and include a concise reminder footer and real event timestamp.

#### Scenario: One or more assignees are added

- **WHEN** an update adds one or more assignee IDs that were not present before the update
- **THEN** the system sends one visually structured Chinese assignment card and mentions only the newly added assignees with configured Discord mappings

#### Scenario: Assignee is removed without another addition

- **WHEN** an update only removes one or more assignees
- **THEN** the system sends no `work_item.assignee_added` notification

#### Scenario: Other work-item fields change without an assignment addition

- **WHEN** an update changes work-item fields but leaves the assignee set unchanged
- **THEN** the system sends no `work_item.assignee_added` notification

### Requirement: Work-item completion notifications are delivered once per completion transition

When `work_item.completed` is enabled, the integration is enabled, and a work item in the configured workspace transitions from a non-completed state group to the completed state group, the system SHALL asynchronously send one Discord embed containing the event type, work-item name and identifier, project context, actor, current assignee names, and a link to the Plane work item. The system SHALL mention mapped current assignees. The card SHALL follow `docs/spec/discord-card-design.md`: use `Plane · {project}` as its source, use the linked Chinese title `✅ 已完成｜{identifier} · {name}`, describe the actor's action in Chinese, display assignee, completed status, and completion time using icon labels and inline-code badge values, use the completion event color, and include a concise footer and real event timestamp.

#### Scenario: Work item transitions to completed

- **WHEN** a work item's state group changes from a non-completed group to the completed group
- **THEN** the system sends one visually structured Chinese completion card and mentions each current assignee with a configured Discord mapping

#### Scenario: Completed work item receives another update

- **WHEN** a work item already in the completed state group is updated without first leaving that group
- **THEN** the system sends no additional `work_item.completed` notification

### Requirement: Notifications are isolated to the configured workspace

The system SHALL evaluate and deliver Discord notifications only for the single workspace selected in the active configuration.

#### Scenario: Matching event occurs in another workspace

- **WHEN** an enabled event occurs in a workspace other than the configured workspace
- **THEN** the system sends no Discord notification for that event

### Requirement: Discord mentions are explicitly constrained

For every notification containing user mentions, the system MUST use Discord mention syntax derived only from saved mappings and MUST set `allowed_mentions.users` to exactly the Discord User IDs intended for that notification. The system MUST disable role and broad mention parsing.

#### Scenario: Notification contains mapped recipients

- **WHEN** a notification has one or more mapped recipient Discord User IDs
- **THEN** the payload contains matching `<@DISCORD_USER_ID>` mentions and permits only those exact user IDs in `allowed_mentions.users`

#### Scenario: Notification has no mapped recipients

- **WHEN** none of the notification recipients have a saved Discord mapping
- **THEN** the payload contains no generated user mention and permits no user, role, `@everyone`, or `@here` mentions

### Requirement: Delivery is a single bounded attempt

The system SHALL perform one asynchronous HTTP POST per generated notification with a bounded timeout. If delivery fails, the system SHALL write a sanitized error that identifies the event and response category without exposing the Webhook URL or message secrets, and SHALL NOT automatically retry, persist delivery history, or roll back the originating Plane operation.

#### Scenario: Discord accepts a notification

- **WHEN** Discord accepts the outbound Webhook POST
- **THEN** the delivery attempt ends successfully without affecting the originating Plane operation

#### Scenario: Discord delivery fails

- **WHEN** Discord rejects the POST, the request times out, or a network error occurs
- **THEN** the system records one sanitized error, performs no retry, and leaves the originating Plane operation successful

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

### Requirement: New work-item comments notify the responsible assignees

When the integration and `work_item.comment_activity` event are enabled, creation of a work-item comment in the configured workspace SHALL produce at most one Chinese comment card for the work item's assignees captured at event time. The system SHALL exclude the comment actor and SHALL mention only assignees with saved Discord mappings. If no eligible mapped assignee remains, the system SHALL send no comment card.

#### Scenario: Comment is created on an assigned work item

- **WHEN** a member creates a comment on a work item with one or more mapped assignees other than the actor
- **THEN** the system sends one comment card and mentions every eligible mapped assignee exactly once

#### Scenario: Comment actor is an assignee

- **WHEN** a work-item assignee creates a comment
- **THEN** the system excludes the actor from the comment recipients while still notifying other eligible mapped assignees

#### Scenario: Comment has no mapped assignee recipient

- **WHEN** a comment is created on an unassigned work item or every assignee is unmapped or is the comment actor
- **THEN** the system sends no `work_item.comment_activity` card for that creation

#### Scenario: Assignees change before asynchronous delivery

- **WHEN** the work item's assignees change after comment creation but before Discord delivery executes
- **THEN** the comment recipients remain based on the assignee snapshot captured when the comment was created

### Requirement: Comment mentions are classified by assignee responsibility

For a newly created comment, the system SHALL classify each newly mentioned member using the assignee snapshot captured at event time. A mentioned assignee SHALL remain only a comment recipient; a mentioned non-assignee SHALL be a `user.mentioned` recipient. The actor SHALL be excluded from both sets. Each non-empty mapped recipient set SHALL produce at most one card of its event type, so one mixed comment produces at most one comment card and one mention card.

#### Scenario: Comment mentions an assignee

- **WHEN** a new comment mentions a current assignee
- **THEN** that assignee is included only in the comment card and receives no second mention card for the same comment

#### Scenario: Comment mentions a non-assignee

- **WHEN** a new comment mentions a member who is not a current assignee and that member has a Discord mapping
- **THEN** the system includes that member in one mention card and does not add that member to the comment card

#### Scenario: Comment has mixed recipients

- **WHEN** a new comment mentions one or more assignees and one or more non-assignees while other assignees are also responsible
- **THEN** the system sends at most one deduplicated comment card to eligible assignees and one deduplicated mention card to eligible mentioned non-assignees

#### Scenario: Only mention notifications are enabled

- **WHEN** `user.mentioned` is enabled, `work_item.comment_activity` is disabled, and a comment mentions both an assignee and a non-assignee
- **THEN** the system sends a mention card only to the eligible mentioned non-assignee and does not reclassify the assignee as a mention recipient

#### Scenario: Only comment notifications are enabled

- **WHEN** `work_item.comment_activity` is enabled, `user.mentioned` is disabled, and a comment mentions both an assignee and a non-assignee
- **THEN** the system sends the comment card to eligible assignees and sends no card to the mentioned non-assignee

### Requirement: Comment edits notify only newly mentioned recipients

When an existing work-item comment is edited, the system SHALL compare the old and new rich-text content and consider only newly added user mentions. If `work_item.comment_activity` is enabled, a newly mentioned event-time assignee SHALL receive one comment-update card. If `user.mentioned` is enabled, a newly mentioned non-assignee SHALL receive one mention card. The system SHALL NOT renotify other assignees or mentions already present before the edit.

#### Scenario: Edit newly mentions an assignee

- **WHEN** a comment edit newly mentions a mapped current assignee other than the editor
- **THEN** the system sends one comment-update card to that assignee without notifying the other assignees again

#### Scenario: Edit newly mentions a non-assignee

- **WHEN** a comment edit newly mentions a mapped member who is not a current assignee and is not the editor
- **THEN** the system sends one mention card to that newly mentioned member

#### Scenario: Edit changes text without adding a mention

- **WHEN** a comment edit changes text but adds no user mention
- **THEN** the system sends neither a comment-update card nor a mention card

#### Scenario: Existing mention remains after edit

- **WHEN** a member mention was already present before a comment edit and remains afterward
- **THEN** the system does not notify that member again

### Requirement: Work-item description mentions notify mapped members

When the integration and `user.mentioned` event are enabled, the system SHALL notify mapped active workspace members newly mentioned through direct creation or editing of a work-item description in the configured workspace. Assignee status SHALL NOT change this classification, and the actor SHALL never receive a self-notification.

#### Scenario: Description adds a new mention

- **WHEN** a member directly creates or edits a work-item description and adds one or more mapped member mentions
- **THEN** the system sends at most one mention card containing the deduplicated eligible recipients

#### Scenario: Description mention targets an assignee

- **WHEN** a work-item description newly mentions a mapped current assignee
- **THEN** the system treats that recipient as mentioned and sends a mention card rather than a comment card

#### Scenario: Description is edited without a new mention

- **WHEN** a work-item description changes but its set of mentioned members gains no recipient
- **THEN** the system sends no mention card

### Requirement: Public Plane Page mentions notify mapped members once

When the integration and `user.mentioned` event are enabled, direct creation or editing of a public project-linked Plane Page in the configured workspace SHALL notify mapped active workspace members newly mentioned in the Page content, excluding the actor. The system SHALL use the mention node transaction identity to send at most once for a newly persisted mention, even when Page content is saved or the background task is invoked repeatedly.

#### Scenario: Public Plane Page adds a mention

- **WHEN** a member directly creates or edits a public Plane Page and adds one or more mapped member mentions
- **THEN** the system sends at most one mention card containing the deduplicated eligible recipients, Page context, and a link using the project context of the edit

#### Scenario: Plane Page is saved repeatedly

- **WHEN** repeated saves or duplicate background-task invocations contain a mention transaction that was already persisted for that Page
- **THEN** the system sends no additional notification for that transaction

#### Scenario: Private Plane Page contains a mention

- **WHEN** a private Plane Page is created or edited with a user mention
- **THEN** the system sends no Discord notification and exposes no Page title or content

#### Scenario: Plane Page is copied or restored

- **WHEN** mention nodes appear because a Page is duplicated, imported, synchronized by the system, or restored from a previous version
- **THEN** the system records normal Page state as required but sends no Discord mention notification

#### Scenario: Plane Page actor mentions self

- **WHEN** a member directly adds a mention of themselves to a public Plane Page
- **THEN** the system sends no notification to that member

### Requirement: Interaction cards use safe Chinese presentation and accurate links

Comment and mention notifications SHALL follow the single-event card hierarchy in `docs/spec/discord-card-design.md`. Fixed presentation copy SHALL be Chinese. A comment card SHALL identify the work item, project, actor, bounded comment excerpt, and exact `#comment-{comment_id}` link. A work-item mention card SHALL identify the actor, work item, source location, bounded surrounding excerpt, and work-item or exact comment link. A Plane Page mention card SHALL identify the actor, Page name, project context, bounded surrounding excerpt, and Page link without promising a block-level anchor.

The system MUST convert rich text to safe plain text, render Plane user mentions in excerpts using display names rather than internal IDs or raw tags, escape Discord formatting in surrounding prose, and limit each excerpt to 300 visible characters with a truncation marker when needed. URL-looking tokens in user-authored content MUST remain textually unchanged, including their dots, slashes, hyphens, query delimiters, fragments, and trailing path separators. Images, files, and unsupported rich content MUST NOT expose raw markup or internal storage details.

#### Scenario: URL in an interaction excerpt is preserved

- **WHEN** an eligible comment, work-item description, or public Page mention contains a URL such as `https://plane.tmlab.top/tml/projects/254ee0b6-b92b-4493-82b9-8c074a1a7071/pages/6ac5bf0b-6ad5-4279-a73c-9c5e15c7b350/`
- **THEN** the Discord content field shows the same URL text without inserted backslashes before dots or hyphens, while the notification's canonical Embed URL remains unchanged

#### Scenario: Markdown safety remains for surrounding prose

- **WHEN** the same excerpt contains Discord formatting characters, raw mention-like text, Plane mention nodes, images, or attachments outside the URL
- **THEN** surrounding prose remains safely escaped or replaced, no user-authored text creates an additional Discord mention, and the excerpt stays within the visible limit

#### Scenario: URL preservation does not expose unsupported rich content

- **WHEN** a rich-text excerpt contains a URL together with image, file, or unsupported component markup
- **THEN** the URL is preserved as plain text and unsupported components are represented by the existing safe placeholders without exposing raw tags or storage identifiers

### Requirement: Interaction notifications require mapped recipients and constrained mentions

The system SHALL send a comment or mention card only when its classified recipient set contains at least one member with a saved Plane-to-Discord mapping. It MUST place generated `<@DISCORD_USER_ID>` values only in top-level message content, set `allowed_mentions.parse` to an empty list, and set `allowed_mentions.users` to exactly the deduplicated mapped Discord User IDs classified for that card. User-authored content MUST NOT create any additional Discord mention.

#### Scenario: Some classified recipients are unmapped

- **WHEN** an interaction event classifies both mapped and unmapped Plane members
- **THEN** the system sends the card only for mapped recipients and does not generate mentions for unmapped members

#### Scenario: No classified recipient is mapped

- **WHEN** an interaction event has no classified recipient with a Discord mapping
- **THEN** the system sends no card for that event type

#### Scenario: Source content contains broad mention text

- **WHEN** user-authored content includes text such as `@everyone`, `@here`, a role mention, or another Discord-like token
- **THEN** the payload permits only the explicitly classified mapped user IDs and triggers no broad or unintended mention

### Requirement: Interaction delivery remains workspace-scoped and single-attempt

The system SHALL evaluate comment and mention notifications only for the configured workspace and enabled event keys. Each generated card SHALL use the existing bounded single-attempt Webhook transport; a failure SHALL be logged without Webhook URLs or interaction content, SHALL NOT retry, and SHALL NOT roll back or otherwise affect the originating comment, work-item, or Plane Page operation.

#### Scenario: Interaction occurs in another workspace

- **WHEN** a qualifying comment or mention occurs outside the configured workspace
- **THEN** the system sends no Discord card for that interaction

#### Scenario: Interaction delivery fails

- **WHEN** Discord rejects an interaction card, the request times out, or a network error occurs
- **THEN** the system records one sanitized failure, performs no retry, and leaves the originating Plane operation successful
