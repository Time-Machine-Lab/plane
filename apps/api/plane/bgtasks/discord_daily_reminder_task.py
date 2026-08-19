# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import logging
from datetime import date, datetime, timezone as datetime_timezone

import pytz
from celery import shared_task
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from plane.db.models import Workspace
from plane.integrations.discord import (
    DISCORD_EVENT_WORK_ITEM_DAILY_REMINDER,
    collect_daily_reminder_groups,
    deliver_daily_task_briefs,
    get_discord_configuration,
)


logger = logging.getLogger("plane.worker")

DISCORD_DAILY_REMINDER_CACHE_PREFIX = "discord:daily-task-reminder"
DISCORD_DAILY_REMINDER_CLAIM_TTL_SECONDS = 60 * 60 * 48


def _claim_daily_reminder(workspace_id: str, local_date: date) -> bool:
    cache_key = f"{DISCORD_DAILY_REMINDER_CACHE_PREFIX}:{workspace_id}:{local_date.isoformat()}"
    try:
        return bool(cache.add(cache_key, "claimed", timeout=DISCORD_DAILY_REMINDER_CLAIM_TTL_SECONDS))
    except Exception:
        logger.exception(
            "Discord daily reminder claim failed",
            extra={"workspace_id": workspace_id, "local_date": local_date.isoformat()},
        )
        return False


def process_discord_daily_task_reminder(*, now: datetime | None = None) -> None:
    configuration = get_discord_configuration()
    if (
        not configuration.enabled
        or not configuration.workspace_id
        or not configuration.webhook_url
        or DISCORD_EVENT_WORK_ITEM_DAILY_REMINDER not in configuration.enabled_events
    ):
        return

    workspace = Workspace.objects.only("id", "slug", "timezone").filter(pk=configuration.workspace_id).first()
    if not workspace:
        return

    current_time = now or timezone.now()
    if timezone.is_naive(current_time):
        current_time = current_time.replace(tzinfo=datetime_timezone.utc)
    try:
        local_time = current_time.astimezone(pytz.timezone(workspace.timezone or "UTC"))
    except pytz.UnknownTimeZoneError:
        logger.error(
            "Discord daily reminder workspace timezone is invalid",
            extra={"workspace_id": str(workspace.id)},
        )
        return

    if local_time.hour != 8:
        return

    base_url = (settings.APP_BASE_URL or settings.WEB_URL or "").rstrip("/")
    if not base_url:
        logger.error(
            "Discord daily reminder application base URL is unavailable",
            extra={"workspace_id": str(workspace.id)},
        )
        return

    local_date = local_time.date()
    if not _claim_daily_reminder(str(workspace.id), local_date):
        return

    groups = collect_daily_reminder_groups(
        workspace_id=str(workspace.id),
        local_date=local_date,
    )
    if not groups:
        return

    deliver_daily_task_briefs(
        configuration=configuration,
        groups=groups,
        base_url=base_url,
    )


@shared_task
def discord_daily_task_reminder() -> None:
    try:
        process_discord_daily_task_reminder()
    except Exception:
        logger.exception("Discord daily reminder processing failed")
