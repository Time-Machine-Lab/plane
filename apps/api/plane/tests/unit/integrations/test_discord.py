# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from unittest.mock import Mock

import pytest
import requests

from plane.db.models import Issue, IssueAssignee, Project, State, User, Workspace, WorkspaceMember
from plane.db.models.state import StateGroup
from plane.integrations.discord import (
    DISCORD_EVENT_REGISTRY,
    DISCORD_EVENT_WORK_ITEM_ASSIGNEE_ADDED,
    DISCORD_EVENT_WORK_ITEM_COMPLETED,
    DISCORD_EVENT_WORK_ITEM_CREATED,
    DiscordIntegrationConfiguration,
    DiscordIssueContext,
    DiscordNotification,
    build_discord_payload,
    build_issue_context,
    deliver_issue_notifications,
    is_supported_discord_webhook_url,
    resolve_discord_recipients,
    send_discord_webhook,
    validate_discord_configuration,
)


WEBHOOK_URL = "https://discord.com/api/webhooks/12345678901234567/test_token"


@pytest.fixture
def discord_issue(db):
    owner = User.objects.create(email="discord-owner@example.com", display_name="Owner")
    assignee = User.objects.create(email="discord-assignee@example.com", display_name="Assignee")
    second_assignee = User.objects.create(email="discord-second@example.com", display_name="Second Assignee")
    workspace = Workspace.objects.create(name="Discord Workspace", slug="discord-workspace", owner=owner)
    for member in (owner, assignee, second_assignee):
        WorkspaceMember.objects.create(workspace=workspace, member=member, role=20)
    project = Project.objects.create(name="Discord Project", identifier="DISC", workspace=workspace)
    started = State.objects.create(
        name="Started",
        color="#f59e0b",
        group=StateGroup.STARTED,
        project=project,
        workspace=workspace,
    )
    completed = State.objects.create(
        name="Completed",
        color="#22c55e",
        group=StateGroup.COMPLETED,
        project=project,
        workspace=workspace,
    )
    issue = Issue.objects.create(
        name="Notify Discord",
        project=project,
        workspace=workspace,
        state=started,
    )
    IssueAssignee.objects.create(
        issue=issue,
        assignee=assignee,
        project=project,
        workspace=workspace,
    )
    return {
        "owner": owner,
        "assignee": assignee,
        "second_assignee": second_assignee,
        "workspace": workspace,
        "project": project,
        "started": started,
        "completed": completed,
        "issue": issue,
    }


@pytest.mark.unit
def test_discord_webhook_url_validation_is_strict():
    assert is_supported_discord_webhook_url(WEBHOOK_URL)
    assert is_supported_discord_webhook_url("https://discord.com/api/v10/webhooks/12345678901234567890/a.b-c_d")
    assert not is_supported_discord_webhook_url("http://discord.com/api/webhooks/12345678901234567/token")
    assert not is_supported_discord_webhook_url("https://example.com/api/webhooks/12345678901234567/token")
    assert not is_supported_discord_webhook_url(
        "https://discord.com/api/webhooks/12345678901234567/token?redirect=https://internal"
    )


@pytest.mark.unit
@pytest.mark.django_db
def test_configuration_validation_is_atomic_and_workspace_scoped(discord_issue):
    member_id = str(discord_issue["assignee"].id)
    configuration = validate_discord_configuration(
        enabled=True,
        workspace_id=str(discord_issue["workspace"].id),
        webhook_url=WEBHOOK_URL,
        enabled_events=[DISCORD_EVENT_WORK_ITEM_CREATED],
        member_mappings=[
            {
                "plane_user_id": member_id,
                "discord_user_id": "123456789012345678",
            }
        ],
        has_saved_webhook=False,
    )
    assert configuration.enabled_events == (DISCORD_EVENT_WORK_ITEM_CREATED,)

    outsider = User.objects.create(email="discord-outsider@example.com")
    with pytest.raises(ValueError, match="active member"):
        validate_discord_configuration(
            enabled=True,
            workspace_id=str(discord_issue["workspace"].id),
            webhook_url=WEBHOOK_URL,
            enabled_events=[DISCORD_EVENT_WORK_ITEM_CREATED],
            member_mappings=[
                {
                    "plane_user_id": str(outsider.id),
                    "discord_user_id": "123456789012345678",
                }
            ],
            has_saved_webhook=False,
        )

    with pytest.raises(ValueError, match="valid UUID"):
        validate_discord_configuration(
            enabled=True,
            workspace_id=str(discord_issue["workspace"].id),
            webhook_url=WEBHOOK_URL,
            enabled_events=[DISCORD_EVENT_WORK_ITEM_CREATED],
            member_mappings=[
                {
                    "plane_user_id": "not-a-uuid",
                    "discord_user_id": "123456789012345678",
                }
            ],
            has_saved_webhook=False,
        )


