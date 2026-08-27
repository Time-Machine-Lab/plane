# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from requests import RequestException
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response

from plane.app.permissions import ROLE, allow_permission
from plane.app.serializers import MuticaConnectionInputSerializer
from plane.db.models import MuticaConnection, MuticaExternalAgent, Workspace
from plane.integrations.mutica import (
    connect_mutica,
    disconnect_mutica,
    rotate_mutica_service_token,
    verify_mutica_endpoint,
)
from plane.utils.secret_encryption import decrypt_secret

from .base import BaseAPIView


def serialize_connection(connection: MuticaConnection) -> dict:
    agent = MuticaExternalAgent.objects.filter(
        workspace_integration=connection.workspace_integration,
        is_default=True,
    ).first()
    return {
        "id": str(connection.id),
        "endpoint_url": connection.endpoint_url,
        "is_enabled": connection.is_enabled,
        "verified_at": connection.verified_at,
        "disabled_at": connection.disabled_at,
        "assistant": (
            {
                "id": str(agent.id),
                "external_id": agent.external_id,
                "display_name": agent.display_name,
                "avatar_url": agent.avatar_url,
                "is_enabled": agent.is_enabled,
            }
            if agent
            else None
        ),
    }


class MuticaConnectionEndpoint(BaseAPIView):
    @allow_permission([ROLE.ADMIN], level="WORKSPACE")
    def get(self, request, slug):
        connection = (
            MuticaConnection.objects.filter(
                workspace_integration__workspace__slug=slug,
                workspace_integration__integration__provider="mutica",
            )
            .select_related("workspace_integration")
            .first()
        )
        return Response(serialize_connection(connection) if connection else None, status=status.HTTP_200_OK)

    @allow_permission([ROLE.ADMIN], level="WORKSPACE")
    def post(self, request, slug):
        serializer = MuticaConnectionInputSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        try:
            verify_mutica_endpoint(
                values["endpoint_url"],
                slug,
                values["signing_secret"],
                values["agent_external_id"],
            )
        except (RequestException, ValueError):
            return Response(
                {"error": "Mutica connection verification failed."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        workspace = Workspace.objects.get(slug=slug)
        connection, service_token = connect_mutica(workspace=workspace, **values)
        return Response(
            {**serialize_connection(connection), "service_token": service_token},
            status=status.HTTP_201_CREATED,
        )

    @allow_permission([ROLE.ADMIN], level="WORKSPACE")
    def delete(self, request, slug):
        connection = MuticaConnection.objects.filter(
            workspace_integration__workspace__slug=slug,
            workspace_integration__integration__provider="mutica",
            is_enabled=True,
        ).first()
        if connection is None:
            return Response(status=status.HTTP_204_NO_CONTENT)
        disconnect_mutica(connection)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MuticaConnectionVerifyEndpoint(BaseAPIView):
    @allow_permission([ROLE.ADMIN], level="WORKSPACE")
    def post(self, request, slug):
        connection = MuticaConnection.objects.filter(
            workspace_integration__workspace__slug=slug,
            workspace_integration__integration__provider="mutica",
            is_enabled=True,
        ).first()
        if connection is None:
            return Response({"error": "Mutica is not connected."}, status=status.HTTP_404_NOT_FOUND)
        agent = MuticaExternalAgent.objects.filter(
            workspace_integration=connection.workspace_integration,
            is_default=True,
            is_enabled=True,
        ).first()
        if agent is None:
            return Response({"error": "Mutica is not connected."}, status=status.HTTP_404_NOT_FOUND)
        try:
            verify_mutica_endpoint(
                connection.endpoint_url,
                slug,
                decrypt_secret(connection.signing_secret),
                agent.external_id,
            )
        except (RequestException, ValueError):
            return Response(
                {"error": "Mutica connection verification failed."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        connection.verified_at = timezone.now()
        connection.save(update_fields=["verified_at", "updated_at"])
        return Response(serialize_connection(connection), status=status.HTTP_200_OK)


class MuticaServiceTokenRotateEndpoint(BaseAPIView):
    @allow_permission([ROLE.ADMIN], level="WORKSPACE")
    def post(self, request, slug):
        connection = MuticaConnection.objects.filter(
            workspace_integration__workspace__slug=slug,
            workspace_integration__integration__provider="mutica",
            is_enabled=True,
        ).first()
        if connection is None:
            return Response({"error": "Mutica is not connected."}, status=status.HTTP_404_NOT_FOUND)
        return Response(
            {"service_token": rotate_mutica_service_token(connection)},
            status=status.HTTP_201_CREATED,
        )
