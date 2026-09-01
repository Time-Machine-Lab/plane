## Context

The main project Work Items view reads project display preferences, builds server-side filter and grouping parameters, and stores the returned IDs in the project issue store. The API uses `Issue.issue_objects`, whose manager excludes archived work items. Archived work items are loaded separately through an archive endpoint and an archive-only store, and that store currently supports only list layout.

The combined view crosses the web display controls, project filter/store behavior, shared view parameter types, the Django query path, and archived detail/restore actions. It must preserve the default response, server-side authorization, pagination, and state grouping while allowing archived and active records to coexist in one project result.

## Goals / Non-Goals

**Goals:**

- Add a persisted, per-user project display preference that includes archived work items in the main list and board.
- Keep archived work items in their retained state groups and in the same server-side filter, count, order, and pagination model as active work items.
- Make archived cards visibly distinct and read-only while preserving detail viewing and authorized restoration.
- Keep omission or disabling of the new option fully compatible with current project work item behavior.

**Non-Goals:**

- Adding a synthetic Archive state or board column.
- Enabling combined archived visibility in cycles, modules, custom views, workspace/profile views, or layouts other than list and board.
- Changing archive eligibility, retention, deletion, project archival, or authorization rules.
- Replacing or removing the archive-only page.

## Decisions

### Store the option as a project display filter

Use an `include_archived` boolean in the existing project user `display_filters` JSON and corresponding shared TypeScript types. Missing values resolve to `false`. The Display menu exposes it as "Show archived work items" only for the main project list and board.

This follows the existing persisted handling for options that change which work items are returned, such as sub-work item visibility. Storing it as a display property would be incorrect because display properties only control fields rendered on an already-visible card.

When the user switches to an unsupported layout, query generation omits `include_archived` even if the saved preference remains true. Returning to list or board restores the saved choice. This avoids silently expanding the first release to layouts whose editing surfaces have not been made archive-aware.

### Extend the normal project query with an opt-in parameter

Add an optional validated `include_archived` query parameter to the existing project work item list. With the parameter absent or false, continue using the current unarchived manager and response behavior. With it true, build a project-scoped queryset that retains the existing exclusions for soft-deleted records, triage records, drafts, and archived projects while omitting only the work-item `archived_at` exclusion.

The same queryset must drive filtering, group values, group counts, ordering, and pagination. Hard-coded `archived_at IS NULL` count predicates must follow the visibility mode. This is preferable to fetching the archive endpoint separately and merging in the browser, which would produce incorrect pagination, ordering, filter results, and group counts.

No existing endpoint is removed or changed by default, and the archive-only endpoint remains the source for archive-only navigation and archived detail retrieval.

### Let the project store represent the server result without archive filtering

The project issue store remains the owner of combined-view IDs. Its response processing and local reordering must operate on the IDs returned for the current visibility mode rather than assuming every project-store item is unarchived. The archive-only store retains its archived-only behavior.

Changing `include_archived` is a server-affecting display-filter update and triggers a project issue refetch. Archiving, restoring, or deleting a visible item must update or refetch the combined result so IDs, counts, and pagination do not retain stale archive state.

### Enforce read-only behavior per work item

List and board rendering determine editability from both project permission and `issue.archived_at`. Archived work items cannot be edited, dragged, used as reorder targets, bulk-selected, quick-added beneath, or sent through normal archive/delete actions from the combined view. They use an archive-aware quick action that permits detail viewing and exposes Restore only when the existing server authorization allows it.

Archived cards use the existing archive iconography and a restrained visual treatment without changing layout dimensions. Restoring a card clears its archived treatment and returns it to normal editability in the same retained state group.

### Route archived detail reads through the archive contract

The peek/detail fetch path must use archived retrieval when the selected item carries `archived_at`, instead of relying only on presentation-time `isArchived` flags. The detail remains read-only and uses the existing restore contract. Restore failures leave the item archived and surface the existing actionable error behavior.

## Risks / Trade-offs

- [The unrestricted model manager also contains drafts, triage items, or items in archived projects] -> Centralize or explicitly reproduce every existing visibility exclusion except work-item archival, and cover the default and opt-in query contracts with focused API tests.
- [Group counts or pagination diverge from displayed cards] -> Derive results, group values, counts, and cursors from the same visibility-aware queryset rather than merging endpoints client-side.
- [Archived items become editable through an overlooked interaction] -> Make archive state part of the shared per-item editability decision and verify inline editing, drag/drop, selection, quick actions, and detail operations.
- [Large archive histories increase response traversal] -> Keep server pagination and filters authoritative; avoid eager loading all archived items and assess query plans if affected-project contract tests expose a regression.
- [Saved true preference leaks into unsupported layouts] -> Gate both option rendering and query parameter generation to the project list and board layouts.

## Migration Plan

No schema or data migration is required. Deploy the backward-compatible API handling before or together with the web change. Existing and missing preferences default to false. Rollback consists of removing the UI/query emission; persisted unknown JSON keys are harmless to older code, and the default API path remains unchanged.

## Open Questions

None. The product decision is to show archived work items in their retained Completed or Cancelled state groups, not in a dedicated Archive column.
