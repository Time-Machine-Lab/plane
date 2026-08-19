# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from datetime import date, datetime, timezone as datetime_timezone

import pytest
from django.utils import timezone

from plane.bgtasks.discord_daily_reminder_task import (
    _claim_daily_reminder,
    process_discord_daily_task_reminder,
)
from plane.db.models import Issue, IssueAssignee, Project, State, User, Workspace, WorkspaceMember
from plane.db.models.state import StateGroup
from plane.integrations.discord import (
    DISCORD_COLOR_DUE_TODAY,
    DISCORD_COLOR_OVERDUE,
    DISCORD_COLOR_PENDING,
    DISCORD_EVENT_WORK_ITEM_DAILY_REMINDER,
    DISCORD_MAX_EMBED_CHARACTERS_PER_MESSAGE,
    DISCORD_MAX_EMBEDS_PER_MESSAGE,
    DiscordIntegrationConfiguration,
    DiscordTaskBriefGroup,
    DiscordTaskBriefItem,
    build_daily_task_brief_payloads,
    collect_daily_reminder_groups,
    deliver_daily_task_briefs,
    discord_embed_character_count,
)


WEBHOOK_URL = "https://discord.com/api/webhooks/12345678901234567/test_token"
LOCAL_DATE = date(2026, 8, 19)


def _configuration(workspace, *, enabled=True, events=(DISCORD_EVENT_WORK_ITEM_DAILY_REMINDER,)):
    return DiscordIntegrationConfiguration(
        enabled=enabled,
        workspace_id=str(workspace.id),
        webhook_url=WEBHOOK_URL,
        enabled_events=events,
        member_mappings=(),
    )


def _brief_item(
    sequence_id: int,
    *,
    target_date: date | None,
    priority: str = "medium",
    name: str | None = None,
) -> DiscordTaskBriefItem:
    return DiscordTaskBriefItem(
        issue_id=f"issue-{sequence_id}",
        identifier=f"REM-{sequence_id}",
        name=name or f"任务 {sequence_id}",
        project_identifier="REM",
        project_name="提醒项目",
        workspace_slug="reminder-workspace",
        state_name="进行中",
        state_group=StateGroup.STARTED,
        priority=priority,
        sequence_id=sequence_id,
        start_date=date(2026, 8, 1),
        target_date=target_date,
    )


@pytest.fixture
def reminder_workspace(db):
    owner = User.objects.create(email="reminder-owner@example.com", display_name="Owner")
    assignee = User.objects.create(email="reminder-assignee@example.com", display_name="Genius")
    second_assignee = User.objects.create(email="reminder-second@example.com", display_name="Alpha")
    workspace = Workspace.objects.create(
        name="Reminder Workspace",
        slug="reminder-workspace",
        owner=owner,
        timezone="Asia/Kolkata",
    )
    for member in (owner, assignee, second_assignee):
        WorkspaceMember.objects.create(workspace=workspace, member=member, role=20)
    project = Project.objects.create(name="Reminder Project", identifier="REM", workspace=workspace)
    states = {
        group: State.all_state_objects.create(
            name=f"State {group}",
            color="#60646c",
            group=group,
            project=project,
            workspace=workspace,
        )
        for group in (
            StateGroup.BACKLOG,
            StateGroup.UNSTARTED,
            StateGroup.STARTED,
            StateGroup.COMPLETED,
            StateGroup.CANCELLED,
            StateGroup.TRIAGE,
        )
    }
    return {
        "owner": owner,
        "assignee": assignee,
        "second_assignee": second_assignee,
        "workspace": workspace,
        "project": project,
        "states": states,
    }


def _create_issue(reminder_workspace, name, **overrides):
    values = {
        "name": name,
        "workspace": reminder_workspace["workspace"],
        "project": reminder_workspace["project"],
        "state": reminder_workspace["states"][StateGroup.STARTED],
        "start_date": LOCAL_DATE,
        "target_date": None,
        "priority": "none",
    }
    values.update(overrides)
    return Issue.objects.create(**values)


def _assign(issue, user):
    return IssueAssignee.objects.create(
        issue=issue,
        assignee=user,
        project=issue.project,
        workspace=issue.workspace,
    )


