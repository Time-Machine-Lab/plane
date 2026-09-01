# project-page-hierarchy Specification

## Purpose

TBD - created by archiving change add-project-page-hierarchy. Update Purpose after archive.

## Requirements

### Requirement: Existing Pages become the project Knowledge Base

The system SHALL present the existing project Pages capability as Knowledge Base navigation while retaining Page as the document entity and preserving existing Page identifiers, content, versions, collaboration data, favorites, and `/pages/...` links.

#### Scenario: Existing project opens after the upgrade

- **WHEN** a member opens Knowledge Base in a project containing existing Pages
- **THEN** every existing active project Page is available without content loss or manual migration, previously flat Pages remain roots, and valid same-project legacy nesting is preserved

#### Scenario: Existing Page link is opened

- **WHEN** a user follows an authorized pre-upgrade `/pages/{page_id}` link
- **THEN** the same Page opens in its Knowledge Base context and the surrounding hierarchy is available

#### Scenario: Page is linked to multiple projects

- **WHEN** the same Page has active links in two projects
- **THEN** its parent, sibling order, archive state, and path in one project do not change its position or archive state in the other project

### Requirement: Project-scoped hierarchy remains structurally valid

The system SHALL represent each active ProjectPage link as exactly one node whose parent is either null or another active node in the same workspace and project, with deterministic sibling ordering and a maximum supported depth of 20 levels.

#### Scenario: Root and child nodes are returned

- **WHEN** the hierarchy contains root Pages and nested Pages
- **THEN** each visible node is returned once with its project-scoped parent, order, child-presence, and Page metadata

#### Scenario: User attempts to create a cycle

- **WHEN** a user attempts to move a node under itself or any of its descendants
- **THEN** the server rejects the mutation with a stable validation error and leaves the hierarchy unchanged

#### Scenario: User selects a parent from another project or workspace

- **WHEN** a hierarchy mutation references a parent without an active ProjectPage link in the requested project and workspace
- **THEN** the server rejects the mutation without disclosing unauthorized node metadata

#### Scenario: Move would exceed the supported depth

- **WHEN** moving a subtree would place any node deeper than level 20
- **THEN** the server rejects the complete move and returns the supported-depth reason

#### Scenario: Sibling order values require compaction

- **WHEN** repeated insertions no longer leave a usable position between adjacent siblings
- **THEN** the server rebalances that sibling set atomically and returns the authoritative order without changing parent relationships

### Requirement: Users can browse and resume a multi-level page tree

The system SHALL provide a tree-first Knowledge Base view that supports expanding and collapsing branches, opens the selected Page without losing tree context, and persists expanded node identifiers per user and project.

#### Scenario: User expands and collapses branches

- **WHEN** a user expands or collapses a node with children
- **THEN** only that branch changes visibility and the selected Page and other expanded branches remain stable

#### Scenario: User returns to the project

- **WHEN** a user revisits the same project on another authenticated session after changing expanded branches
- **THEN** the system restores accessible expanded nodes from that user's project preferences and ignores stale or inaccessible node identifiers

#### Scenario: Deep Page link is opened

- **WHEN** a user opens an authorized nested Page directly
- **THEN** the system loads and expands its visible ancestor chain, selects the Page, and does not require the user to expand each ancestor manually

#### Scenario: Collapsed branch contains many descendants

- **WHEN** a project has a large collapsed subtree
- **THEN** the initial tree response and rendered tree omit that subtree's unloaded descendants while still indicating that the node has children

#### Scenario: Tree metadata cannot be loaded

- **WHEN** hierarchy retrieval fails
- **THEN** the Knowledge Base shows a retryable error without discarding the currently open Page content or presenting an empty tree as authoritative

### Requirement: Authorized users can create child Pages in context

The system SHALL allow a user with Page creation permission and access to the intended parent to create a new Page at the root or as the last child of that parent and immediately edit its title.

#### Scenario: Create a child from a public Page

- **WHEN** an authorized member invokes Add child Page on a public Page
- **THEN** a new Page is created as its last child, the parent branch expands, and the new Page enters title editing

#### Scenario: Create a child under a private Page

