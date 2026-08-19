## MODIFIED Requirements

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
