# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import json
import logging
import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Callable, TypedDict
from urllib.parse import urlsplit

import requests
from django.conf import settings
from django.db.models import Prefetch
from django.utils import timezone

from plane.db.models import Issue, IssueAssignee, State, User, Workspace, WorkspaceMember
from plane.db.models.state import StateGroup
from plane.license.utils.instance_value import get_configuration_value
from plane.utils.url_security import pinned_fetch
from plane.utils.uuid import is_valid_uuid


DISCORD_EVENT_WORK_ITEM_CREATED = "work_item.created"
DISCORD_EVENT_WORK_ITEM_ASSIGNEE_ADDED = "work_item.assignee_added"
DISCORD_EVENT_WORK_ITEM_COMPLETED = "work_item.completed"
DISCORD_EVENT_WORK_ITEM_DAILY_REMINDER = "work_item.daily_reminder"
DISCORD_SUPPORTED_EVENT_KEYS = frozenset(
    {
        DISCORD_EVENT_WORK_ITEM_CREATED,
        DISCORD_EVENT_WORK_ITEM_ASSIGNEE_ADDED,
        DISCORD_EVENT_WORK_ITEM_COMPLETED,
        DISCORD_EVENT_WORK_ITEM_DAILY_REMINDER,
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

DISCORD_COLOR_CREATED = 0x5865F2
DISCORD_COLOR_ASSIGNED = 0xF0B232
DISCORD_COLOR_COMPLETED = 0x57F287
DISCORD_COLOR_OVERDUE = 0xED4245
DISCORD_COLOR_DUE_TODAY = 0xF0B232
DISCORD_COLOR_PENDING = 0x5865F2

DISCORD_MAX_EMBEDS_PER_MESSAGE = 10
DISCORD_MAX_EMBED_CHARACTERS_PER_MESSAGE = 6000
DISCORD_MAX_CONTENT_CHARACTERS = 2000
DISCORD_MAX_AUTHOR_CHARACTERS = 256
DISCORD_MAX_TITLE_CHARACTERS = 256
DISCORD_MAX_DESCRIPTION_CHARACTERS = 4096
DISCORD_MAX_FIELD_VALUE_CHARACTERS = 1024
DISCORD_MAX_FOOTER_CHARACTERS = 2048

DISCORD_FIELD_STATUS = "📍 状态"
DISCORD_FIELD_PRIORITY = "⚡ 优先级"
DISCORD_FIELD_DEADLINE = "⏰ 截止"
DISCORD_FIELD_ASSIGNEE = "👤 负责人"
DISCORD_FIELD_COMPLETED_AT = "🗓️ 完成时间"
DISCORD_FIELD_TASK_TIME = "🗓️ 任务时间"

DISCORD_DOT_RED = "🔴"
DISCORD_DOT_YELLOW = "🟡"
DISCORD_DOT_GREEN = "🟢"
DISCORD_DOT_BLUE = "🔵"
DISCORD_DOT_WHITE = "⚪"

DISCORD_STATE_DOTS = {
    StateGroup.BACKLOG: DISCORD_DOT_BLUE,
    StateGroup.UNSTARTED: DISCORD_DOT_BLUE,
    StateGroup.STARTED: DISCORD_DOT_YELLOW,
    StateGroup.COMPLETED: DISCORD_DOT_GREEN,
    StateGroup.CANCELLED: DISCORD_DOT_WHITE,
    StateGroup.TRIAGE: DISCORD_DOT_WHITE,
}
DISCORD_PRIORITY_PRESENTATION = {
    "urgent": (DISCORD_DOT_RED, "紧急"),
    "high": (DISCORD_DOT_RED, "高"),
    "medium": (DISCORD_DOT_YELLOW, "中"),
    "low": (DISCORD_DOT_BLUE, "低"),
    "none": (DISCORD_DOT_WHITE, "无优先级"),
}
DISCORD_PRIORITY_ORDER = {
    "urgent": 0,
    "high": 1,
    "medium": 2,
    "low": 3,
    "none": 4,
}

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
class DiscordEmbedField:
    name: str
    value: str
    inline: bool = True


@dataclass(frozen=True)
class DiscordNotification:
    event_key: str
    source_text: str
    title: str
    description: str
    url: str
    color: int
    fields: tuple[DiscordEmbedField, ...]
    footer_text: str
    timestamp: datetime
    recipient_plane_user_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if len(self.fields) > 3:
            raise ValueError("Discord single-event cards support at most three fields.")


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


@dataclass(frozen=True)
class DiscordTaskBriefItem:
    issue_id: str
    identifier: str
    name: str
    project_identifier: str
    project_name: str
    workspace_slug: str
    state_name: str
    state_group: str
    priority: str
    sequence_id: int
    start_date: date
    target_date: date | None


@dataclass(frozen=True)
class DiscordTaskBriefGroup:
    plane_user_id: str | None
    display_name: str
    local_date: date
    items: tuple[DiscordTaskBriefItem, ...]


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


def _truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return f"{value[: limit - 1]}…"


def _escape_markdown(value: str) -> str:
    return re.sub(r"([\\`*_{}\[\]()<>#+\-.!|~])", r"\\\1", value)


def _inline_code_badge(value: str, dot: str | None = None) -> str:
    normalized = " ".join(str(value or "").split()).replace("`", "ˋ") or "未设置"
    badge = f"`{_truncate(normalized, 1000)}`"
    return f"{dot} {badge}" if dot else badge


def _actor_name(context: DiscordIssueContext) -> str:
    if not context.actor:
        return "Plane 用户"
    return context.actor.display_name or context.actor.full_name or "Plane 用户"


def _source_text(context: DiscordIssueContext) -> str:
    return _truncate(f"Plane · {context.issue.project.name}", 256)


def _work_item_title(context: DiscordIssueContext, event_label: str) -> str:
    issue = context.issue
    return _truncate(f"{event_label}｜{issue.project.identifier}-{issue.sequence_id} · {issue.name}", 256)


def _state_field(issue: Issue) -> DiscordEmbedField:
    state_name = issue.state.name if issue.state else "未设置"
    state_group = issue.state.group if issue.state else None
    return DiscordEmbedField(
        name=DISCORD_FIELD_STATUS,
        value=_inline_code_badge(state_name, DISCORD_STATE_DOTS.get(state_group, DISCORD_DOT_WHITE)),
    )


def _priority_field(issue: Issue) -> DiscordEmbedField:
    dot, label = DISCORD_PRIORITY_PRESENTATION.get(
        issue.priority,
        (DISCORD_DOT_WHITE, "无优先级"),
    )
    return DiscordEmbedField(name=DISCORD_FIELD_PRIORITY, value=_inline_code_badge(label, dot))


def _assignee_field(assignee_names: tuple[str, ...]) -> DiscordEmbedField:
    names = "、".join(assignee_names) if assignee_names else "未分配"
    dot = None if assignee_names else DISCORD_DOT_WHITE
    return DiscordEmbedField(name=DISCORD_FIELD_ASSIGNEE, value=_inline_code_badge(names, dot))


def _format_date(value: date) -> str:
    return f"{value.month}月{value.day}日"


def _deadline_field(target_date: date | None) -> DiscordEmbedField:
    if not target_date:
        return DiscordEmbedField(
            name=DISCORD_FIELD_DEADLINE,
            value=_inline_code_badge("未设置", DISCORD_DOT_WHITE),
        )

    today = timezone.localdate()
    if target_date < today:
        dot, label = DISCORD_DOT_RED, f"已逾期 · {_format_date(target_date)}"
    elif target_date == today:
        dot, label = DISCORD_DOT_YELLOW, "今天"
    else:
        dot, label = DISCORD_DOT_BLUE, _format_date(target_date)
    return DiscordEmbedField(name=DISCORD_FIELD_DEADLINE, value=_inline_code_badge(label, dot))


def _format_datetime(value: datetime) -> str:
    localized = timezone.localtime(value) if timezone.is_aware(value) else value
    return f"{localized.month}月{localized.day}日 {localized:%H:%M}"


def _completed_at_field(value: datetime) -> DiscordEmbedField:
    return DiscordEmbedField(name=DISCORD_FIELD_COMPLETED_AT, value=_inline_code_badge(_format_datetime(value)))


def _created_handler(context: DiscordIssueContext) -> DiscordNotification | None:
    if context.activity_type != "issue.activity.created":
        return None
    return DiscordNotification(
        event_key=DISCORD_EVENT_WORK_ITEM_CREATED,
        source_text=_source_text(context),
        title=_work_item_title(context, "🆕 新任务"),
        description=f"**{_escape_markdown(_actor_name(context))}** 创建了这个任务。",
        url=_canonical_work_item_url(context),
        color=DISCORD_COLOR_CREATED,
        fields=(
            _state_field(context.issue),
            _priority_field(context.issue),
            _assignee_field(context.assignee_names),
        ),
        footer_text="点击标题，在 Plane 中查看任务详情",
        timestamp=context.issue.created_at,
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

    added_name_by_id = {
        str(user_id): display_name or "Plane 用户"
        for user_id, display_name in User.objects.filter(pk__in=added_assignees).values_list("id", "display_name")
    }
    added_names = tuple(added_name_by_id.get(user_id, "Plane 用户") for user_id in added_assignees)
    assigned_to = "、".join(_escape_markdown(name) for name in added_names)
    return DiscordNotification(
        event_key=DISCORD_EVENT_WORK_ITEM_ASSIGNEE_ADDED,
        source_text=_source_text(context),
        title=_work_item_title(context, "👤 分配给你"),
        description=f"**{_escape_markdown(_actor_name(context))}** 将任务分配给 {assigned_to}。",
        url=_canonical_work_item_url(context),
        color=DISCORD_COLOR_ASSIGNED,
        fields=(
            _state_field(context.issue),
            _priority_field(context.issue),
            _deadline_field(context.issue.target_date),
        ),
        footer_text="请及时查看并推进任务",
        timestamp=context.issue.updated_at,
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

    completed_at = context.issue.completed_at or timezone.now()
    return DiscordNotification(
        event_key=DISCORD_EVENT_WORK_ITEM_COMPLETED,
        source_text=_source_text(context),
        title=_work_item_title(context, "✅ 已完成"),
        description=f"**{_escape_markdown(_actor_name(context))}** 完成了这个任务。",
        url=_canonical_work_item_url(context),
        color=DISCORD_COLOR_COMPLETED,
        fields=(
            _assignee_field(context.assignee_names),
            DiscordEmbedField(
                name=DISCORD_FIELD_STATUS,
                value=_inline_code_badge("已完成", DISCORD_DOT_GREEN),
            ),
            _completed_at_field(completed_at),
        ),
        footer_text="任务已完成，点击标题查看详情",
        timestamp=completed_at,
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
            link.assignee.display_name or link.assignee.full_name or "Plane 用户" for link in assignee_links
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


def _daily_reminder_risk_rank(item: DiscordTaskBriefItem, local_date: date) -> int:
    if item.target_date is None:
        return 3
    if item.target_date < local_date:
        return 0
    if item.target_date == local_date:
        return 1
    return 2


def _daily_reminder_sort_key(item: DiscordTaskBriefItem, local_date: date) -> tuple[Any, ...]:
    return (
        _daily_reminder_risk_rank(item, local_date),
        DISCORD_PRIORITY_ORDER.get(item.priority, DISCORD_PRIORITY_ORDER["none"]),
        item.target_date or date.max,
        item.project_identifier.casefold(),
        item.sequence_id,
        item.issue_id,
    )


def collect_daily_reminder_groups(
    *,
    workspace_id: str,
    local_date: date,
) -> tuple[DiscordTaskBriefGroup, ...]:
    assignee_prefetch = Prefetch(
        "issue_assignee",
        queryset=IssueAssignee.objects.select_related("assignee").order_by("assignee_id"),
        to_attr="discord_reminder_assignee_links",
    )
    issues = (
        Issue.issue_objects.filter(
            workspace_id=workspace_id,
            start_date__isnull=False,
            start_date__lte=local_date,
            state__group__in=(StateGroup.BACKLOG, StateGroup.UNSTARTED, StateGroup.STARTED),
            archived_at__isnull=True,
            is_draft=False,
            project__archived_at__isnull=True,
            project__deleted_at__isnull=True,
        )
        .select_related("workspace", "project", "state")
        .prefetch_related(assignee_prefetch)
    )

    grouped_items: dict[str, tuple[str, list[DiscordTaskBriefItem]]] = {}
    unassigned_items: list[DiscordTaskBriefItem] = []
    for issue in issues:
        item = DiscordTaskBriefItem(
            issue_id=str(issue.id),
            identifier=f"{issue.project.identifier}-{issue.sequence_id}",
            name=issue.name,
            project_identifier=issue.project.identifier,
            project_name=issue.project.name,
            workspace_slug=issue.workspace.slug,
            state_name=issue.state.name,
            state_group=issue.state.group,
            priority=issue.priority,
            sequence_id=issue.sequence_id,
            start_date=issue.start_date,
            target_date=issue.target_date,
        )
        assignee_links = issue.discord_reminder_assignee_links
        if not assignee_links:
            unassigned_items.append(item)
            continue

        for link in assignee_links:
            plane_user_id = str(link.assignee_id)
            display_name = link.assignee.display_name or link.assignee.full_name or "Plane 用户"
            grouped_items.setdefault(plane_user_id, (display_name, []))[1].append(item)

    groups = [
        DiscordTaskBriefGroup(
            plane_user_id=plane_user_id,
            display_name=display_name,
            local_date=local_date,
            items=tuple(sorted(items, key=lambda item: _daily_reminder_sort_key(item, local_date))),
        )
        for plane_user_id, (display_name, items) in grouped_items.items()
    ]
    groups.sort(key=lambda group: (group.display_name.casefold(), group.plane_user_id or ""))
    if unassigned_items:
        groups.append(
            DiscordTaskBriefGroup(
                plane_user_id=None,
                display_name="未分配",
                local_date=local_date,
                items=tuple(
                    sorted(unassigned_items, key=lambda item: _daily_reminder_sort_key(item, local_date))
                ),
            )
        )
    return tuple(groups)


def _task_brief_group_label(group: DiscordTaskBriefGroup, *, markdown: bool = True) -> str:
    if group.plane_user_id is None:
        return "未分配任务简报"
    display_name = _truncate(" ".join(group.display_name.split()) or "Plane 用户", 200)
    if markdown:
        display_name = _escape_markdown(display_name)
    return f"{display_name} 的任务简报"


def _task_brief_summary(group: DiscordTaskBriefGroup, discord_user_id: str | None) -> str:
    overdue = sum(item.target_date is not None and item.target_date < group.local_date for item in group.items)
    due_today = sum(item.target_date == group.local_date for item in group.items)
    pending = len(group.items) - overdue - due_today
    summary_date = f"{group.local_date.year}年{group.local_date.month}月{group.local_date.day}日"
    lines = [
        f"**{_task_brief_group_label(group)} · {summary_date} · 共 {len(group.items)} 项**",
        f"逾期 {overdue} 项 · 今日截止 {due_today} 项 · 待推进 {pending} 项",
    ]
    if discord_user_id:
        lines.insert(0, f"<@{discord_user_id}>")
    return _truncate("\n".join(lines), DISCORD_MAX_CONTENT_CHARACTERS)


def _task_brief_risk_presentation(item: DiscordTaskBriefItem, local_date: date) -> tuple[str, int]:
    if item.target_date is not None and item.target_date < local_date:
        overdue_days = (local_date - item.target_date).days
        return f"{DISCORD_DOT_RED} **已逾期 {overdue_days} 天**", DISCORD_COLOR_OVERDUE
    if item.target_date == local_date:
        return f"{DISCORD_DOT_YELLOW} **今天截止**", DISCORD_COLOR_DUE_TODAY
    if item.target_date is not None:
        remaining_days = (item.target_date - local_date).days
        return f"{DISCORD_DOT_BLUE} **还有 {remaining_days} 天截止**", DISCORD_COLOR_PENDING
    return f"{DISCORD_DOT_BLUE} **待推进**", DISCORD_COLOR_PENDING


def _task_brief_footer(
    item: DiscordTaskBriefItem,
    group: DiscordTaskBriefGroup,
    part_number: int,
    total_parts: int,
) -> str:
    if group.plane_user_id is None:
        reminder = "这项任务还没有负责人，记得尽快认领或分配喵~"
    elif item.target_date is not None and item.target_date < group.local_date:
        overdue_days = (group.local_date - item.target_date).days
        reminder = f"主人，这项任务已经逾期 {overdue_days} 天，今天优先处理一下喵~"
    elif item.target_date == group.local_date:
        reminder = "主人，这项任务今天截止，记得及时收尾喵~"
    else:
        reminder = "主人，今天也一起稳稳推进这项任务喵~"
    return _truncate(
        f"{_task_brief_group_label(group, markdown=False)} · 第 {part_number}/{total_parts} 部分 · {reminder}",
        DISCORD_MAX_FOOTER_CHARACTERS,
    )


def _build_task_brief_embed(
    item: DiscordTaskBriefItem,
    group: DiscordTaskBriefGroup,
    base_url: str,
    part_number: int,
    total_parts: int,
) -> dict[str, Any]:
    risk_text, color = _task_brief_risk_presentation(item, group.local_date)
    priority_dot, priority_label = DISCORD_PRIORITY_PRESENTATION.get(
        item.priority,
        (DISCORD_DOT_WHITE, "无优先级"),
    )
    task_time = f"{_format_date(item.start_date)} → {_format_date(item.target_date) if item.target_date else '未设置'}"
    url = f"{base_url.rstrip('/')}/{item.workspace_slug}/browse/{item.identifier}/"
    return {
        "author": {
            "name": _truncate(
                f"Plane · {' '.join(item.project_name.split())}",
                DISCORD_MAX_AUTHOR_CHARACTERS,
            )
        },
        "title": _truncate(
            f"{item.identifier} · {_escape_markdown(item.name)}",
            DISCORD_MAX_TITLE_CHARACTERS,
        ),
        "description": _truncate(risk_text, DISCORD_MAX_DESCRIPTION_CHARACTERS),
        "url": url,
        "color": color,
        "fields": [
            {
                "name": DISCORD_FIELD_PRIORITY,
                "value": _truncate(
                    _inline_code_badge(priority_label, priority_dot),
                    DISCORD_MAX_FIELD_VALUE_CHARACTERS,
                ),
                "inline": True,
            },
            {
                "name": DISCORD_FIELD_STATUS,
                "value": _truncate(
                    _inline_code_badge(
                        item.state_name,
                        DISCORD_STATE_DOTS.get(item.state_group, DISCORD_DOT_WHITE),
                    ),
                    DISCORD_MAX_FIELD_VALUE_CHARACTERS,
                ),
                "inline": True,
            },
            {
                "name": DISCORD_FIELD_TASK_TIME,
                "value": _truncate(
                    _inline_code_badge(task_time),
                    DISCORD_MAX_FIELD_VALUE_CHARACTERS,
                ),
                "inline": True,
            },
        ],
        "footer": {"text": _task_brief_footer(item, group, part_number, total_parts)},
    }


def discord_embed_character_count(embed: dict[str, Any]) -> int:
    fields = embed.get("fields", [])
    return sum(
        (
            len(str(embed.get("author", {}).get("name", ""))),
            len(str(embed.get("title", ""))),
            len(str(embed.get("description", ""))),
            len(str(embed.get("footer", {}).get("text", ""))),
            *(len(str(field.get("name", ""))) + len(str(field.get("value", ""))) for field in fields),
        )
    )


def _pack_task_brief_embeds(
    group: DiscordTaskBriefGroup,
    base_url: str,
) -> tuple[tuple[dict[str, Any], ...], ...]:
    if not group.items:
        return ()

    total_parts = 1
    while True:
        parts: list[list[dict[str, Any]]] = []
        current_part: list[dict[str, Any]] = []
        current_characters = 0
        for item in group.items:
            part_number = len(parts) + 1
            embed = _build_task_brief_embed(item, group, base_url, part_number, total_parts)
            embed_characters = discord_embed_character_count(embed)
            if current_part and (
                len(current_part) >= DISCORD_MAX_EMBEDS_PER_MESSAGE
                or current_characters + embed_characters > DISCORD_MAX_EMBED_CHARACTERS_PER_MESSAGE
            ):
                parts.append(current_part)
                current_part = []
                current_characters = 0
                part_number = len(parts) + 1
                embed = _build_task_brief_embed(item, group, base_url, part_number, total_parts)
                embed_characters = discord_embed_character_count(embed)
            current_part.append(embed)
            current_characters += embed_characters
        if current_part:
            parts.append(current_part)

        if len(parts) == total_parts:
            return tuple(tuple(part) for part in parts)
        total_parts = len(parts)


def build_daily_task_brief_payloads(
    *,
    group: DiscordTaskBriefGroup,
    member_mappings: tuple[DiscordMemberMapping, ...],
    base_url: str,
) -> tuple[dict[str, Any], ...]:
    resolved_user_ids = (
        resolve_discord_recipients((group.plane_user_id,), member_mappings) if group.plane_user_id else ()
    )
    discord_user_id = next(
        (user_id for user_id in resolved_user_ids if DISCORD_USER_ID_PATTERN.fullmatch(user_id)),
        None,
    )
    parts = _pack_task_brief_embeds(group, base_url)
    payloads = []
    for index, embeds in enumerate(parts):
        is_first = index == 0
        allowed_user_ids = [discord_user_id] if is_first and discord_user_id else []
        payloads.append(
            {
                "content": _task_brief_summary(group, discord_user_id) if is_first else "",
                "embeds": list(embeds),
                "allowed_mentions": {
                    "parse": [],
                    "users": allowed_user_ids,
                    "roles": [],
                },
            }
        )
    return tuple(payloads)


def deliver_daily_task_briefs(
    *,
    configuration: DiscordIntegrationConfiguration,
    groups: tuple[DiscordTaskBriefGroup, ...],
    base_url: str,
) -> None:
    for group in groups:
        payloads = build_daily_task_brief_payloads(
            group=group,
            member_mappings=configuration.member_mappings,
            base_url=base_url,
        )
        for payload in payloads:
            send_discord_webhook(
                webhook_url=configuration.webhook_url,
                payload=payload,
                event_key=DISCORD_EVENT_WORK_ITEM_DAILY_REMINDER,
                workspace_id=configuration.workspace_id,
            )


def build_discord_payload(
    notification: DiscordNotification,
    discord_user_ids: tuple[str, ...],
) -> dict[str, Any]:
    allowed_user_ids = tuple(
        dict.fromkeys(user_id for user_id in discord_user_ids if DISCORD_USER_ID_PATTERN.fullmatch(user_id))
    )
    embed = {
        "author": {"name": notification.source_text},
        "title": notification.title,
        "description": notification.description,
        "url": notification.url,
        "color": notification.color,
        "fields": [
            {"name": field.name, "value": field.value, "inline": field.inline} for field in notification.fields
        ],
        "footer": {"text": notification.footer_text},
        "timestamp": notification.timestamp.isoformat(),
    }
    return {
        "content": " ".join(f"<@{user_id}>" for user_id in allowed_user_ids),
        "embeds": [embed],
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
        source_text="Plane · Discord 集成",
        title="🔔 Discord 连接测试",
        description="这是一条连接测试消息，用于确认 Discord 通知配置可用。",
        url=f"{base_url}/discord/"
        if origin
        else (f"{base_url}/god-mode/discord/" if base_url else "https://plane.so/"),
        color=DISCORD_COLOR_CREATED,
        fields=(
            DiscordEmbedField(
                name=DISCORD_FIELD_STATUS,
                value=_inline_code_badge("连接正常", DISCORD_DOT_GREEN),
            ),
        ),
        footer_text="点击标题，返回 God Mode 查看配置",
        timestamp=timezone.now(),
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
