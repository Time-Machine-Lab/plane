# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import json

import pytest
from django.core.cache import cache
from django.utils import timezone

from plane.db.models import User, Workspace, WorkspaceMember
from plane.license.models import Instance, InstanceAdmin, InstanceConfiguration
from plane.license.utils.encryption import decrypt_data, encrypt_data


CONFIGURATION_PATH = "/api/instances/discord-configuration/"
MEMBERS_PATH = "/api/instances/discord-configuration/members/"
TEST_PATH = "/api/instances/discord-configuration/test/"
GENERIC_CONFIGURATION_PATH = "/api/instances/configurations/"
WEBHOOK_URL = "https://discord.com/api/webhooks/12345678901234567/test_token"


@pytest.fixture(autouse=True)
def clear_configuration_cache(settings):
    settings.SKIP_ENV_VAR = True
    settings.WEB_URL = "https://plane.example.com"
    settings.APP_BASE_URL = "https://plane.example.com"
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def instance(db):
    return Instance.objects.create(
        instance_name="Discord Test Instance",
        instance_id="discord-test-instance",
        current_version="1.0.0",
        last_checked_at=timezone.now(),
    )


@pytest.fixture
def admin_user(db, instance):
    user = User.objects.create(email="discord-admin@example.com", display_name="Discord Admin")
    InstanceAdmin.objects.create(instance=instance, user=user, role=20, is_verified=True)
    return user


@pytest.fixture
def regular_user(db, instance):
    return User.objects.create(email="discord-regular@example.com", display_name="Regular User")


@pytest.fixture
def configured_workspace(db, admin_user):
    workspace = Workspace.objects.create(
        name="Configured Workspace",
        slug="configured-workspace",
        owner=admin_user,
    )
    WorkspaceMember.objects.create(workspace=workspace, member=admin_user, role=20)
    return workspace


@pytest.fixture
def admin_client(api_client, admin_user):
    api_client.force_authenticate(user=admin_user)
    return api_client


def valid_payload(workspace, user):
    return {
        "enabled": True,
        "workspace_id": str(workspace.id),
        "webhook_url": WEBHOOK_URL,
        "enabled_events": [
            "work_item.created",
            "work_item.assignee_added",
            "work_item.completed",
            "work_item.daily_reminder",
            "user.mentioned",
            "work_item.comment_activity",
        ],
        "member_mappings": [
            {
                "plane_user_id": str(user.id),
                "discord_user_id": "123456789012345678",
            }
        ],
    }


@pytest.mark.contract
@pytest.mark.django_db
def test_configuration_defaults_and_authorization(api_client, regular_user, admin_client):
    api_client.force_authenticate(user=regular_user)
    assert api_client.get(CONFIGURATION_PATH).status_code == 403
    assert api_client.patch(CONFIGURATION_PATH, {}, format="json").status_code == 403
    assert api_client.post(TEST_PATH, {}, format="json").status_code == 403

    response = admin_client.get(CONFIGURATION_PATH)
    assert response.status_code == 200
    assert response.data["enabled"] is False
    assert response.data["workspace_id"] is None
    assert response.data["webhook_configured"] is False
    assert response.data["enabled_events"] == []
    assert response.data["member_mappings"] == []


@pytest.mark.contract
@pytest.mark.django_db
def test_valid_update_masks_encrypts_and_retains_webhook(admin_client, configured_workspace, admin_user):
    response = admin_client.patch(
        CONFIGURATION_PATH,
        valid_payload(configured_workspace, admin_user),
        format="json",
    )
    assert response.status_code == 200
    assert response.data["webhook_configured"] is True
    assert "work_item.daily_reminder" in response.data["enabled_events"]
    assert "user.mentioned" in response.data["enabled_events"]
    assert "work_item.comment_activity" in response.data["enabled_events"]
    assert "webhook_url" not in response.data

    stored = InstanceConfiguration.objects.get(key="DISCORD_WEBHOOK_URL")
    assert stored.value != WEBHOOK_URL
    assert decrypt_data(stored.value) == WEBHOOK_URL

    retained_ciphertext = stored.value
    response = admin_client.patch(
        CONFIGURATION_PATH,
        {
            "enabled": False,
            "workspace_id": str(configured_workspace.id),
            "enabled_events": ["work_item.completed"],
            "member_mappings": [],
        },
        format="json",
    )
    assert response.status_code == 200
    assert response.data["webhook_configured"] is True
    assert InstanceConfiguration.objects.get(key="DISCORD_WEBHOOK_URL").value == retained_ciphertext
    assert "webhook_url" not in admin_client.get(CONFIGURATION_PATH).data


@pytest.mark.contract
@pytest.mark.django_db
@pytest.mark.parametrize("event_key", ["user.mentioned", "work_item.comment_activity"])
def test_interaction_events_are_independently_opt_in(admin_client, configured_workspace, admin_user, event_key):
    payload = valid_payload(configured_workspace, admin_user)
    payload["enabled_events"] = [event_key]
    response = admin_client.patch(CONFIGURATION_PATH, payload, format="json")
    assert response.status_code == 200
    assert response.data["enabled_events"] == [event_key]


