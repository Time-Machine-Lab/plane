# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import json
import re
from dataclasses import dataclass
from typing import Any, Mapping

from bs4 import BeautifulSoup, Tag

from plane.utils.uuid import is_valid_uuid


MENTION_TAG = "mention-component"
USER_MENTION_ENTITY = "user_mention"
EXCERPT_BLOCK_TAGS = ("p", "li", "blockquote", "h1", "h2", "h3", "h4", "h5", "h6")
DISCORD_URL_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_])https?://[^\s<>\[\]{}\"\u3001\u3002\uff0c\uff01\uff1f\uff1b\uff1a\u300d\u300f\u3009\u300b\u3011\u301b]+",
    re.IGNORECASE,
)
DISCORD_MARKDOWN_ESCAPE_PATTERN = re.compile(r"([\\`*_{}\[\]()<>#+\-.!|~])")


def _rich_text_html(value: Any, field: str | None = None) -> str:
    if isinstance(value, dict):
        candidate = value.get(field) if field else value.get("description_html")
        return candidate if isinstance(candidate, str) else ""
    if isinstance(value, str):
        if field:
            try:
                parsed = json.loads(value)
            except (TypeError, json.JSONDecodeError):
                return ""
            return _rich_text_html(parsed, field)
        return value
    return ""


def extract_user_mentions(value: Any, *, field: str | None = None) -> tuple[str, ...]:
    html = _rich_text_html(value, field)
    if not html:
        return ()
    try:
        soup = BeautifulSoup(html, "html.parser")
    except Exception:
        return ()

    mentions = []
    for tag in soup.find_all(MENTION_TAG, attrs={"entity_name": USER_MENTION_ENTITY}):
        identifier = str(tag.get("entity_identifier") or "").strip()
        if identifier and is_valid_uuid(identifier):
            mentions.append(identifier)
    return tuple(dict.fromkeys(mentions))


def get_new_user_mentions(new_value: Any, old_value: Any, *, field: str | None = None) -> tuple[str, ...]:
    old_mentions = set(extract_user_mentions(old_value, field=field))
    return tuple(mention for mention in extract_user_mentions(new_value, field=field) if mention not in old_mentions)


def get_removed_user_mentions(new_value: Any, old_value: Any, *, field: str | None = None) -> tuple[str, ...]:
    new_mentions = set(extract_user_mentions(new_value, field=field))
    return tuple(mention for mention in extract_user_mentions(old_value, field=field) if mention not in new_mentions)


def escape_discord_markdown(value: str) -> str:
    escaped_parts: list[str] = []
    last_end = 0
    for match in DISCORD_URL_PATTERN.finditer(value):
        escaped_parts.append(_escape_discord_markdown_segment(value[last_end : match.start()]))
        escaped_parts.append(match.group(0))
        last_end = match.end()
    escaped_parts.append(_escape_discord_markdown_segment(value[last_end:]))
    return "".join(escaped_parts)


def _escape_discord_markdown_segment(value: str) -> str:
    return DISCORD_MARKDOWN_ESCAPE_PATTERN.sub(r"\\\1", value)


def _truncate_discord_excerpt(escaped: str, limit: int) -> str:
    target_length = limit - 1
    cutoff = target_length
    for match in DISCORD_URL_PATTERN.finditer(escaped):
        if match.start() < target_length < match.end():
            cutoff = match.start()
            break
    output = escaped[:cutoff]
    if output.endswith("\\"):
        output = output[:-1]
    return f"{output}…"


def _replace_rich_components(soup: BeautifulSoup, display_names: Mapping[str, str]) -> None:
    for mention in soup.find_all(MENTION_TAG):
        if mention.get("entity_name") == USER_MENTION_ENTITY:
            identifier = str(mention.get("entity_identifier") or "")
            label = display_names.get(identifier) or mention.get_text(" ", strip=True) or "Plane 用户"
            mention.replace_with(f"@{label}")
        else:
            mention.decompose()
    for image in soup.find_all(["image-component", "img"]):
        image.replace_with("[图片]")
    for attachment in soup.find_all(["file-component", "attachment-component"]):
        attachment.replace_with("[附件]")


def build_safe_rich_text_excerpt(
    value: Any,
    *,
    display_names: Mapping[str, str],
    relevant_user_ids: tuple[str, ...] = (),
    field: str | None = None,
    limit: int = 300,
) -> str:
    html = _rich_text_html(value, field)
    if not html or limit <= 0:
        return ""
    try:
        soup = BeautifulSoup(html, "html.parser")
    except Exception:
        return ""

    selected: Tag | BeautifulSoup = soup
    relevant = set(relevant_user_ids)
    if relevant:
        mention = next(
            (
                tag
                for tag in soup.find_all(MENTION_TAG, attrs={"entity_name": USER_MENTION_ENTITY})
                if str(tag.get("entity_identifier") or "") in relevant
            ),
            None,
        )
        if mention:
            selected = mention.find_parent(EXCERPT_BLOCK_TAGS) or soup

    fragment = BeautifulSoup(str(selected), "html.parser")
    _replace_rich_components(fragment, display_names)
    plain_text = " ".join(fragment.get_text(" ", strip=True).split())
    escaped = escape_discord_markdown(plain_text)
    if len(escaped) <= limit:
        return escaped
    return _truncate_discord_excerpt(escaped, limit)


@dataclass(frozen=True)
class DiscordInteractionRecipients:
    comment_user_ids: tuple[str, ...]
    mention_user_ids: tuple[str, ...]


def classify_interaction_recipients(
    *,
    origin: str,
    actor_id: str,
    assignee_ids: tuple[str, ...] = (),
    newly_mentioned_user_ids: tuple[str, ...] = (),
) -> DiscordInteractionRecipients:
    actor_id = str(actor_id)
    assignees = tuple(dict.fromkeys(str(user_id) for user_id in assignee_ids if str(user_id) != actor_id))
    assignee_set = set(assignees)
    mentions = tuple(
        dict.fromkeys(str(user_id) for user_id in newly_mentioned_user_ids if str(user_id) != actor_id)
    )

    if origin == "comment_created":
        return DiscordInteractionRecipients(
            comment_user_ids=assignees,
            mention_user_ids=tuple(user_id for user_id in mentions if user_id not in assignee_set),
        )
    if origin == "comment_updated":
        return DiscordInteractionRecipients(
            comment_user_ids=tuple(user_id for user_id in mentions if user_id in assignee_set),
            mention_user_ids=tuple(user_id for user_id in mentions if user_id not in assignee_set),
        )
    if origin in {"work_item_description", "page"}:
        return DiscordInteractionRecipients(comment_user_ids=(), mention_user_ids=mentions)
    return DiscordInteractionRecipients(comment_user_ids=(), mention_user_ids=())
