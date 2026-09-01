# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Python imports
import os
from datetime import timedelta

# Django imports
from django.utils import timezone
from django.db.models import Q

# Third party imports
from celery import shared_task

# Module imports
from plane.db.models import FileAsset
from plane.license.models import StorageProfile
from plane.settings.storage import S3Storage


@shared_task
def delete_unuploaded_file_asset():
    """This task deletes unuploaded file assets older than a certain number of days."""
    expired = FileAsset.objects.filter(
        Q(created_at__lt=timezone.now() - timedelta(days=int(os.environ.get("UNUPLOADED_ASSET_DELETE_DAYS", "7"))))
        & Q(is_uploaded=False)
    ).select_related("storage_profile")[:500]
    ids = []
    for asset in expired:
        S3Storage.for_asset(asset).delete_files([asset.asset.name])
        ids.append(asset.id)
    if ids:
        FileAsset.objects.filter(id__in=ids, is_uploaded=False).delete()

    probe_cutoff = timezone.now() - timedelta(days=1)
    profiles = StorageProfile.objects.exclude(probe_object_key="").filter(last_probe_at__lt=probe_cutoff)[:100]
    for profile in profiles:
        S3Storage(profile=profile).delete_files([profile.probe_object_key])
        profile.probe_object_key = ""
        profile.save(update_fields=["probe_object_key", "updated_at"])
