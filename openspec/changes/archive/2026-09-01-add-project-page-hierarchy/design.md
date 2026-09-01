## Context

Plane already has a mature Page document entity, editor, real-time content collaboration, versions, favorites, export, Page-level access, lock state, and project links. The current Django `Page` model also has `parent`, `sort_order`, and `archived_at`, but the web list only consumes root Pages and its shared `TPage` contract does not expose hierarchy. Those fields are global to a Page even though a Page may have multiple active `ProjectPage` links, so they cannot safely represent different locations or archive states in different projects.

This change crosses the Django API, migrations, shared contracts and utilities, the web MobX store, project navigation, search presentation, and Page lifecycle actions. It has elevated authorization, tenant-isolation, migration, concurrency, and data-loss risk. Page content collaboration and other Page capabilities are not structurally changed and are outside this change's acceptance scope.

## Goals / Non-Goals

**Goals:**

- Upgrade the existing project Pages experience into a tree-first Knowledge Base without creating a second document system.
- Make hierarchy, order, and archive state authoritative per active ProjectPage link.
- Preserve existing Page IDs, content, links, versions, favorites, ownership, visibility, lock behavior, collaboration, and export.
- Provide deterministic, atomic, permission-safe structural and subtree lifecycle operations.
- Keep large knowledge bases usable through lazy tree loading, bounded metadata, stable pagination, and normalized client state.
- Provide focused executable and independent runtime evidence for hierarchy invariants, migration, authorization, concurrency, rollback, accessibility, and responsive behavior.

**Non-Goals:**

- Separate folder nodes, multiple knowledge bases per project, cross-project knowledge-base navigation, public documentation sites, backlinks, templates, or review workflows.
- Replacing the current Page editor, Yjs document format, Page outline, version history, or export format.
- Removing legacy Page hierarchy fields during the same release window.
- Making Page access or lock state project-specific; only hierarchy placement and archive state become project-scoped here.

## Decisions

### 1. Treat Knowledge Base as a presentation of existing Pages

The project navigation label and information architecture become Knowledge Base, but the document remains `Page` and canonical URLs remain `/pages/{page_id}`. Existing links, mentions, recent visits, Page transactions, live document names, and exports therefore keep their current identity.

Alternative considered: add `KnowledgeBase` and `KnowledgeBaseDocument` entities. This would duplicate editing, versioning, collaboration, search, permissions, favorites, and lifecycle behavior without satisfying a current requirement for multiple independent knowledge bases.

### 2. Move project placement to ProjectPage

Extend `ProjectPage` with:

- nullable self-referential `parent` pointing to another active ProjectPage;
- indexed sibling `sort_order`;
- project-scoped `archived_at`;
- nullable `archive_batch_id` identifying the subtree archive operation;
- indexes for active children ordered by `(project, parent, sort_order, id)` and archived management queries.

The service layer validates that parent and child share workspace and project, are active links, and satisfy access and depth rules. A database self-reference prevents dangling parents; service transactions and invariant tests cover cross-row constraints that a portable database check cannot express. Parent hard deletion is protected until subtree links are explicitly processed.

`Page.parent`, `Page.sort_order`, and `Page.archived_at` remain during a compatibility window but stop being authoritative for project hierarchy. Project-scoped serializers expose hierarchy values from the requested ProjectPage link. Legacy fields are mirrored only where an unambiguous single active project link permits it; ambiguous multi-project placement is never collapsed back into a false global value.

Alternative considered: continue using Page hierarchy fields. This cannot represent a Page under different parents in two projects and makes an archive in one project unexpectedly affect another project.

### 3. Use a revisioned hierarchy mutation boundary

Add a small project-scoped hierarchy state record containing a monotonically increasing revision. Structural and subtree lifecycle mutations:

1. validate workspace, active membership, project role, node access, target access, visibility compatibility, cycle, archive state, and resulting maximum depth;
2. lock the project hierarchy state and affected sibling/node rows in a database transaction;
3. apply parent, order, archive, restore, or relation-removal changes atomically;
4. compact only affected sibling sets when ranks become too close;
5. increment the revision and return it with authoritative affected nodes and sibling order.

Each mutation accepts a client-generated idempotency identifier recorded with the bounded audit event. Replaying that identity for the same actor/project/operation returns the committed result. A stale base revision is advisory: the mutation is revalidated against current state and either commits validly or returns a conflict requiring refresh. This prevents stale clients from overwriting hierarchy assumptions silently.

Alternative considered: let the client calculate and PATCH raw parent and floating order fields. It cannot enforce subtree depth, concurrent target changes, permission inheritance, or atomic multi-row lifecycle behavior.

### 4. Expose purpose-built hierarchy reads while preserving Page endpoints

