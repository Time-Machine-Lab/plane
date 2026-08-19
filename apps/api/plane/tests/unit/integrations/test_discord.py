# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from unittest.mock import Mock

import pytest
import requests
from django.utils import timezone

from plane.db.models import Issue, IssueAssignee, Project, State, User, Workspace, WorkspaceMember
from plane.db.models.state import StateGroup
from plane.integrations.discord import (
    DISCORD_EVENT_REGISTRY,
    DISCORD_EVENT_WORK_ITEM_ASSIGNEE_ADDED,
    DISCORD_EVENT_WORK_ITEM_COMPLETED,
    DISCORD_EVENT_WORK_ITEM_CREATED,
    DISCORD_EVENT_USER_MENTIONED,
    DISCORD_EVENT_WORK_ITEM_COMMENT_ACTIVITY,
    DiscordEmbedField,
    DiscordIntegrationConfiguration,
    DiscordIssueContext,
    DiscordNotification,
    DiscordPageMentionContext,
    build_discord_payload,
    build_issue_context,
    deliver_issue_notifications,
    deliver_page_mention_notification,
    is_supported_discord_webhook_url,
    resolve_discord_recipients,
    send_discord_webhook,
    validate_discord_configuration,
)
from plane.utils.rich_text_mentions import (
    build_safe_rich_text_excerpt,
    classify_interaction_recipients,
    extract_user_mentions,
    get_new_user_mentions,
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
def test_rich_text_mentions_diff_and_safe_excerpt():
    first_id = "11111111-1111-4111-8111-111111111111"
    second_id = "22222222-2222-4222-8222-222222222222"
    old_html = (
        f'<p>Earlier <mention-component entity_name="user_mention" entity_identifier="{first_id}">'
        "raw</mention-component></p>"
    )
    new_html = (
        old_html
        + '<p><mention-component entity_name="user_mention" entity_identifier="not-a-uuid">bad</mention-component></p>'
        + f'<p>Review **this** <mention-component entity_name="user_mention" entity_identifier="{second_id}">'
        + "raw</mention-component>"
        + '<image-component src="private-storage-key"></image-component> @everyone</p>'
    )

    assert extract_user_mentions(new_html) == (first_id, second_id)
    assert get_new_user_mentions(new_html, old_html) == (second_id,)
    assert extract_user_mentions('<mention-component entity_name="user_mention"></mention-component>') == ()
    excerpt = build_safe_rich_text_excerpt(
        new_html,
        display_names={second_id: "Reviewer"},
        relevant_user_ids=(second_id,),
    )
    assert "@Reviewer" in excerpt
    assert r"\[图片\]" in excerpt
    assert "private-storage-key" not in excerpt
    assert "entity_identifier" not in excerpt
    assert "\\*\\*this\\*\\*" in excerpt
    assert len(excerpt) <= 300

    long_excerpt = build_safe_rich_text_excerpt("<p>" + "a" * 400 + "</p>", display_names={})
    assert len(long_excerpt) == 300
    assert long_excerpt.endswith("…")


@pytest.mark.unit
def test_interaction_recipient_classifier_keeps_event_semantics():
    created = classify_interaction_recipients(
        origin="comment_created",
        actor_id="actor",
        assignee_ids=("actor", "assignee", "assignee"),
        newly_mentioned_user_ids=("assignee", "mentioned", "mentioned", "actor"),
    )
    assert created.comment_user_ids == ("assignee",)
    assert created.mention_user_ids == ("mentioned",)

    updated = classify_interaction_recipients(
        origin="comment_updated",
        actor_id="actor",
        assignee_ids=("assignee", "other-assignee"),
        newly_mentioned_user_ids=("assignee", "mentioned"),
    )
    assert updated.comment_user_ids == ("assignee",)
    assert updated.mention_user_ids == ("mentioned",)

    description = classify_interaction_recipients(
        origin="work_item_description",
        actor_id="actor",
        assignee_ids=("assignee",),
        newly_mentioned_user_ids=("assignee",),
    )
    assert description.comment_user_ids == ()
    assert description.mention_user_ids == ("assignee",)


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
    assert created.source_text == "Plane · Discord Project"
    assert created.title == f"🆕 新任务｜DISC-{issue.sequence_id} · Notify Discord"
    assert "Owner" in created.description
    assert [field.name for field in created.fields] == ["📍 状态", "⚡ 优先级", "👤 负责人"]
    assert "Assignee" in created.fields[2].value

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
    assert added.title == f"👤 分配给你｜DISC-{issue.sequence_id} · Notify Discord"
    assert [field.name for field in added.fields] == ["📍 状态", "⚡ 优先级", "⏰ 截止"]

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
    assert completed.title == f"✅ 已完成｜DISC-{issue.sequence_id} · Notify Discord"
    assert [field.name for field in completed.fields] == ["👤 负责人", "📍 状态", "🗓️ 完成时间"]
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
        source_text="Plane · Project",
        title="Created",
        description="@everyone should stay plain text",
        url="https://plane.example.com/work-item",
        color=1,
        fields=(DiscordEmbedField(name="📍 状态", value="🟡 `进行中`"),),
        footer_text="查看详情",
        timestamp=timezone.now(),
        recipient_plane_user_ids=(),
    )
    payload = build_discord_payload(notification, ("123456789012345678", "234567890123456789"))
    assert payload["content"] == "<@123456789012345678> <@234567890123456789>"
    assert payload["allowed_mentions"] == {
        "parse": [],
        "users": ["123456789012345678", "234567890123456789"],
        "roles": [],
    }
    embed = payload["embeds"][0]
    assert embed["author"] == {"name": "Plane · Project"}
    assert embed["fields"] == [{"name": "📍 状态", "value": "🟡 `进行中`", "inline": True}]
    assert embed["footer"] == {"text": "查看详情"}
    assert embed["timestamp"] == notification.timestamp.isoformat()

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
@pytest.mark.django_db
def test_mixed_comment_sends_at_most_one_card_per_event_with_snapshot_recipients(mocker, discord_issue):
    issue = discord_issue["issue"]
    assignee_id = str(discord_issue["assignee"].id)
    mentioned_id = str(discord_issue["second_assignee"].id)
    configuration = DiscordIntegrationConfiguration(
        enabled=True,
        workspace_id=str(discord_issue["workspace"].id),
        webhook_url=WEBHOOK_URL,
        enabled_events=(DISCORD_EVENT_WORK_ITEM_COMMENT_ACTIVITY, DISCORD_EVENT_USER_MENTIONED),
        member_mappings=(
            {"plane_user_id": assignee_id, "discord_user_id": "123456789012345678"},
            {"plane_user_id": mentioned_id, "discord_user_id": "234567890123456789"},
        ),
    )
    mocker.patch("plane.integrations.discord.get_discord_configuration", return_value=configuration)
    send = mocker.patch("plane.integrations.discord.send_discord_webhook")
    html = (
        f'<p>@assignee <mention-component entity_name="user_mention" entity_identifier="{assignee_id}">'
        "</mention-component>"
        f' @guest <mention-component entity_name="user_mention" entity_identifier="{mentioned_id}">'
        "</mention-component></p>"
    )

    deliver_issue_notifications(
        activity_type="comment.activity.created",
        requested_data={"id": "comment-1", "comment_html": html},
        current_instance=None,
        issue_id=str(issue.id),
        actor_id=str(discord_issue["owner"].id),
        origin="https://plane.example.com",
        assignee_ids=(assignee_id,),
        event_timestamp=timezone.now(),
    )

    assert send.call_count == 2
    calls = {call.kwargs["event_key"]: call.kwargs["payload"] for call in send.call_args_list}
    comment_payload = calls[DISCORD_EVENT_WORK_ITEM_COMMENT_ACTIVITY]
    mention_payload = calls[DISCORD_EVENT_USER_MENTIONED]
    assert comment_payload["allowed_mentions"]["users"] == ["123456789012345678"]
    assert mention_payload["allowed_mentions"]["users"] == ["234567890123456789"]
    assert comment_payload["embeds"][0]["url"].endswith("#comment-comment-1")
    assert "entity_identifier" not in str(mention_payload)
    assert "@everyone" not in mention_payload["content"]


