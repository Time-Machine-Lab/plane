## Implementation

- [x] Update `apps/api/plane/utils/rich_text_mentions.py` so URL-looking tokens bypass Markdown escaping while surrounding text retains the existing safe escaping, component replacement, mention handling, and visible-length bound.
- [x] Keep the change limited to the shared Discord excerpt formatter and merge it through normal code review; no separate test-environment deployment or independent acceptance task is required for this narrow formatting fix.
