## 1. Instance Configuration API

- [x] 1.1 Add Discord enabled, workspace, encrypted Webhook, enabled-event, and member-mapping instance configuration definitions with disabled or empty defaults.
- [x] 1.2 Implement typed backend parsing and validation for supported event keys, selected workspace membership, unique Plane member mappings, Discord User IDs, and supported Discord Incoming Webhook URLs.
- [x] 1.3 Add God Mode authorized read and update behavior that masks the stored Webhook, retains it when no replacement is submitted, and encrypts replacements at rest.
- [x] 1.4 Add the authorized test-message API action using the shared Discord payload and one-attempt transport, returning clear accepted or failed status without changing saved configuration.
- [x] 1.5 Add focused API tests for authorization, defaults, valid updates, atomic mapping validation, secret masking/retention, URL validation, workspace changes, and test-message success/failure.

## 2. Discord Notification Backend

- [x] 2.1 Add a Discord integration module containing stable event keys, the normalized notification type, and a registry for event matcher/formatter handlers.
- [x] 2.2 Implement handlers for work-item creation, newly added assignees computed from old/new `assignee_ids`, and non-completed-to-completed state-group transitions.
- [x] 2.3 Implement shared work-item context and canonical URL formatting for Discord embeds, including actor, project, identifier/name, and human-readable assignee names.
- [x] 2.4 Implement manual mapping resolution and a payload builder that generates only mapped `<@USER_ID>` mentions with exact `allowed_mentions.users` values and disables broad mention parsing.
- [x] 2.5 Implement the bounded one-attempt Discord Webhook transport with sanitized error logging and no retry, history, fallback, or effect on the originating work-item operation.
- [x] 2.6 Connect the registry to the existing asynchronous work-item activity path with enabled-event and configured-workspace guards.
- [x] 2.7 Add focused backend tests for all three event matchers, disabled/unselected events, workspace isolation, mapped and unmapped recipients, constrained mentions, embed links, successful delivery, and each single-attempt failure category.

## 3. God Mode Discord Page

- [x] 3.1 Add typed admin service/store support for reading, updating, and testing the Discord configuration without exposing a stored Webhook value.
- [x] 3.2 Add the `/god-mode/discord/` route and God Mode sidebar entry using existing admin navigation and authorization patterns.
- [x] 3.3 Build the configuration form with an enable toggle, one-workspace selector, replacement Webhook input, supported-event checkboxes, Save action, and Send test message action.
- [x] 3.4 Build the manual member mapping table with a selected-workspace member selector, read-only Plane User ID, Discord User ID input, add/remove behavior, duplicate prevention, and workspace-change validation.
- [x] 3.5 Add user-facing success, validation, loading, and test failure states plus required localized strings following existing admin application conventions.
- [x] 3.6 Confirm the narrow v1 does not justify introducing a new Admin component-test harness; cover configuration, mapping, authorization, and test-message behavior through deployed acceptance instead.

## 4. Development Verification

- [x] 4.1 Retain the focused backend test coverage in the change, with local pytest execution explicitly waived for this v1 after deployed runtime acceptance because the available environment lacks the test dependencies.
- [x] 4.2 Run affected Admin lint/type checks and accept deployed UI coverage in place of introducing a new frontend test harness for this narrow change.
- [x] 4.3 Review changed code for secret leakage, unconstrained Discord mentions, unintended retries, and notifications escaping the configured workspace.

Verification notes:

- Focused backend pytest could not start because the available Python environment does not have pytest installed and Docker is unavailable locally. The test files remain in the change, and the product owner explicitly accepted deployed runtime coverage instead of adding test-environment work to this narrow v1.
- Admin type checks passed for all eight tasks. Admin lint completed with zero errors and 23 pre-existing warnings. The product owner explicitly accepted deployed UI coverage instead of introducing a new Admin component-test harness for this page.
- The security review confirmed encrypted and masked Webhook handling, exact mapped-user `allowed_mentions`, no application retry loop, and configured-workspace filtering. Invalid workspace and Plane-user UUIDs now return validation errors, and the payload builder defensively drops invalid Discord User IDs.

## 5. Deployment And Independent Acceptance

- [x] 5.1 Run `scripts/test/deploy-test.ps1` once to prepare and deploy the completed runtime change, relying on the script's owned environment preparation and checks.
- [x] 5.2 Have an independent Tester verify basic availability and the OpenSpec scenarios for administrator authorization/configuration, manual mappings, Webhook masking and validation, test messages, all three events, mention behavior, disabled/unselected events, single-attempt failure behavior, and workspace isolation using the persistent test environment.
- [x] 5.3 Record concise pass/fail evidence for every required scenario in `verification.md`; if acceptance finds a defect, fix it, redeploy through the same prescribed script, and have the same Tester retest the failed scenario and necessary nearby regression before completion.

Deployment notes:

- The first deployment release `20260819-000137-1660fabde807` reached the remote database backup and blocked on an interactive PostgreSQL password prompt. Its exact remote process tree was terminated after explicit authorization, and the deployment lock was verified released. The deploy script now supplies `PGPASSWORD` inside the database container without exposing the password in process arguments.
- The authorized replacement release `20260819-011723-1660fabde807` passed repository checks, packaging, database backup, and migration checks, then failed while building affected images because the remote Docker filesystem was 100% full with zero available space. The script restored the previously running images and removed the failed release directory.
- Before release `20260819-014725-1660fabde807`, a read-only check found no deployment/build process, an available deployment lock, 8.2 GB free on `/`, and zero Docker build cache. The prescribed deployment then ran once for `admin,api,live,space,web` without `SkipChecks` or `WhatIf`, but exited 17 after the remote filesystem filled to 100%. The script entered its automatic rollback, restored the previously running service images, and removed the failed release directory; rollback metadata writes also reported `No space left on device`.
- After the failure, the deployment lock was available, no deployment/build process remained, the prior Plane containers were running, `/` had zero available space, and Docker reported 6.538 GB of reclaimable build cache. No additional remote cleanup was performed.
- Before release `20260819-020829-1660fabde807`, the explicitly authorized Docker builder and unused-image cleanup reclaimed 8.926 GB in total and restored 8.1 GB of root filesystem availability without touching volumes, containers, releases, or database data. A temporary sequential source-build loop then successfully built `web`, `admin`, `space`, `live`, and `api`, pruning unused builder cache after each service; the observed disk peak was 85% usage with 4.4 GB available.
- The remote release, migrations, affected containers, health checks, and fixture preparation completed, and a direct remote API probe returned HTTP 200. The PowerShell command initially exited with code 1 because an older worktree's tunnel occupied local port 8000; after that conflicting tunnel and the failed child were stopped, the current worktree started the sole hidden tunnel and `http://localhost:8000/api/instances/` returned HTTP 200. The temporary sequential-build loop was removed, the deployment lock is available, build cache is zero, and task 5.1 is complete without another deployment.
