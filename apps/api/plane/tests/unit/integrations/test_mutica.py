# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import json
from types import SimpleNamespace

import pytest
from celery.exceptions import Retry
from django.test import override_settings
from django.urls import reverse
from rest_framework import status

from plane.bgtasks.mutica_task import build_mutica_event, deliver_mutica_delegation
from plane.db.models import (
    APIToken,
    Integration,
    Issue,
    IssueActivity,
    IssueAssignee,
    MuticaConnection,
    MuticaDelegationStatus,
    MuticaDeliveryAttempt,
    MuticaDeliveryStatus,
    MuticaExternalAgent,
    MuticaIssueDelegation,
    Project,
    ProjectMember,
    User,
    WorkspaceMember,
)
from plane.integrations.mutica import (
    connect_mutica,
    disconnect_mutica,
    rotate_mutica_service_token,
    sync_mutica_project_membership,
)
from plane.utils.secret_encryption import decrypt_secret


class StubResponse:
    def __init__(self, status_code):
        self.status_code = status_code
        self.closed = False

    def close(self):
        self.closed = True


@pytest.fixture
def mutica_integration(db):
    return Integration.objects.create(
        provider="mutica",
        title="Mutica",
        network=1,
        description={"text": "Mutica"},
        author="Plane",
        verified=True,
    )


@pytest.fixture
def project(workspace):
    return Project.objects.create(name="Engineering", identifier="ENG", workspace=workspace)


@pytest.fixture
def issue(project):
    return Issue.objects.create(name="Implement agent handoff", project=project)


def connect_workspace(workspace, mutica_integration, project=None):
    connection, raw_token = connect_mutica(
        workspace=workspace,
        endpoint_url="https://mutica.example.test/events",
        signing_secret="super-secret-signing-value",
        agent_external_id="assistant-default",
        agent_display_name="Mutica Assistant",
        agent_avatar_url=None,
    )
    return connection, raw_token


def grant_project_access(workspace, project, user, role=20):
    WorkspaceMember.objects.update_or_create(
        workspace=workspace,
        member=user,
        defaults={"role": role, "is_active": True},
    )
    ProjectMember.objects.update_or_create(
        workspace=workspace,
        project=project,
        member=user,
        defaults={"role": role, "is_active": True},
    )


def delegation_url(workspace, project, issue):
    return reverse(
        "mutica-issue-delegation",
        kwargs={"slug": workspace.slug, "project_id": project.id, "issue_id": issue.id},
    )


def retry_url(workspace, project, issue):
    return reverse(
        "mutica-issue-delegation-retry",
        kwargs={"slug": workspace.slug, "project_id": project.id, "issue_id": issue.id},
    )


def capture_scheduled_deliveries(monkeypatch):
    scheduled = []
    monkeypatch.setattr(
        "plane.app.views.mutica_delegation.deliver_mutica_delegation.delay",
        lambda delegation_id, attempt_offset: scheduled.append((delegation_id, attempt_offset)),
    )
    return scheduled


def assert_activity_is_non_sensitive(activity, delegation, actor, verb):
    assert activity.field == "mutica_delegation"
    assert activity.verb == verb
    assert activity.actor == actor
    assert activity.new_identifier == delegation.id
    serialized = json.dumps(
        {
            "old_value": activity.old_value,
            "new_value": activity.new_value,
            "comment": activity.comment,
            "attachments": activity.attachments,
        },
        default=str,
    )
    assert "super-secret-signing-value" not in serialized
    assert "plane_api_" not in serialized


