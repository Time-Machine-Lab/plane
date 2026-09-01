# Preserve URLs in Discord interaction excerpts

## Why

When the same rich-text comment contains a Plane Page URL, the URL is correct in the original Plane comment but appears with extra slash-like characters in the Discord notification excerpt. The source comment is not being rewritten and the canonical URL stored in the Embed `url` property is also unaffected.

The defect is in Plane's API-side excerpt formatter:

1. `apps/api/plane/integrations/discord.py` and `apps/api/plane/bgtasks/page_transaction_task.py` call `build_safe_rich_text_excerpt` for interaction cards.
2. `apps/api/plane/utils/rich_text_mentions.py::build_safe_rich_text_excerpt` converts the HTML to plain text and calls `escape_discord_markdown`.
3. `escape_discord_markdown` currently prefixes every `.` and `-` with a backslash, producing values such as `https://plane\.tmlab\.top/.../254ee0b6\-b92b...`.
4. Those characters are part of normal URL syntax and are not required to protect this single-line quoted excerpt, so Discord can display the inserted backslashes instead of the original URL.

This evidence points to a Plane formatting bug rather than Discord changing the submitted comment or URL.

## What Changes

- Make rich-text excerpt escaping URL-aware: preserve URL-looking tokens exactly as user-authored while continuing to escape Discord formatting syntax in surrounding prose.
- Keep mention replacement, unsupported-component removal, the 300-character bound, explicit `allowed_mentions`, and the existing Embed destination URL behavior unchanged.
- Add the URL-preservation behavior to the Discord interaction capability scenarios so comment, work-item description, and public Page excerpts share the same contract.

## Scope

### In scope

- API rich-text excerpt formatting used by Discord comment and mention cards.
- Focused payload verification for URLs containing dots, slashes, hyphens, UUIDs, query/fragment delimiters, and trailing punctuation.

### Out of scope

- Discord Webhook transport, rate limits, retries, or external Discord behavior.
- Plane comment, Page, or work-item persistence and canonical link generation.
- Changes to daily task reminders, recipient classification, member mappings, or notification permissions.
- General Markdown rendering changes outside Discord interaction excerpts.

## Capabilities

### Modified Capabilities

- `discord-work-item-notifications`: preserve user-authored URLs in safe interaction excerpts.

## Impact

- **Affected module:** `apps/api/plane` rich-text utility and its Discord interaction consumers.
- **No schema or API contract migration:** only the formatted field value in outbound Discord embeds changes.
- **Compatibility:** existing saved configurations and event keys remain valid; non-URL Markdown escaping and mention safety remain in force.
- **Delivery:** this is a narrow formatting-only fix in the existing API worker path; it can proceed through normal code review and merge without a separate test-environment deployment or independent acceptance task.
- **Applicable standards:** `docs/spec/general-development.md`, `docs/spec/backend-development.md`, `docs/spec/testing-quality.md`, `docs/spec/test-environment.md`, `docs/spec/discord-card-design.md`, and `docs/spec/module-structure.md`.
- **Licensing:** no licensing or entitlement change.