@pytest.mark.unit
@pytest.mark.django_db
def test_collector_filters_groups_and_orders_without_n_plus_one(reminder_workspace, django_assert_num_queries):
    assignee = reminder_workspace["assignee"]
    second_assignee = reminder_workspace["second_assignee"]

    overdue = _create_issue(
        reminder_workspace,
        "Overdue urgent",
        start_date=date(2026, 8, 18),
        target_date=date(2026, 8, 18),
        priority="urgent",
    )
    due_today = _create_issue(
        reminder_workspace,
        "Due today low",
        target_date=LOCAL_DATE,
        priority="low",
    )
    future = _create_issue(
        reminder_workspace,
        "Future high",
        target_date=date(2026, 8, 20),
        priority="high",
    )
    future_low = _create_issue(
        reminder_workspace,
        "Future low",
        target_date=date(2026, 8, 20),
        priority="low",
    )
    no_target = _create_issue(reminder_workspace, "No target urgent", priority="urgent")
    unassigned = _create_issue(reminder_workspace, "Unassigned", priority="medium")
    for issue in (overdue, due_today, future, future_low, no_target):
        _assign(issue, assignee)
    _assign(due_today, second_assignee)

    _create_issue(reminder_workspace, "Future start", start_date=date(2026, 8, 20))
    _create_issue(reminder_workspace, "Missing start", start_date=None)
    _create_issue(
        reminder_workspace,
        "Completed",
        state=reminder_workspace["states"][StateGroup.COMPLETED],
    )
    _create_issue(
        reminder_workspace,
        "Cancelled",
        state=reminder_workspace["states"][StateGroup.CANCELLED],
    )
    _create_issue(
        reminder_workspace,
        "Triage",
        state=reminder_workspace["states"][StateGroup.TRIAGE],
    )
    _create_issue(reminder_workspace, "Draft", is_draft=True)
    _create_issue(reminder_workspace, "Archived", archived_at=LOCAL_DATE)

    archived_project = Project.objects.create(
        name="Archived Project",
        identifier="ARC",
        workspace=reminder_workspace["workspace"],
        archived_at=timezone.now(),
    )
    archived_state = State.objects.create(
        name="Archived project state",
        color="#60646c",
        group=StateGroup.STARTED,
        project=archived_project,
        workspace=reminder_workspace["workspace"],
    )
    _create_issue(
        reminder_workspace,
        "Archived project issue",
        project=archived_project,
        state=archived_state,
    )

    other_workspace = Workspace.objects.create(
        name="Other Workspace",
        slug="other-reminder-workspace",
        owner=reminder_workspace["owner"],
    )
    other_project = Project.objects.create(name="Other Project", identifier="OTHER", workspace=other_workspace)
    other_state = State.objects.create(
        name="Other state",
        color="#60646c",
        group=StateGroup.STARTED,
        project=other_project,
        workspace=other_workspace,
    )
    Issue.objects.create(
        name="Other workspace issue",
        workspace=other_workspace,
        project=other_project,
        state=other_state,
        start_date=LOCAL_DATE,
    )

    with django_assert_num_queries(2):
        groups = collect_daily_reminder_groups(
            workspace_id=str(reminder_workspace["workspace"].id),
            local_date=LOCAL_DATE,
        )

    groups_by_user = {group.plane_user_id: group for group in groups}
    assignee_group = groups_by_user[str(assignee.id)]
    assert [item.issue_id for item in assignee_group.items] == [
        str(overdue.id),
        str(due_today.id),
        str(future.id),
        str(future_low.id),
        str(no_target.id),
    ]
    assert [item.issue_id for item in groups_by_user[str(second_assignee.id)].items] == [str(due_today.id)]
    assert [item.issue_id for item in groups_by_user[None].items] == [str(unassigned.id)]
    included_ids = {item.issue_id for group in groups for item in group.items}
    assert included_ids == {
        str(overdue.id),
        str(due_today.id),
        str(future.id),
        str(future_low.id),
        str(no_target.id),
        str(unassigned.id),
    }


