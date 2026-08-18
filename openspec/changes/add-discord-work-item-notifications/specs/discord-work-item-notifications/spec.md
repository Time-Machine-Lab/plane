## ADDED Requirements

### Requirement: God Mode administrators can configure one Discord destination

The system SHALL provide an authorized God Mode Discord configuration page that lets an instance administrator enable or disable the integration, select exactly one Plane workspace, enter a Discord Incoming Webhook URL, and choose any of the supported event keys. The supported initial event keys SHALL be `work_item.created`, `work_item.assignee_added`, and `work_item.completed`.

#### Scenario: Administrator saves a valid configuration

- **WHEN** an authorized instance administrator saves a valid Webhook URL, one workspace, and a set of enabled events
- **THEN** the system stores the configuration and uses it for subsequent matching events in that workspace

#### Scenario: Integration is disabled

- **WHEN** an administrator saves the Discord integration as disabled
- **THEN** the system sends no Discord work-item notifications until it is enabled again

#### Scenario: Unsupported or unselected event occurs

- **WHEN** a work-item activity does not match an enabled supported event key
- **THEN** the system sends no Discord notification for that activity

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

The system SHALL provide an authorized test-message action that performs one delivery attempt using the configured Discord Webhook and reports whether Discord accepted the request.

#### Scenario: Test message succeeds

- **WHEN** an authorized administrator sends a test message with a valid saved configuration and Discord accepts the Webhook request
- **THEN** a clearly identified Plane test embed appears in the configured Discord channel and the God Mode page reports success

#### Scenario: Test message fails

- **WHEN** Discord rejects the Webhook request, the request times out, or a network error occurs
- **THEN** the God Mode page reports failure without retrying the request or changing the saved configuration

### Requirement: Work-item creation notifications are delivered

When `work_item.created` is enabled, the integration is enabled, and a work item is created in the configured workspace, the system SHALL asynchronously send one Discord embed containing the event type, work-item name and identifier, project context, actor, current assignee names, and a link to the Plane work item.

#### Scenario: Work item is created with mapped assignees

- **WHEN** a work item is created in the configured workspace and one or more current assignees have saved Discord mappings
- **THEN** the system sends one creation notification that mentions each mapped current assignee and identifies all current assignees by Plane display name

#### Scenario: Work item is created with unmapped assignees

- **WHEN** a work item is created in the configured workspace and a current assignee has no saved Discord mapping
- **THEN** the notification identifies that assignee by Plane display name without producing a Discord mention for that assignee

### Requirement: Newly assigned members receive assignment notifications

When `work_item.assignee_added` is enabled, the integration is enabled, and a work-item update in the configured workspace adds assignees, the system SHALL compare the previous and new `assignee_ids` values and asynchronously send one Discord embed for the update. The notification SHALL identify all newly added assignees and SHALL mention only newly added assignees that have saved Discord mappings.

#### Scenario: One or more assignees are added

- **WHEN** an update adds one or more assignee IDs that were not present before the update
- **THEN** the system sends one assignment notification and mentions only the newly added assignees with configured Discord mappings

#### Scenario: Assignee is removed without another addition

- **WHEN** an update only removes one or more assignees
- **THEN** the system sends no `work_item.assignee_added` notification

#### Scenario: Other work-item fields change without an assignment addition

- **WHEN** an update changes work-item fields but leaves the assignee set unchanged
- **THEN** the system sends no `work_item.assignee_added` notification

### Requirement: Work-item completion notifications are delivered once per completion transition

When `work_item.completed` is enabled, the integration is enabled, and a work item in the configured workspace transitions from a non-completed state group to the completed state group, the system SHALL asynchronously send one Discord embed containing the event type, work-item name and identifier, project context, actor, current assignee names, and a link to the Plane work item. The system SHALL mention mapped current assignees.

#### Scenario: Work item transitions to completed

- **WHEN** a work item's state group changes from a non-completed group to the completed group
- **THEN** the system sends one completion notification and mentions each current assignee with a configured Discord mapping

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