Keep existing Page detail/content endpoints and add project hierarchy contracts that use Page IDs externally while resolving ProjectPage links internally:

- root or direct-child metadata, stable ordered pagination, child presence, current hierarchy revision;
- visible ancestor chain for a selected Page;
- structural mutation with destination parent and before/after placement intent;
- subtree impact preview for archive, restore, copy, bulk move, and permanent removal;
- paginated All Pages metadata including path and depth.

Tree responses contain navigation metadata only: Page ID, title/logo, access, lock and favorite state, project archive state, parent Page ID, sort order, child-presence, and permitted actions. They do not include Page bodies. Collapsed descendants are lazy loaded. Search and breadcrumb paths are computed server-side from the project hierarchy after permission filtering rather than trusted from client ancestry.

The existing Page list remains compatible during rollout. The web application moves to hierarchy and All Pages reads; other consumers are not required to understand the new tree response immediately.

### 5. Enforce effective access across every ancestor

Existing Page access remains public-to-project or owner-only private. A hierarchy node is visible only when the requester can access that Page and every ancestor in the requested project. The API applies this rule to tree reads, direct Page hierarchy context, breadcrumbs, child counts, search, favorites, and mutations.

Every edge must satisfy:

- a child cannot be nominally more visible than its parent;
- a private Page beneath a private parent must remain navigable under the owner-only model, which requires compatible ownership through that private branch;
- changing a Page's access is rejected if it would invalidate any project hierarchy edge or make a descendant branch unreachable to its owner;
- moves never silently change access or ownership.

The response for an unauthorized or cross-tenant identifier follows established non-disclosing behavior. Hidden ancestors are not replaced with titled placeholders because even their titles and child counts are sensitive metadata.

Alternative considered: render accessible descendants beneath an “unavailable parent” placeholder. This leaks topology and produces Pages whose canonical path cannot be navigated.

### 6. Keep hierarchy and document lifecycle responsibilities separate

Archive, restore, and removal in a project operate on ProjectPage links; Page content is deleted only under the established permanent-deletion policy when no active project link remains.

Archiving a subtree assigns one `archive_batch_id` only to nodes active at the time. Restoring that archive root restores nodes with that batch and retains their stored parent/order. A descendant already archived by another operation remains archived. Direct restoration below an archived ancestor is rejected so the active tree cannot contain a child of an archived node.

Single-Page duplicate remains the default and creates a root Page, matching current user expectations. Copy with descendants is explicit and copies Page content and assets through the existing mechanisms while creating new ProjectPage nodes in a transactionally staged operation. A failed async asset copy is recoverable and does not expose a partially navigable subtree.

Permanent subtree removal first previews unique affected links and descendants. Links in other projects survive. Exclusive Pages follow the current archived Page deletion policy after their final link is removed.

### 7. Normalize tree state in the web store

Extend shared types and the project Page store with normalized structures rather than nesting mutable Page objects:

- Page metadata by Page ID;
- ordered child IDs keyed by parent Page ID or root;
- load/error state per branch;
- visible ancestor paths;
- hierarchy revision;
- optimistic mutation snapshots keyed by mutation identity.

Selectors derive visible rows, depth, valid move targets, favorite shortcuts, and All Pages metadata. An optimistic move updates only the affected parent lists; rejection restores its snapshot and refreshes the server-authoritative branch. Incoming newer revisions invalidate affected cached branches.

Expanded IDs are stored under the existing per-user, per-project `ProjectUserProperty.preferences.pages` JSON with a schema version and a bounded list. Preference updates are debounced. Missing, archived, or inaccessible IDs are ignored and eventually pruned.

Alternative considered: store a recursively nested tree in component state and expansion only in local storage. That makes concurrent reconciliation and targeted lazy loading difficult and does not meet cross-session per-user memory.

### 8. Reuse established interaction primitives

The tree uses existing Plane/Propel components and the repository's Atlaskit pragmatic drag-and-drop patterns. It provides explicit before, inside, and after targets with server-derived permission cues. Pointer drag is an accelerator, not the only command: the Page action menu includes a searchable Move dialog supporting root/parent selection and ordered placement.

Desktop Page detail uses a resizable/collapsible Knowledge Base navigation pane alongside the existing document editor; the Page outline remains a separate current-document concept. Narrow viewports use a drawer. Visual indentation is capped after a presentation threshold while semantic `aria-level`, expand state, breadcrumbs, and tooltips preserve depth. Tree keyboard behavior follows the ARIA tree pattern.

### 9. Bound large-tree work

Hierarchy reads fetch roots or one direct-child page at a time and use indexed stable ordering. Opening a deep link fetches its bounded ancestor chain plus the selected branch. All Pages remains server-paginated. Search computes only paths for authorized matches. No hierarchy endpoint loads Page bodies.

