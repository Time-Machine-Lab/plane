## 1. Shared Card Contract

- [x] 1.1 Extend the existing normalized Discord notification and payload builder to support source text, up to three structured fields, footer text, and a real event timestamp while preserving recipient IDs and the linked title.
- [x] 1.2 Add small colocated helpers/constants for approved event colors, fixed icon labels, semantic dots, safe inline-code badge values, and missing metadata handling according to `docs/spec/discord-card-design.md`.
- [x] 1.3 Preserve top-level mapped mentions and exact `allowed_mentions.users` behavior independently of all Embed content.

## 2. Existing Event Cards

- [x] 2.1 Restyle `work_item.created` with the Chinese linked task title, Plane/project source, actor description, and status/priority/assignee property bar.
- [x] 2.2 Restyle `work_item.assignee_added` with the Chinese linked task title, actor description, status/priority/deadline property bar, semantic urgency, and concise reminder footer.
- [x] 2.3 Restyle `work_item.completed` with the Chinese linked task title, actor description, assignee/completed-status/completion-time property bar, and completion color.
- [x] 2.4 Restyle the God Mode connection-test notification with the same single-event hierarchy and no member mention.
- [x] 2.5 Confirm event matching, configured-workspace filtering, recipient selection, Webhook transport, and failure behavior remain unchanged.

## 3. Development Checks

- [x] 3.1 Update only existing Discord test fixtures or assertions that must reflect the normalized notification and payload shape; do not add automated test cases or a new test harness.
- [x] 3.2 Inspect the complete diff and generated payload samples to ensure the previously supplied Webhook URL and test subarea ID do not appear anywhere and no validation command sends a Discord message.

## 4. Independent Acceptance

- [x] 4.1 Have an independent Tester verify two non-network journeys from generated payload output: the three production work-item cards follow the approved Chinese hierarchy and property style, and the connection-test card plus mention allowlist remain structurally correct without executing the Webhook transport.
- [x] 4.2 Retain concise independent evidence in `verification.md`, explicitly confirming that no message was sent to the previously supplied Webhook or test subarea.
