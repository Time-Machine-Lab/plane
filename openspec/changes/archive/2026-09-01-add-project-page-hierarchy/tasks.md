## 1. Project-Scoped Hierarchy Data

- [x] 1.1 Extend ProjectPage with parent, sibling order, project archive timestamp, and archive batch fields plus the active-child and archive-management indexes defined in the design.
- [x] 1.2 Add the project hierarchy revision and idempotent mutation/audit records with bounded, content-free operation metadata.
- [x] 1.3 Implement the expand-phase schema migration without removing or changing the legacy Page hierarchy columns.
- [x] 1.4 Implement the data backfill for roots, valid legacy nesting, ordering, and archive state, with deterministic repair of cycles, cross-project parents, missing parents, and over-depth placements.
- [x] 1.5 Add migration invariant reporting and a reverse path that removes only newly introduced schema while preserving Page content and legacy columns.

## 2. Hierarchy Domain and Authorization

- [x] 2.1 Implement project-scoped hierarchy lookup helpers for roots, direct children, visible ancestors, descendants, depth, and stable paths without loading Page bodies.
- [x] 2.2 Implement effective visibility across the complete ancestor chain and apply it consistently to node metadata, child presence, paths, favorites, and search.
- [x] 2.3 Implement edge validation for active same-project parents, self/descendant cycles, maximum depth 20, archive state, private ownership compatibility, and child visibility no wider than its parent.
- [x] 2.4 Implement transactional sibling placement and compaction using deterministic `(sort_order, id)` ordering and locks on the hierarchy revision and affected rows.
- [x] 2.5 Implement idempotent, revision-aware create, reorder, reparent, and root-move operations that return authoritative affected ordering.
- [x] 2.6 Integrate hierarchy validation with Page access changes so invalid tightening or widening is rejected atomically without changing ownership or descendant access.
- [x] 2.7 Emit structured success and validation-failure audit events without Page bodies, secrets, or unauthorized titles.

## 3. Hierarchy and Management APIs

- [x] 3.1 Add paginated root/direct-child hierarchy reads with Page navigation metadata, permitted actions, child presence, and current revision.
- [x] 3.2 Add visible ancestor-path retrieval for direct Page links and selected tree/search results.
- [x] 3.3 Add child creation and structural mutation contracts using external Page IDs and server-resolved active ProjectPage links.
- [x] 3.4 Add subtree impact preview and atomic bulk validation for move, archive, restore, copy, and permanent removal operations, including overlapping selections.
- [x] 3.5 Extend the paginated All Pages contract with root and nested Pages, path, depth, owner, visibility, lock, project archive, and update metadata while preserving existing filters and sorting.
- [x] 3.6 Extend project Page search responses with authorized project-scoped paths and exclude any result whose ancestor chain is inaccessible.
- [x] 3.7 Preserve existing Page detail/content URLs and compatible Page response fields while projecting project-scoped placement and archive state in project context.

## 4. Subtree Lifecycle

- [x] 4.1 Replace project archive behavior with an atomic ProjectPage subtree archive that assigns one batch only to nodes active in that operation and preserves other-project links.
- [x] 4.2 Implement batch-aware subtree restoration that retains parent/order, leaves previously archived descendants archived, and rejects restoration beneath an archived ancestor.
- [x] 4.3 Keep existing single-Page duplication as a root-level copy and remove any accidental inheritance of the source hierarchy parent.
- [x] 4.4 Implement explicit copy-with-descendants using new Page IDs, preserved relative hierarchy and order, compatible access, existing content/asset copy mechanisms, idempotency, and recoverable failure state.
- [x] 4.5 Implement descendant-aware permanent removal of archived project links, preserving Pages linked to other projects and applying existing content deletion policy only after the last active link is removed.
- [x] 4.6 Update favorite and recent-visit behavior so project-archived or effectively inaccessible Pages disappear from active shortcuts without corrupting stored relations.

## 5. Shared Contracts and Web State

- [x] 5.1 Add typed hierarchy node, path, revision, placement, preview, bulk-operation, and stable error contracts in the appropriate shared packages and service client.
- [x] 5.2 Add pure utilities for normalized child maps, visible tree rows, path/depth derivation, valid destination filtering, and deterministic reconciliation.
- [x] 5.3 Refactor the project Page MobX store to keep normalized node metadata, ordered children per parent, per-branch loading/error state, ancestor paths, and hierarchy revision.
- [x] 5.4 Implement lazy root/child loading, direct-link ancestor expansion, branch retry, and newer-revision invalidation without clearing the open Page.
- [x] 5.5 Implement optimistic move snapshots, success reconciliation, rollback on failure, and targeted authoritative refresh for affected branches.
- [x] 5.6 Persist a versioned, bounded expanded-node list in per-user ProjectUserProperty Page preferences with debounced updates and stale/inaccessible ID pruning.

