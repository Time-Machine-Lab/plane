## MODIFIED Requirements

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

## ADDED Requirements

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

The system MUST convert rich text to safe plain text, render Plane user mentions in excerpts using display names rather than internal IDs or raw tags, escape Discord formatting, and limit each excerpt to 300 characters with a visible truncation marker when needed. Images, files, and unsupported rich content MUST NOT expose raw markup or internal storage details.

#### Scenario: Comment card is rendered

- **WHEN** an eligible new comment notification is generated
- **THEN** its Chinese card uses the comment theme, quotes a safe bounded excerpt, and links directly to the comment anchor

#### Scenario: Mention card is rendered

- **WHEN** an eligible work-item or Plane Page mention notification is generated
- **THEN** its Chinese card uses the mention theme, identifies where the mention occurred, quotes a safe bounded excerpt, and links to the eligible source object

#### Scenario: Rich content exceeds presentation limits

- **WHEN** source content contains rich markup, mentions, attachments, unsafe Discord formatting, or more than 300 excerpt characters
- **THEN** the card contains a safe plain-text excerpt with Plane display names, no raw internal markup, and a visible truncation marker within the limit

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