@pytest.mark.unit
def test_task_brief_payloads_are_chinese_bounded_ordered_and_mention_once():
    items = tuple(
        _brief_item(
            sequence_id,
            target_date=(
                date(2026, 8, 18)
                if sequence_id == 1
                else LOCAL_DATE
                if sequence_id == 2
                else date(2026, 8, 25)
                if sequence_id < 12
                else None
            ),
            priority="urgent" if sequence_id == 1 else "medium",
        )
        for sequence_id in range(1, 13)
    )
    group = DiscordTaskBriefGroup(
        plane_user_id="plane-user-1",
        display_name="Genius",
        local_date=LOCAL_DATE,
        items=items,
    )
    payloads = build_daily_task_brief_payloads(
        group=group,
        member_mappings=(
            {
                "plane_user_id": "plane-user-1",
                "discord_user_id": "123456789012345678",
            },
        ),
        base_url="https://plane.example.com",
    )

    assert len(payloads) == 2
    assert "<@123456789012345678>" in payloads[0]["content"]
    assert "Genius 的任务简报" in payloads[0]["content"]
    assert "共 12 项" in payloads[0]["content"]
    assert payloads[0]["allowed_mentions"]["users"] == ["123456789012345678"]
    assert payloads[1]["content"] == ""
    assert payloads[1]["allowed_mentions"]["users"] == []

    embeds = [embed for payload in payloads for embed in payload["embeds"]]
    assert [embed["title"].split(" · ", 1)[0] for embed in embeds] == [f"REM-{number}" for number in range(1, 13)]
    assert embeds[0]["color"] == DISCORD_COLOR_OVERDUE
    assert "已逾期 1 天" in embeds[0]["description"]
    assert embeds[1]["color"] == DISCORD_COLOR_DUE_TODAY
    assert "今天截止" in embeds[1]["description"]
    assert embeds[-1]["color"] == DISCORD_COLOR_PENDING
    assert "待推进" in embeds[-1]["description"]
    assert all(embed["author"]["name"] == "Plane · 提醒项目" for embed in embeds)
    assert all(embed["url"].startswith("https://plane.example.com/reminder-workspace/browse/") for embed in embeds)
    expected_field_names = ["⚡ 优先级", "📍 状态", "🗓️ 任务时间"]
    assert all([field["name"] for field in embed["fields"]] == expected_field_names for embed in embeds)
    assert all(embed["footer"]["text"].endswith("喵~") for embed in embeds)
    assert all(len(payload["embeds"]) <= DISCORD_MAX_EMBEDS_PER_MESSAGE for payload in payloads)
    assert all(
        sum(discord_embed_character_count(embed) for embed in payload["embeds"])
        <= DISCORD_MAX_EMBED_CHARACTERS_PER_MESSAGE
        for payload in payloads
    )
    assert all("第 1/2 部分" in embed["footer"]["text"] for embed in payloads[0]["embeds"])
    assert all("第 2/2 部分" in embed["footer"]["text"] for embed in payloads[1]["embeds"])


@pytest.mark.unit
def test_unmapped_and_unassigned_briefs_never_allow_mentions():
    item = _brief_item(1, target_date=None)
    for group in (
        DiscordTaskBriefGroup("plane-user-1", "@everyone", LOCAL_DATE, (item,)),
        DiscordTaskBriefGroup(None, "未分配", LOCAL_DATE, (item,)),
    ):
        payload = build_daily_task_brief_payloads(
            group=group,
            member_mappings=(),
            base_url="https://plane.example.com",
        )[0]
        assert payload["allowed_mentions"] == {"parse": [], "users": [], "roles": []}
        assert not payload["content"].startswith("<@")
    assert (
        "认领或分配"
        in build_daily_task_brief_payloads(
            group=DiscordTaskBriefGroup(None, "未分配", LOCAL_DATE, (item,)),
            member_mappings=(),
            base_url="https://plane.example.com",
        )[0]["embeds"][0]["footer"]["text"]
    )


@pytest.mark.unit
def test_daily_brief_delivery_continues_after_one_payload_failure(mocker):
    group = DiscordTaskBriefGroup(
        plane_user_id="plane-user-1",
        display_name="Genius",
        local_date=LOCAL_DATE,
        items=tuple(_brief_item(number, target_date=None) for number in range(1, 12)),
    )
    configuration = DiscordIntegrationConfiguration(
        enabled=True,
        workspace_id="workspace-1",
        webhook_url=WEBHOOK_URL,
        enabled_events=(DISCORD_EVENT_WORK_ITEM_DAILY_REMINDER,),
        member_mappings=(),
    )
    send = mocker.patch(
        "plane.integrations.discord.send_discord_webhook",
        side_effect=[(False, "timeout"), (True, None)],
    )

    deliver_daily_task_briefs(
        configuration=configuration,
        groups=(group,),
        base_url="https://plane.example.com",
    )

    assert send.call_count == 2


@pytest.mark.unit
@pytest.mark.django_db
@pytest.mark.parametrize(
    ("utc_time", "should_process"),
    [
        (datetime(2026, 8, 19, 2, 29, tzinfo=datetime_timezone.utc), False),
        (datetime(2026, 8, 19, 2, 30, tzinfo=datetime_timezone.utc), True),
        (datetime(2026, 8, 19, 3, 29, tzinfo=datetime_timezone.utc), True),
        (datetime(2026, 8, 19, 3, 30, tzinfo=datetime_timezone.utc), False),
    ],
)
def test_scheduled_reminder_uses_workspace_local_eight_oclock(
    mocker,
    settings,
    reminder_workspace,
    utc_time,
    should_process,
):
    settings.APP_BASE_URL = "https://plane.example.com"
    mocker.patch(
        "plane.bgtasks.discord_daily_reminder_task.get_discord_configuration",
        return_value=_configuration(reminder_workspace["workspace"]),
    )
    claim = mocker.patch("plane.bgtasks.discord_daily_reminder_task._claim_daily_reminder", return_value=True)
    collect = mocker.patch("plane.bgtasks.discord_daily_reminder_task.collect_daily_reminder_groups", return_value=())

    process_discord_daily_task_reminder(now=utc_time)

    assert claim.called is should_process
    assert collect.called is should_process


