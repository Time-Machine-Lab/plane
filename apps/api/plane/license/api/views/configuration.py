# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Python imports
import json
from smtplib import (
    SMTPAuthenticationError,
    SMTPConnectError,
    SMTPRecipientsRefused,
    SMTPSenderRefused,
    SMTPServerDisconnected,
)

# Django imports
from django.core.mail import BadHeaderError, EmailMultiAlternatives, get_connection
from django.db import transaction
from django.db.models import Q, Case, When, Value

# Third party imports
from rest_framework import status
from rest_framework.response import Response

# Module imports
from .base import BaseAPIView
from plane.license.api.permissions import InstanceAdminPermission
from plane.license.models import InstanceConfiguration
from plane.license.api.serializers import InstanceConfigurationSerializer
from plane.license.utils.encryption import encrypt_data
from plane.db.models import Workspace, WorkspaceMember
from plane.integrations.discord import (
    DISCORD_CONFIG_KEYS,
    build_discord_payload,
    build_test_notification,
    get_discord_configuration,
    is_supported_discord_webhook_url,
    send_discord_webhook,
    validate_discord_configuration,
)
from plane.utils.cache import cache_response, invalidate_cache
from plane.utils.host import base_host
from plane.utils.uuid import is_valid_uuid
from plane.license.utils.instance_value import get_email_configuration


