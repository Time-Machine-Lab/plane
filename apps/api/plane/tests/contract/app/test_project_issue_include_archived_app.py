# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from uuid import uuid4

import pytest
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from plane.db.models import Issue, Project, ProjectMember, State, User


ISSUES_URL = "/api/workspaces/{slug}/projects/{project_id}/issues/"


@pytest.fixture(autouse=True)
def mock_background_tasks(mocker):
    mocker.patch("plane.app.views.issue.base.recent_visited_task.delay")
    mocker.patch("plane.db.mixins.soft_delete_related_objects.delay")


@pytest.fixture
def project(db, workspace, create_user):
    project = Project.objects.create(
        name="Archive visibility project",
        identifier="AVP",
        workspace=workspace,
        created_by=create_user,
    )
    ProjectMember.objects.create(project=project, member=create_user, workspace=workspace, role=20)
    return project


@pytest.fixture
def completed_state(db, workspace, project):
    return State.objects.create(
        name="Completed",
        color="#22C55E",
        group="completed",
        project=project,
        workspace=workspace,
    )


def create_issue(name, project, state, *, archived=False, priority="high", is_draft=False):
    return Issue.objects.create(
        name=name,
        project=project,
        workspace=project.workspace,
        state=state,
        priority=priority,
        archived_at=timezone.now().date() if archived else None,
        is_draft=is_draft,
    )


def response_issue_ids(response):
    return {str(issue["id"]) for issue in response.data["results"]}


@pytest.mark.contract
@pytest.mark.django_db
class TestProjectIssueIncludeArchived:
    def test_default_and_false_exclude_archived(self, session_client, workspace, project, completed_state):
        active_issue = create_issue("Active", project, completed_state)
        archived_issue = create_issue("Archived", project, completed_state, archived=True)
        url = ISSUES_URL.format(slug=workspace.slug, project_id=project.id)

        default_response = session_client.get(url)
        false_response = session_client.get(url, {"include_archived": "false"})

        assert default_response.status_code == status.HTTP_200_OK
        assert false_response.status_code == status.HTTP_200_OK
        assert response_issue_ids(default_response) == {str(active_issue.id)}
        assert response_issue_ids(false_response) == {str(active_issue.id)}
        assert str(archived_issue.id) not in response_issue_ids(default_response)

    def test_true_includes_archived_and_uses_same_filter_and_group_count(
        self, session_client, workspace, project, completed_state
    ):
        active_issue = create_issue("Active high", project, completed_state)
        archived_issue = create_issue("Archived high", project, completed_state, archived=True)
        create_issue("Archived low", project, completed_state, archived=True, priority="low")
        url = ISSUES_URL.format(slug=workspace.slug, project_id=project.id)

        response = session_client.get(
            url,
            {
                "include_archived": "true",
                "priority": "high",
                "group_by": "state_id",
            },
        )

        assert response.status_code == status.HTTP_200_OK
        group = response.data["results"][str(completed_state.id)]
        returned_ids = {str(issue["id"]) for issue in group["results"]}
        assert returned_ids == {str(active_issue.id), str(archived_issue.id)}
        assert group["total_results"] == 2

    def test_true_preserves_record_and_project_exclusions(
        self, session_client, workspace, project, completed_state, create_user
    ):
        visible_issue = create_issue("Visible", project, completed_state, archived=True)
        draft_issue = create_issue("Draft", project, completed_state, archived=True, is_draft=True)
        triage_state = State.objects.create(
            name="Triage",
            color="#64748B",
            group="triage",
            project=project,
            workspace=workspace,
        )
        triage_issue = create_issue("Triage issue", project, triage_state, archived=True)
        deleted_issue = create_issue("Deleted", project, completed_state, archived=True)
        deleted_issue.delete()

        other_project = Project.objects.create(
            name="Other project",
            identifier="OTHER",
            workspace=workspace,
            created_by=create_user,
        )
        other_state = State.objects.create(
            name="Completed",
            color="#22C55E",
            group="completed",
            project=other_project,
            workspace=workspace,
        )
        other_issue = create_issue("Other project issue", other_project, other_state, archived=True)

        url = ISSUES_URL.format(slug=workspace.slug, project_id=project.id)
        response = session_client.get(url, {"include_archived": "true"})

        assert response.status_code == status.HTTP_200_OK
        returned_ids = response_issue_ids(response)
        assert returned_ids == {str(visible_issue.id)}
        assert str(draft_issue.id) not in returned_ids
        assert str(triage_issue.id) not in returned_ids
        assert str(deleted_issue.id) not in returned_ids
        assert str(other_issue.id) not in returned_ids

    def test_archived_project_and_unauthorized_user_are_excluded(self, session_client, workspace, create_user):
        archived_project = Project.objects.create(
            name="Archived project",
            identifier="ARCH",
            workspace=workspace,
            archived_at=timezone.now(),
            created_by=create_user,
        )
        ProjectMember.objects.create(
            project=archived_project,
            member=create_user,
            workspace=workspace,
            role=20,
        )
        archived_state = State.objects.create(
            name="Completed",
            color="#22C55E",
            group="completed",
            project=archived_project,
            workspace=workspace,
        )
        create_issue("Archived project issue", archived_project, archived_state, archived=True)
        url = ISSUES_URL.format(slug=workspace.slug, project_id=archived_project.id)

        member_response = session_client.get(url, {"include_archived": "true"})
        assert member_response.status_code == status.HTTP_200_OK
        assert response_issue_ids(member_response) == set()

        outsider = User.objects.create(
            email=f"outsider-{uuid4().hex[:8]}@plane.so",
            username=f"outsider_{uuid4().hex[:8]}",
        )
        outsider_client = APIClient()
        outsider_client.force_authenticate(user=outsider)
        outsider_response = outsider_client.get(url, {"include_archived": "true"})
        assert outsider_response.status_code == status.HTTP_403_FORBIDDEN

    def test_invalid_value_is_rejected(self, session_client, workspace, project):
        url = ISSUES_URL.format(slug=workspace.slug, project_id=project.id)

        response = session_client.get(url, {"include_archived": "sometimes"})

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "include_archived" in response.data