@pytest.mark.contract
@pytest.mark.django_db
def test_invalid_url_and_mapping_do_not_partially_update(admin_client, configured_workspace, admin_user):
    initial_payload = valid_payload(configured_workspace, admin_user)
    assert admin_client.patch(CONFIGURATION_PATH, initial_payload, format="json").status_code == 200
    stored_events = InstanceConfiguration.objects.get(key="DISCORD_ENABLED_EVENTS").value
    stored_mappings = InstanceConfiguration.objects.get(key="DISCORD_MEMBER_MAPPINGS").value

    invalid_url_payload = {**initial_payload, "webhook_url": "https://example.com/not-discord"}
    assert admin_client.patch(CONFIGURATION_PATH, invalid_url_payload, format="json").status_code == 400

    outsider = User.objects.create(email="discord-outsider-config@example.com")
    invalid_mapping_payload = {
        **initial_payload,
        "enabled_events": [],
        "member_mappings": [
            {
                "plane_user_id": str(outsider.id),
                "discord_user_id": "234567890123456789",
            }
        ],
    }
    assert admin_client.patch(CONFIGURATION_PATH, invalid_mapping_payload, format="json").status_code == 400
    assert InstanceConfiguration.objects.get(key="DISCORD_ENABLED_EVENTS").value == stored_events
    assert InstanceConfiguration.objects.get(key="DISCORD_MEMBER_MAPPINGS").value == stored_mappings

    invalid_plane_user_payload = {
        **initial_payload,
        "member_mappings": [
            {
                "plane_user_id": "not-a-uuid",
                "discord_user_id": "234567890123456789",
            }
        ],
    }
    response = admin_client.patch(CONFIGURATION_PATH, invalid_plane_user_payload, format="json")
    assert response.status_code == 400
    assert "valid UUID" in response.data["error"]

    unsupported_event_payload = {
        **initial_payload,
        "enabled_events": ["user.mentioned", "work_item.comment_activity", "work_item.unsupported"],
    }
    response = admin_client.patch(CONFIGURATION_PATH, unsupported_event_payload, format="json")
    assert response.status_code == 400
    assert "unsupported" in response.data["error"]
    assert InstanceConfiguration.objects.get(key="DISCORD_ENABLED_EVENTS").value == stored_events


@pytest.mark.contract
@pytest.mark.django_db
def test_workspace_change_revalidates_all_mappings(admin_client, configured_workspace, admin_user):
    other_workspace = Workspace.objects.create(
        name="Other Config Workspace",
        slug="other-config-workspace",
        owner=admin_user,
    )
    payload = valid_payload(configured_workspace, admin_user)
    payload["workspace_id"] = str(other_workspace.id)
    response = admin_client.patch(CONFIGURATION_PATH, payload, format="json")
    assert response.status_code == 400
    assert "active member" in response.data["error"]


@pytest.mark.contract
@pytest.mark.django_db
def test_member_list_is_instance_admin_authorized(admin_client, configured_workspace, admin_user):
    response = admin_client.get(MEMBERS_PATH, {"workspace_id": configured_workspace.id})
    assert response.status_code == 200
    assert response.data == [{"id": str(admin_user.id), "display_name": "Discord Admin"}]

    response = admin_client.get(MEMBERS_PATH, {"workspace_id": "not-a-uuid"})
    assert response.status_code == 400
    assert response.data["error"] == "A valid workspace is required."


@pytest.mark.contract
@pytest.mark.django_db
def test_test_message_reports_success_and_failure_without_mutating_configuration(
    mocker,
    admin_client,
    configured_workspace,
    admin_user,
):
    assert (
        admin_client.patch(
            CONFIGURATION_PATH,
            valid_payload(configured_workspace, admin_user),
            format="json",
        ).status_code
        == 200
    )
    before = {
        configuration.key: configuration.value
        for configuration in InstanceConfiguration.objects.filter(category="DISCORD")
    }

    transport = mocker.patch(
        "plane.license.api.views.configuration.send_discord_webhook",
        return_value=(True, None),
    )
    response = admin_client.post(TEST_PATH, {}, format="json")
    assert response.status_code == 200
    assert response.data == {"accepted": True}
    transport.assert_called_once()

    transport.reset_mock()
    transport.return_value = (False, "timeout")
    response = admin_client.post(TEST_PATH, {}, format="json")
    assert response.status_code == 400
    assert response.data["accepted"] is False
    assert response.data["category"] == "timeout"
    transport.assert_called_once()
    after = {
        configuration.key: configuration.value
        for configuration in InstanceConfiguration.objects.filter(category="DISCORD")
    }
    assert after == before


@pytest.mark.contract
@pytest.mark.django_db
def test_generic_configuration_endpoint_cannot_read_or_replace_discord_secret(admin_client):
    encrypted = encrypt_data(WEBHOOK_URL)
    InstanceConfiguration.objects.create(
        key="DISCORD_WEBHOOK_URL",
        value=encrypted,
        category="DISCORD",
        is_encrypted=True,
    )
    InstanceConfiguration.objects.create(
        key="DISCORD_ENABLED_EVENTS",
        value=json.dumps(["work_item.created"]),
        category="DISCORD",
        is_encrypted=False,
    )

    response = admin_client.get(GENERIC_CONFIGURATION_PATH)
    assert response.status_code == 200
    assert all(item["key"] != "DISCORD_WEBHOOK_URL" for item in response.data)

    response = admin_client.patch(
        GENERIC_CONFIGURATION_PATH,
        {"DISCORD_WEBHOOK_URL": "https://example.com/bypass"},
        format="json",
    )
    assert response.status_code == 200
    assert InstanceConfiguration.objects.get(key="DISCORD_WEBHOOK_URL").value == encrypted
