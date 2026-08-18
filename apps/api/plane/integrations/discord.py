# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Callable, TypedDict
from urllib.parse import urlsplit

import requests
from django.conf import settings

from plane.db.models import Issue, IssueAssignee, State, User, Workspace, WorkspaceMember
from plane.db.models.state import StateGroup
from plane.license.utils.instance_value import get_configuration_value
from plane.utils.url_security import pinned_fetch
from plane.utils.uuid import is_valid_uuid


DISCORD_EVENT_WORK_ITEM_CREATED = "work_item.created"
DISCORD_EVENT_WORK_ITEM_ASSIGNEE_ADDED = "work_item.assignee_added"
DISCORD_EVENT_WORK_ITEM_COMPLETED = "work_item.completed"
DISCORD_SUPPORTED_EVENT_KEYS = frozenset(
    {
        DISCORD_EVENT_WORK_ITEM_CREATED,
        DISCORD_EVENT_WORK_ITEM_ASSIGNEE_ADDED,
        DISCORD_EVENT_WORK_ITEM_COMPLETED,
    }
)

DISCORD_CONFIG_KEYS = {
    "enabled": "DISCORD_INTEGRATION_ENABLED",
    "workspace_id": "DISCORD_WORKSPACE_ID",
    "webhook_url": "DISCORD_WEBHOOK_URL",
    "enabled_events": "DISCORD_ENABLED_EVENTS",
    "member_mappings": "DISCORD_MEMBER_MAPPINGS",
}

DISCORD_WEBHOOK_HOSTS = frozenset(
    {
        "discord.com",
        "discordapp.com",
        "canary.discord.com",
        "ptb.discord.com",
    }
)
DISCORD_WEBHOOK_PATH_PATTERN = re.compile(r"^/api(?:/v\d+)?/webhooks/\d{17,20}/[A-Za-z0-9._-]+/?$")
DISCORD_USER_ID_PATTERN = re.compile(r"^\d{17,20}$")
DISCORD_WEBHOOK_TIMEOUT_SECONDS = 5

logger = logging.getLogger("plane.worker")


class DiscordMemberMapping(TypedDict):
    plane_user_id: str
    discord_user_id: str


@dataclass(frozen=True)
class DiscordIntegrationConfiguration:
    enabled: bool
    workspace_id: str | None
    webhook_url: str
    enabled_events: tuple[str, ...]
    member_mappings: tuple[DiscordMemberMapping, ...]


@dataclass(frozen=True)
class DiscordNotification:
    event_key: str
    title: str
    description: str
    url: str
    color: int
    recipient_plane_user_ids: tuple[str, ...]


@dataclass(frozen=True)
class DiscordIssueContext:
    activity_type: str
    requested_data: dict[str, Any]
    current_instance: dict[str, Any] | None
    issue: Issue
    actor: User | None
    assignee_ids: tuple[str, ...]
    assignee_names: tuple[str, ...]
    origin: str | None


DiscordEventHandler = Callable[[DiscordIssueContext], DiscordNotification | None]


def is_supported_discord_webhook_url(value: str) -> bool:
    try:
        parsed = urlsplit(value.strip())
    except ValueError:
        return False

    return bool(
        parsed.scheme == "https"
        and parsed.hostname
        and parsed.hostname.lower() in DISCORD_WEBHOOK_HOSTS
        and parsed.port in (None, 443)
        and not parsed.username
        and not parsed.password
        and not parsed.query
        and not parsed.fragment
        and DISCORD_WEBHOOK_PATH_PATTERN.fullmatch(parsed.path)
    )


def validate_discord_user_id(value: Any) -> str:
    user_id = str(value or "").strip()
    if not DISCORD_USER_ID_PATTERN.fullmatch(user_id):
        raise ValueError("Discord User ID must contain 17 to 20 digits.")
    return user_id


