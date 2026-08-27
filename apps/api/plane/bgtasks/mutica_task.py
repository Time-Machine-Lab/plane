# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import hashlib
import hmac
import json
from datetime import timezone as datetime_timezone

import requests
from celery import shared_task
from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.utils import timezone

from plane.db.models import (
    IssueActivity,
    MuticaConnection,
    MuticaDelegationStatus,
    MuticaDeliveryAttempt,
    MuticaDeliveryStatus,
    MuticaIssueDelegation,
)
from plane.utils.secret_encryption import decrypt_secret
from plane.utils.url_security import pinned_fetch


MAX_DELIVERY_RETRIES = 2
RETRYABLE_STATUS_CODES = {408, 425, 429}


def build_mutica_event(delegation: MuticaIssueDelegation, attempt: MuticaDeliveryAttempt) -> tuple[bytes, dict[str, str]]:
    connection = MuticaConnection.objects.get(workspace_integration=delegation.agent.workspace_integration)
    timestamp = str(int(timezone.now().timestamp()))
    plane_origin = (settings.APP_BASE_URL or settings.WEB_URL or "http://localhost").rstrip("/")
    payload = {
        "type": "plane.work_item.delegated",
        "schema_version": 1,
        "event_id": f"mutica-delegation:{delegation.id}",
        "delivery_id": str(attempt.delivery_id),
        "delegation_id": str(delegation.id),
        "delegated_at": delegation.created_at.astimezone(datetime_timezone.utc).isoformat(),
        "plane_origin": plane_origin,
        "workspace_slug": delegation.workspace.slug,
        "project_id": str(delegation.project_id),
        "work_item_id": str(delegation.issue_id),
        "work_item_url": (
            f"{plane_origin}/{delegation.workspace.slug}/projects/{delegation.project_id}/issues/{delegation.issue_id}"
        ),
        "agent_external_id": delegation.agent.external_id,
    }
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"), cls=DjangoJSONEncoder).encode("utf-8")
    secret = decrypt_secret(connection.signing_secret).encode("utf-8")
    signature = hmac.new(secret, timestamp.encode("ascii") + b"." + body, hashlib.sha256).hexdigest()
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Idempotency-Key": str(delegation.id),
        "X-Plane-Delivery-ID": str(attempt.delivery_id),
        "X-Plane-Timestamp": timestamp,
        "X-Plane-Signature": f"sha256={signature}",
        "User-Agent": "Plane-Mutica/1",
    }
    return body, headers


def _record_activity(delegation: MuticaIssueDelegation, verb: str, value: str = "") -> None:
    IssueActivity.objects.create(
        issue=delegation.issue,
        project=delegation.project,
        workspace=delegation.workspace,
        field="mutica_delegation",
        verb=verb,
        actor=delegation.initiated_by,
        new_value=value or delegation.agent.display_name,
        new_identifier=delegation.id,
    )


def _mark_failed(delegation: MuticaIssueDelegation, category: str) -> None:
    changed = MuticaIssueDelegation.objects.filter(
        pk=delegation.pk,
        status=MuticaDelegationStatus.DISPATCHING,
    ).update(status=MuticaDelegationStatus.FAILED, failure_category=category)
    if changed:
        _record_activity(delegation, "failed", category)


@shared_task(bind=True, max_retries=MAX_DELIVERY_RETRIES)
def deliver_mutica_delegation(self, delegation_id: str, attempt_offset: int = 1) -> None:
    delegation = (
        MuticaIssueDelegation.objects.select_related(
            "workspace",
            "project",
            "issue",
            "agent__workspace_integration",
            "initiated_by",
        )
        .filter(pk=delegation_id)
        .first()
    )
    if delegation is None:
        return

    attempt_number = attempt_offset + self.request.retries
    attempt, _ = MuticaDeliveryAttempt.objects.get_or_create(
        delegation=delegation,
        attempt_number=attempt_number,
    )
    if delegation.status != MuticaDelegationStatus.DISPATCHING:
        if attempt.status == MuticaDeliveryStatus.PENDING:
            attempt.status = MuticaDeliveryStatus.STALE
            attempt.completed_at = timezone.now()
            attempt.save(update_fields=["status", "completed_at", "updated_at"])
        return

    connection = MuticaConnection.objects.filter(
        workspace_integration=delegation.agent.workspace_integration,
        is_enabled=True,
    ).first()
    if connection is None or not delegation.agent.is_enabled:
        attempt.status = MuticaDeliveryStatus.PERMANENT_FAILURE
        attempt.failure_category = "connection_disabled"
        attempt.completed_at = timezone.now()
        attempt.save(update_fields=["status", "failure_category", "completed_at", "updated_at"])
        _mark_failed(delegation, "connection_disabled")
        return

    response = None
    try:
        body, headers = build_mutica_event(delegation, attempt)
        response = pinned_fetch(
            "POST",
            connection.endpoint_url,
            allowed_ips=settings.WEBHOOK_ALLOWED_IPS,
            allowed_hosts=settings.WEBHOOK_ALLOWED_HOSTS,
            headers=headers,
            timeout=10,
            data=body,
        )
        attempt.response_status = response.status_code
        if 200 <= response.status_code < 300:
            attempt.status = MuticaDeliveryStatus.ACCEPTED
            attempt.completed_at = timezone.now()
            attempt.save(update_fields=["status", "response_status", "completed_at", "updated_at"])
            changed = MuticaIssueDelegation.objects.filter(
                pk=delegation.pk,
                status=MuticaDelegationStatus.DISPATCHING,
            ).update(status=MuticaDelegationStatus.HANDED_OFF, handed_off_at=timezone.now(), failure_category="")
            if changed:
                _record_activity(delegation, "handed_off")
            else:
                MuticaDeliveryAttempt.objects.filter(pk=attempt.pk).update(status=MuticaDeliveryStatus.STALE)
            return

        retryable = response.status_code in RETRYABLE_STATUS_CODES or response.status_code >= 500
        category = "mutica_unavailable" if retryable else "mutica_rejected"
    except requests.Timeout:
        retryable = True
        category = "timeout"
    except requests.RequestException:
        retryable = True
        category = "transport_error"
    except ValueError:
        retryable = False
        category = "unsafe_endpoint"
    finally:
        if response is not None:
            response.close()

    attempt.status = MuticaDeliveryStatus.RETRYABLE_FAILURE if retryable else MuticaDeliveryStatus.PERMANENT_FAILURE
    attempt.failure_category = category
    attempt.completed_at = timezone.now()
    attempt.save(
        update_fields=["status", "response_status", "failure_category", "completed_at", "updated_at"]
    )
    if retryable and self.request.retries < MAX_DELIVERY_RETRIES:
        raise self.retry(countdown=2 ** self.request.retries)
    _mark_failed(delegation, category)
