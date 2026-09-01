## 1. Project-Scoped Hierarchy Data

- [ ] 1.1 Extend ProjectPage with parent, sibling order, project archive timestamp, and archive batch fields plus the active-child and archive-management indexes defined in the design.
- [ ] 1.2 Add the project hierarchy revision and idempotent mutation/audit records with bounded, content-free operation metadata.
- [ ] 1.3 Implement the expand-phase schema migration without removing or changing the legacy Page hierarchy columns.
- [ ] 1.4 Implement the data backfill for roots, valid legacy nesting, ordering, and archive state, with deterministic repair of cycles, cross-project parents, missing parents, and over-depth placements.
- [ ] 1.5 Add migration invariant reporting and a reverse path that removes only newly introduced schema while preserving Page content and legacy columns.

## 2. Hierarchy Domain and Authorization

- [ ] 2.1 Implement project-scoped hierarchy lookup helpers for roots, direct children, visible ancestors, descendants, depth, and stable paths without loading Page bodies.
- [ ] 2.2 Implement effective visibility across the complete ancestor chain and apply it consistently to node metadata, child presence, paths, favorites, and search.
- [ ] 2.3 Implement edge validation for active same-project parents, self/descendant cycles, maximum depth 20, archive state, private ownership compatibility, and child visibility no wider than its parent.
- [ ] 2.4 Implement transactional sibling placement and compaction using deterministic `(sort_order, id)` ordering and locks on the hierarchy revision and affected rows.
- [ ] 2.5 Implement idempotent, revision-aware create, reorder, reparent, and root-move operations that return authoritative affected ordering.
- [ ] 2.6 Integrate hierarchy validation with Page access changes so invalid tightening or widening is rejected atomically without changing ownership or descendant access.
- [ ] 2.7 Emit structured success and validation-failure audit events without Page bodies, secrets, or unauthorized titles.

## 3. Hierarchy and Management APIs

- [ ] 3.1 Add paginated root/direct-child hierarchy reads with Page navigation metadata, permitted actions, child presence, and current revision.
- [ ] 3.2 Add visible ancestor-path retrieval for direct Page links and selected tree/search results.
- [ ] 3.3 Add child creation and structural mutation contracts using external Page IDs and server-resolved active ProjectPage links.
- [ ] 3.4 Add subtree impact preview and atomic bulk validation for move, archive, restore, copy, and permanent removal operations, including overlapping selections.
- [ ] 3.5 Extend the paginated All Pages contract with root and nested Pages, path, depth, owner, visibility, lock, project archive, and update metadata while preserving existing filters and sorting.
- [ ] 3.6 Extend project Page search responses with authorized project-scoped paths and exclude any result whose ancestor chain is inaccessible.
- [ ] 3.7 Preserve existing Page detail/content URLs and compatible Page response fields while projecting project-scoped placement and archive state in project context.

## 4. Subtree Lifecycle

- [ ] 4.1 Replace project archive behavior with an atomic ProjectPage subtree archive that assigns one batch only to nodes active in that operation and preserves other-project links.
- [ ] 4.2 Implement batch-aware subtree restoration that retains parent/order, leaves previously archived descendants archived, and rejects restoration beneath an archived ancestor.
- [ ] 4.3 Keep existing single-Page duplication as a root-level copy and remove any accidental inheritance of the source hierarchy parent.
- [ ] 4.4 Implement explicit copy-with-descendants using new Page IDs, preserved relative hierarchy and order, compatible access, existing content/asset copy mechanisms, idempotency, and recoverable failure state.
- [ ] 4.5 Implement descendant-aware permanent removal of archived project links, preserving Pages linked to other projects and applying existing content deletion policy only after the last active link is removed.
- [ ] 4.6 Update favorite and recent-visit behavior so project-archived or effectively inaccessible Pages disappear from active shortcuts without corrupting stored relations.

## 5. Shared Contracts and Web State

