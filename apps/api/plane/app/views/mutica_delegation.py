# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.db import transaction
from django.db.models import Max
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response

from plane.app.permissions import ProjectEntityPermission, ROLE, allow_permission
from plane.bgtasks.mutica_task import deliver_mutica_delegation
from plane.db.models import (
    Issue,
    IssueActivity,
    MuticaConnection,
    MuticaDelegationStatus,
    MuticaExternalAgent,
    MuticaIssueDelegation,
)

from .base import BaseAPIView


ACTIVE_STATUSES = [
    MuticaDelegationStatus.DISPATCHING,
    MuticaDelegationStatus.HANDED_OFF,
    MuticaDelegationStatus.FAILED,
]


def serialize_agent(agent: MuticaExternalAgent) -> dict:
    return {
        "id": str(agent.id),
        "external_id": agent.external_id,
        "display_name": agent.display_name,
        "avatar_url": agent.avatar_url,
        "is_enabled": agent.is_enabled,
    }


def serialize_delegation(delegation: MuticaIssueDelegation) -> dict:
    return {
        "id": str(delegation.id),
        "work_item_id": str(delegation.issue_id),
        "status": delegation.status,
        "failure_category": delegation.failure_category or None,
        "agent": serialize_agent(delegation.agent),
        "initiated_by": str(delegation.initiated_by_id) if delegation.initiated_by_id else None,
        "created_at": delegation.created_at,
        "handed_off_at": delegation.handed_off_at,
        "superseded_at": delegation.superseded_at,
    }


def _activity(delegation: MuticaIssueDelegation, verb: str, actor, value: str | None = None) -> None:
    IssueActivity.objects.create(
        issue=delegation.issue,
        project=delegation.project,
        workspace=delegation.workspace,
        field="mutica_delegation",
        verb=verb,
        actor=actor,
        new_value=value or delegation.agent.display_name,
        new_identifier=delegation.id,
    )


def _default_agent(slug: str) -> MuticaExternalAgent | None:
    return (
        MuticaExternalAgent.objects.filter(
            workspace_integration__workspace__slug=slug,
            workspace_integration__integration__provider="mutica",
            workspace_integration__mutica_connection__is_enabled=True,
            is_default=True,
            is_enabled=True,
        )
        .select_related("workspace_integration")
        .first()
    )


class MuticaAssistantAvailabilityEndpoint(BaseAPIView):
    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST], level="WORKSPACE")
    def get(self, request, slug):
        agent = _default_agent(slug)
        return Response(
            {"available": agent is not None, "assistant": serialize_agent(agent) if agent else None},
            status=status.HTTP_200_OK,
        )


class MuticaIssueDelegationEndpoint(BaseAPIView):
    permission_classes = [ProjectEntityPermission]

    def get(self, request, slug, project_id, issue_id):
        Issue.objects.get(pk=issue_id, workspace__slug=slug, project_id=project_id)
        delegations = MuticaIssueDelegation.objects.filter(
            issue_id=issue_id,
            workspace__slug=slug,
            project_id=project_id,
        ).select_related("agent")
        current = delegations.filter(status__in=ACTIVE_STATUSES).first()
        agent = _default_agent(slug)
        return Response(
            {
                "available": agent is not None,
                "assistant": serialize_agent(agent) if agent else None,
                "current": serialize_delegation(current) if current else None,
                "history": [serialize_delegation(item) for item in delegations.order_by("-created_at")[:50]],
            },
            status=status.HTTP_200_OK,
        )

    @transaction.atomic
    def post(self, request, slug, project_id, issue_id):
        issue = Issue.objects.select_for_update().get(pk=issue_id, workspace__slug=slug, project_id=project_id)
        agent_id = request.data.get("agent_id")
        agent = _default_agent(slug) if not agent_id else MuticaExternalAgent.objects.filter(
            pk=agent_id,
            workspace_integration__workspace__slug=slug,
            workspace_integration__mutica_connection__is_enabled=True,
            is_enabled=True,
        ).first()
        if agent is None:
            return Response({"error": "Mutica is not available."}, status=status.HTTP_409_CONFLICT)

        previous = MuticaIssueDelegation.objects.filter(issue=issue, status__in=ACTIVE_STATUSES).first()
        if previous is not None:
            previous.status = MuticaDelegationStatus.SUPERSEDED
            previous.superseded_at = timezone.now()
            previous.save(update_fields=["status", "superseded_at", "updated_at"])

        delegation = MuticaIssueDelegation.objects.create(
            issue=issue,
            project=issue.project,
            agent=agent,
            initiated_by=request.user,
        )
        _activity(delegation, "reassigned" if previous else "delegated", request.user)
        transaction.on_commit(lambda: deliver_mutica_delegation.delay(str(delegation.id), 1))
        return Response(serialize_delegation(delegation), status=status.HTTP_201_CREATED)

    @transaction.atomic
    def delete(self, request, slug, project_id, issue_id):
        Issue.objects.select_for_update().get(pk=issue_id, workspace__slug=slug, project_id=project_id)
        delegation = (
            MuticaIssueDelegation.objects.filter(issue_id=issue_id, status__in=ACTIVE_STATUSES)
            .select_related("agent", "issue", "project", "workspace")
            .first()
        )
        if delegation is None:
            return Response(status=status.HTTP_204_NO_CONTENT)
        delegation.status = MuticaDelegationStatus.SUPERSEDED
        delegation.superseded_at = timezone.now()
        delegation.save(update_fields=["status", "superseded_at", "updated_at"])
        _activity(delegation, "cleared", request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MuticaIssueDelegationRetryEndpoint(BaseAPIView):
    permission_classes = [ProjectEntityPermission]

    @transaction.atomic
    def post(self, request, slug, project_id, issue_id):
        Issue.objects.select_for_update().get(pk=issue_id, workspace__slug=slug, project_id=project_id)
        delegation = (
            MuticaIssueDelegation.objects.select_for_update()
            .filter(issue_id=issue_id, status=MuticaDelegationStatus.FAILED)
            .select_related("agent", "issue", "project", "workspace")
            .first()
        )
        if delegation is None:
            return Response({"error": "No failed Mutica handoff to retry."}, status=status.HTTP_409_CONFLICT)
        connection_exists = MuticaConnection.objects.filter(
            workspace_integration=delegation.agent.workspace_integration,
            is_enabled=True,
        ).exists()
        if not connection_exists or not delegation.agent.is_enabled:
            return Response({"error": "Mutica is not available."}, status=status.HTTP_409_CONFLICT)
        next_attempt = (delegation.delivery_attempts.aggregate(value=Max("attempt_number"))["value"] or 0) + 1
        delegation.status = MuticaDelegationStatus.DISPATCHING
        delegation.failure_category = ""
        delegation.save(update_fields=["status", "failure_category", "updated_at"])
        _activity(delegation, "retried", request.user)
        transaction.on_commit(lambda: deliver_mutica_delegation.delay(str(delegation.id), next_attempt))
        return Response(serialize_delegation(delegation), status=status.HTTP_202_ACCEPTED)
