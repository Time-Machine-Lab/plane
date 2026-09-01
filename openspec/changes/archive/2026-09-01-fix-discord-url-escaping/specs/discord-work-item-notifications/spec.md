## MODIFIED Requirements

### Requirement: Interaction cards use safe Chinese presentation and accurate links

Comment and mention notifications SHALL follow the single-event card hierarchy in `docs/spec/discord-card-design.md`. Fixed presentation copy SHALL be Chinese. A comment card SHALL identify the work item, project, actor, bounded comment excerpt, and exact `#comment-{comment_id}` link. A work-item mention card SHALL identify the actor, work item, source location, bounded surrounding excerpt, and work-item or exact comment link. A Plane Page mention card SHALL identify the actor, Page name, project context, bounded surrounding excerpt, and Page link without promising a block-level anchor.

The system MUST convert rich text to safe plain text, render Plane user mentions in excerpts using display names rather than internal IDs or raw tags, escape Discord formatting in surrounding prose, and limit each excerpt to 300 visible characters with a truncation marker when needed. URL-looking tokens in user-authored content MUST remain textually unchanged, including their dots, slashes, hyphens, query delimiters, fragments, and trailing path separators. Images, files, and unsupported rich content MUST NOT expose raw markup or internal storage details.

#### Scenario: URL in an interaction excerpt is preserved

- **WHEN** an eligible comment, work-item description, or public Page mention contains a URL such as `https://plane.tmlab.top/tml/projects/254ee0b6-b92b-4493-82b9-8c074a1a7071/pages/6ac5bf0b-6ad5-4279-a73c-9c5e15c7b350/`
- **THEN** the Discord content field shows the same URL text without inserted backslashes before dots or hyphens, while the notification's canonical Embed URL remains unchanged

#### Scenario: Markdown safety remains for surrounding prose

- **WHEN** the same excerpt contains Discord formatting characters, raw mention-like text, Plane mention nodes, images, or attachments outside the URL
- **THEN** surrounding prose remains safely escaped or replaced, no user-authored text creates an additional Discord mention, and the excerpt stays within the visible limit

#### Scenario: URL preservation does not expose unsupported rich content

- **WHEN** a rich-text excerpt contains a URL together with image, file, or unsupported component markup
- **THEN** the URL is preserved as plain text and unsupported components are represented by the existing safe placeholders without exposing raw tags or storage identifiers
