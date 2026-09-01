# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only

from urllib.parse import urlparse

from rest_framework import serializers

from plane.license.models import StorageProfile


MIN_FILE_SIZE_LIMIT = 1024 * 1024
MAX_FILE_SIZE_LIMIT = 10 * 1024 * 1024 * 1024


class StorageProfileSerializer(serializers.ModelSerializer):
    endpoint = serializers.CharField(required=False, allow_blank=True)
    access_key_secret = serializers.CharField(required=False, write_only=True, allow_blank=False)
    secret_configured = serializers.SerializerMethodField()
    effective_endpoint = serializers.ReadOnlyField()

    class Meta:
        model = StorageProfile
        fields = (
            "id", "provider", "bucket", "region", "endpoint", "effective_endpoint",
            "access_key_id", "access_key_secret", "secret_configured", "status",
            "file_size_limit", "verified_at", "verification_error", "last_probe_at",
        )
        read_only_fields = ("id", "status", "verified_at", "verification_error", "last_probe_at")

    def get_secret_configured(self, instance):
        return bool(instance.access_key_secret)

    def validate_endpoint(self, value):
        value = value.strip()
        if not value:
            return ""
        parsed = urlparse(value)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise serializers.ValidationError("Enter a valid HTTP or HTTPS endpoint.")
        return value.rstrip("/")

    def validate_file_size_limit(self, value):
        if not MIN_FILE_SIZE_LIMIT <= value <= MAX_FILE_SIZE_LIMIT:
            raise serializers.ValidationError("Enter a limit between 1 and 10,240 MB.")
        return value
