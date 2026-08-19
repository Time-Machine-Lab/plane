# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import json
import uuid
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from plane.api.views.issue import IssueCommentDetailAPIEndpoint, IssueCommentListCreateAPIEndpoint
from plane.space.views.issue import IssueCommentPublicViewSet


def _request(data=None):
    return SimpleNamespace(data=data or {}, user=SimpleNamespace(id=uuid.uuid4()))


def _assignee_query(mocker, module_path, assignee_id):
    issue_assignee = mocker.patch(f"{module_path}.IssueAssignee")
    issue_assignee.objects.filter.return_value.values_list.return_value = [assignee_id]
    return issue_assignee


@pytest.mark.unit
def test_api_comment_create_passes_event_time_assignee_snapshot(mocker):
    module_path = "plane.api.views.issue"
    issue_id = uuid.uuid4()
    project_id = uuid.uuid4()
    assignee_id = uuid.uuid4()
    comment_id = uuid.uuid4()
    request = _request({"comment_html": "<p>Created</p>"})
    view = IssueCommentListCreateAPIEndpoint()
    view.request = request
    view.kwargs = {"issue_id": issue_id, "project_id": project_id}

    create_serializer = Mock()
    create_serializer.is_valid.return_value = True
    create_serializer.data = {"id": str(comment_id), "comment_html": "<p>Created</p>"}
    create_serializer.instance.id = comment_id
    mocker.patch(f"{module_path}.IssueCommentCreateSerializer", return_value=create_serializer)
    mocker.patch(f"{module_path}.IssueCommentSerializer", return_value=SimpleNamespace(data=create_serializer.data))
    comment = SimpleNamespace(id=comment_id, created_by_id=request.user.id, actor_id=request.user.id, save=Mock())
    issue_comment = mocker.patch(f"{module_path}.IssueComment")
    issue_comment.objects.get.return_value = comment
    _assignee_query(mocker, module_path, assignee_id)
    activity = mocker.patch(f"{module_path}.issue_activity")
    mocker.patch(f"{module_path}.model_activity")
    mocker.patch(f"{module_path}.base_host", return_value="https://plane.example.com")

    view.post(request, "workspace", project_id, issue_id)

    assert activity.delay.call_args.kwargs["discord_assignee_ids"] == [str(assignee_id)]


@pytest.mark.unit
def test_api_comment_edit_passes_event_time_assignee_snapshot(mocker):
    module_path = "plane.api.views.issue"
    issue_id = uuid.uuid4()
    project_id = uuid.uuid4()
    assignee_id = uuid.uuid4()
    comment_id = uuid.uuid4()
    request = _request({"comment_html": "<p>Updated</p>"})
    view = IssueCommentDetailAPIEndpoint()
    view.request = request

    comment = SimpleNamespace(id=comment_id, external_id=None, external_source=None)
    issue_comment = mocker.patch(f"{module_path}.IssueComment")
    issue_comment.objects.get.return_value = comment
    old_data = {"id": str(comment_id), "comment_html": "<p>Old</p>"}
    mocker.patch(f"{module_path}.IssueCommentSerializer", return_value=SimpleNamespace(data=old_data))
    update_serializer = Mock()
    update_serializer.is_valid.return_value = True
    update_serializer.instance.id = comment_id
    mocker.patch(f"{module_path}.IssueCommentCreateSerializer", return_value=update_serializer)
    _assignee_query(mocker, module_path, assignee_id)
    activity = mocker.patch(f"{module_path}.issue_activity")
    mocker.patch(f"{module_path}.model_activity")
    mocker.patch(f"{module_path}.base_host", return_value="https://plane.example.com")

    view.patch(request, "workspace", project_id, issue_id, comment_id)

    assert activity.delay.call_args.kwargs["discord_assignee_ids"] == [str(assignee_id)]


@pytest.mark.unit
def test_space_comment_create_passes_event_time_assignee_snapshot(mocker):
    module_path = "plane.space.views.issue"
    issue_id = uuid.uuid4()
    project_id = uuid.uuid4()
    assignee_id = uuid.uuid4()
    request = _request({"comment_html": "<p>Created</p>"})
    view = IssueCommentPublicViewSet()
    board = SimpleNamespace(is_comments_enabled=True, project_id=project_id)
    mocker.patch(f"{module_path}.DeployBoard").objects.get.return_value = board
    serializer = Mock()
    serializer.is_valid.return_value = True
    serializer.data = {"id": str(uuid.uuid4()), "comment_html": "<p>Created</p>"}
    mocker.patch(f"{module_path}.IssueCommentSerializer", return_value=serializer)
    _assignee_query(mocker, module_path, assignee_id)
    mocker.patch(f"{module_path}.ProjectMember").objects.filter.return_value.exists.return_value = True
    activity = mocker.patch(f"{module_path}.issue_activity")

    view.create(request, "public-anchor", issue_id)

    assert activity.delay.call_args.kwargs["discord_assignee_ids"] == [str(assignee_id)]


@pytest.mark.unit
def test_space_comment_edit_captures_old_content_and_assignee_snapshot_before_save(mocker):
    module_path = "plane.space.views.issue"
    issue_id = uuid.uuid4()
    project_id = uuid.uuid4()
    assignee_id = uuid.uuid4()
    comment_id = uuid.uuid4()
    old_html = "<p>Old</p>"
    new_html = "<p>New mention</p>"
    request = _request({"comment_html": new_html})
    view = IssueCommentPublicViewSet()
    board = SimpleNamespace(is_comments_enabled=True, project_id=project_id)
    mocker.patch(f"{module_path}.DeployBoard").objects.get.return_value = board
    comment = SimpleNamespace(id=comment_id, comment_html=old_html)
    mocker.patch(f"{module_path}.IssueComment").objects.get.return_value = comment
    update_serializer = Mock()
    update_serializer.is_valid.return_value = True
    update_serializer.data = {"id": str(comment_id), "comment_html": new_html}
    update_serializer.save.side_effect = lambda: setattr(comment, "comment_html", new_html)

    def serializer_factory(instance=None, data=None, partial=False):
        if data is not None:
            return update_serializer
        return SimpleNamespace(data={"id": str(comment_id), "comment_html": instance.comment_html})

    mocker.patch(f"{module_path}.IssueCommentSerializer", side_effect=serializer_factory)
    _assignee_query(mocker, module_path, assignee_id)
    activity = mocker.patch(f"{module_path}.issue_activity")

    view.partial_update(request, "public-anchor", issue_id, comment_id)

    call_kwargs = activity.delay.call_args.kwargs
    assert json.loads(call_kwargs["current_instance"])["comment_html"] == old_html
    assert call_kwargs["discord_assignee_ids"] == [str(assignee_id)]