@pytest.mark.unit
@pytest.mark.django_db
def test_registry_matches_created_added_and_completed_events(discord_issue):
    issue = discord_issue["issue"]
    assignee_id = str(discord_issue["assignee"].id)
    second_assignee_id = str(discord_issue["second_assignee"].id)
    base_context = build_issue_context(
        activity_type="issue.activity.created",
        requested_data={},
        current_instance=None,
        issue=issue,
        actor=discord_issue["owner"],
        origin="https://plane.example.com",
    )
    created = DISCORD_EVENT_REGISTRY[DISCORD_EVENT_WORK_ITEM_CREATED](base_context)
    assert created is not None
    assert created.recipient_plane_user_ids == (assignee_id,)
    assert created.url.endswith(f"/discord-workspace/browse/DISC-{issue.sequence_id}/")
    assert "Owner" in created.description
    assert "Assignee" in created.description

    IssueAssignee.objects.create(
        issue=issue,
        assignee=discord_issue["second_assignee"],
        project=discord_issue["project"],
        workspace=discord_issue["workspace"],
    )
    added_context = build_issue_context(
        activity_type="issue.activity.updated",
        requested_data={"assignee_ids": [assignee_id, second_assignee_id]},
        current_instance={"assignee_ids": [assignee_id]},
        issue=issue,
        actor=discord_issue["owner"],
        origin="https://plane.example.com",
    )
    added = DISCORD_EVENT_REGISTRY[DISCORD_EVENT_WORK_ITEM_ASSIGNEE_ADDED](added_context)
    assert added is not None
    assert added.recipient_plane_user_ids == (second_assignee_id,)

    removed_only_context = DiscordIssueContext(
        **{
            **added_context.__dict__,
            "requested_data": {"assignee_ids": [assignee_id]},
            "current_instance": {"assignee_ids": [assignee_id, second_assignee_id]},
            "assignee_ids": (assignee_id,),
        }
    )
    assert DISCORD_EVENT_REGISTRY[DISCORD_EVENT_WORK_ITEM_ASSIGNEE_ADDED](removed_only_context) is None

    completed_context = DiscordIssueContext(
        **{
            **added_context.__dict__,
            "requested_data": {"state_id": str(discord_issue["completed"].id)},
            "current_instance": {"state_id": str(discord_issue["started"].id)},
        }
    )
    completed = DISCORD_EVENT_REGISTRY[DISCORD_EVENT_WORK_ITEM_COMPLETED](completed_context)
    assert completed is not None
    already_completed_context = DiscordIssueContext(
        **{
            **completed_context.__dict__,
            "current_instance": {"state_id": str(discord_issue["completed"].id)},
        }
    )
    assert DISCORD_EVENT_REGISTRY[DISCORD_EVENT_WORK_ITEM_COMPLETED](already_completed_context) is None


@pytest.mark.unit
def test_payload_mentions_only_explicit_mapped_users():
    notification = DiscordNotification(
        event_key=DISCORD_EVENT_WORK_ITEM_CREATED,
        title="Created",
        description="@everyone should stay plain text",
        url="https://plane.example.com/work-item",
        color=1,
        recipient_plane_user_ids=(),
    )
    payload = build_discord_payload(notification, ("123456789012345678", "234567890123456789"))
    assert payload["content"] == "<@123456789012345678> <@234567890123456789>"
    assert payload["allowed_mentions"] == {
        "parse": [],
        "users": ["123456789012345678", "234567890123456789"],
        "roles": [],
    }

    unmapped_payload = build_discord_payload(notification, ())
    assert unmapped_payload["content"] == ""
    assert unmapped_payload["allowed_mentions"]["users"] == []

    unsafe_payload = build_discord_payload(notification, ("123456789012345678", "123> @everyone"))
    assert unsafe_payload["content"] == "<@123456789012345678>"
    assert unsafe_payload["allowed_mentions"]["users"] == ["123456789012345678"]


