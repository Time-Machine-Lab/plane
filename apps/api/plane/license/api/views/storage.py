# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only

import uuid

from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response

from .base import BaseAPIView
from plane.license.api.serializers.storage import StorageProfileSerializer
from plane.license.models import Instance, StorageProfile
from plane.settings.storage import S3Storage


def _instance():
    return Instance.objects.order_by("created_at").first()


class StorageProfileEndpoint(BaseAPIView):
    """God Mode CRUD for the compact Aliyun OSS storage configuration."""

    def get(self, request):
        instance = _instance()
        profiles = StorageProfile.objects.filter(instance=instance) if instance else StorageProfile.objects.none()
        return Response(StorageProfileSerializer(profiles, many=True).data)

    @transaction.atomic
    def post(self, request):
        instance = _instance()
        if instance is None:
            return Response({"error": "Instance is not initialized."}, status=status.HTTP_404_NOT_FOUND)
        data = request.data.copy()
        secret = data.pop("access_key_secret", None)
        missing = [field for field in ("access_key_id", "bucket", "region") if not str(data.get(field) or "").strip()]
        if missing or not secret:
            return Response({"error": "Access Key ID, Access Key Secret, Bucket, and Region are required.", "code": "invalid_configuration", "fields": missing + ([] if secret else ["access_key_secret"])}, status=status.HTTP_400_BAD_REQUEST)
        profile = StorageProfile(instance=instance)
        serializer = StorageProfileSerializer(profile, data=data, partial=True)
        serializer.is_valid(raise_exception=True)
        profile = serializer.save(status=StorageProfile.Status.DRAFT)
        if secret:
            profile.set_secret(str(secret))
            profile.save(update_fields=["access_key_secret", "updated_at"])
        return Response(StorageProfileSerializer(profile).data, status=status.HTTP_201_CREATED)

    @transaction.atomic
    def patch(self, request, pk):
        profile = StorageProfile.objects.get(pk=pk)
        data = request.data.copy()
        secret = data.pop("access_key_secret", None)
        serializer = StorageProfileSerializer(profile, data=data, partial=True)
        serializer.is_valid(raise_exception=True)
        # Location changes create a new profile; only credentials and limit can
        # be rotated in place for an active profile.
        location_fields = {"provider", "bucket", "region", "endpoint"}
        if profile.status == StorageProfile.Status.ACTIVE and location_fields.intersection(data):
            return Response({"error": "Create a new profile when changing storage location.", "code": "location_immutable"}, status=status.HTTP_409_CONFLICT)
        profile = serializer.save()
        if secret:
            profile.set_secret(str(secret))
            profile.save(update_fields=["access_key_secret", "updated_at"])
        return Response(StorageProfileSerializer(profile).data)

    def delete(self, request, pk):
        profile = StorageProfile.objects.get(pk=pk)
        if profile.assets.exists():
            return Response({"error": "Storage profile is still referenced by assets.", "code": "profile_in_use"}, status=status.HTTP_409_CONFLICT)
        if profile.status == StorageProfile.Status.ACTIVE:
            return Response({"error": "Roll back active storage before deleting it.", "code": "profile_active"}, status=status.HTTP_409_CONFLICT)
        profile.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class StorageProfileProbeEndpoint(BaseAPIView):
    def post(self, request, pk):
        profile = StorageProfile.objects.get(pk=pk)
        key = f"{profile.object_prefix}probes/{uuid.uuid4().hex}.txt"
        profile.probe_object_key = key
        profile.last_probe_at = timezone.now()
        profile.verification_error = ""
        profile.save(update_fields=["probe_object_key", "last_probe_at", "verification_error", "updated_at"])
        upload_data = S3Storage(request=request, profile=profile).generate_presigned_post(key, "text/plain", 128)
        if not upload_data:
            profile.verification_error = "Unable to sign probe upload."
            profile.save(update_fields=["verification_error", "updated_at"])
            return Response({"error": profile.verification_error, "code": "probe_signing_failed"}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"profile_id": str(profile.id), "probe_object_key": key, "upload_data": upload_data})


class StorageProfileProbeCompleteEndpoint(BaseAPIView):
    def post(self, request, pk):
        profile = StorageProfile.objects.get(pk=pk)
        key = profile.probe_object_key
        storage = S3Storage(request=request, profile=profile)
        metadata = storage.get_object_metadata(key) if key else None
        probe_bytes = storage.read_object(key, 128) if metadata else None
        if not metadata or probe_bytes is None:
            profile.verification_error = "Probe object was not found. Check bucket CORS and permissions."
            profile.save(update_fields=["verification_error", "updated_at"])
            return Response({"error": profile.verification_error, "code": "probe_missing"}, status=status.HTTP_400_BAD_REQUEST)
        storage.delete_files([key])
        profile.status = StorageProfile.Status.VERIFIED
        profile.verified_at = timezone.now()
        profile.verification_error = ""
        profile.save(update_fields=["status", "verified_at", "verification_error", "updated_at"])
        return Response(StorageProfileSerializer(profile).data)


class StorageProfileActivateEndpoint(BaseAPIView):
    @transaction.atomic
    def post(self, request, pk):
        profile = StorageProfile.objects.get(pk=pk)
        if profile.status != StorageProfile.Status.VERIFIED:
            return Response({"error": "A successful browser probe is required before activation.", "code": "not_verified"}, status=status.HTTP_409_CONFLICT)
        StorageProfile.objects.filter(instance=profile.instance, status=StorageProfile.Status.ACTIVE).exclude(pk=pk).update(status=StorageProfile.Status.RETIRED)
        profile.status = StorageProfile.Status.ACTIVE
        profile.save(update_fields=["status", "updated_at"])
        return Response(StorageProfileSerializer(profile).data)


class StorageProfileRollbackEndpoint(BaseAPIView):
    @transaction.atomic
    def post(self, request):
        instance = _instance()
        StorageProfile.objects.filter(instance=instance, status=StorageProfile.Status.ACTIVE).update(status=StorageProfile.Status.RETIRED)
        return Response({"status": "legacy"})
