# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.urls import path


from plane.app.views import (
    PageViewSet,
    PageFavoriteViewSet,
    PagesDescriptionViewSet,
    PageVersionEndpoint,
    PageDuplicateEndpoint,
    PageHierarchyViewSet,
)

urlpatterns = [
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/pages/hierarchy/",
        PageHierarchyViewSet.as_view({"get": "list"}),
        name="project-page-hierarchy",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/pages/hierarchy/preferences/",
        PageHierarchyViewSet.as_view({"get": "retrieve_preferences", "patch": "update_preferences"}),
        name="project-page-hierarchy-preferences",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/pages/hierarchy/all-pages/",
        PageHierarchyViewSet.as_view({"get": "all_pages"}),
        name="project-page-hierarchy-all-pages",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/pages/hierarchy/bulk-preview/",
        PageHierarchyViewSet.as_view({"post": "bulk_preview"}),
        name="project-page-hierarchy-bulk-preview",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/pages/hierarchy/bulk/",
        PageHierarchyViewSet.as_view({"post": "bulk_mutate"}),
        name="project-page-hierarchy-bulk",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/pages/<uuid:page_id>/hierarchy-path/",
        PageHierarchyViewSet.as_view({"get": "path"}),
        name="project-page-hierarchy-path",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/pages/<uuid:page_id>/move-in-hierarchy/",
        PageHierarchyViewSet.as_view({"post": "move"}),
        name="project-page-hierarchy-move",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/pages/<uuid:page_id>/hierarchy-preview/",
        PageHierarchyViewSet.as_view({"get": "preview"}),
        name="project-page-hierarchy-preview",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/pages/<uuid:page_id>/copy-subtree/",
        PageHierarchyViewSet.as_view({"post": "copy_subtree"}),
        name="project-page-hierarchy-copy-subtree",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/pages-summary/",
        PageViewSet.as_view({"get": "summary"}),
        name="project-pages-summary",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/pages/",
        PageViewSet.as_view({"get": "list", "post": "create"}),
        name="project-pages",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/pages/<uuid:page_id>/",
        PageViewSet.as_view({"get": "retrieve", "patch": "partial_update", "delete": "destroy"}),
        name="project-pages",
    ),
    # favorite pages
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/favorite-pages/<uuid:page_id>/",
        PageFavoriteViewSet.as_view({"post": "create", "delete": "destroy"}),
        name="user-favorite-pages",
    ),
    # archived pages
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/pages/<uuid:page_id>/archive/",
        PageViewSet.as_view({"post": "archive", "delete": "unarchive"}),
        name="project-page-archive-unarchive",
    ),
    # lock and unlock
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/pages/<uuid:page_id>/lock/",
        PageViewSet.as_view({"post": "lock", "delete": "unlock"}),
        name="project-pages-lock-unlock",
    ),
    # private and public page
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/pages/<uuid:page_id>/access/",
        PageViewSet.as_view({"post": "access"}),
        name="project-pages-access",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/pages/<uuid:page_id>/description/",
        PagesDescriptionViewSet.as_view({"get": "retrieve", "patch": "partial_update"}),
        name="page-description",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/pages/<uuid:page_id>/versions/",
        PageVersionEndpoint.as_view(),
        name="page-versions",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/pages/<uuid:page_id>/versions/<uuid:pk>/",
        PageVersionEndpoint.as_view(),
        name="page-versions",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/pages/<uuid:page_id>/duplicate/",
        PageDuplicateEndpoint.as_view(),
        name="page-duplicate",
    ),
]