- **WHEN** the owner of a private Page creates a child under it
- **THEN** the child is created with compatible private access and ownership so the branch remains navigable

#### Scenario: Unauthorized child creation

- **WHEN** a user cannot access the parent or lacks Page creation permission
- **THEN** the child action is unavailable and a direct request is rejected without creating either a Page or ProjectPage link

#### Scenario: Child creation partially fails

- **WHEN** Page creation succeeds internally but hierarchy placement cannot be committed
- **THEN** the transaction rolls back and no orphaned Page or hierarchy node remains

### Requirement: Authorized users can reorder and reparent a subtree

The system SHALL allow a Page owner or project administrator to move a node before or after a sibling, into another Page, or to the root through drag-and-drop and a keyboard-accessible Move command, with the node and all descendants retaining their relative structure.

#### Scenario: Reorder within the same parent

- **WHEN** an authorized user drops a node between two siblings
- **THEN** the server persists the new deterministic sibling order and the tree reflects the authoritative result

#### Scenario: Reparent a subtree

- **WHEN** an authorized user moves a Page containing descendants under a valid target Page
- **THEN** the Page receives the new project-scoped parent and all descendants retain their internal parents and order

#### Scenario: Move a node to the root

- **WHEN** an authorized user chooses the Knowledge Base root as the destination
- **THEN** the node becomes a root node at the requested position with its descendants intact

#### Scenario: Invalid drop target

- **WHEN** a user hovers or drops on a target that would violate project scope, depth, cycle, archive, or visibility rules
- **THEN** the UI marks the target invalid, the server independently rejects a forged request, and the original hierarchy remains visible

#### Scenario: Move request fails

- **WHEN** the server rejects or cannot persist an optimistic move
- **THEN** the client restores the last authoritative structure and presents an actionable error

### Requirement: Concurrent hierarchy changes converge on server authority

The system SHALL serialize mutations that affect the same sibling sets, apply each accepted mutation atomically, and return an authoritative hierarchy revision and affected ordering so clients can reconcile concurrent edits.

#### Scenario: Two users reorder the same sibling set

- **WHEN** two valid reorder requests overlap
- **THEN** each committed transaction leaves a valid deterministic order and stale clients reconcile to the latest server revision without duplicated or missing nodes

#### Scenario: Target changes before a pending move commits

- **WHEN** a target is moved, archived, removed, or becomes inaccessible before another user's move is committed
- **THEN** the pending mutation either evaluates against the current valid structure or is rejected atomically without partial parent or order changes

#### Scenario: Duplicate mutation is retried

- **WHEN** a client retries the same hierarchy mutation using the same idempotency identity
- **THEN** the server returns the already committed result without applying the move twice

### Requirement: Page locations are visible through safe breadcrumbs and paths

The system SHALL show the complete accessible ancestor path above an open Page and alongside Page search results, and selecting an ancestor SHALL navigate to that Page in the same project Knowledge Base.

#### Scenario: Nested Page is open

- **WHEN** a user opens `Technical documentation / Backend / Permission model`
- **THEN** the header displays each accessible segment in order and each ancestor segment is navigable

#### Scenario: Search returns Pages with duplicate names

- **WHEN** multiple accessible Pages share a title
- **THEN** each search result includes its project-scoped path so the Pages can be distinguished

#### Scenario: Search selects a nested Page

- **WHEN** a user selects a nested search result
- **THEN** the Page opens and its visible ancestor branch is expanded and selected in the tree

#### Scenario: Path contains an inaccessible ancestor

- **WHEN** a Page or ancestor is not accessible to the requesting user
- **THEN** the Page is excluded from tree, direct hierarchy retrieval, breadcrumbs, and search results, and no hidden title or path segment is disclosed

### Requirement: Favorites provide shortcuts without changing hierarchy

The system SHALL show accessible favorite Pages in a pinned Favorites section while keeping each favorite's single canonical location in the page tree.

#### Scenario: User favorites a nested Page

- **WHEN** a user favorites an accessible nested Page
- **THEN** a shortcut appears in Favorites and the Page remains under its existing parent and order

#### Scenario: Favorite shortcut is opened

