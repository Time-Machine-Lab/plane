# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import uuid

import pytest

from plane.bgtasks.page_transaction_task import page_transaction
from plane.db.models import Page, PageLog, Project, ProjectPage, User, Workspace, WorkspaceMember


@pytest.fixture
def discord_page(db):
    owner = User.objects.create(email="page-owner@example.com", display_name="Page Owner")
    mentioned = User.objects.create(email="page-mentioned@example.com", display_name="Page Member")
    workspace = Workspace.objects.create(name="Page Workspace", slug="page-workspace", owner=owner)
    WorkspaceMember.objects.create(workspace=workspace, member=owner, role=20)
    WorkspaceMember.objects.create(workspace=workspace, member=mentioned, role=20)
    project = Project.objects.create(name="Page Project", identifier="PAGE", workspace=workspace)
    page = Page.objects.create(name="Release Notes", workspace=workspace, owned_by=owner, access=Page.PUBLIC_ACCESS)
    ProjectPage.objects.create(workspace=workspace, project=project, page=page)
    return {
        "owner": owner,
        "mentioned": mentioned,
        "workspace": workspace,
        "project": project,
        "page": page,
    }


def mention_html(transaction_id, user_id, text="Please review"):
    return (
        f'<p>{text} <mention-component id="{transaction_id}" entity_name="user_mention" '
        f'entity_identifier="{user_id}"></mention-component></p>'
    )


@pytest.mark.unit
@pytest.mark.django_db
def test_direct_public_page_mention_claims_once_and_groups_recipients(mocker, discord_page):
    second_member = User.objects.create(email="page-second@example.com", display_name="Second Member")
    WorkspaceMember.objects.create(workspace=discord_page["workspace"], member=second_member, role=20)
    first_transaction = uuid.uuid4()
    second_transaction = uuid.uuid4()
    html = mention_html(first_transaction, discord_page["mentioned"].id) + mention_html(
        second_transaction, second_member.id, "Also review"
    )
    deliver = mocker.patch("plane.bgtasks.page_transaction_task.deliver_page_mention_notification")

    page_transaction.run(
        html,
        "<p></p>",
        str(discord_page["page"].id),
        actor_id=str(discord_page["owner"].id),
        project_id=str(discord_page["project"].id),
        operation_kind="direct_edit",
        origin="https://plane.example.com",
    )

    deliver.assert_called_once()
    context = deliver.call_args.args[0]
    assert context.workspace_id == str(discord_page["workspace"].id)
    assert context.project_id == str(discord_page["project"].id)
    assert context.recipient_plane_user_ids == (str(discord_page["mentioned"].id), str(second_member.id))
    assert "entity_identifier" not in context.excerpt
    assert PageLog.objects.filter(page=discord_page["page"], entity_name="user_mention").count() == 2

    deliver.reset_mock()
    page_transaction.run(
        html,
        html,
        str(discord_page["page"].id),
        actor_id=str(discord_page["owner"].id),
        project_id=str(discord_page["project"].id),
        operation_kind="direct_edit",
        origin="https://plane.example.com",
    )
    deliver.assert_not_called()


@pytest.mark.unit
@pytest.mark.django_db
def test_malformed_page_transaction_does_not_block_valid_mention(mocker, discord_page):
    valid_transaction = uuid.uuid4()
    old_html = mention_html("malformed-old-id", discord_page["mentioned"].id, "Remove malformed")
    html = mention_html("not-a-uuid", discord_page["mentioned"].id, "Ignore malformed") + mention_html(
        valid_transaction, discord_page["mentioned"].id, "Process valid"
    )
    deliver = mocker.patch("plane.bgtasks.page_transaction_task.deliver_page_mention_notification")

    page_transaction.run(
        html,
        old_html,
        str(discord_page["page"].id),
        actor_id=str(discord_page["owner"].id),
        project_id=str(discord_page["project"].id),
        operation_kind="direct_edit",
        origin="https://plane.example.com",
    )

    assert PageLog.objects.filter(page=discord_page["page"], transaction=valid_transaction).exists()
    assert PageLog.objects.filter(page=discord_page["page"], entity_name="user_mention").count() == 1
    deliver.assert_called_once()
    assert deliver.call_args.args[0].recipient_plane_user_ids == (str(discord_page["mentioned"].id),)


@pytest.mark.unit
@pytest.mark.django_db
@pytest.mark.parametrize("operation_kind", [None, "duplicate", "import", "sync", "restore"])
def test_non_direct_page_operations_never_notify(mocker, discord_page, operation_kind):
    deliver = mocker.patch("plane.bgtasks.page_transaction_task.deliver_page_mention_notification")
    html = mention_html(uuid.uuid4(), discord_page["mentioned"].id)

    page_transaction.run(
        html,
        "<p></p>",
        str(discord_page["page"].id),
        actor_id=str(discord_page["owner"].id),
        project_id=str(discord_page["project"].id),
        operation_kind=operation_kind,
        origin="https://plane.example.com",
    )

    deliver.assert_not_called()


@pytest.mark.unit
@pytest.mark.django_db
def test_private_self_unmapped_and_invalid_project_page_mentions_are_silent(mocker, discord_page):
    deliver = mocker.patch("plane.bgtasks.page_transaction_task.deliver_page_mention_notification")
    page = discord_page["page"]
    page.access = Page.PRIVATE_ACCESS
    page.save(update_fields=["access"])
    page_transaction.run(
        mention_html(uuid.uuid4(), discord_page["mentioned"].id),
        "<p></p>",
        str(page.id),
        actor_id=str(discord_page["owner"].id),
        project_id=str(discord_page["project"].id),
        operation_kind="direct_edit",
    )
    deliver.assert_not_called()

    page.access = Page.PUBLIC_ACCESS
    page.save(update_fields=["access"])
    page_transaction.run(
        mention_html(uuid.uuid4(), discord_page["owner"].id),
        "<p></p>",
        str(page.id),
        actor_id=str(discord_page["owner"].id),
        project_id=str(discord_page["project"].id),
        operation_kind="direct_edit",
    )
    deliver.assert_not_called()

    page_transaction.run(
        mention_html(uuid.uuid4(), discord_page["mentioned"].id),
        "<p></p>",
        str(page.id),
        actor_id=str(discord_page["owner"].id),
        project_id=str(uuid.uuid4()),
        operation_kind="direct_edit",
    )
    deliver.assert_not_called()
