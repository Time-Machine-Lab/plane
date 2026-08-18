## 1. Instance Configuration API

- [ ] 1.1 Add Discord enabled, workspace, encrypted Webhook, enabled-event, and member-mapping instance configuration definitions with disabled or empty defaults.
- [ ] 1.2 Implement typed backend parsing and validation for supported event keys, selected workspace membership, unique Plane member mappings, Discord User IDs, and supported Discord Incoming Webhook URLs.
- [ ] 1.3 Add God Mode authorized read and update behavior that masks the stored Webhook, retains it when no replacement is submitted, and encrypts replacements at rest.
- [ ] 1.4 Add the authorized test-message API action using the shared Discord payload and one-attempt transport, returning clear accepted or failed status without changing saved configuration.
- [ ] 1.5 Add focused API tests for authorization, defaults, valid updates, atomic mapping validation, secret masking/retention, URL validation, workspace changes, and test-message success/failure.

## 2. Discord Notification Backend

- [ ] 2.1 Add a Discord integration module containing stable event keys, the normalized notification type, and a registry for event matcher/formatter handlers.
- [ ] 2.2 Implement handlers for work-item creation, newly added assignees computed from old/new `assignee_ids`, and non-completed-to-completed state-group transitions.
- [ ] 2.3 Implement shared work-item context and canonical URL formatting for Discord embeds, including actor, project, identifier/name, and human-readable assignee names.
- [ ] 2.4 Implement manual mapping resolution and a payload builder that generates only mapped `<@USER_ID>` mentions with exact `allowed_mentions.users` values and disables broad mention parsing.
- [ ] 2.5 Implement the bounded one-attempt Discord Webhook transport with sanitized error logging and no retry, history, fallback, or effect on the originating work-item operation.
- [ ] 2.6 Connect the registry to the existing asynchronous work-item activity path with enabled-event and configured-workspace guards.
- [ ] 2.7 Add focused backend tests for all three event matchers, disabled/unselected events, workspace isolation, mapped and unmapped recipients, constrained mentions, embed links, successful delivery, and each single-attempt failure category.

## 3. God Mode Discord Page

- [ ] 3.1 Add typed admin service/store support for reading, updating, and testing the Discord configuration without exposing a stored Webhook value.
- [ ] 3.2 Add the `/god-mode/discord/` route and God Mode sidebar entry using existing admin navigation and authorization patterns.
- [ ] 3.3 Build the configuration form with an enable toggle, one-workspace selector, replacement Webhook input, supported-event checkboxes, Save action, and Send test message action.
- [ ] 3.4 Build the manual member mapping table with a selected-workspace member selector, read-only Plane User ID, Discord User ID input, add/remove behavior, duplicate prevention, and workspace-change validation.
- [ ] 3.5 Add user-facing success, validation, loading, and test failure states plus required localized strings following existing admin application conventions.
- [ ] 3.6 Add focused frontend tests for configuration loading/saving, masked Webhook retention, mapping edits, disabled controls where applicable, authorization routing, and test-message feedback.

## 4. Development Verification

- [ ] 4.1 Run focused backend tests for the affected configuration, activity, and Discord integration modules and fix any failures.
- [ ] 4.2 Run affected admin lint/type checks and focused frontend tests, then fix any failures without expanding to a duplicate full-repository acceptance run.
- [ ] 4.3 Review changed code for secret leakage, unconstrained Discord mentions, unintended retries, and notifications escaping the configured workspace.

## 5. Deployment And Independent Acceptance

- [ ] 5.1 Run `scripts/test/deploy-test.ps1` once to prepare and deploy the completed runtime change, relying on the script's owned environment preparation and checks.
- [ ] 5.2 Have an independent Tester verify basic availability and the OpenSpec scenarios for administrator authorization/configuration, manual mappings, Webhook masking and validation, test messages, all three events, mention behavior, disabled/unselected events, single-attempt failure behavior, and workspace isolation using the persistent test environment.
- [ ] 5.3 Record concise pass/fail evidence for every required scenario in `verification.md`; if acceptance finds a defect, fix it, redeploy through the same prescribed script, and have the same Tester retest the failed scenario and necessary nearby regression before completion.