- **WHEN** a user selects a favorite shortcut
- **THEN** the canonical Page opens and its accessible ancestor chain expands in the tree

#### Scenario: Favorite becomes archived or inaccessible

- **WHEN** a favorite Page is archived in the project or the user loses effective access
- **THEN** it is omitted from active Favorites without leaking its title and its stored favorite does not corrupt the hierarchy

### Requirement: Tree nodes communicate Page state

The system SHALL display private, locked, and archived states with accessible names and consistent visual indicators without using those client indicators as authorization enforcement.

#### Scenario: Active node has multiple states

- **WHEN** an accessible Page is both private and locked
- **THEN** its tree node exposes both states visually and to assistive technology without obscuring its title or controls

#### Scenario: Archived hierarchy is viewed

- **WHEN** a user opens the archived management context
- **THEN** archived nodes and their archived ancestry are distinguishable and active-tree drag or edit controls are unavailable

#### Scenario: Client state is stale

- **WHEN** a client displays an editable or public indicator after permissions or lock state changed
- **THEN** the server still enforces the current authoritative state and the client refreshes the affected metadata after rejection

### Requirement: All Pages remains a flat management view

The system SHALL retain an All Pages view that lists every accessible project Page independently of tree expansion and supports existing filters and sorting plus path, depth, owner, visibility, lock, archive, and update metadata.

#### Scenario: Manager opens All Pages

- **WHEN** an authorized user opens All Pages
- **THEN** accessible root and nested Pages appear as individual rows with their current project paths and management metadata

#### Scenario: User filters or sorts All Pages

- **WHEN** a user applies supported filters or sorting
- **THEN** the flat result is filtered and ordered without changing hierarchy parent or sibling order

#### Scenario: User performs a bulk hierarchy action

- **WHEN** an authorized user selects multiple valid Pages for move, archive, or restore
- **THEN** the system previews the affected unique nodes and descendants, rejects overlapping or invalid selections, and applies the confirmed operation atomically

#### Scenario: Page list is large

- **WHEN** All Pages contains more rows than one response limit
- **THEN** the view uses stable server pagination and does not require loading Page bodies or the entire hierarchy to manage a page

### Requirement: Effective visibility follows the ancestor chain

The system SHALL authorize a hierarchy node only when the user can access its Page and every ancestor in the requested project, SHALL allow a child to be more restrictive than its parent, and SHALL reject an edge or access change that makes a child more visible than its parent or makes the branch inaccessible to all intended owners.

#### Scenario: Private child under a public parent

- **WHEN** a public parent has a private child owned by the current user
- **THEN** the owner can navigate the full branch while other project members see the public parent but receive no child title, count disclosure, breadcrumb, or search result for the private Page

#### Scenario: Public child under a private parent

- **WHEN** a request attempts to create, move, or make a Page public beneath a private parent
- **THEN** the server rejects the complete request with a visibility-inheritance error

#### Scenario: Private child owner cannot access the intended private ancestor

- **WHEN** a private Page would be placed under a private ancestor owned by another user
- **THEN** the server rejects the placement because the resulting branch would not be navigable under the existing owner-only private access model

#### Scenario: Parent visibility is tightened

- **WHEN** making a parent private would leave any descendant more visible or inaccessible to its owner
- **THEN** the server rejects the access change, identifies that descendant compatibility must be resolved, and changes no access values

#### Scenario: Page is moved into a more restrictive valid branch

- **WHEN** an authorized user moves a compatible private subtree under a private parent
- **THEN** the move succeeds without silently changing Page ownership or access

#### Scenario: Unauthorized hierarchy request is forged

- **WHEN** a user requests another workspace's, another project's, inactive, private, or otherwise inaccessible node by identifier
- **THEN** the server returns the established non-disclosing not-found or permission response and performs no mutation

### Requirement: Archive and restore preserve subtree intent per project

The system SHALL archive a selected ProjectPage node and all of its active descendants in the requested project as one atomic operation, preserve links in other projects, and restore only nodes archived by the corresponding subtree operation while maintaining their original hierarchy.

#### Scenario: Parent subtree is archived

