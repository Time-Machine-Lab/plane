# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.urls import path

from plane.license.api.views import (
    DiscordConfigurationEndpoint,
    DiscordTestMessageEndpoint,
    DiscordWorkspaceMembersEndpoint,
    EmailCredentialCheckEndpoint,
    InstanceAdminEndpoint,
    InstanceAdminSignInEndpoint,
    InstanceAdminSignUpEndpoint,
    InstanceConfigurationEndpoint,
    DisableEmailFeatureEndpoint,
    InstanceEndpoint,
    SignUpScreenVisitedEndpoint,
    InstanceAdminUserMeEndpoint,
    InstanceAdminSignOutEndpoint,
    InstanceAdminUserSessionEndpoint,
    InstanceWorkSpaceAvailabilityCheckEndpoint,
    InstanceWorkSpaceEndpoint,
    StorageProfileEndpoint,
    StorageProfileProbeEndpoint,
    StorageProfileProbeCompleteEndpoint,
    StorageProfileActivateEndpoint,
    StorageProfileRollbackEndpoint,
)

urlpatterns = [
    path("", InstanceEndpoint.as_view(), name="instance"),
    path("admins/", InstanceAdminEndpoint.as_view(), name="instance-admins"),
    path("admins/me/", InstanceAdminUserMeEndpoint.as_view(), name="instance-admins"),
    path(
        "admins/session/",
        InstanceAdminUserSessionEndpoint.as_view(),
        name="instance-admin-session",
    ),
    path(
        "admins/sign-out/",
        InstanceAdminSignOutEndpoint.as_view(),
        name="instance-admins",
    ),
    path("admins/<uuid:pk>/", InstanceAdminEndpoint.as_view(), name="instance-admins"),
    path(
        "configurations/",
        InstanceConfigurationEndpoint.as_view(),
        name="instance-configuration",
    ),
    path(
        "discord-configuration/",
        DiscordConfigurationEndpoint.as_view(),
        name="discord-configuration",
    ),
    path(
        "discord-configuration/members/",
        DiscordWorkspaceMembersEndpoint.as_view(),
        name="discord-configuration-members",
    ),
    path(
        "discord-configuration/test/",
        DiscordTestMessageEndpoint.as_view(),
        name="discord-configuration-test",
    ),
    path(
        "configurations/disable-email-feature/",
        DisableEmailFeatureEndpoint.as_view(),
        name="disable-email-configuration",
    ),
    path(
        "admins/sign-in/",
        InstanceAdminSignInEndpoint.as_view(),
        name="instance-admin-sign-in",
    ),
    path(
        "admins/sign-up/",
        InstanceAdminSignUpEndpoint.as_view(),
        name="instance-admin-sign-in",
    ),
    path(
        "admins/sign-up-screen-visited/",
        SignUpScreenVisitedEndpoint.as_view(),
        name="instance-sign-up",
    ),
    path(
        "email-credentials-check/",
        EmailCredentialCheckEndpoint.as_view(),
        name="email-credential-check",
    ),
    path(
        "workspace-slug-check/",
        InstanceWorkSpaceAvailabilityCheckEndpoint.as_view(),
        name="instance-workspace-availability",
    ),
    path("workspaces/", InstanceWorkSpaceEndpoint.as_view(), name="instance-workspace"),
    path("storage-profiles/", StorageProfileEndpoint.as_view(), name="storage-profiles"),
    path("storage-profiles/<uuid:pk>/", StorageProfileEndpoint.as_view(), name="storage-profile"),
    path("storage-profiles/<uuid:pk>/probe/", StorageProfileProbeEndpoint.as_view(), name="storage-profile-probe"),
    path("storage-profiles/<uuid:pk>/probe/complete/", StorageProfileProbeCompleteEndpoint.as_view(), name="storage-profile-probe-complete"),
    path("storage-profiles/<uuid:pk>/activate/", StorageProfileActivateEndpoint.as_view(), name="storage-profile-activate"),
    path("storage-profiles/rollback/", StorageProfileRollbackEndpoint.as_view(), name="storage-profile-rollback"),
]