Recursive CTEs are bounded to 20 levels and scoped by workspace/project before recursion. Query-count regression tests use representative broad and deep fixtures to detect N+1 behavior; frontend tests assert collapsed branches do not create descendant rows. The server rejects over-depth mutations before writes.

### 10. Test by risk boundary and retain durable verification evidence

The implementation adds executable coverage for the frontend's pure hierarchy utilities and MobX state boundary using existing lightweight tooling. Existing backend test files remain useful regression assets, but adding or running backend pytest is not required for this change's acceptance and no component test framework is introduced.

Development checks cover TypeScript contracts, frontend/store behavior, Python syntax, feature-gate wiring, migration shape, and focused formatting. Because the core requirement depends on real database migration, permissions, API transactions, pointer/keyboard interaction, responsive rendering, and representative hierarchy scale, final acceptance uses the test environment with only affected services deployed.

The primary Agent creates a fresh Tester sub-agent that did not participate in implementation. The Tester verifies only the TMLPLANE-7 knowledge-base capability: migration compatibility; root, nested, and direct-link navigation; remembered expansion and child creation; move, drag-and-drop, concurrency, rollback, and invalid-target handling; breadcrumb/search paths and favorites; subtree archive/restore/copy/removal; private-ancestor non-disclosure and tenant isolation; status indicators and All Pages metadata; feature-gate fallback; query bounds for representative broad/deep trees; and responsive/accessibility behavior. Versions, mentions, export, collaboration, editor behavior, and other unrelated Page directions are outside acceptance. The Tester records durable, sanitized evidence in `verification.md` because of the migration and authorization risk. If acceptance fails, the implementation Agent fixes the affected scope and the same Tester rechecks only the failure and directly affected behavior.

## Risks / Trade-offs

- [Legacy hierarchy data contains cycles or cross-project parents] -> The data migration detects invalid ancestry, promotes only the invalid ProjectPage placement to root, records bounded counts, and never changes Page content.
- [Project-scoped archive behavior differs from the legacy global Page field] -> Migrate legacy archive state to every active link, serve project context from ProjectPage, keep compatibility projection fields during rollout, and cover multi-project behavior explicitly.
- [Permission filtering produces orphaned visible nodes] -> Visibility requires the complete accessible ancestor chain; descendants of an inaccessible node are omitted from every hierarchy projection.
- [Concurrent reorder creates duplicate or unstable ranks] -> Lock the hierarchy revision and affected siblings, use deterministic `(sort_order, id)` ordering, compact atomically, and reconcile clients from returned revisions.
- [Subtree copy spans database and object storage] -> Stage navigation visibility until required database copies commit, use idempotent asset-copy work, expose recoverable failure, and never publish a partial subtree as successful.
- [Large projects make a full tree expensive] -> Load direct children lazily, paginate siblings and All Pages, bound recursion, index project/parent/archive/order, and test query counts.
- [Users cannot use drag-and-drop] -> Keep a fully equivalent Move command and standard keyboard tree navigation.
- [Renaming Pages confuses existing users or integrations] -> Change only the project-facing label, keep URLs and Page terminology in stable APIs where compatibility matters, and preserve existing redirects/navigation state.
- [Rollback after writes loses project placement] -> The first rollback disables the new UI and reads legacy compatibility projections while retaining new ProjectPage columns and data; destructive schema removal is deferred to a later change after the compatibility window.

## Migration Plan

1. Add nullable ProjectPage hierarchy/archive fields, hierarchy state/mutation records, and supporting indexes without removing or changing legacy Page columns.
2. Backfill every active ProjectPage link. Copy valid Page parent placement only when the parent has an active link in the same project; otherwise place the node at root. Copy legacy order and archive state, detect cycles/depth violations, and deterministically normalize affected sibling order.
3. Deploy API reads capable of serving project hierarchy while existing clients continue using Page endpoints. Compare migration counts and invariant checks before enabling mutations.
4. Enable server hierarchy mutations and project-scoped lifecycle behavior, then deploy shared contracts and the web Knowledge Base experience behind a reversible feature gate.
5. Verify migration, authorization, concurrency, and browser behavior in the test environment. Roll out with metrics for hierarchy errors, conflict responses, invalid legacy placements, and query bounds.
6. On rollback, disable the new UI and mutation gate while retaining populated ProjectPage fields. Do not reverse data into ambiguous Page-global hierarchy fields or drop new columns during the incident rollback.
7. Remove legacy Page hierarchy fields only in a later separately reviewed change after all consumers and rollback requirements have expired.

## Open Questions

No blocking product decisions remain for the first release. The implementation may choose the existing repository-consistent endpoint names and rank spacing, but the project-scoped contract, 20-level maximum, permission rules, archive-batch semantics, and compatibility behavior above are fixed.