@pytest.mark.unit
@pytest.mark.django_db
def test_scheduled_reminder_claims_once_and_skips_empty_results(mocker, settings, reminder_workspace):
    settings.APP_BASE_URL = "https://plane.example.com"
    mocker.patch(
        "plane.bgtasks.discord_daily_reminder_task.get_discord_configuration",
        return_value=_configuration(reminder_workspace["workspace"]),
    )
    claim = mocker.patch(
        "plane.bgtasks.discord_daily_reminder_task._claim_daily_reminder",
        side_effect=[True, False],
    )
    collect = mocker.patch("plane.bgtasks.discord_daily_reminder_task.collect_daily_reminder_groups", return_value=())
    deliver = mocker.patch("plane.bgtasks.discord_daily_reminder_task.deliver_daily_task_briefs")
    now = datetime(2026, 8, 19, 2, 30, tzinfo=datetime_timezone.utc)

    process_discord_daily_task_reminder(now=now)
    process_discord_daily_task_reminder(now=now)

    assert claim.call_count == 2
    collect.assert_called_once()
    deliver.assert_not_called()


@pytest.mark.unit
@pytest.mark.django_db
def test_scheduled_reminder_uses_application_base_url(mocker, settings, reminder_workspace):
    settings.APP_BASE_URL = "https://plane.example.com/app"
    configuration = _configuration(reminder_workspace["workspace"])
    group = DiscordTaskBriefGroup(
        plane_user_id=None,
        display_name="未分配",
        local_date=LOCAL_DATE,
        items=(_brief_item(1, target_date=None),),
    )
    mocker.patch(
        "plane.bgtasks.discord_daily_reminder_task.get_discord_configuration",
        return_value=configuration,
    )
    mocker.patch("plane.bgtasks.discord_daily_reminder_task._claim_daily_reminder", return_value=True)
    mocker.patch(
        "plane.bgtasks.discord_daily_reminder_task.collect_daily_reminder_groups",
        return_value=(group,),
    )
    deliver = mocker.patch("plane.bgtasks.discord_daily_reminder_task.deliver_daily_task_briefs")

    process_discord_daily_task_reminder(now=datetime(2026, 8, 19, 2, 30, tzinfo=datetime_timezone.utc))

    deliver.assert_called_once_with(
        configuration=configuration,
        groups=(group,),
        base_url="https://plane.example.com/app",
    )


@pytest.mark.unit
@pytest.mark.django_db
@pytest.mark.parametrize(
    "configuration",
    [
        lambda workspace: _configuration(workspace, enabled=False),
        lambda workspace: _configuration(workspace, events=()),
    ],
)
def test_scheduled_reminder_respects_disabled_configuration(mocker, reminder_workspace, configuration):
    mocker.patch(
        "plane.bgtasks.discord_daily_reminder_task.get_discord_configuration",
        return_value=configuration(reminder_workspace["workspace"]),
    )
    collect = mocker.patch("plane.bgtasks.discord_daily_reminder_task.collect_daily_reminder_groups")

    process_discord_daily_task_reminder(now=datetime(2026, 8, 19, 2, 30, tzinfo=datetime_timezone.utc))

    collect.assert_not_called()


@pytest.mark.unit
def test_daily_reminder_claim_fails_closed_when_cache_is_unavailable(mocker):
    mocker.patch(
        "plane.bgtasks.discord_daily_reminder_task.cache.add",
        side_effect=RuntimeError("cache unavailable"),
    )
    log = mocker.patch("plane.bgtasks.discord_daily_reminder_task.logger.exception")

    assert _claim_daily_reminder("workspace-1", LOCAL_DATE) is False
    log.assert_called_once()


@pytest.mark.unit
def test_daily_reminder_claim_is_atomic_for_workspace_and_local_date(mocker):
    cache_add = mocker.patch(
        "plane.bgtasks.discord_daily_reminder_task.cache.add",
        side_effect=[True, False],
    )

    assert _claim_daily_reminder("workspace-1", LOCAL_DATE) is True
    assert _claim_daily_reminder("workspace-1", LOCAL_DATE) is False
    assert cache_add.call_count == 2
    assert cache_add.call_args_list[0] == cache_add.call_args_list[1]