- [ ] 5.1 Add typed hierarchy node, path, revision, placement, preview, bulk-operation, and stable error contracts in the appropriate shared packages and service client.
- [ ] 5.2 Add pure utilities for normalized child maps, visible tree rows, path/depth derivation, valid destination filtering, and deterministic reconciliation.
- [ ] 5.3 Refactor the project Page MobX store to keep normalized node metadata, ordered children per parent, per-branch loading/error state, ancestor paths, and hierarchy revision.
- [ ] 5.4 Implement lazy root/child loading, direct-link ancestor expansion, branch retry, and newer-revision invalidation without clearing the open Page.
- [ ] 5.5 Implement optimistic move snapshots, success reconciliation, rollback on failure, and targeted authoritative refresh for affected branches.
- [ ] 5.6 Persist a versioned, bounded expanded-node list in per-user ProjectUserProperty Page preferences with debounced updates and stale/inaccessible ID pruning.

## 6. Knowledge Base Experience

- [ ] 6.1 Rename the project-facing Pages navigation and headings to localized Knowledge Base terminology while retaining canonical Page URLs and internal document identity.
- [ ] 6.2 Build the lazy multi-level tree with stable row dimensions, expand/collapse, selection, title/logo, child presence, and accessible private/locked/archived indicators.
- [ ] 6.3 Add contextual root and child Page creation, expand the destination branch, and place the created Page into immediate title editing with transactional error recovery.
- [ ] 6.4 Add pointer drag-and-drop with explicit before/inside/after cues, invalid-target feedback, subtree movement, and authoritative rollback using existing pragmatic drag-and-drop patterns.
- [ ] 6.5 Add a searchable keyboard/touch Move dialog with root/parent selection and ordered placement equivalent to drag-and-drop.
- [ ] 6.6 Add complete navigable Page breadcrumbs and make favorite/search selection expand and locate the canonical tree node.
- [ ] 6.7 Add a pinned Favorites shortcut section that never duplicates or relocates canonical tree nodes.
- [ ] 6.8 Retain All Pages as a paginated flat management view with hierarchy columns, filters, sorting, subtree impact preview, and supported bulk actions.
- [ ] 6.9 Provide complete loading, empty, retryable error, conflict, disabled, and archived states for tree and management operations.
- [ ] 6.10 Implement ARIA tree keyboard behavior, visible focus, named icon controls, capped visual indentation, and a non-overlapping narrow-viewport hierarchy drawer separate from the Page outline.

## 7. Test Environment Deployment

- [ ] 7.1 After implementation is complete, have the primary Agent immediately deploy only the affected API, web, worker, and migration runtime through `scripts/test/deploy-test.ps1` without waiting for host-side Django, pytest, Ruff, local Docker, or automated-test execution.
- [ ] 7.2 Confirm the deployed services are healthy and the migration completed, then hand the deployment address to a fresh Tester sub-agent that did not participate in implementation.

## 8. Independent Tester Acceptance

- [ ] 8.1 Have the Tester independently verify the OpenSpec goal, directly affected behavior, and necessary adjacent Page regression in the deployed test environment without modifying product code or running backend/frontend automated test suites.
- [ ] 8.2 Validate root/nested navigation, remembered expansion, child creation, pointer and keyboard movement, breadcrumbs/search/favorites, status display, All Pages management, subtree lifecycle, and responsive/accessibility behavior using suitable project roles.
- [ ] 8.3 Probe migration compatibility, private ancestor non-disclosure, invalid/cyclic/deep/cross-project moves, concurrent reconciliation, partial failure recovery, multi-project survival, stable ordering, and large-tree behavior through observable test-environment outcomes.
- [ ] 8.4 Verify feature-gate behavior, compatibility reads, sanitized audit behavior, rollback constraints, and necessary adjacent Page flows including editing, lock/access enforcement, favorites, versions, duplication, export, and collaboration identity.
- [ ] 8.5 Record sanitized durable acceptance evidence and residual risks in `verification.md`; if acceptance fails, have the implementation Agent fix the affected scope, redeploy affected services, and have the same Tester recheck only the failure and necessary adjacent behavior before completion.