def validate_enabled_events(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ValueError("Enabled events must be a list.")

    normalized = tuple(dict.fromkeys(str(item).strip() for item in value))
    unsupported = set(normalized) - DISCORD_SUPPORTED_EVENT_KEYS
    if unsupported:
        raise ValueError("One or more Discord event keys are unsupported.")
    return normalized


def validate_member_mappings(value: Any, workspace_id: str | None) -> tuple[DiscordMemberMapping, ...]:
    if not isinstance(value, list):
        raise ValueError("Member mappings must be a list.")
    if value and not workspace_id:
        raise ValueError("Select a workspace before adding member mappings.")

    normalized: list[DiscordMemberMapping] = []
    plane_user_ids: set[str] = set()
    discord_user_ids: set[str] = set()

    for mapping in value:
        if not isinstance(mapping, dict):
            raise ValueError("Each member mapping must be an object.")
        plane_user_id = str(mapping.get("plane_user_id") or "").strip()
        discord_user_id = validate_discord_user_id(mapping.get("discord_user_id"))
        if not plane_user_id:
            raise ValueError("Plane User ID is required for every member mapping.")
        if not is_valid_uuid(plane_user_id):
            raise ValueError("Plane User ID must be a valid UUID.")
        if plane_user_id in plane_user_ids or discord_user_id in discord_user_ids:
            raise ValueError("Plane and Discord users can only be mapped once.")
        plane_user_ids.add(plane_user_id)
        discord_user_ids.add(discord_user_id)
        normalized.append(
            {
                "plane_user_id": plane_user_id,
                "discord_user_id": discord_user_id,
            }
        )

    if plane_user_ids:
        valid_ids = {
            str(member_id)
            for member_id in WorkspaceMember.objects.filter(
                workspace_id=workspace_id,
                member_id__in=plane_user_ids,
                is_active=True,
            ).values_list("member_id", flat=True)
        }
        if valid_ids != plane_user_ids:
            raise ValueError("Every mapped Plane user must be an active member of the selected workspace.")

    return tuple(normalized)


def validate_discord_configuration(
    *,
    enabled: Any,
    workspace_id: Any,
    webhook_url: Any,
    enabled_events: Any,
    member_mappings: Any,
    has_saved_webhook: bool,
) -> DiscordIntegrationConfiguration:
    if not isinstance(enabled, bool):
        raise ValueError("Enabled must be a boolean.")

    normalized_workspace_id = str(workspace_id or "").strip() or None
    if normalized_workspace_id:
        if not is_valid_uuid(normalized_workspace_id):
            raise ValueError("Selected workspace does not exist.")
        if not Workspace.objects.filter(pk=normalized_workspace_id).exists():
            raise ValueError("Selected workspace does not exist.")

    normalized_webhook_url = str(webhook_url or "").strip()
    if normalized_webhook_url and not is_supported_discord_webhook_url(normalized_webhook_url):
        raise ValueError("Enter a supported Discord Incoming Webhook URL.")

    normalized_events = validate_enabled_events(enabled_events)
    normalized_mappings = validate_member_mappings(member_mappings, normalized_workspace_id)

    if enabled:
        if not normalized_workspace_id:
            raise ValueError("A workspace is required when Discord is enabled.")
        if not normalized_webhook_url and not has_saved_webhook:
            raise ValueError("A Discord Incoming Webhook URL is required when Discord is enabled.")

    return DiscordIntegrationConfiguration(
        enabled=enabled,
        workspace_id=normalized_workspace_id,
        webhook_url=normalized_webhook_url,
        enabled_events=normalized_events,
        member_mappings=normalized_mappings,
    )


def _load_json_list(raw_value: Any) -> list[Any]:
    try:
        value = json.loads(raw_value or "[]")
    except (TypeError, json.JSONDecodeError):
        return []
    return value if isinstance(value, list) else []


def get_discord_configuration() -> DiscordIntegrationConfiguration:
    enabled, workspace_id, webhook_url, enabled_events, member_mappings = get_configuration_value(
        [
            {"key": DISCORD_CONFIG_KEYS["enabled"], "default": "0"},
            {"key": DISCORD_CONFIG_KEYS["workspace_id"], "default": ""},
            {"key": DISCORD_CONFIG_KEYS["webhook_url"], "default": ""},
            {"key": DISCORD_CONFIG_KEYS["enabled_events"], "default": "[]"},
            {"key": DISCORD_CONFIG_KEYS["member_mappings"], "default": "[]"},
        ]
    )
    parsed_events = _load_json_list(enabled_events)
    parsed_mappings = _load_json_list(member_mappings)
    return DiscordIntegrationConfiguration(
        enabled=str(enabled) == "1",
        workspace_id=str(workspace_id or "").strip() or None,
        webhook_url=str(webhook_url or ""),
        enabled_events=tuple(
            event for event in parsed_events if isinstance(event, str) and event in DISCORD_SUPPORTED_EVENT_KEYS
        ),
        member_mappings=tuple(
            mapping
            for mapping in parsed_mappings
            if isinstance(mapping, dict)
            and isinstance(mapping.get("plane_user_id"), str)
            and isinstance(mapping.get("discord_user_id"), str)
        ),
    )


def _canonical_work_item_url(context: DiscordIssueContext) -> str:
    base_url = (context.origin or settings.APP_BASE_URL or settings.WEB_URL or "").rstrip("/")
    issue = context.issue
    return f"{base_url}/{issue.workspace.slug}/browse/{issue.project.identifier}-{issue.sequence_id}/"


def _notification_description(context: DiscordIssueContext, event_summary: str) -> str:
    issue = context.issue
    identifier = f"{issue.project.identifier}-{issue.sequence_id}"
    actor_name = context.actor.display_name if context.actor and context.actor.display_name else "Plane user"
    assignees = ", ".join(context.assignee_names) if context.assignee_names else "None"
    return (
        f"**{identifier}** {issue.name}\n"
        f"{event_summary}\n"
        f"Project: {issue.project.name}\n"
        f"Actor: {actor_name}\n"
        f"Assignees: {assignees}"
    )


def _created_handler(context: DiscordIssueContext) -> DiscordNotification | None:
    if context.activity_type != "issue.activity.created":
        return None
    return DiscordNotification(
        event_key=DISCORD_EVENT_WORK_ITEM_CREATED,
        title="Work item created",
        description=_notification_description(context, "A work item was created."),
        url=_canonical_work_item_url(context),
        color=0x3B82F6,
        recipient_plane_user_ids=context.assignee_ids,
    )


def _assignee_added_handler(context: DiscordIssueContext) -> DiscordNotification | None:
    assignee_key = next(
        (key for key in ("assignee_ids", "assignees") if key in context.requested_data),
        None,
    )
    if context.activity_type != "issue.activity.updated" or not assignee_key:
        return None

    current_assignee_key = "assignee_ids" if "assignee_ids" in (context.current_instance or {}) else "assignees"
    old_assignees = {str(user_id) for user_id in (context.current_instance or {}).get(current_assignee_key, [])}
    new_assignees = {str(user_id) for user_id in context.requested_data.get(assignee_key, [])}
    added_assignees = tuple(user_id for user_id in context.assignee_ids if user_id in new_assignees - old_assignees)
    if not added_assignees:
        return None

    added_names = list(User.objects.filter(pk__in=added_assignees).values_list("display_name", flat=True))
    summary = f"New assignees: {', '.join(name or 'Plane user' for name in added_names)}"
    return DiscordNotification(
        event_key=DISCORD_EVENT_WORK_ITEM_ASSIGNEE_ADDED,
        title="Work item assigned",
        description=_notification_description(context, summary),
        url=_canonical_work_item_url(context),
        color=0xF59E0B,
        recipient_plane_user_ids=added_assignees,
    )


def _completed_handler(context: DiscordIssueContext) -> DiscordNotification | None:
    state_key = next(
        (key for key in ("state_id", "state") if key in context.requested_data),
        None,
    )
    if context.activity_type != "issue.activity.updated" or not state_key:
        return None

    current_state_key = "state_id" if "state_id" in (context.current_instance or {}) else "state"
    old_state_id = (context.current_instance or {}).get(current_state_key)
    new_state_id = context.requested_data.get(state_key)
    state_groups = {
        str(state_id): group
        for state_id, group in State.all_state_objects.filter(pk__in=[old_state_id, new_state_id]).values_list(
            "id", "group"
        )
    }
    if (
        state_groups.get(str(old_state_id)) == StateGroup.COMPLETED
        or state_groups.get(str(new_state_id)) != StateGroup.COMPLETED
    ):
        return None

    return DiscordNotification(
        event_key=DISCORD_EVENT_WORK_ITEM_COMPLETED,
        title="Work item completed",
        description=_notification_description(context, "The work item moved to a completed state."),
        url=_canonical_work_item_url(context),
        color=0x22C55E,
        recipient_plane_user_ids=context.assignee_ids,
    )


DISCORD_EVENT_REGISTRY: dict[str, DiscordEventHandler] = {
    DISCORD_EVENT_WORK_ITEM_CREATED: _created_handler,
    DISCORD_EVENT_WORK_ITEM_ASSIGNEE_ADDED: _assignee_added_handler,
    DISCORD_EVENT_WORK_ITEM_COMPLETED: _completed_handler,
}


def build_issue_context(
    *,
    activity_type: str,
    requested_data: dict[str, Any],
    current_instance: dict[str, Any] | None,
    issue: Issue,
    actor: User | None,
    origin: str | None,
) -> DiscordIssueContext:
    assignee_links = list(
        IssueAssignee.objects.filter(issue_id=issue.id).select_related("assignee").order_by("created_at")
    )
    return DiscordIssueContext(
        activity_type=activity_type,
        requested_data=requested_data,
        current_instance=current_instance,
        issue=issue,
        actor=actor,
        assignee_ids=tuple(str(link.assignee_id) for link in assignee_links),
        assignee_names=tuple(
            link.assignee.display_name or link.assignee.full_name or "Plane user" for link in assignee_links
        ),
        origin=origin,
    )


def resolve_discord_recipients(
    recipient_plane_user_ids: tuple[str, ...],
    member_mappings: tuple[DiscordMemberMapping, ...],
) -> tuple[str, ...]:
    mapping_by_plane_id = {mapping["plane_user_id"]: mapping["discord_user_id"] for mapping in member_mappings}
    return tuple(
        dict.fromkeys(
            mapping_by_plane_id[user_id] for user_id in recipient_plane_user_ids if user_id in mapping_by_plane_id
        )
    )


def build_discord_payload(
    notification: DiscordNotification,
    discord_user_ids: tuple[str, ...],
) -> dict[str, Any]:
    allowed_user_ids = tuple(
        dict.fromkeys(user_id for user_id in discord_user_ids if DISCORD_USER_ID_PATTERN.fullmatch(user_id))
    )
    return {
        "content": " ".join(f"<@{user_id}>" for user_id in allowed_user_ids),
        "embeds": [
            {
                "title": notification.title,
                "description": notification.description,
                "url": notification.url,
                "color": notification.color,
                "footer": {"text": "Plane"},
            }
        ],
        "allowed_mentions": {
            "parse": [],
            "users": list(allowed_user_ids),
            "roles": [],
        },
    }


def build_test_notification(origin: str | None = None) -> DiscordNotification:
    base_url = (origin or settings.ADMIN_BASE_URL or settings.WEB_URL or "").rstrip("/")
    return DiscordNotification(
        event_key="discord.test",
        title="Plane Discord test",
        description="Your Plane Discord integration is configured correctly.",
        url=f"{base_url}/discord/"
        if origin
        else (f"{base_url}/god-mode/discord/" if base_url else "https://plane.so/"),
        color=0x5865F2,
        recipient_plane_user_ids=(),
    )


def send_discord_webhook(
    *,
    webhook_url: str,
    payload: dict[str, Any],
    event_key: str,
    workspace_id: str | None = None,
    issue_id: str | None = None,
) -> tuple[bool, str | None]:
    try:
        response = pinned_fetch(
            "POST",
            webhook_url,
            headers={"Content-Type": "application/json"},
            timeout=DISCORD_WEBHOOK_TIMEOUT_SECONDS,
            json=payload,
        )
        if 200 <= response.status_code < 300:
            return True, None
        category = f"http_{response.status_code}"
    except requests.Timeout:
        category = "timeout"
    except (requests.RequestException, ValueError):
        category = "network"

    logger.error(
        "Discord webhook delivery failed",
        extra={
            "discord_event_key": event_key,
            "workspace_id": workspace_id,
            "issue_id": issue_id,
            "failure_category": category,
        },
    )
    return False, category


def deliver_issue_notifications(
    *,
    activity_type: str,
    requested_data: dict[str, Any],
    current_instance: dict[str, Any] | None,
    issue_id: str,
    actor_id: str,
    origin: str | None,
) -> None:
    configuration = get_discord_configuration()
    if not configuration.enabled or not configuration.workspace_id or not configuration.webhook_url:
        return

    issue = (
        Issue.objects.select_related("workspace", "project", "state")
        .filter(pk=issue_id, workspace_id=configuration.workspace_id)
        .first()
    )
    if not issue:
        return

    context = build_issue_context(
        activity_type=activity_type,
        requested_data=requested_data,
        current_instance=current_instance,
        issue=issue,
        actor=User.objects.filter(pk=actor_id).first(),
        origin=origin,
    )
    for event_key in configuration.enabled_events:
        handler = DISCORD_EVENT_REGISTRY.get(event_key)
        if not handler:
            continue
        notification = handler(context)
        if not notification:
            continue
        discord_user_ids = resolve_discord_recipients(
            notification.recipient_plane_user_ids,
            configuration.member_mappings,
        )
        payload = build_discord_payload(notification, discord_user_ids)
        send_discord_webhook(
            webhook_url=configuration.webhook_url,
            payload=payload,
            event_key=notification.event_key,
            workspace_id=str(issue.workspace_id),
            issue_id=str(issue.id),
        )
