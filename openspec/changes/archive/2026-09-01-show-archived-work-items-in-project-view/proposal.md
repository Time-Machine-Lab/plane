## Why

Archived work items are currently separated from the project's main work item view, so users must navigate through the project archive whenever they need historical context. A per-user display option should let users include archived work items in the main project list or board without changing the default focused view.

## What Changes

- Add a "Show archived work items" option to the Display menu on the main project Work Items page, defaulting to off and persisting with that user's project display preferences.
- When enabled in list or board layout, include archived work items in the same server-filtered, grouped, counted, ordered, and paginated result set as active work items.
- Keep each archived work item in its retained state group, such as Completed or Cancelled, rather than creating a separate Archive column.
- Give archived work items a clear archived treatment and make them read-only in the combined view; users can inspect them and authorized members can restore them.
- Keep the existing archive-only page available.
- Limit the first version to the main project Work Items list and board. Cycles, modules, custom views, workspace/profile views, calendar, table, and timeline layouts are out of scope.
- Do not change which work items may be archived, archive retention, deletion behavior, or project-level authorization.

## Capabilities

### New Capabilities

- `project-work-item-archive-visibility`: Controls how a user's main project Work Items view includes, presents, and permits interaction with archived work items.

### Modified Capabilities

None.

## Impact

- Affected modules: `apps/web` project work item display controls, filters, stores, layouts, quick actions, and archived detail handling; `apps/api` project work item query and grouping behavior; shared issue view types/constants and localized strings under `packages/*`.
- Applicable standards: `docs/spec/general-development.md`, `docs/spec/frontend-development.md`, `docs/spec/backend-development.md`, and `docs/spec/shared-packages-development.md`.
- API compatibility: the project work item list gains an optional archived-visibility query parameter; omission preserves the existing response and behavior.
- Data and migration: the preference can be stored in the existing JSON display filters, so no database schema or data migration is expected.
- Authorization: existing project read permissions and archive restore permissions remain authoritative; the UI must not grant restore access independently of the API.
- Dependencies, deployment, and licensing: no new dependency, deployment topology, or licensing impact is expected.