class InstanceConfigurationEndpoint(BaseAPIView):
    permission_classes = [InstanceAdminPermission]

    @cache_response(60 * 60 * 2, user=False)
    def get(self, request):
        instance_configurations = InstanceConfiguration.objects.exclude(category="DISCORD")
        serializer = InstanceConfigurationSerializer(instance_configurations, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @invalidate_cache(path="/api/instances/configurations/", user=False)
    @invalidate_cache(path="/api/instances/", user=False)
    def patch(self, request):
        configurations = InstanceConfiguration.objects.filter(key__in=request.data.keys()).exclude(category="DISCORD")

        bulk_configurations = []
        for configuration in configurations:
            raw_value = request.data.get(configuration.key, configuration.value)
            value = "" if raw_value is None else str(raw_value).strip()
            if configuration.is_encrypted:
                configuration.value = encrypt_data(value)
            else:
                configuration.value = value
            bulk_configurations.append(configuration)

        InstanceConfiguration.objects.bulk_update(bulk_configurations, ["value"], batch_size=100)

        serializer = InstanceConfigurationSerializer(configurations, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


def _serialize_discord_configuration():
    configuration = get_discord_configuration()
    return {
        "enabled": configuration.enabled,
        "workspace_id": configuration.workspace_id,
        "webhook_configured": bool(configuration.webhook_url),
        "enabled_events": list(configuration.enabled_events),
        "member_mappings": list(configuration.member_mappings),
        "workspaces": list(Workspace.objects.order_by("name").values("id", "name", "slug")),
    }


def _set_discord_configuration_value(key, value, *, encrypted=False):
    configuration, _ = InstanceConfiguration.objects.get_or_create(
        key=key,
        defaults={"category": "DISCORD", "is_encrypted": encrypted, "value": ""},
    )
    configuration.category = "DISCORD"
    configuration.is_encrypted = encrypted
    configuration.value = encrypt_data(value) if encrypted else value
    configuration.save(update_fields=["category", "is_encrypted", "value", "updated_at"])


class DiscordConfigurationEndpoint(BaseAPIView):
    permission_classes = [InstanceAdminPermission]

    def get(self, request):
        return Response(_serialize_discord_configuration(), status=status.HTTP_200_OK)

    @transaction.atomic
    @invalidate_cache(path="/api/instances/configurations/", user=False)
    @invalidate_cache(path="/api/instances/", user=False)
    def patch(self, request):
        current = get_discord_configuration()
        replacement_webhook = str(request.data.get("webhook_url") or "").strip()
        try:
            configuration = validate_discord_configuration(
                enabled=request.data.get("enabled", current.enabled),
                workspace_id=request.data.get("workspace_id", current.workspace_id),
                webhook_url=replacement_webhook,
                enabled_events=request.data.get("enabled_events", list(current.enabled_events)),
                member_mappings=request.data.get("member_mappings", list(current.member_mappings)),
                has_saved_webhook=bool(current.webhook_url),
            )
        except ValueError as error:
            return Response({"error": str(error)}, status=status.HTTP_400_BAD_REQUEST)

        _set_discord_configuration_value(
            DISCORD_CONFIG_KEYS["enabled"],
            "1" if configuration.enabled else "0",
        )
        _set_discord_configuration_value(
            DISCORD_CONFIG_KEYS["workspace_id"],
            configuration.workspace_id or "",
        )
        _set_discord_configuration_value(
            DISCORD_CONFIG_KEYS["enabled_events"],
            json.dumps(configuration.enabled_events),
        )
        _set_discord_configuration_value(
            DISCORD_CONFIG_KEYS["member_mappings"],
            json.dumps(configuration.member_mappings),
        )
        if replacement_webhook:
            _set_discord_configuration_value(
                DISCORD_CONFIG_KEYS["webhook_url"],
                replacement_webhook,
                encrypted=True,
            )

        return Response(_serialize_discord_configuration(), status=status.HTTP_200_OK)


class DiscordWorkspaceMembersEndpoint(BaseAPIView):
    permission_classes = [InstanceAdminPermission]

    def get(self, request):
        workspace_id = str(request.query_params.get("workspace_id") or "").strip()
        if (
            not workspace_id
            or not is_valid_uuid(workspace_id)
            or not Workspace.objects.filter(pk=workspace_id).exists()
        ):
            return Response({"error": "A valid workspace is required."}, status=status.HTTP_400_BAD_REQUEST)

        members = (
            WorkspaceMember.objects.filter(workspace_id=workspace_id, is_active=True, member__is_bot=False)
            .select_related("member")
            .order_by("member__display_name", "member__email")
        )
        return Response(
            [
                {
                    "id": str(workspace_member.member_id),
                    "display_name": workspace_member.member.display_name
                    or workspace_member.member.full_name
                    or workspace_member.member.email,
                }
                for workspace_member in members
            ],
            status=status.HTTP_200_OK,
        )


class DiscordTestMessageEndpoint(BaseAPIView):
    permission_classes = [InstanceAdminPermission]

    def post(self, request):
        configuration = get_discord_configuration()
        webhook_url = str(request.data.get("webhook_url") or "").strip() or configuration.webhook_url
        if not webhook_url:
            return Response(
                {"accepted": False, "error": "Configure a Discord Incoming Webhook URL first."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not is_supported_discord_webhook_url(webhook_url):
            return Response(
                {"accepted": False, "error": "Enter a supported Discord Incoming Webhook URL."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        notification = build_test_notification(base_host(request=request, is_admin=True))
        accepted, category = send_discord_webhook(
            webhook_url=webhook_url,
            payload=build_discord_payload(notification, ()),
            event_key=notification.event_key,
            workspace_id=configuration.workspace_id,
        )
        if accepted:
            return Response({"accepted": True}, status=status.HTTP_200_OK)
        return Response(
            {
                "accepted": False,
                "error": "Discord did not accept the test message.",
                "category": category,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )


class DisableEmailFeatureEndpoint(BaseAPIView):
    permission_classes = [InstanceAdminPermission]

    @invalidate_cache(path="/api/instances/", user=False)
    def delete(self, request):
        try:
            InstanceConfiguration.objects.filter(
                Q(
                    key__in=[
                        "EMAIL_HOST",
                        "EMAIL_HOST_USER",
                        "EMAIL_HOST_PASSWORD",
                        "ENABLE_SMTP",
                        "EMAIL_PORT",
                        "EMAIL_FROM",
                    ]
                )
            ).update(value=Case(When(key="ENABLE_SMTP", then=Value("0")), default=Value("")))
            return Response(status=status.HTTP_200_OK)
        except Exception:
            return Response(
                {"error": "Failed to disable email configuration"},
                status=status.HTTP_400_BAD_REQUEST,
            )


class EmailCredentialCheckEndpoint(BaseAPIView):
    def post(self, request):
        receiver_email = request.data.get("receiver_email", False)
        if not receiver_email:
            return Response(
                {"error": "Receiver email is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        (
            EMAIL_HOST,
            EMAIL_HOST_USER,
            EMAIL_HOST_PASSWORD,
            EMAIL_PORT,
            EMAIL_USE_TLS,
            EMAIL_USE_SSL,
            EMAIL_FROM,
        ) = get_email_configuration()

        # Configure all the connections
        connection = get_connection(
            host=EMAIL_HOST,
            port=int(EMAIL_PORT),
            username=EMAIL_HOST_USER,
            password=EMAIL_HOST_PASSWORD,
            use_tls=EMAIL_USE_TLS == "1",
            use_ssl=EMAIL_USE_SSL == "1",
        )
        # Prepare email details
        subject = "Email Notification from Plane"
        message = "This is a sample email notification sent from Plane application."
        # Send the email
        try:
            msg = EmailMultiAlternatives(
                subject=subject,
                body=message,
                from_email=EMAIL_FROM,
                to=[receiver_email],
                connection=connection,
            )
            msg.send(fail_silently=False)
            return Response({"message": "Email successfully sent."}, status=status.HTTP_200_OK)
        except BadHeaderError:
            return Response({"error": "Invalid email header."}, status=status.HTTP_400_BAD_REQUEST)
        except SMTPAuthenticationError:
            return Response(
                {"error": "Invalid credentials provided"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except SMTPConnectError:
            return Response(
                {"error": "Could not connect with the SMTP server."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except SMTPSenderRefused:
            return Response(
                {"error": "From address is invalid."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except SMTPServerDisconnected:
            return Response(
                {"error": "SMTP server disconnected unexpectedly."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except SMTPRecipientsRefused:
            return Response(
                {"error": "All recipient addresses were refused."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except TimeoutError:
            return Response(
                {"error": "Timeout error while trying to connect to the SMTP server."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except ConnectionError:
            return Response(
                {"error": "Network connection error. Please check your internet connection."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception:
            return Response(
                {"error": "Could not send email. Please check your configuration"},
                status=status.HTTP_400_BAD_REQUEST,
            )
