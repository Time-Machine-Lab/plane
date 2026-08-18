# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import json
import logging
from typing import Any

from celery import shared_task

from plane.integrations.discord import deliver_issue_notifications


logger = logging.getLogger("plane.worker")


def _deserialize_activity_value(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return None


@shared_task
def discord_issue_notification(
    *,
    activity_type,
    requested_data,
    current_instance,
    issue_id,
    actor_id,
    origin=None,
):
    try:
        parsed_requested_data = _deserialize_activity_value(requested_data)
        parsed_current_instance = _deserialize_activity_value(current_instance)
        if not isinstance(parsed_requested_data, dict):
            return
        if parsed_current_instance is not None and not isinstance(parsed_current_instance, dict):
            return
        deliver_issue_notifications(
            activity_type=activity_type,
            requested_data=parsed_requested_data,
            current_instance=parsed_current_instance,
            issue_id=str(issue_id),
            actor_id=str(actor_id),
            origin=origin,
        )
    except Exception:
        logger.exception(
            "Discord notification processing failed",
            extra={"issue_id": str(issue_id), "activity_type": activity_type},
        )