- **WHEN** an authorized owner or administrator archives a parent with active descendants
- **THEN** the parent and every active descendant become archived in that project, disappear from the active tree, and retain parent and sibling order for restoration

#### Scenario: Descendant was already archived

- **WHEN** a parent is archived after one of its descendants was archived by an earlier operation
- **THEN** restoring the parent does not implicitly restore the previously archived descendant

#### Scenario: Archived parent is restored

- **WHEN** an authorized user restores a subtree archive root
- **THEN** nodes archived by that operation return atomically to their preserved locations unless current validation makes restoration impossible

#### Scenario: User attempts to restore a child beneath an archived ancestor

- **WHEN** a user directly restores a descendant while an ancestor remains archived
- **THEN** the server rejects the restore and offers restoration from the highest required archived ancestor

#### Scenario: Descendant is linked to another project

- **WHEN** a subtree is archived in project A and one of its Pages is also linked in project B
- **THEN** the Page remains active at its independent project B location

### Requirement: Copy and permanent removal make subtree scope explicit

The system SHALL keep single-Page duplication as the default, offer an explicit copy-with-descendants operation, and require a descendant-aware confirmation before permanently removing an archived node from a project.

#### Scenario: Duplicate only the selected Page

- **WHEN** a user invokes the existing duplicate action without selecting descendants
- **THEN** one new root-level Page is created with supported Page content and no children are copied

#### Scenario: Copy a subtree

- **WHEN** an authorized user confirms Copy Page and sub-pages
- **THEN** the system creates a structurally equivalent subtree with new Page identifiers, preserved relative order, compatible access, and supported Page content

#### Scenario: Subtree copy fails

- **WHEN** any required Page, asset, ProjectPage link, or hierarchy placement cannot be copied
- **THEN** the copy is rolled back or marked as a recoverable failed operation without exposing a partially navigable subtree

#### Scenario: Permanently remove an archived parent

- **WHEN** an authorized user requests permanent removal of an archived node with descendants
- **THEN** the confirmation reports the unique affected descendant count and the operation removes the selected project links as one subtree

#### Scenario: Removed Page remains linked elsewhere

- **WHEN** a removed subtree contains a Page with another active project link
- **THEN** the Page content and its other project locations survive, while a Page with no remaining active links follows the existing permanent-deletion policy

### Requirement: Hierarchy interactions remain accessible and responsive

The system SHALL provide keyboard-operable tree navigation and commands, visible focus, named controls, screen-reader tree semantics, and layouts that remain usable on supported desktop and narrow viewports.

#### Scenario: Keyboard user navigates the tree

- **WHEN** focus is in the page tree
- **THEN** standard tree keys move among visible nodes, expand or collapse branches, and open a Page without requiring pointer drag-and-drop

#### Scenario: Keyboard or touch user moves a Page

- **WHEN** drag-and-drop is unavailable or unsuitable
- **THEN** the Move command provides a searchable valid-parent picker and ordered placement choices with the same server validation

#### Scenario: Knowledge Base is used on a narrow viewport

- **WHEN** the viewport cannot display the project tree, editor, and Page outline together
- **THEN** hierarchy navigation is available in a non-overlapping drawer, the current Page remains readable, and controls and text remain within their containers

#### Scenario: Hierarchy is visually deep

- **WHEN** a Page is nested beyond the configured visual indentation threshold
- **THEN** the UI caps indentation while preserving depth through expand controls, breadcrumbs, labels, and accessible hierarchy levels

### Requirement: Hierarchy operations are observable and auditable

The system SHALL record actor, project, affected root, old and new parent, operation identity, descendant count, and outcome for structural and subtree lifecycle mutations without recording Page content or unauthorized titles.

#### Scenario: Hierarchy mutation succeeds

- **WHEN** a create, move, reorder, archive, restore, subtree copy, or removal operation commits
- **THEN** a structured audit event can be correlated with the resulting hierarchy revision

#### Scenario: Hierarchy mutation fails validation

- **WHEN** a structural operation is rejected
- **THEN** diagnostic logs contain bounded identifiers and the stable failure category without secrets, Page bodies, or inaccessible path titles
