# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import datetime
import logging
import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.utils import timezone


MAX_DEPTH = 20
logger = logging.getLogger("plane.migrations.project_page_hierarchy")


def _audit_fields():
    return [
        ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Created At")),
        ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Last Modified At")),
        ("deleted_at", models.DateTimeField(blank=True, null=True, verbose_name="Deleted At")),
        (
            "id",
            models.UUIDField(
                db_index=True,
                default=uuid.uuid4,
                editable=False,
                primary_key=True,
                serialize=False,
                unique=True,
            ),
        ),
        (
            "created_by",
            models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="%(class)s_created_by",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Created By",
            ),
        ),
        (
            "updated_by",
            models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="%(class)s_updated_by",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Last Modified By",
            ),
        ),
    ]


def backfill_project_page_hierarchy(apps, schema_editor):
    ProjectPage = apps.get_model("db", "ProjectPage")
    HierarchyState = apps.get_model("db", "ProjectPageHierarchyState")

    totals = {
        "projects": 0,
        "links": 0,
        "preserved_parents": 0,
        "missing_or_cross_project_parents": 0,
        "cycle_or_depth_repairs": 0,
        "archived_links": 0,
    }
    project_ids = ProjectPage.objects.filter(deleted_at__isnull=True).values_list("project_id", flat=True).distinct()
    for project_id in project_ids.iterator():
        links = list(
            ProjectPage.objects.filter(project_id=project_id, deleted_at__isnull=True)
            .select_related("page")
            .order_by("page__sort_order", "page_id")
        )
        by_page_id = {link.page_id: link for link in links}
        candidates = {}
        for link in links:
            parent_page_id = link.page.parent_id
            candidates[link.id] = by_page_id.get(parent_page_id).id if parent_page_id in by_page_id else None
            if parent_page_id and parent_page_id not in by_page_id:
                totals["missing_or_cross_project_parents"] += 1

        accepted = {}
        for link in links:
            candidate = candidates[link.id]
            chain = {link.id}
            depth = 1
            cursor = candidate
            valid = True
            while cursor is not None:
                if cursor in chain or depth >= MAX_DEPTH:
                    valid = False
                    break
                chain.add(cursor)
                cursor = accepted.get(cursor, candidates.get(cursor))
                depth += 1
            accepted[link.id] = candidate if valid else None
            if candidate is not None and valid:
                totals["preserved_parents"] += 1
            elif candidate is not None:
                totals["cycle_or_depth_repairs"] += 1

        for link in links:
            legacy_archived_at = link.page.archived_at
            if legacy_archived_at and not isinstance(legacy_archived_at, datetime.datetime):
                legacy_archived_at = timezone.make_aware(
                    datetime.datetime.combine(legacy_archived_at, datetime.time.min)
                )
            link.parent_id = accepted[link.id]
            link.sort_order = link.page.sort_order
            link.archived_at = legacy_archived_at
            if legacy_archived_at:
                totals["archived_links"] += 1

        ProjectPage.objects.bulk_update(links, ["parent", "sort_order", "archived_at"], batch_size=1000)
        first = links[0]
        HierarchyState.objects.get_or_create(
            project_id=project_id,
            defaults={"workspace_id": first.workspace_id, "revision": 0},
        )
        totals["projects"] += 1
        totals["links"] += len(links)

    invalid_parent_count = ProjectPage.objects.filter(
        deleted_at__isnull=True,
        parent__isnull=False,
    ).exclude(project_id=models.F("parent__project_id")).count()
    if invalid_parent_count:
        raise RuntimeError("Project Page hierarchy backfill produced cross-project parents")
    logger.info("Project Page hierarchy backfill complete", extra={"hierarchy_backfill": totals})


def reverse_backfill(apps, schema_editor):
    # The reverse schema operations remove only the new project placement data.
    # Legacy Page hierarchy and content were never changed by the forward migration.
    logger.info(
        "Project Page hierarchy reverse requested; legacy Page hierarchy and content remain unchanged",
        extra={"database": schema_editor.connection.alias},
    )


class Migration(migrations.Migration):
    dependencies = [("db", "0123_mutica_agent_delegation")]

    operations = [
        migrations.AddField(
            model_name="projectpage",
            name="archive_batch_id",
            field=models.UUIDField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="projectpage",
            name="archived_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="projectpage",
            name="parent",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="children",
                to="db.projectpage",
            ),
        ),
        migrations.AddField(
            model_name="projectpage",
            name="sort_order",
            field=models.FloatField(default=65535),
        ),
        migrations.CreateModel(
            name="ProjectPageHierarchyState",
            fields=_audit_fields()
            + [
                ("revision", models.PositiveBigIntegerField(default=0)),
                (
                    "project",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="page_hierarchy_state",
                        to="db.project",
                    ),
                ),
                (
                    "workspace",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="page_hierarchy_states",
                        to="db.workspace",
                    ),
                ),
            ],
            options={"db_table": "project_page_hierarchy_states", "ordering": ("-created_at",)},
        ),
        migrations.CreateModel(
            name="ProjectPageHierarchyMutation",
            fields=_audit_fields()
            + [
                ("operation_id", models.UUIDField()),
                ("operation", models.CharField(max_length=32)),
                ("outcome", models.CharField(max_length=32)),
                ("root_page_id", models.UUIDField(blank=True, null=True)),
                ("old_parent_page_id", models.UUIDField(blank=True, null=True)),
                ("new_parent_page_id", models.UUIDField(blank=True, null=True)),
                ("descendant_count", models.PositiveIntegerField(default=0)),
                ("revision", models.PositiveBigIntegerField(default=0)),
                ("result", models.JSONField(default=dict)),
                (
                    "actor",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="page_hierarchy_mutations",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "project",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="page_hierarchy_mutations",
                        to="db.project",
                    ),
                ),
                (
                    "workspace",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="page_hierarchy_mutations",
                        to="db.workspace",
                    ),
                ),
            ],
            options={"db_table": "project_page_hierarchy_mutations", "ordering": ("-created_at",)},
        ),
        migrations.AddIndex(
            model_name="projectpage",
            index=models.Index(
                fields=["project", "parent", "archived_at", "sort_order", "id"],
                name="project_page_active_tree_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="projectpage",
            index=models.Index(
                fields=["project", "archived_at", "archive_batch_id"],
                name="project_page_archive_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="projectpagehierarchymutation",
            constraint=models.UniqueConstraint(
                condition=models.Q(deleted_at__isnull=True),
                fields=("project", "actor", "operation_id"),
                name="project_page_mutation_idempotency",
            ),
        ),
        migrations.AddIndex(
            model_name="projectpagehierarchymutation",
            index=models.Index(fields=["project", "revision"], name="project_page_mutation_rev_idx"),
        ),
        migrations.RunPython(backfill_project_page_hierarchy, reverse_code=reverse_backfill),
    ]
