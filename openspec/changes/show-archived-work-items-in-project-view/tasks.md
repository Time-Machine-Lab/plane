## 1. Project Query Contract

- [ ] 1.1 Add validated optional `include_archived` handling to the project work item list while preserving every existing project, deletion, draft, triage, and archived-project exclusion.
- [ ] 1.2 Make filtering, state grouping, group values, counts, ordering, and pagination use the same visibility-aware queryset.
- [ ] 1.3 Add focused app API contract coverage for the unchanged default response, opt-in active-plus-archived response, filtering/count behavior, and authorization/project isolation.

## 2. Display Preference And Query State

- [ ] 2.1 Extend shared display-filter and request parameter types/constants with `include_archived`, limited to the main project list and board layouts.
- [ ] 2.2 Add the localized "Show archived work items" Display-menu option and keep it hidden in unsupported layouts.
- [ ] 2.3 Persist the option in project user display preferences, default missing values to false, and refetch project work items when the option changes.

## 3. Combined Archived Work Item Behavior

- [ ] 3.1 Update project issue response processing, local ordering, and archive/restore refresh behavior so active and archived IDs can coexist without stale counts or archive-only filtering assumptions.
- [ ] 3.2 Render archived list rows and board cards with an archived treatment and disable their inline editing, selection, drag/drop, reorder-target, quick-add, and normal mutation actions without changing active-item behavior.
- [ ] 3.3 Provide archive-aware quick actions that expose Restore only to authorized users and correctly update the combined view after success or failure.
- [ ] 3.4 Route archived peek/detail reads through the archived retrieval contract and keep archived detail read-only until restoration succeeds.
- [ ] 3.5 Confirm the existing archive-only page retains its archived-only list, filters, detail access, and restore behavior.

## 4. Development Checks

- [ ] 4.1 Run the focused API contract tests and directly affected web/shared type, lint, and i18n synchronization checks, fixing only failures caused by this change.
- [ ] 4.2 Exercise the project list and board locally with the option off and on, including filters, counts, archived detail, denied editing/dragging, restore success/failure, unsupported layout switching, and active-item regression behavior.

## 5. Independent Verification

- [ ] 5.1 Have the primary Agent create a new Tester sub-agent that did not participate in implementation to verify the requirement goal and necessary adjacent archive-page regression using the least expensive sufficient local or offline method without modifying product code.
- [ ] 5.2 If verification fails, fix the focused defect and have the same Tester recheck only the failed scope and necessary adjacent behavior before completion.
