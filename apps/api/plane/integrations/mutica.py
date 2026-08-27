# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import hashlib
import hmac
import json
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from plane.db.models import (
    APIToken,
    BotTypeEnum,
    Integration,
    MuticaConnection,
    MuticaExternalAgent,
    Project,
    ProjectMember,
    User,
    WorkspaceIntegration,
    WorkspaceMember,
)
from plane.utils.secret_encryption import encrypt_secret
from plane.utils.url_security import pinned_fetch


MUTICA_PROVIDER = "mutica"
MUTICA_MEMBER_ROLE = 15
VERIFICATION_EVENT = "plane.mutica.connection.verify"


def _verify_headers(body: bytes, signing_secret: str) -> dict[str, str]:
    timestamp = str(int(timezone.now().timestamp()))
    signature = hmac.new(
        signing_secret.encode("utf-8"),
        timestamp.encode("ascii") + b"." + body,
        hashlib.sha256,
    ).hexdigest()
    return {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-Plane-Timestamp": timestamp,
        "X-Plane-Signature": f"sha256={signature}",
        "User-Agent": "Plane-Mutica/1",
    }


def verify_mutica_endpoint(endpoint_url: str, workspace_slug: str, signing_secret: str, agent_external_id: str) -> None:
    body = json.dumps(
        {
            "type": VERIFICATION_EVENT,
            "schema_version": 1,
            "workspace_slug": workspace_slug,
            "agent_external_id": agent_external_id,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    response = pinned_fetch(
        "POST",
        endpoint_url,
        allowed_ips=settings.WEBHOOK_ALLOWED_IPS,
        allowed_hosts=settings.WEBHOOK_ALLOWED_HOSTS,
        headers=_verify_headers(body, signing_secret),
        timeout=5,
        data=body,
    )
    try:
        if not 200 <= response.status_code < 300:
            raise ValueError("Mutica rejected the connection verification request")
    finally:
        response.close()


def _ensure_bot(workspace) -> User:
    bot_email = f"mutica-{workspace.id}@bots.plane.local"
    bot, created = User.objects.get_or_create(
        email=bot_email,
        defaults={
            "username": f"mutica-{workspace.id}",
            "display_name": "Mutica Integration",
            "first_name": "Mutica",
            "last_name": "Integration",
            "is_bot": True,
            "bot_type": BotTypeEnum.MUTICA,
            "is_active": True,
            "is_email_verified": True,
        },
    )
    if created:
        bot.set_unusable_password()
        bot.save(update_fields=["password"])
    changed_fields = []
    if not bot.is_active:
        bot.is_active = True
        changed_fields.append("is_active")
    if bot.bot_type != BotTypeEnum.MUTICA:
        bot.bot_type = BotTypeEnum.MUTICA
        changed_fields.append("bot_type")
    if changed_fields:
        bot.save(update_fields=changed_fields)
    return bot


def sync_mutica_project_membership(project: Project) -> None:
    connection = (
        MuticaConnection.objects.filter(
            workspace_integration__workspace_id=project.workspace_id,
            is_enabled=True,
            workspace_integration__integration__provider=MUTICA_PROVIDER,
        )
        .select_related("workspace_integration__actor")
        .first()
    )
    if connection is None:
        return
    ProjectMember.objects.update_or_create(
        project=project,
        member=connection.workspace_integration.actor,
        defaults={"role": MUTICA_MEMBER_ROLE, "is_active": True},
    )


@transaction.atomic
def connect_mutica(
    *,
    workspace,
    endpoint_url: str,
    signing_secret: str,
    agent_external_id: str,
    agent_display_name: str,
    agent_avatar_url: str | None,
) -> tuple[MuticaConnection, str]:
    integration = Integration.objects.get(provider=MUTICA_PROVIDER)
    bot = _ensure_bot(workspace)
    WorkspaceMember.objects.update_or_create(
        workspace=workspace,
        member=bot,
        defaults={"role": MUTICA_MEMBER_ROLE, "is_active": True},
    )
    for project in Project.objects.filter(workspace=workspace, deleted_at__isnull=True).iterator():
        ProjectMember.objects.update_or_create(
            project=project,
            member=bot,
            defaults={"role": MUTICA_MEMBER_ROLE, "is_active": True},
        )

    old_integration = WorkspaceIntegration.objects.filter(workspace=workspace, integration=integration).first()
    if old_integration is not None:
        APIToken.objects.filter(pk=old_integration.api_token_id).update(is_active=False)

    token = APIToken.objects.create(
        label="Mutica workspace service token",
        description="Workspace-bound service credential for the Mutica integration.",
        user=bot,
        user_type=1,
        workspace=workspace,
        is_service=True,
    )
    workspace_integration, _ = WorkspaceIntegration.objects.update_or_create(
        workspace=workspace,
        integration=integration,
        defaults={"actor": bot, "api_token": token, "metadata": {}, "config": {}},
    )
    connection, _ = MuticaConnection.objects.update_or_create(
        workspace_integration=workspace_integration,
        defaults={
            "endpoint_url": endpoint_url,
            "signing_secret": encrypt_secret(signing_secret),
            "is_enabled": True,
            "verified_at": timezone.now(),
            "disabled_at": None,
        },
    )
    MuticaExternalAgent.objects.filter(workspace_integration=workspace_integration).update(
        is_default=False, is_enabled=False
    )
    MuticaExternalAgent.objects.update_or_create(
        workspace_integration=workspace_integration,
        external_id=agent_external_id,
        defaults={
            "display_name": agent_display_name,
            "avatar_url": agent_avatar_url,
            "is_default": True,
            "is_enabled": True,
        },
    )
    return connection, token.token


@transaction.atomic
def rotate_mutica_service_token(connection: MuticaConnection) -> str:
    workspace_integration = WorkspaceIntegration.objects.select_for_update().get(
        pk=connection.workspace_integration_id
    )
    APIToken.objects.filter(pk=workspace_integration.api_token_id).update(is_active=False)
    token = APIToken.objects.create(
        label="Mutica workspace service token",
        description="Workspace-bound service credential for the Mutica integration.",
        user=workspace_integration.actor,
        user_type=1,
        workspace=workspace_integration.workspace,
        is_service=True,
    )
    workspace_integration.api_token = token
    workspace_integration.save(update_fields=["api_token", "updated_at"])
    return token.token


@transaction.atomic
def disconnect_mutica(connection: MuticaConnection) -> None:
    from plane.db.models import MuticaDelegationStatus, MuticaIssueDelegation

    workspace_integration = WorkspaceIntegration.objects.select_for_update().get(
        pk=connection.workspace_integration_id
    )
    APIToken.objects.filter(pk=workspace_integration.api_token_id).update(is_active=False)
    connection.is_enabled = False
    connection.disabled_at = timezone.now()
    connection.save(update_fields=["is_enabled", "disabled_at", "updated_at"])
    MuticaExternalAgent.objects.filter(workspace_integration=workspace_integration).update(is_enabled=False)
    MuticaIssueDelegation.objects.filter(
        workspace_id=workspace_integration.workspace_id,
        status__in=[
            MuticaDelegationStatus.DISPATCHING,
            MuticaDelegationStatus.HANDED_OFF,
            MuticaDelegationStatus.FAILED,
        ],
    ).update(status=MuticaDelegationStatus.SUPERSEDED, superseded_at=timezone.now())
