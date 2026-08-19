## 1. Event Configuration

- [ ] 1.1 Add `work_item.daily_reminder` to the backend supported-event allowlist and shared Discord event-key type while preserving existing saved configurations as opt-in.
- [ ] 1.2 Add the localized “daily task brief” option and fixed workspace-timezone 08:00 description to the existing God Mode Discord event controls, following the repository translation workflow.
- [ ] 1.3 Update focused configuration contract assertions so authorized saves accept the new key and unsupported keys remain rejected.

## 2. Reminder Collection And Grouping

- [ ] 2.1 Add a typed daily-reminder collector that derives the local date from the configured workspace timezone and queries only eligible active work items with `start_date <= local_date`.
- [ ] 2.2 Eagerly load project, state, and assignee data and explicitly exclude completed, cancelled, missing-start-date, draft, triage, archived, archived-project, and other-workspace items.
- [ ] 2.3 Group each eligible work item into every assignee group or the unassigned group and implement the confirmed stable date-risk, priority, date, and identifier ordering.

## 3. Task-Brief Cards And Delivery

- [ ] 3.1 Add a task-brief representation separate from the existing single-event notification contract, reusing safe URL, text escaping, badge, mapping, and Webhook helpers where applicable.
- [ ] 3.2 Build the Chinese group summary and one Embed per work item with linked title, project, priority, state, task-time range, semantic risk color, and the correct assigned or unassigned `喵~` footer.
- [ ] 3.3 Implement Discord-limit-aware packing that preserves every ordered task, labels continuation parts, and emits the minimum payload sequence supported by the chosen bounded Embeds.
- [ ] 3.4 Resolve only the group's mapped assignee, include that mention and exact allowlist in the first payload, and keep continuation, unmapped, and unassigned payload mention allowlists empty.
- [ ] 3.5 Send every generated payload through the existing bounded single-attempt transport, continue independent remaining attempts after one failure, and keep logs free of Webhook URLs and task content.

## 4. Scheduling And Duplicate Protection

- [ ] 4.1 Add a Discord reminder Celery task and periodic Beat entry that checks the configured workspace at a short interval and proceeds only during its local 08:00 hour when the integration and event are enabled.
- [ ] 4.2 Atomically claim a transient `workspace + local date` cache key before collection, fail closed when the claim mechanism is unavailable, and prevent later ticks from regenerating an attempted day's brief.
- [ ] 4.3 Ensure an empty collection exits without Webhook delivery and scheduled execution uses the configured application base URL for work-item links.

## 5. Focused Regression Coverage And Development Checks

- [ ] 5.1 Add focused backend tests for workspace-local 08:00 boundaries, once-per-date claiming, disabled configuration, empty results, and single-attempt partial failure behavior using a mocked Discord transport.
- [ ] 5.2 Add focused collector tests for inclusion boundaries, excluded state/object categories, workspace isolation, multi-assignee duplication, unassigned grouping, and deterministic ordering without N+1 query regression.
- [ ] 5.3 Add focused payload tests for required Chinese task information, risk variants, `喵~` footers, Discord limits, continuation parts, exact first-part mentions, and empty mention allowlists elsewhere.
- [ ] 5.4 Run only the necessary affected backend and admin development checks and inspect representative generated payloads offline, without issuing a real Discord request.

## 6. Independent Tester Verification

- [ ] 6.1 After implementation and development checks, have the primary Agent create a new Tester sub-agent that did not participate in implementation and instruct it to leave product code unchanged.
- [ ] 6.2 Have the Tester independently verify the reminder goal with the least expensive sufficient static, offline, local, or test-environment method: confirmed task selection, grouping, order, workspace-local schedule, no-message empty result, card contents, pagination, mention safety, and once-per-date behavior.
- [ ] 6.3 Have the Tester check only the necessary adjacent regression that existing single-event Discord notifications still use their prior triggers and payload path; do not perform a real Discord call without explicit user authorization.
- [ ] 6.4 If verification fails, fix the affected implementation and return it to the same Tester for the failed scope and necessary adjacent behavior only; do not complete or archive the change until the Tester passes it.
