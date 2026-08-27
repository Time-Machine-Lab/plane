# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from urllib.parse import urlparse

from django.conf import settings
from rest_framework import serializers

from plane.utils.ip_address import validate_url


class MuticaConnectionInputSerializer(serializers.Serializer):
    endpoint_url = serializers.URLField(max_length=2048)
    signing_secret = serializers.CharField(min_length=16, max_length=1024, trim_whitespace=False, write_only=True)
    agent_external_id = serializers.CharField(min_length=1, max_length=255)
    agent_display_name = serializers.CharField(min_length=1, max_length=255)
    agent_avatar_url = serializers.URLField(max_length=2048, required=False, allow_null=True, allow_blank=True)

    def validate_endpoint_url(self, value: str) -> str:
        try:
            validate_url(
                value,
                allowed_ips=settings.WEBHOOK_ALLOWED_IPS,
                allowed_hosts=settings.WEBHOOK_ALLOWED_HOSTS,
            )
        except ValueError as exc:
            raise serializers.ValidationError("Invalid or disallowed Mutica endpoint.") from exc

        hostname = (urlparse(value).hostname or "").rstrip(".").lower()
        parsed = urlparse(value)
        if parsed.username is not None or parsed.password is not None:
            raise serializers.ValidationError("Invalid or disallowed Mutica endpoint.")
        trusted_hosts = {(host or "").rstrip(".").lower() for host in settings.WEBHOOK_ALLOWED_HOSTS if host}
        if hostname not in trusted_hosts:
            disallowed_domains = {
                (domain or "").rstrip(".").lower() for domain in settings.WEBHOOK_DISALLOWED_DOMAINS if domain
            }
            request = self.context.get("request")
            if request is not None:
                disallowed_domains.add(request.get_host().split(":")[0].rstrip(".").lower())
            if any(hostname == domain or hostname.endswith(f".{domain}") for domain in disallowed_domains):
                raise serializers.ValidationError("Invalid or disallowed Mutica endpoint.")
        return value
