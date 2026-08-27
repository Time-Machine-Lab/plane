# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""
Unit tests for APIKeyAuthentication.

Covers the access-control guarantees of the external API key authentication:
- a valid token belonging to an active user authenticates successfully
- a valid token is rejected once the underlying user account is deactivated
  (prevents an authentication bypass via a disabled account that still holds
  a previously generated API key)
"""

import pytest
from rest_framework.exceptions import AuthenticationFailed
from types import SimpleNamespace

from plane.api.middleware.api_authentication import APIKeyAuthentication
from plane.db.models import APIToken, Workspace


@pytest.mark.unit
class TestAPIKeyAuthentication:
    @pytest.mark.django_db
    def test_validate_api_token_authenticates_active_user(self, create_user):
        token = APIToken.objects.create(
            user=create_user, label="Active Token", token="active-user-token"
        )

        user, returned_token = APIKeyAuthentication().validate_api_token(token.token)

        assert user == create_user
        assert returned_token == token.token

    @pytest.mark.django_db
    def test_validate_api_token_rejects_deactivated_user(self, create_user):
        token = APIToken.objects.create(
            user=create_user, label="Stale Token", token="deactivated-user-token"
        )

        # Account is deactivated by an administrator after the token was issued.
        create_user.is_active = False
        create_user.save()

        with pytest.raises(AuthenticationFailed):
            APIKeyAuthentication().validate_api_token(token.token)

    @pytest.mark.django_db
    def test_validate_api_token_accepts_workspace_bound_service_token_for_its_workspace(self, create_user, workspace):
        token = APIToken.objects.create(
            user=create_user,
            label="Workspace Service Token",
            token="workspace-service-token",
            workspace=workspace,
            is_service=True,
        )
        request = SimpleNamespace(parser_context={"kwargs": {"slug": workspace.slug}}, resolver_match=None)

        user, returned_token = APIKeyAuthentication().validate_api_token(token.token, request=request)

        assert user == create_user
        assert returned_token == token.token

    @pytest.mark.django_db
    def test_validate_api_token_rejects_workspace_bound_service_token_for_other_workspace(self, create_user, workspace):
        other_workspace = Workspace.objects.create(
            name="Other Workspace",
            owner=create_user,
            slug="other-workspace",
        )
        token = APIToken.objects.create(
            user=create_user,
            label="Workspace Service Token",
            token="cross-workspace-service-token",
            workspace=workspace,
            is_service=True,
        )
        request = SimpleNamespace(
            parser_context=None,
            resolver_match=SimpleNamespace(kwargs={"slug": other_workspace.slug}),
        )

        with pytest.raises(AuthenticationFailed):
            APIKeyAuthentication().validate_api_token(token.token, request=request)