## 6. Knowledge Base Experience

- [x] 6.1 Rename the project-facing Pages navigation and headings to localized Knowledge Base terminology while retaining canonical Page URLs and internal document identity.
- [x] 6.2 Build the lazy multi-level tree with stable row dimensions, expand/collapse, selection, title/logo, child presence, and accessible private/locked/archived indicators.
- [x] 6.3 Add contextual root and child Page creation, expand the destination branch, and place the created Page into immediate title editing with transactional error recovery.
- [x] 6.4 Add pointer drag-and-drop with explicit before/inside/after cues, invalid-target feedback, subtree movement, and authoritative rollback using existing pragmatic drag-and-drop patterns.
- [x] 6.5 Add a searchable keyboard/touch Move dialog with root/parent selection and ordered placement equivalent to drag-and-drop.
- [x] 6.6 Add complete navigable Page breadcrumbs and make favorite/search selection expand and locate the canonical tree node.
- [x] 6.7 Add a pinned Favorites shortcut section that never duplicates or relocates canonical tree nodes.
- [x] 6.8 Retain All Pages as a paginated flat management view with hierarchy columns, filters, sorting, subtree impact preview, and supported bulk actions.
- [x] 6.9 Provide complete loading, empty, retryable error, conflict, disabled, and archived states for tree and management operations.
- [x] 6.10 Implement ARIA tree keyboard behavior, visible focus, named icon controls, capped visual indentation, and a non-overlapping narrow-viewport hierarchy drawer separate from the Page outline.

## 7. Backend Automated Regression Coverage

- [x] 7.1 Add migration tests covering legacy roots/nesting, multi-project Pages, archived branches, invalid parents, cycles, over-depth data, deterministic repair, reverse schema behavior, and preservation of Page IDs/content.
- [x] 7.2 Add hierarchy read tests for lazy roots/children, deep ancestor paths, stable pagination, duplicate titles, depth, metadata-only payloads, and bounded query counts on broad and deep fixtures.
- [x] 7.3 Add mutation tests for child creation rollback, reorder, reparent, root move, subtree preservation, cycle/depth/project validation, compaction, stable errors, and forged payloads.
- [x] 7.6 Add lifecycle tests for archive batches, pre-archived descendants, restore restrictions, multi-project survival, bulk overlap, single copy, subtree copy success/failure recovery, and final-link removal.

## 8. Frontend Automated Regression Coverage

- [x] 8.1 Add pure utility and MobX tests for normalized tree derivation, stable ordering, lazy branch state, direct-link expansion, expansion preference pruning, favorite shortcuts, and filter/sort isolation.
- [x] 8.2 Add store mutation tests for optimistic reorder/reparent, subtree preservation, rollback, concurrent newer revisions, idempotent responses, branch refresh, and Page-content state retention after hierarchy errors.

## 9. Development Checks and Rollout Readiness

- [x] 9.1 Run focused Python syntax/static checks plus executable frontend utility and MobX store tests, and resolve failures in affected scope; backend pytest is not required for this change.
- [x] 9.2 Run affected web/shared-package type, lint, locale synchronization, and focused automated checks and resolve introduced failures.

## 10. Independent Tester Verification

- [x] 10.1 Deploy only the affected API, web, worker, and migration runtime through the repository test-environment workflow because core acceptance requires real database, authorization, transaction, and browser behavior.
- [x] 10.2 Have the primary Agent create a fresh Tester sub-agent that did not participate in implementation to independently verify the TMLPLANE-7 Knowledge Base goal and directly affected behavior without modifying product code.
- [x] 10.3 Have the Tester validate representative root/nested/direct-link navigation, remembered expansion, child creation, pointer and keyboard movement, breadcrumbs/search paths/favorites, status display, All Pages management, subtree lifecycle, feature-gate fallback, and responsive/accessibility behavior using suitable project roles.
- [x] 10.4 Have the Tester independently probe hierarchy migration and query bounds, private ancestor non-disclosure, inactive/cyclic/deep/cross-project moves, concurrent reconciliation and rollback, multi-project survival, and feature-gate compatibility where required to establish the TMLPLANE-7 risk boundaries.
- [x] 10.5 Record sanitized durable acceptance evidence and residual risks in `verification.md`; if acceptance fails, have the implementation Agent fix the affected scope and the same Tester recheck only the failure and directly affected behavior before completion.