@pytest.mark.unit
def test_recipient_resolution_ignores_unmapped_members_and_deduplicates_discord_users():
    recipients = resolve_discord_recipients(
        ("plane-1", "plane-unmapped", "plane-2"),
        (
            {"plane_user_id": "plane-1", "discord_user_id": "123456789012345678"},
            {"plane_user_id": "plane-2", "discord_user_id": "123456789012345678"},
        ),
    )
    assert recipients == ("123456789012345678",)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("side_effect", "status_code", "expected_category"),
    [
        (None, 204, None),
        (None, 404, "http_404"),
        (requests.Timeout(), None, "timeout"),
        (requests.ConnectionError(), None, "network"),
    ],
)
def test_transport_makes_one_attempt(mocker, side_effect, status_code, expected_category):
    response = Mock(status_code=status_code)
    pinned_fetch = mocker.patch(
        "plane.integrations.discord.pinned_fetch",
        side_effect=side_effect,
        return_value=response,
    )
    accepted, category = send_discord_webhook(
        webhook_url=WEBHOOK_URL,
        payload={"content": "test"},
        event_key="discord.test",
    )
    assert accepted is (expected_category is None)
    assert category == expected_category
    pinned_fetch.assert_called_once()


@pytest.mark.unit
@pytest.mark.django_db
def test_delivery_respects_enabled_events_and_workspace_isolation(mocker, discord_issue):
    issue = discord_issue["issue"]
    send = mocker.patch("plane.integrations.discord.send_discord_webhook")
    get_configuration = mocker.patch(
        "plane.integrations.discord.get_discord_configuration",
        return_value=DiscordIntegrationConfiguration(
            enabled=True,
            workspace_id=str(discord_issue["workspace"].id),
            webhook_url=WEBHOOK_URL,
            enabled_events=(),
            member_mappings=(),
        ),
    )
    get_configuration.return_value = DiscordIntegrationConfiguration(
        enabled=False,
        workspace_id=str(discord_issue["workspace"].id),
        webhook_url=WEBHOOK_URL,
        enabled_events=(DISCORD_EVENT_WORK_ITEM_CREATED,),
        member_mappings=(),
    )
    deliver_issue_notifications(
        activity_type="issue.activity.created",
        requested_data={},
        current_instance=None,
        issue_id=str(issue.id),
        actor_id=str(discord_issue["owner"].id),
        origin="https://plane.example.com",
    )
    send.assert_not_called()

    get_configuration.return_value = DiscordIntegrationConfiguration(
        enabled=True,
        workspace_id=str(discord_issue["workspace"].id),
        webhook_url=WEBHOOK_URL,
        enabled_events=(),
        member_mappings=(),
    )
    deliver_issue_notifications(
        activity_type="issue.activity.created",
        requested_data={},
        current_instance=None,
        issue_id=str(issue.id),
        actor_id=str(discord_issue["owner"].id),
        origin="https://plane.example.com",
    )
    send.assert_not_called()

    other_workspace = Workspace.objects.create(
        name="Other Workspace",
        slug="other-workspace",
        owner=discord_issue["owner"],
    )
    get_configuration.return_value = DiscordIntegrationConfiguration(
        enabled=True,
        workspace_id=str(other_workspace.id),
        webhook_url=WEBHOOK_URL,
        enabled_events=(DISCORD_EVENT_WORK_ITEM_CREATED,),
        member_mappings=(),
    )
    deliver_issue_notifications(
        activity_type="issue.activity.created",
        requested_data={},
        current_instance=None,
        issue_id=str(issue.id),
        actor_id=str(discord_issue["owner"].id),
        origin="https://plane.example.com",
    )
    send.assert_not_called()