@pytest.mark.unit
class TestMuticaConnection:
    @pytest.mark.django_db
    @override_settings(WEBHOOK_ALLOWED_HOSTS=["mutica.example.test"], WEBHOOK_DISALLOWED_DOMAINS=[])
    def test_workspace_member_cannot_connect_mutica(self, session_client, create_user, workspace, monkeypatch):
        member = User.objects.create(email="member@plane.so", username="member")
        WorkspaceMember.objects.create(workspace=workspace, member=member, role=15)
        session_client.force_authenticate(user=member)
        monkeypatch.setattr("plane.app.views.mutica.verify_mutica_endpoint", lambda *args, **kwargs: None)

        response = session_client.post(
            reverse("mutica-connection", kwargs={"slug": workspace.slug}),
            {
                "endpoint_url": "https://mutica.example.test/events",
                "signing_secret": "super-secret-signing-value",
                "agent_external_id": "assistant-default",
                "agent_display_name": "Mutica Assistant",
            },
            format="json",
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert not MuticaConnection.objects.exists()

    @pytest.mark.django_db
    @override_settings(WEBHOOK_ALLOWED_HOSTS=["mutica.example.test"], WEBHOOK_DISALLOWED_DOMAINS=[])
    def test_admin_connects_with_one_time_token_and_no_secret_in_response(
        self, session_client, create_user, workspace, project, mutica_integration, monkeypatch
    ):
        captured = {}

        def pinned_fetch(method, url, **kwargs):
            captured.update({"method": method, "url": url, **kwargs})
            return StubResponse(204)

        monkeypatch.setattr("plane.integrations.mutica.pinned_fetch", pinned_fetch)
        session_client.force_authenticate(user=create_user)

        response = session_client.post(
            reverse("mutica-connection", kwargs={"slug": workspace.slug}),
            {
                "endpoint_url": "https://mutica.example.test/events",
                "signing_secret": "super-secret-signing-value",
                "agent_external_id": "assistant-default",
                "agent_display_name": "Mutica Assistant",
            },
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["service_token"].startswith("plane_api_")
        assert "signing_secret" not in response.data
        assert captured["method"] == "POST"
        assert captured["headers"]["X-Plane-Signature"].startswith("sha256=")
        assert b"super-secret-signing-value" not in captured["data"]

    @pytest.mark.django_db
    def test_connect_rotate_disconnect_manage_workspace_service_identity_and_history(
        self, workspace, project, issue, mutica_integration, create_user
    ):
        connection, raw_token = connect_workspace(workspace, mutica_integration, project)
        workspace_integration = connection.workspace_integration
        service_token = APIToken.objects.get(token=raw_token)
        delegation = MuticaIssueDelegation.objects.create(
            issue=issue,
            project=project,
            agent=MuticaExternalAgent.objects.get(workspace_integration=workspace_integration),
            initiated_by=create_user,
        )

        assert service_token.is_service is True
        assert service_token.workspace == workspace
        assert workspace_integration.actor.is_bot is True
        assert workspace_integration.actor.bot_type == "MUTICA"
        assert WorkspaceMember.objects.filter(workspace=workspace, member=workspace_integration.actor, role=15).exists()
        assert ProjectMember.objects.filter(project=project, member=workspace_integration.actor, role=15).exists()
        assert decrypt_secret(connection.signing_secret) == "super-secret-signing-value"

        new_project = Project.objects.create(name="New Project", identifier="NEW", workspace=workspace)
        assert ProjectMember.objects.filter(project=new_project, member=workspace_integration.actor, role=15).exists()

        rotated_raw_token = rotate_mutica_service_token(connection)
        service_token.refresh_from_db()
        rotated_token = APIToken.objects.get(token=rotated_raw_token)
        workspace_integration.refresh_from_db()
        assert service_token.is_active is False
        assert rotated_token.is_active is True
        assert rotated_token.is_service is True
        assert rotated_token.workspace == workspace
        assert workspace_integration.api_token == rotated_token

        disconnect_mutica(connection)
        rotated_token.refresh_from_db()
        delegation.refresh_from_db()
        connection.refresh_from_db()
        assert rotated_token.is_active is False
        assert connection.is_enabled is False
        assert delegation.status == MuticaDelegationStatus.SUPERSEDED

    @pytest.mark.django_db
    def test_manual_project_sync_is_noop_without_connection(self, workspace):
        project = Project.objects.create(name="No Connection", identifier="NC", workspace=workspace)

        sync_mutica_project_membership(project)

        assert ProjectMember.objects.filter(project=project, member__is_bot=True).count() == 0


@pytest.mark.unit
class TestMuticaDelegationAPI:
    @pytest.mark.django_db
    def test_authorized_delegate_retry_and_clear_preserve_issue_assignees(
        self, session_client, create_user, workspace, project, issue, mutica_integration, monkeypatch
    ):
        connect_workspace(workspace, mutica_integration, project)
        grant_project_access(workspace, project, create_user)
        scheduled = capture_scheduled_deliveries(monkeypatch)
        assignee = User.objects.create(email="assignee@plane.so", username="assignee")
        IssueAssignee.objects.create(issue=issue, assignee=assignee, project=project)

        session_client.force_authenticate(user=create_user)
        response = session_client.post(delegation_url(workspace, project, issue), {}, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["status"] == MuticaDelegationStatus.DISPATCHING
        assert scheduled == [(response.data["id"], 1)]
        assert IssueAssignee.objects.filter(issue=issue, assignee=assignee, deleted_at__isnull=True).exists()

        delegation = MuticaIssueDelegation.objects.get(pk=response.data["id"])
        activity = IssueActivity.objects.get(new_identifier=delegation.id, verb="delegated")
        assert_activity_is_non_sensitive(activity, delegation, create_user, "delegated")

        delegation.status = MuticaDelegationStatus.FAILED
        delegation.failure_category = "timeout"
        delegation.save(update_fields=["status", "failure_category", "updated_at"])

        response = session_client.post(retry_url(workspace, project, issue), {}, format="json")

        assert response.status_code == status.HTTP_202_ACCEPTED
        delegation.refresh_from_db()
        assert delegation.status == MuticaDelegationStatus.DISPATCHING
        assert delegation.failure_category == ""
        assert scheduled[-1] == (str(delegation.id), 1)
        retry_activity = IssueActivity.objects.get(new_identifier=delegation.id, verb="retried")
        assert_activity_is_non_sensitive(retry_activity, delegation, create_user, "retried")
        assert IssueAssignee.objects.filter(issue=issue, assignee=assignee, deleted_at__isnull=True).exists()

        response = session_client.delete(delegation_url(workspace, project, issue))

        assert response.status_code == status.HTTP_204_NO_CONTENT
        delegation.refresh_from_db()
        assert delegation.status == MuticaDelegationStatus.SUPERSEDED
        clear_activity = IssueActivity.objects.get(new_identifier=delegation.id, verb="cleared")
        assert_activity_is_non_sensitive(clear_activity, delegation, create_user, "cleared")
        assert IssueAssignee.objects.filter(issue=issue, assignee=assignee, deleted_at__isnull=True).exists()

    @pytest.mark.django_db
    def test_guest_cannot_delegate_retry_or_clear(
        self, session_client, create_user, workspace, project, issue, mutica_integration, monkeypatch
    ):
        connection, _ = connect_workspace(workspace, mutica_integration, project)
        grant_project_access(workspace, project, create_user)
        guest = User.objects.create(email="guest@plane.so", username="guest")
        grant_project_access(workspace, project, guest, role=5)
        delegation = MuticaIssueDelegation.objects.create(
            issue=issue,
            project=project,
            agent=MuticaExternalAgent.objects.get(workspace_integration=connection.workspace_integration),
            initiated_by=create_user,
            status=MuticaDelegationStatus.FAILED,
            failure_category="timeout",
        )
        scheduled = capture_scheduled_deliveries(monkeypatch)

        session_client.force_authenticate(user=guest)

        assert session_client.post(delegation_url(workspace, project, issue), {}, format="json").status_code == (
            status.HTTP_403_FORBIDDEN
        )
        assert session_client.post(retry_url(workspace, project, issue), {}, format="json").status_code == (
            status.HTTP_403_FORBIDDEN
        )
        assert session_client.delete(delegation_url(workspace, project, issue)).status_code == status.HTTP_403_FORBIDDEN

        delegation.refresh_from_db()
        assert delegation.status == MuticaDelegationStatus.FAILED
        assert delegation.failure_category == "timeout"
        assert scheduled == []
        assert MuticaIssueDelegation.objects.filter(issue=issue).count() == 1

    @pytest.mark.django_db
    def test_success_and_permanent_failure_transitions_record_non_sensitive_activity(
        self, workspace, project, issue, mutica_integration, create_user, monkeypatch
    ):
        connection, _ = connect_workspace(workspace, mutica_integration, project)
        agent = MuticaExternalAgent.objects.get(workspace_integration=connection.workspace_integration)
        accepted_delegation = MuticaIssueDelegation.objects.create(
            issue=issue,
            project=project,
            agent=agent,
            initiated_by=create_user,
        )
        monkeypatch.setattr("plane.bgtasks.mutica_task.pinned_fetch", lambda *args, **kwargs: StubResponse(204))

        deliver_mutica_delegation.run(str(accepted_delegation.id), 1)

        accepted_delegation.refresh_from_db()
        accepted_attempt = accepted_delegation.delivery_attempts.get(attempt_number=1)
        assert accepted_delegation.status == MuticaDelegationStatus.HANDED_OFF
        assert accepted_attempt.status == MuticaDeliveryStatus.ACCEPTED
        handed_off_activity = IssueActivity.objects.get(new_identifier=accepted_delegation.id, verb="handed_off")
        assert_activity_is_non_sensitive(handed_off_activity, accepted_delegation, create_user, "handed_off")

        failed_issue = Issue.objects.create(name="Reject handoff", project=project)
        failed_delegation = MuticaIssueDelegation.objects.create(
            issue=failed_issue,
            project=project,
            agent=agent,
            initiated_by=create_user,
        )
        monkeypatch.setattr("plane.bgtasks.mutica_task.pinned_fetch", lambda *args, **kwargs: StubResponse(400))

        deliver_mutica_delegation.run(str(failed_delegation.id), 1)

        failed_delegation.refresh_from_db()
        failed_attempt = failed_delegation.delivery_attempts.get(attempt_number=1)
        assert failed_delegation.status == MuticaDelegationStatus.FAILED
        assert failed_delegation.failure_category == "mutica_rejected"
        assert failed_attempt.status == MuticaDeliveryStatus.PERMANENT_FAILURE
        failed_activity = IssueActivity.objects.get(new_identifier=failed_delegation.id, verb="failed")
        assert_activity_is_non_sensitive(failed_activity, failed_delegation, create_user, "failed")
        assert failed_activity.new_value == "mutica_rejected"

    @pytest.mark.django_db
    def test_in_flight_success_after_reassign_marks_old_attempt_stale_without_overriding_current(
        self, session_client, create_user, workspace, project, issue, mutica_integration, monkeypatch
    ):
        connect_workspace(workspace, mutica_integration, project)
        grant_project_access(workspace, project, create_user)
        capture_scheduled_deliveries(monkeypatch)

        session_client.force_authenticate(user=create_user)
        first_response = session_client.post(delegation_url(workspace, project, issue), {}, format="json")
        assert first_response.status_code == status.HTTP_201_CREATED
        first = MuticaIssueDelegation.objects.get(pk=first_response.data["id"])

        def reassign_before_accepting(*args, **kwargs):
            response = session_client.post(delegation_url(workspace, project, issue), {}, format="json")
            assert response.status_code == status.HTTP_201_CREATED
            return StubResponse(204)

        monkeypatch.setattr("plane.bgtasks.mutica_task.pinned_fetch", reassign_before_accepting)

        deliver_mutica_delegation.run(str(first.id), 1)

        first.refresh_from_db()
        first_attempt = first.delivery_attempts.get(attempt_number=1)
        second = MuticaIssueDelegation.objects.exclude(pk=first.pk).get(issue=issue)
        assert first.status == MuticaDelegationStatus.SUPERSEDED
        assert first_attempt.status == MuticaDeliveryStatus.STALE
        assert second.status == MuticaDelegationStatus.DISPATCHING
        assert (
            MuticaIssueDelegation.objects.filter(issue=issue, status__in=["dispatching", "handed_off", "failed"]).get()
            == second
        )
        reassigned_activity = IssueActivity.objects.get(new_identifier=second.id, verb="reassigned")
        assert_activity_is_non_sensitive(reassigned_activity, second, create_user, "reassigned")

    @pytest.mark.django_db
    def test_in_flight_success_after_clear_marks_attempt_stale_without_restoring_current(
        self, session_client, create_user, workspace, project, issue, mutica_integration, monkeypatch
    ):
        connect_workspace(workspace, mutica_integration, project)
        grant_project_access(workspace, project, create_user)
        capture_scheduled_deliveries(monkeypatch)

        session_client.force_authenticate(user=create_user)
        response = session_client.post(delegation_url(workspace, project, issue), {}, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        delegation = MuticaIssueDelegation.objects.get(pk=response.data["id"])

        def clear_before_accepting(*args, **kwargs):
            clear_response = session_client.delete(delegation_url(workspace, project, issue))
            assert clear_response.status_code == status.HTTP_204_NO_CONTENT
            return StubResponse(204)

        monkeypatch.setattr("plane.bgtasks.mutica_task.pinned_fetch", clear_before_accepting)

        deliver_mutica_delegation.run(str(delegation.id), 1)

        delegation.refresh_from_db()
        attempt = delegation.delivery_attempts.get(attempt_number=1)
        assert delegation.status == MuticaDelegationStatus.SUPERSEDED
        assert attempt.status == MuticaDeliveryStatus.STALE
        assert not MuticaIssueDelegation.objects.filter(
            issue=issue, status__in=["dispatching", "handed_off", "failed"]
        ).exists()
        cleared_activity = IssueActivity.objects.get(new_identifier=delegation.id, verb="cleared")
        assert_activity_is_non_sensitive(cleared_activity, delegation, create_user, "cleared")


@pytest.mark.unit
class TestMuticaDelivery:
    @pytest.mark.django_db
    def test_signed_event_is_thin_and_redacted(self, workspace, project, issue, mutica_integration, create_user):
        connection, _ = connect_workspace(workspace, mutica_integration, project)
        delegation = MuticaIssueDelegation.objects.create(
            issue=issue,
            project=project,
            agent=MuticaExternalAgent.objects.get(workspace_integration=connection.workspace_integration),
            initiated_by=create_user,
        )
        attempt = MuticaDeliveryAttempt.objects.create(delegation=delegation, attempt_number=1)

        body, headers = build_mutica_event(delegation, attempt)
        payload = json.loads(body)

        assert payload == {
            "type": "plane.work_item.delegated",
            "schema_version": 1,
            "event_id": f"mutica-delegation:{delegation.id}",
            "delivery_id": str(attempt.delivery_id),
            "delegation_id": str(delegation.id),
            "delegated_at": payload["delegated_at"],
            "plane_origin": payload["plane_origin"],
            "workspace_slug": workspace.slug,
            "project_id": str(project.id),
            "work_item_id": str(issue.id),
            "work_item_url": payload["work_item_url"],
            "agent_external_id": "assistant-default",
        }
        assert headers["Idempotency-Key"] == str(delegation.id)
        assert headers["X-Plane-Signature"].startswith("sha256=")
        serialized = body.decode("utf-8")
        assert "super-secret-signing-value" not in serialized
        assert "plane_api_" not in serialized
        assert "comments" not in serialized
        assert "attachments" not in serialized

    @pytest.mark.django_db
    def test_stale_delivery_attempt_cannot_restore_superseded_delegation(
        self, workspace, project, issue, mutica_integration, create_user
    ):
        connection, _ = connect_workspace(workspace, mutica_integration, project)
        delegation = MuticaIssueDelegation.objects.create(
            issue=issue,
            project=project,
            agent=MuticaExternalAgent.objects.get(workspace_integration=connection.workspace_integration),
            initiated_by=create_user,
            status=MuticaDelegationStatus.SUPERSEDED,
        )

        deliver_mutica_delegation.run(str(delegation.id), 1)

        delegation.refresh_from_db()
        attempt = delegation.delivery_attempts.get(attempt_number=1)
        assert delegation.status == MuticaDelegationStatus.SUPERSEDED
        assert attempt.status == MuticaDeliveryStatus.STALE

    @pytest.mark.django_db
    def test_retryable_delivery_failure_is_bounded_and_redacted(
        self, workspace, project, issue, mutica_integration, create_user, monkeypatch
    ):
        connection, _ = connect_workspace(workspace, mutica_integration, project)
        delegation = MuticaIssueDelegation.objects.create(
            issue=issue,
            project=project,
            agent=MuticaExternalAgent.objects.get(workspace_integration=connection.workspace_integration),
            initiated_by=create_user,
        )
        monkeypatch.setattr("plane.bgtasks.mutica_task.pinned_fetch", lambda *args, **kwargs: StubResponse(503))

        with pytest.raises(Retry):
            deliver_mutica_delegation.run(str(delegation.id), 1)

        attempt = delegation.delivery_attempts.get(attempt_number=1)
        assert attempt.status == MuticaDeliveryStatus.RETRYABLE_FAILURE
        assert attempt.response_status == 503
        assert attempt.failure_category == "mutica_unavailable"
