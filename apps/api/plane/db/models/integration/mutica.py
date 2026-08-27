# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q

from plane.db.models import BaseModel
from plane.db.models.project import ProjectBaseModel


class MuticaConnection(BaseModel):
    workspace_integration = models.OneToOneField(
        "db.WorkspaceIntegration",
        related_name="mutica_connection",
        on_delete=models.CASCADE,
    )
    endpoint_url = models.URLField(max_length=2048)
    signing_secret = models.TextField()
    is_enabled = models.BooleanField(default=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    disabled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "mutica_connections"
        ordering = ("-created_at",)


class MuticaExternalAgent(BaseModel):
    workspace_integration = models.ForeignKey(
        "db.WorkspaceIntegration",
        related_name="mutica_agents",
        on_delete=models.CASCADE,
    )
    external_id = models.CharField(max_length=255)
    display_name = models.CharField(max_length=255)
    avatar_url = models.URLField(max_length=2048, null=True, blank=True)
    is_default = models.BooleanField(default=False)
    is_enabled = models.BooleanField(default=True)

    class Meta:
        db_table = "mutica_external_agents"
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=["workspace_integration", "external_id"],
                condition=Q(deleted_at__isnull=True),
                name="mutica_agent_unique_external_id",
            ),
            models.UniqueConstraint(
                fields=["workspace_integration"],
                condition=Q(is_default=True, is_enabled=True, deleted_at__isnull=True),
                name="mutica_agent_one_enabled_default",
            ),
        ]


class MuticaDelegationStatus(models.TextChoices):
    DISPATCHING = "dispatching", "Dispatching"
    HANDED_OFF = "handed_off", "Handed off"
    FAILED = "failed", "Failed"
    SUPERSEDED = "superseded", "Superseded"


class MuticaIssueDelegation(ProjectBaseModel):
    issue = models.ForeignKey("db.Issue", related_name="mutica_delegations", on_delete=models.CASCADE)
    agent = models.ForeignKey(
        "db.MuticaExternalAgent",
        related_name="delegations",
        on_delete=models.PROTECT,
    )
    initiated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="mutica_delegations",
        on_delete=models.SET_NULL,
        null=True,
    )
    correlation_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    status = models.CharField(
        max_length=32,
        choices=MuticaDelegationStatus.choices,
        default=MuticaDelegationStatus.DISPATCHING,
    )
    failure_category = models.CharField(max_length=64, blank=True)
    handed_off_at = models.DateTimeField(null=True, blank=True)
    superseded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "mutica_issue_delegations"
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=["issue"],
                condition=Q(status__in=["dispatching", "handed_off", "failed"]),
                name="mutica_delegation_one_active_per_issue",
            )
        ]


class MuticaDeliveryStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    ACCEPTED = "accepted", "Accepted"
    RETRYABLE_FAILURE = "retryable_failure", "Retryable failure"
    PERMANENT_FAILURE = "permanent_failure", "Permanent failure"
    STALE = "stale", "Stale"


class MuticaDeliveryAttempt(BaseModel):
    delegation = models.ForeignKey(
        "db.MuticaIssueDelegation",
        related_name="delivery_attempts",
        on_delete=models.CASCADE,
    )
    delivery_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    attempt_number = models.PositiveSmallIntegerField()
    status = models.CharField(
        max_length=32,
        choices=MuticaDeliveryStatus.choices,
        default=MuticaDeliveryStatus.PENDING,
    )
    response_status = models.PositiveSmallIntegerField(null=True, blank=True)
    failure_category = models.CharField(max_length=64, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "mutica_delivery_attempts"
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=["delegation", "attempt_number"],
                name="mutica_delivery_unique_attempt_number",
            )
        ]
