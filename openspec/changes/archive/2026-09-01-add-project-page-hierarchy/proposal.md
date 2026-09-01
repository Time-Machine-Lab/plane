## Why

Project Pages are currently presented as a flat collection, which becomes difficult to navigate and govern as project documentation grows. Upgrade the existing Pages experience into a project knowledge base with a stable page hierarchy while preserving the current editor, collaboration, versioning, links, and document ownership model.

## What Changes

- Rename the project-facing Pages navigation experience to Knowledge Base while retaining Page as the underlying document entity and preserving existing `/pages/...` URLs.
- Add a multi-level project page tree with expand, collapse, per-user expansion memory, favorites, status indicators, and complete page breadcrumbs.
- Allow authorized users to create a child page from any page and reorder or reparent pages through drag-and-drop and an accessible move command.
- Make hierarchy operations subtree-aware: moving, archiving, restoring, copying when requested, and permanent deletion confirmation account for descendants.
- Show a visible, permission-filtered page path in search results and provide a flat All Pages management view for sorting, filtering, and bulk operations.
- Define inherited page visibility rules: a child may be more restrictive than its ancestors but may not be more visible; inaccessible nodes and path segments are not disclosed.
- Store parent, sibling order, and project archive state in the project-page relationship so a Page linked to multiple projects can occupy a different location and lifecycle state in each project knowledge base.
- Migrate existing active project-page links without changing Page IDs, content, ownership, or links: preserve valid same-project legacy nesting and place previously flat or invalid legacy placements at the root.
- Add focused executable coverage for frontend tree and store logic, and independently verify hierarchy migration, authorization, transactions, subtree lifecycle, accessibility, responsive behavior, and rollout controls in the test environment.

### Non-goals

- Introduce a second KnowledgeBase document entity, a separate editor, or an independent knowledge-base membership system.
- Add standalone folders; an empty Page may be used as a section or index page.
- Add cross-project knowledge bases, public branded documentation sites, backlinks, templates, content review reminders, or knowledge-health reporting in this change.
- Replace the current Page outline, version history, real-time content collaboration, export, or All Pages filtering model beyond the hierarchy integration required here.

## Capabilities

### New Capabilities

- `project-page-hierarchy`: Project-scoped hierarchical navigation, ordering, child creation, path presentation, subtree lifecycle operations, permission inheritance, migration compatibility, and knowledge-base management behavior for existing Pages.

### Modified Capabilities

None.

## Impact

- `apps/api`: ProjectPage hierarchy schema and migration, hierarchy query and mutation contracts, subtree lifecycle handling, permission enforcement, search path projection, and API regression tests.
- `apps/web`: Knowledge Base navigation, tree and management views, MobX hierarchy state, drag-and-drop and keyboard-accessible move flows, breadcrumbs, search paths, responsive behavior, and focused component/store tests.
- `packages/types`, `packages/services`, `packages/constants`, `packages/utils`, and `packages/i18n`: shared hierarchy contracts, service methods, tree utilities, navigation labels, and localized user-facing text as needed.
- Existing Page URLs, IDs, content, versions, favorites, and project links remain compatible. Existing links become root nodes during migration; rollback must not destroy hierarchy data before the compatibility window is complete.
- Authorization and tenant isolation are high-risk boundaries: every hierarchy read and mutation remains scoped to an active ProjectPage link in the requested workspace and project, and unauthorized ancestor metadata must not be exposed.
- The change affects the web and API runtimes and requires database migration. No new external dependency, service, license boundary, or third-party integration is expected.
- Applicable standards: `docs/spec/general-development.md`, `frontend-development.md`, `backend-development.md`, `shared-packages-development.md`, `testing-quality.md`, `test-environment.md`, and `module-structure.md`.
