## 1. Prerequisite And Event Configuration

- [x] 1.1 Confirm `add-discord-daily-task-reminders` is completed and archived, then base this implementation on its final event allowlist, shared types, God Mode options, tests, and main specification.
- [x] 1.2 Add `user.mentioned` and `work_item.comment_activity` to the backend supported-event allowlist and shared Discord event-key type while retaining every existing event including `work_item.daily_reminder`.
- [x] 1.3 Add localized "提到了你" and "任务收到新评论" options to the existing God Mode Discord event controls using the repository translation workflow.
- [x] 1.4 Update focused configuration assertions so both new keys are independently opt-in, unsupported keys remain rejected, and existing saved configurations remain compatible.

## 2. Mention Parsing And Recipient Classification

- [x] 2.1 Extract neutral rich-text user-mention parsing and old/new diffing helpers and migrate existing Plane notification logic to use them without changing current in-app or email behavior.
- [x] 2.2 Implement safe excerpt generation that resolves Plane mention display names, selects relevant description/Page context, strips unsupported markup, escapes Discord formatting, and visibly truncates at 300 characters.
- [x] 2.3 Implement the typed interaction recipient classifier for comment creation, comment edits, work-item descriptions, and Plane Pages, including actor exclusion, event-time assignee snapshots, deduplication, and no cross-event fallback.
- [x] 2.4 Add focused tests for malformed rich text, unchanged and newly added mentions, mixed assignee/non-assignee classification, self-mentions, duplicate recipients, and safe bounded excerpts.

## 3. Work-Item Comment And Description Events

- [x] 3.1 Capture comment ID, actor, timestamp, origin, content, and the current assignee snapshot when scheduling Discord processing for work-item comment creation and editing.
- [x] 3.2 Generate one comment card for eligible mapped assignees on comment creation and suppress the card when no mapped recipient remains.
- [x] 3.3 On comment edits, generate a comment-update card only for newly mentioned current assignees and do not renotify other assignees or existing mentions.
- [x] 3.4 Generate one mention card for newly mentioned non-assignees in comments and for every eligible newly mentioned member in work-item descriptions, respecting each independent event toggle.
- [x] 3.5 Build Chinese comment and mention cards following `docs/spec/discord-card-design.md`, including actor, work item, source location, safe excerpt, event timestamp, canonical task link, and exact `#comment-{comment_id}` links where applicable.
- [x] 3.6 Add focused event and payload tests for ordinary comments, unassigned work, actor-as-assignee, mixed mentions, independent toggles, assignment changes before delivery, comment edits, description mentions, exact links, and at-most-two-card behavior.

## 4. Public Plane Page Mention Events

- [x] 4.1 Pass actor ID, project route context, and an explicit operation kind from direct Plane Page creation/edit entry points into Page transaction processing without enabling notifications for duplicate, import, synchronization, or restore flows.
- [x] 4.2 Use successful atomic creation of a `PageLog` user-mention transaction as the notification claim so repeated saves and duplicate tasks cannot resend the same Page mention.
- [x] 4.3 Before dispatch, enforce configured-workspace, public-access, active-member, project-link, actor-exclusion, enabled-event, and mapped-recipient checks.
- [x] 4.4 Generate one Chinese mention card per direct Page operation with deduplicated mapped recipients, actor, Page and project context, safe surrounding excerpt, event timestamp, and a Page-level link.
- [x] 4.5 Add focused tests for direct creation/edit, multiple mentions, repeated saves, duplicate task invocation, private Pages, other workspaces, invalid project context, self-mentions, unmapped members, and silent duplicate/import/restore operations.

## 5. Shared Delivery Safety And Development Checks

- [x] 5.1 Route interaction cards through the existing member mapping and bounded single-attempt Webhook transport with exact top-level mentions, empty broad parsing, sanitized failures, no retry, and no effect on the source Plane operation.
- [x] 5.2 Verify offline payloads contain no raw mention tags, internal IDs, private Page content, unsafe Discord mentions, or duplicate recipients and remain within the single-event card contract.
- [x] 5.3 Run only the necessary affected backend, admin, shared-type, translation, and focused automated checks, and confirm existing lifecycle events and daily reminders retain their prior event keys and delivery paths.

## 6. Independent Tester Verification

- [x] 6.1 After implementation and development checks, have the primary Agent create a new Tester sub-agent that did not participate in implementation and instruct it to leave product code unchanged.
- [x] 6.2 Have the Tester independently verify recipient classification, mixed-comment deduplication, comment edits, description mentions, public/private Plane Page behavior, event toggles, safe cards and links, workspace isolation, and mapped mention constraints using the least expensive sufficient static, offline, local, or test-environment method.
- [x] 6.3 Have the Tester check only the necessary adjacent regression that existing lifecycle notifications and daily task reminders retain their prior configuration and payload paths; deploy affected services only if the core behavior cannot be established otherwise.
- [x] 6.4 If verification fails, fix the affected scope and return it to the same Tester for the failed behavior and necessary adjacent regression only; do not complete or archive the change until verification passes.
