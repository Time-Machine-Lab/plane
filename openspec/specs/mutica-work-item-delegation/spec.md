## Purpose

Define how Plane delegates work items to Mutica assistants while preserving human assignees, authorization, reliable handoff, immutable history, and safe user-visible state.

## Requirements

### Requirement: Mutica delegation is independent of assignees

Plane SHALL represent the active Mutica assistant delegation separately from human work-item assignees and SHALL leave existing assignee data, selection, filtering, analytics, and notifications unchanged.

#### Scenario: Work item is delegated

- **WHEN** an authorized member delegates a work item to the connected Mutica assistant
- **THEN** Plane records the Mutica delegation without adding or removing any human assignee

#### Scenario: Human assignees change

- **WHEN** users change human assignees on a Mutica-delegated work item
- **THEN** the active Mutica delegation remains unchanged

### Requirement: Authorized delegation

Plane SHALL allow delegation only for a persisted work item, an active workspace Mutica connection, an enabled assistant, and a user authorized to edit that work item.

#### Scenario: Existing work item is delegated

- **WHEN** an authorized editor delegates an existing work item to the enabled assistant
- **THEN** Plane atomically creates a current delegation in `dispatching` state and schedules delivery after commit

#### Scenario: Delegation is selected during creation

- **WHEN** an authorized user creates a work item and selects Mutica delegation
- **THEN** Plane persists the work item before creating and delivering the delegation with the final work-item identifier

#### Scenario: Unauthorized member attempts delegation

- **WHEN** a user who cannot edit the work item attempts to delegate, retry, reassign, or clear its Mutica delegation
- **THEN** Plane rejects the operation without changing delegation state or sending an event

#### Scenario: Disabled connection is targeted

- **WHEN** delegation targets a disconnected, disabled, or mismatched workspace Mutica connection
- **THEN** Plane rejects the operation and does not disclose connection details

### Requirement: Signed idempotent handoff

Plane SHALL deliver each delegation through an authenticated, versioned, idempotent event containing stable Plane and Mutica identifiers and no Plane service credential or attachment body.

#### Scenario: Delegation is delivered

- **WHEN** the Mutica endpoint durably accepts the event for its delegation identifier
- **THEN** Plane marks that delegation `handed_off` and records a non-sensitive delivery outcome

#### Scenario: Delivery is retried

- **WHEN** delivery fails with a retryable timeout or response
- **THEN** Plane retries with bounded backoff using the same delegation identifier and distinct delivery-attempt identifiers so Mutica can deduplicate the task

#### Scenario: Delivery permanently fails

- **WHEN** all allowed retries fail or Mutica returns a permanent rejection
- **THEN** Plane marks the delegation `failed`, presents an actionable retry option to authorized users, and does not claim that the agent accepted the task

#### Scenario: Event contents are inspected

- **WHEN** a delegation event is serialized
- **THEN** it contains the schema version, event and delivery identifiers, delegation identifier, Plane origin, workspace slug, project and work-item identifiers, canonical work-item URL, external agent identifier, and timestamp without comments, file bodies, expiring attachment URLs, or service tokens

### Requirement: Handoff state is distinct from execution state

Plane SHALL track only whether delegation is being delivered, has been handed off to Mutica, has failed, or has been superseded, and MUST NOT infer Mutica execution from service-token activity.

#### Scenario: Mutica receives the event

- **WHEN** Mutica durably accepts a delegation event but its agent has not started work
- **THEN** Plane may show the delegation as handed off but does not show the agent as running or completed

#### Scenario: Agent starts or completes work

- **WHEN** a Mutica agent starts work or decides that work is complete
- **THEN** any visible business progress is represented by ordinary Plane work-item state changes made through Plane MCP rather than a second Plane-managed execution lifecycle

#### Scenario: Service token reads the work item

- **WHEN** the Mutica service token retrieves a delegated work item or retries a read
- **THEN** Plane does not change the delegation handoff state merely because the token was used

### Requirement: Reassignment and history

Plane SHALL preserve immutable delegation attempts and ensure that only the newest non-superseded delegation controls the work item's current Mutica property.

#### Scenario: Work item is reassigned

- **WHEN** an authorized user delegates a work item again
- **THEN** Plane supersedes the previous active attempt, creates a new delegation identifier, delivers the new event, and preserves the prior attempt in history

#### Scenario: Stale delivery completes after reassignment

- **WHEN** a response or retry for a superseded delegation arrives after a newer delegation is active
- **THEN** Plane records the old attempt's outcome without replacing or changing the current delegation

#### Scenario: Delegation is cleared

- **WHEN** an authorized user clears the Mutica delegation
- **THEN** Plane removes the active Mutica property, retains the prior attempt history, and prevents pending stale delivery from restoring it

### Requirement: Delegation visibility

Plane SHALL show the default assistant identity and current handoff result on the work item and SHALL record non-sensitive delegation actions in activity history.

#### Scenario: Delegation is active

- **WHEN** a user views a work item with a current delegation
- **THEN** Plane displays the Mutica assistant separately from assignees together with `dispatching`, `handed off`, or actionable `failed` feedback

#### Scenario: Delegation activity is viewed

- **WHEN** a user views work-item activity after delegation, retry, reassignment, or clear
- **THEN** Plane identifies the human initiator, Mutica assistant, action, and time without exposing secrets or inventing execution events