@pytest.mark.unit
@pytest.mark.django_db
def test_comment_edit_notifies_only_new_mentions_and_toggles_do_not_reclassify(mocker, discord_issue):
    issue = discord_issue["issue"]
    assignee_id = str(discord_issue["assignee"].id)
    mentioned_id = str(discord_issue["second_assignee"].id)
    get_configuration = mocker.patch("plane.integrations.discord.get_discord_configuration")
    get_configuration.return_value = DiscordIntegrationConfiguration(
        enabled=True,
        workspace_id=str(discord_issue["workspace"].id),
        webhook_url=WEBHOOK_URL,
        enabled_events=(DISCORD_EVENT_USER_MENTIONED,),
        member_mappings=(
            {"plane_user_id": assignee_id, "discord_user_id": "123456789012345678"},
            {"plane_user_id": mentioned_id, "discord_user_id": "234567890123456789"},
        ),
    )
    send = mocker.patch("plane.integrations.discord.send_discord_webhook")
    old_html = "<p>Initial text</p>"
    new_html = (
        f'<p><mention-component entity_name="user_mention" entity_identifier="{assignee_id}"></mention-component>'
        f'<mention-component entity_name="user_mention" entity_identifier="{mentioned_id}"></mention-component></p>'
    )

    deliver_issue_notifications(
        activity_type="comment.activity.updated",
        requested_data={"comment_html": new_html},
        current_instance={"id": "comment-2", "comment_html": old_html},
        issue_id=str(issue.id),
        actor_id=str(discord_issue["owner"].id),
        origin="https://plane.example.com",
        assignee_ids=(assignee_id,),
    )

    send.assert_called_once()
    assert send.call_args.kwargs["event_key"] == DISCORD_EVENT_USER_MENTIONED
    assert send.call_args.kwargs["payload"]["allowed_mentions"]["users"] == ["234567890123456789"]


