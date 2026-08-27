# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.urls import path

from plane.app.views import (
    MuticaConnectionEndpoint,
    MuticaConnectionVerifyEndpoint,
    MuticaServiceTokenRotateEndpoint,
    MuticaAssistantAvailabilityEndpoint,
    MuticaIssueDelegationEndpoint,
    MuticaIssueDelegationRetryEndpoint,
)


urlpatterns = [
    path(
        "workspaces/<str:slug>/mutica/connection/",
        MuticaConnectionEndpoint.as_view(),
        name="mutica-connection",
    ),
    path(
        "workspaces/<str:slug>/mutica/connection/verify/",
        MuticaConnectionVerifyEndpoint.as_view(),
        name="mutica-connection-verify",
    ),
    path(
        "workspaces/<str:slug>/mutica/connection/service-token/rotate/",
        MuticaServiceTokenRotateEndpoint.as_view(),
        name="mutica-service-token-rotate",
    ),
    path(
        "workspaces/<str:slug>/mutica/assistant/",
        MuticaAssistantAvailabilityEndpoint.as_view(),
        name="mutica-assistant-availability",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/issues/<uuid:issue_id>/mutica-delegation/",
        MuticaIssueDelegationEndpoint.as_view(),
        name="mutica-issue-delegation",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/issues/<uuid:issue_id>/mutica-delegation/retry/",
        MuticaIssueDelegationRetryEndpoint.as_view(),
        name="mutica-issue-delegation-retry",
    ),
]
