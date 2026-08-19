## Context

The existing Discord integration emits a normalized notification containing only a title, description, URL, color, and recipients. The shared payload builder consequently produces a flat Embed without source, structured fields, action-oriented footer, or timestamp. The event triggers, member mapping, Webhook security, and single-attempt transport already work and are outside this visual change.

The approved visual baseline is documented in `docs/spec/discord-card-design.md`. This change applies its single-event card and confirmed “icon label + inline-code badge value” property bar to the three existing work-item events and the God Mode connection test. The future task brief, mention, and comment events are examples in the design standard but are not implemented here.

## Goals / Non-Goals

**Goals:**

- Make the event and work-item subject immediately visible in Chinese.
- Separate source, subject, action description, task properties, and footer into stable Embed regions.
- Reuse one lightweight formatting contract across existing events and the test message.
- Preserve links, mapped mentions, event selection, workspace isolation, and delivery behavior.
- Keep the implementation small and local to the existing Discord integration module.

**Non-Goals:**

- New Discord event types, scheduled briefs, mention notifications, or comment notifications.
- New God Mode settings or UI changes.
- Multiple card themes, administrator-customizable templates, localization settings, or a general notification design system.
- Changes to Discord destination selection, Webhook transport, retry policy, or delivery history.
- New automated test cases or a new visual test harness.
- Any implementation or validation message sent to the previously supplied Discord Webhook or test subarea.

## Decisions

### 1. Extend the existing normalized notification instead of assembling Embeds in the transport

The normalized Discord notification will carry the presentation data required by a single-event card: source text, linked title, description, event color, up to three structured fields, footer text, timestamp, and recipient Plane user IDs. Event formatters own event-specific wording and field selection; the shared payload builder owns conversion to Discord JSON and mention restrictions.

This keeps the current registry boundary intact and lets later event handlers reuse the same builder. The transport remains unaware of card semantics.

**Alternative considered:** building complete Discord dictionaries inside each event handler would be shorter initially but would duplicate payload shape and make future cards inconsistent.

### 2. Use small shared formatting helpers, not a new design-system module

The existing Discord integration module will define or colocate small constants/helpers for approved event colors, semantic dots, inline-code badge escaping, date/time presentation, and the fixed property labels from `docs/spec/discord-card-design.md`. These helpers must safely handle missing priority, state, assignee, and date values without leaving empty or malformed fields.

No new package or cross-application abstraction is introduced. The long-term visual rules stay in the canonical documentation; code contains only the constants and transformations needed to generate the payload.

**Alternative considered:** a configurable template engine would add complexity, validation, and migration concerns without serving the confirmed fixed style.

### 3. Keep the work item as the primary linked subject

For each production event, the Embed title combines the Chinese event label with `{identifier} · {name}` and its URL points directly to the existing canonical work-item URL. `author.name` provides low-emphasis Plane/project context. The description contains one Chinese actor/action sentence.

The property bar uses inline Discord fields with icon labels and inline-code values. Semantic dots are included only where they convey state, priority, or urgency. A field is omitted when it is not useful and cannot be represented by an approved neutral value; no blank layout fields are inserted.

The test card follows the same hierarchy but links to the Discord God Mode configuration and contains no work-item or recipient mention.

### 4. Preserve mention security independently of card content

Mapped Discord mentions remain in the top-level message `content`. `allowed_mentions.parse` remains empty and `allowed_mentions.users` remains the exact deduplicated allowlist. User-entered work-item, project, and member text is displayed in Embed fields and cannot broaden mention permissions.

Formatting helpers must escape backticks or other Markdown characters that could break the selected badge or description structure. They must not include system IDs or Webhook details in visible content.

### 5. Prohibit the previously supplied test destination during implementation

The earlier Webhook URL and test subarea ID are visual-prototyping credentials only. They must not be placed in source, fixtures, environment templates, commands, OpenSpec evidence, or logs, and neither implementation nor acceptance may issue a request to them.

Development verification uses generated payload inspection and the existing mocked transport coverage. The change adds no automated test cases; existing assertions are updated only when required by the normalized notification or payload shape. A real Discord smoke is allowed only if the user later provides a different destination and explicitly authorizes it.

## Risks / Trade-offs

- **[Discord field layout changes between desktop and mobile]** -> Limit cards to three short inline fields and keep long text outside the property row as required by the design standard.
- **[User-entered Markdown breaks badge or description formatting]** -> Centralize escaping and apply it before interpolating task, project, state, priority, or member text.
- **[Missing task metadata creates an uneven card]** -> Use approved neutral presentation only when it adds meaning; otherwise omit the field without adding spacer fields.
- **[Chinese fixed copy does not match every instance language]** -> Accept Chinese as the confirmed scope; localization or administrator-selected language requires a separate proposal.
- **[No live Discord request during development hides platform rendering differences]** -> Rely on the already approved visual prototypes and validate the exact generated JSON shape; use a separately authorized destination only if one is explicitly supplied later.

## Migration Plan

1. During the normal release rollout, deploy the updated API code with no data or configuration migration; this is not an acceptance prerequisite for the change.
2. Existing enabled integrations automatically use the new card presentation for subsequent events.
3. Roll back by reverting the formatter and normalized payload changes; stored Discord configuration remains compatible.
4. Do not send a migration, deployment, or rollback message to any Discord destination.

## Open Questions

None for this style-only scope.