@pytest.mark.unit
@pytest.mark.django_db
def test_description_mentions_assignees_as_mentions_and_requires_mapping(mocker, discord_issue):
    issue = discord_issue["issue"]
    assignee_id = str(discord_issue["assignee"].id)
    get_configuration = mocker.patch(
        "plane.integrations.discord.get_discord_configuration",
        return_value=DiscordIntegrationConfiguration(
            enabled=True,
            workspace_id=str(discord_issue["workspace"].id),
            webhook_url=WEBHOOK_URL,
            enabled_events=(DISCORD_EVENT_USER_MENTIONED,),
            member_mappings=({"plane_user_id": assignee_id, "discord_user_id": "123456789012345678"},),
        ),
    )
    send = mocker.patch("plane.integrations.discord.send_discord_webhook")
    html = (
        '<p>Ignore <mention-component entity_name="user_mention" entity_identifier="not-a-uuid">'
        "invalid</mention-component></p>"
        f'<p>Please review <mention-component entity_name="user_mention" entity_identifier="{assignee_id}">'
        "</mention-component></p>"
    )

    deliver_issue_notifications(
        activity_type="issue.activity.updated",
        requested_data={"description_html": html},
        current_instance={"description_html": "<p>Please review</p>"},
        issue_id=str(issue.id),
        actor_id=str(discord_issue["owner"].id),
        origin="https://plane.example.com",
    )
    send.assert_called_once()
    assert send.call_args.kwargs["event_key"] == DISCORD_EVENT_USER_MENTIONED

    send.reset_mock()
    get_configuration.return_value = DiscordIntegrationConfiguration(
        enabled=True,
        workspace_id=str(discord_issue["workspace"].id),
        webhook_url=WEBHOOK_URL,
        enabled_events=(DISCORD_EVENT_USER_MENTIONED,),
        member_mappings=(),
    )
    deliver_issue_notifications(
        activity_type="issue.activity.updated",
        requested_data={"description_html": html},
        current_instance={"description_html": "<p>Please review</p>"},
        issue_id=str(issue.id),
        actor_id=str(discord_issue["owner"].id),
        origin="https://plane.example.com",
    )
    send.assert_not_called()


@pytest.mark.unit
@pytest.mark.django_db
def test_page_delivery_requires_configured_workspace_active_mapping_and_safe_mentions(mocker, discord_issue):
    recipient_id = str(discord_issue["assignee"].id)
    configuration = DiscordIntegrationConfiguration(
        enabled=True,
        workspace_id=str(discord_issue["workspace"].id),
        webhook_url=WEBHOOK_URL,
        enabled_events=(DISCORD_EVENT_USER_MENTIONED,),
        member_mappings=({"plane_user_id": recipient_id, "discord_user_id": "123456789012345678"},),
    )
    get_configuration = mocker.patch(
        "plane.integrations.discord.get_discord_configuration",
        return_value=configuration,
    )
    send = mocker.patch("plane.integrations.discord.send_discord_webhook")
    context = DiscordPageMentionContext(
        workspace_id=str(discord_issue["workspace"].id),
        page_name="Public Page",
        project_name=discord_issue["project"].name,
        workspace_slug=discord_issue["workspace"].slug,
        project_id=str(discord_issue["project"].id),
        page_id="11111111-1111-1111-1111-111111111111",
        actor_name="Owner",
        recipient_plane_user_ids=(recipient_id, recipient_id),
        excerpt="Safe text @everyone <@999999999999999999>",
        timestamp=timezone.now(),
        origin="https://plane.example.com",
    )
    deliver_page_mention_notification(context)
    send.assert_called_once()
    payload = send.call_args.kwargs["payload"]
    assert payload["allowed_mentions"] == {
        "parse": [],
        "users": ["123456789012345678"],
        "roles": [],
    }
    assert payload["content"] == "<@123456789012345678>"
    assert payload["embeds"][0]["url"].endswith(
        f"/{discord_issue['workspace'].slug}/projects/{discord_issue['project'].id}/pages/{context.page_id}"
    )

    send.reset_mock()
    get_configuration.return_value = DiscordIntegrationConfiguration(
        **{**configuration.__dict__, "member_mappings": ()}
    )
    deliver_page_mention_notification(context)
    send.assert_not_called()

    get_configuration.return_value = DiscordIntegrationConfiguration(
        **{**configuration.__dict__, "workspace_id": "22222222-2222-2222-2222-222222222222"}
    )
    deliver_page_mention_notification(context)
    send.assert_not_called()


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
