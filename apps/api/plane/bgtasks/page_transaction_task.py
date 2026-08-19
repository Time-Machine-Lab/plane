# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Python imports
import logging

# Django imports
from django.db import IntegrityError, transaction
from django.utils import timezone

# Third-party imports
from bs4 import BeautifulSoup

# App imports
from celery import shared_task
from plane.db.models import Page, PageLog, Project, ProjectPage, User, WorkspaceMember
from plane.integrations.discord import DiscordPageMentionContext, deliver_page_mention_notification
from plane.utils.exception_logger import log_exception
from plane.utils.rich_text_mentions import build_safe_rich_text_excerpt, classify_interaction_recipients
from plane.utils.uuid import is_valid_uuid

logger = logging.getLogger("plane.worker")

COMPONENT_MAP = {
    "mention-component": {
        "attributes": ["id", "entity_identifier", "entity_name", "entity_type"],
        "extract": lambda m: {
            "entity_name": m.get("entity_name"),
            "entity_type": None,
            "entity_identifier": m.get("entity_identifier"),
        },
    },
    "image-component": {
        "attributes": ["id", "src"],
        "extract": lambda m: {
            "entity_name": "image",
            "entity_type": None,
            "entity_identifier": m.get("src"),
        },
    },
}

component_map = {
    **COMPONENT_MAP,
}


def extract_all_components(description_html):
    """
    Extracts all component types from the HTML value in a single pass.
    Returns a dict mapping component_type -> list of extracted entities.
    """
    try:
        if not description_html:
            return {component: [] for component in component_map.keys()}

        soup = BeautifulSoup(description_html, "html.parser")
        results = {}

        for component, config in component_map.items():
            attributes = config.get("attributes", ["id"])
            component_tags = soup.find_all(component)

            entities = []
            for tag in component_tags:
                entity = {attr: tag.get(attr) for attr in attributes}
                entities.append(entity)

            results[component] = entities

        return results

    except Exception:
        return {component: [] for component in component_map.keys()}


def get_entity_details(component: str, mention: dict):
    """
    Normalizes mention attributes into entity_name, entity_type, entity_identifier.
    """
    config = component_map.get(component)
    if not config:
        return {"entity_name": None, "entity_type": None, "entity_identifier": None}
    return config["extract"](mention)


@shared_task
def page_transaction(
    new_description_html,
    old_description_html,
    page_id,
    actor_id=None,
    project_id=None,
    operation_kind=None,
    origin=None,
):
    """
    Tracks changes in page content (mentions, embeds, etc.)
    and logs them in PageLog for audit and reference.
    """
    try:
        page = Page.objects.get(pk=page_id)

        has_existing_logs = PageLog.objects.filter(page_id=page_id).exists()

        # Extract all components in a single pass (optimized)
        old_components = extract_all_components(old_description_html)
        new_components = extract_all_components(new_description_html)

        notified_user_ids = []
        deleted_transaction_ids = set()

        for component in component_map.keys():
            old_entities = old_components[component]
            new_entities = new_components[component]

            old_ids = {m.get("id") for m in old_entities if m.get("id") and is_valid_uuid(m["id"])}
            new_ids = {m.get("id") for m in new_entities if m.get("id") and is_valid_uuid(m["id"])}
            deleted_transaction_ids.update(old_ids - new_ids)

            for mention in new_entities:
                mention_id = mention.get("id")
                if not mention_id or not is_valid_uuid(mention_id) or (mention_id in old_ids and has_existing_logs):
                    continue

                details = get_entity_details(component, mention)
                current_time = timezone.now()

                try:
                    with transaction.atomic():
                        _, created = PageLog.all_objects.get_or_create(
                            page_id=page_id,
                            transaction=mention_id,
                            defaults={
                                "entity_identifier": details["entity_identifier"],
                                "entity_name": details["entity_name"],
                                "entity_type": details["entity_type"],
                                "workspace_id": page.workspace_id,
                                "created_at": current_time,
                                "updated_at": current_time,
                            },
                        )
                except IntegrityError:
                    created = False
                if (
                    created
                    and mention_id not in old_ids
                    and component == "mention-component"
                    and details["entity_name"] == "user_mention"
                    and details["entity_identifier"]
                ):
                    notified_user_ids.append(str(details["entity_identifier"]))

        if deleted_transaction_ids:
            PageLog.objects.filter(transaction__in=deleted_transaction_ids).delete()

        if operation_kind not in {"direct_create", "direct_edit"} or not actor_id or not project_id:
            return
        if page.access != Page.PUBLIC_ACCESS or str(page.workspace_id) == "":
            return
        if not ProjectPage.objects.filter(
            page_id=page.id,
            project_id=project_id,
            workspace_id=page.workspace_id,
            deleted_at__isnull=True,
        ).exists():
            return
        project = Project.objects.filter(pk=project_id, workspace_id=page.workspace_id).first()
        actor = User.objects.filter(pk=actor_id).first()
        actor_is_member = WorkspaceMember.objects.filter(
            workspace_id=page.workspace_id,
            member_id=actor_id,
            is_active=True,
        ).exists()
        if not project or not actor or not actor_is_member or not notified_user_ids:
            return

        recipients = classify_interaction_recipients(
            origin="page",
            actor_id=str(actor_id),
            newly_mentioned_user_ids=tuple(notified_user_ids),
        ).mention_user_ids
        if not recipients:
            return
        display_names = {
            str(user_id): display_name or "Plane 用户"
            for user_id, display_name in User.objects.filter(pk__in=recipients).values_list("id", "display_name")
        }
        excerpt = build_safe_rich_text_excerpt(
            new_description_html,
            display_names=display_names,
            relevant_user_ids=recipients,
        )
        deliver_page_mention_notification(
            DiscordPageMentionContext(
                workspace_id=str(page.workspace_id),
                page_name=page.name or "未命名页面",
                project_name=project.name,
                workspace_slug=project.workspace.slug,
                project_id=str(project.id),
                page_id=str(page.id),
                actor_name=actor.display_name or actor.full_name or "Plane 用户",
                recipient_plane_user_ids=recipients,
                excerpt=excerpt,
                timestamp=timezone.now(),
                origin=origin,
            )
        )

    except Page.DoesNotExist:
        return
    except Exception as e:
        log_exception(e)
        return
