## Purpose

Define how project list and board views optionally include archived work items while preserving query semantics, read-only behavior, restoration, and the existing archive-only page.

## Requirements

### Requirement: Project display option controls archived visibility

The system SHALL provide a per-user "Show archived work items" option in the Display menu of the main project Work Items list and board, SHALL default the option to disabled when no preference exists, and SHALL persist changes in that user's project display preferences.

#### Scenario: Existing default remains focused on active work items

- **WHEN** a user opens a project Work Items list or board without a saved archived visibility preference
- **THEN** the option is disabled and archived work items are not included

#### Scenario: User preference persists

- **WHEN** a user enables "Show archived work items" and later reloads or revisits the same project Work Items view
- **THEN** the option remains enabled for that user and project

#### Scenario: Unsupported layout does not include archived work items

- **WHEN** a user with the saved option enabled switches to calendar, table, or timeline layout
- **THEN** the system does not request or display archived work items in that layout

### Requirement: Combined results preserve project query semantics

When the option is enabled, the system SHALL return active and archived work items through the same project-scoped filtering, grouping, ordering, counting, and pagination behavior. Archived work items SHALL remain grouped by their retained state and SHALL NOT create a dedicated Archive column.

#### Scenario: Board includes archived items in retained states

- **WHEN** the option is enabled on a state-grouped project board containing archived Completed or Cancelled work items
- **THEN** each archived work item appears in its retained Completed or Cancelled state column
- **AND** no Archive column is added

#### Scenario: List includes archived items under the same filters

- **WHEN** the option is enabled in project list layout and the user applies supported work item filters
- **THEN** active and archived work items that satisfy those filters appear in the ordered, paginated result
- **AND** work items that do not satisfy the filters remain excluded

#### Scenario: Counts match the visible result mode

- **WHEN** the user toggles archived visibility on or off
- **THEN** project and group counts are recalculated from the same visibility mode used for the displayed work items

#### Scenario: Default API behavior remains compatible

- **WHEN** a project work item request omits the archived visibility parameter or supplies it as false
- **THEN** the response excludes archived work items as it did before this change

#### Scenario: Project and record exclusions remain enforced

- **WHEN** archived visibility is enabled
- **THEN** the result remains scoped to the requested project and authorized user
- **AND** soft-deleted work items, draft work items, triage work items, and work items belonging to archived projects are not introduced by the option

### Requirement: Archived work items are identifiable and read-only

The system SHALL give archived work items a clear archived visual treatment in the combined list and board and SHALL prevent operations that mutate their normal work item properties or ordering.

#### Scenario: Archived card cannot be edited or moved

- **WHEN** an archived work item is visible in the combined list or board
- **THEN** inline property editing, drag and drop, reorder targeting, bulk selection, and normal archive actions are unavailable for that item

#### Scenario: Active card behavior is unchanged

- **WHEN** an active work item is visible beside archived work items and the user has edit permission
- **THEN** the active work item retains its existing edit, selection, drag, and quick-action behavior

#### Scenario: Archived detail can be inspected

- **WHEN** a user opens an archived work item from the combined list or board
- **THEN** the system loads the archived work item detail successfully through an archive-aware read path
- **AND** presents the detail as read-only

### Requirement: Authorized users can restore visible archived work items

The system SHALL expose the existing restore operation for an archived work item only to users authorized to restore it, and SHALL keep server-side authorization authoritative.

#### Scenario: Authorized restore succeeds

- **WHEN** an authorized project member restores an archived work item from the combined view
- **THEN** the work item remains in its retained state group as an active work item
- **AND** its archived treatment is removed
- **AND** its normal editability is restored according to project permissions

#### Scenario: Unauthorized user cannot restore

- **WHEN** a user without restore permission views an archived work item in the combined view
- **THEN** the Restore action is unavailable
- **AND** a direct restore request is rejected by the server's existing authorization rules

#### Scenario: Restore failure preserves archived state

- **WHEN** a restore request fails
- **THEN** the work item remains visibly archived and read-only
- **AND** the user receives an actionable failure indication

### Requirement: Archive-only navigation remains available

The system SHALL preserve the existing archive-only project page and its archive-specific filtering and restoration behavior.

#### Scenario: User opens the archive-only page

- **WHEN** a user navigates to the project's archived work items page after this change
- **THEN** the page continues to show only archived work items using its existing supported layout and actions
