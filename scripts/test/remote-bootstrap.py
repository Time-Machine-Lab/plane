#!/usr/bin/env python3
"""Create or repair the persistent Plane test fixture from private stdin."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "plane.settings.production")

import django

django.setup()

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction

from plane.db.models import (
    Issue,
    Profile,
    Project,
    ProjectIdentifier,
    ProjectMember,
    State,
    User,
    Workspace,
    WorkspaceMember,
)
from plane.license.models import Instance, InstanceAdmin


FIXTURE_KEYS = {
    "PLANE_TEST_ADMIN_EMAIL",
    "PLANE_TEST_ADMIN_PASSWORD",
    "PLANE_TEST_MEMBER_EMAIL",
    "PLANE_TEST_MEMBER_PASSWORD",
    "PLANE_TEST_GUEST_EMAIL",
    "PLANE_TEST_GUEST_PASSWORD",
    "PLANE_TEST_WORKSPACE_NAME",
    "PLANE_TEST_WORKSPACE_SLUG",
    "PLANE_TEST_PROJECT_NAME",
    "PLANE_TEST_PROJECT_IDENTIFIER",
    "PLANE_TEST_FIXTURE_VERSION",
}
SECRET_LIMIT = 65536
ROLE_ADMIN = 20
ROLE_MEMBER = 15
ROLE_GUEST = 5
DEFAULT_STATES = (
    ("Backlog", "#60646C", 15000, "backlog", True),
    ("Todo", "#60646C", 25000, "unstarted", False),
    ("In Progress", "#F59E0B", 35000, "started", False),
    ("Done", "#46A758", 45000, "completed", False),
    ("Cancelled", "#9AA4BC", 55000, "cancelled", False),
)
DEFAULT_ISSUES = (
    ("[AI-TEST] Backlog item", "backlog", "low"),
    ("[AI-TEST] Active item", "started", "medium"),
    ("[AI-TEST] Completed item", "completed", "high"),
)


def fail(message: str) -> None:
    raise RuntimeError(message)


def read_fixture_config() -> dict[str, str]:
    payload = sys.stdin.read(SECRET_LIMIT + 1)
    if len(payload) > SECRET_LIMIT:
        fail("Fixture configuration exceeds the size limit")
    try:
        values = json.loads(payload)
    except json.JSONDecodeError as error:
        raise RuntimeError("Fixture configuration is not valid JSON") from error
    if not isinstance(values, dict):
        fail("Fixture configuration must be a JSON object")
    unsupported = sorted(set(values) - FIXTURE_KEYS)
    if unsupported:
        fail(f"Fixture configuration contains unsupported keys: {', '.join(unsupported)}")
    missing = sorted(FIXTURE_KEYS - set(values))
    if missing:
        fail(f"Fixture configuration is missing required keys: {', '.join(missing)}")
    if any(not isinstance(value, str) for value in values.values()):
        fail("Every fixture configuration value must be a string")
    return values


def validate_fixture_config(values: dict[str, str]) -> None:
    for role in ("ADMIN", "MEMBER", "GUEST"):
        email_key = f"PLANE_TEST_{role}_EMAIL"
        password_key = f"PLANE_TEST_{role}_PASSWORD"
        try:
            validate_email(values[email_key])
        except ValidationError as error:
            raise RuntimeError(f"{email_key} is not a valid email address") from error
        if len(values[password_key]) < 12:
            fail(f"{password_key} must contain at least 12 characters")

    if len({values[f"PLANE_TEST_{role}_EMAIL"].casefold() for role in ("ADMIN", "MEMBER", "GUEST")}) != 3:
        fail("Test account email addresses must be distinct")
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", values["PLANE_TEST_WORKSPACE_SLUG"]):
        fail("PLANE_TEST_WORKSPACE_SLUG must be a lowercase slug")
    if len(values["PLANE_TEST_WORKSPACE_SLUG"]) > 48:
        fail("PLANE_TEST_WORKSPACE_SLUG must not exceed 48 characters")
    if not 1 <= len(values["PLANE_TEST_WORKSPACE_NAME"]) <= 80:
        fail("PLANE_TEST_WORKSPACE_NAME must contain between 1 and 80 characters")
    if not re.fullmatch(r"[A-Za-z0-9]{1,12}", values["PLANE_TEST_PROJECT_IDENTIFIER"]):
        fail("PLANE_TEST_PROJECT_IDENTIFIER must contain 1-12 letters or digits")
    if not 1 <= len(values["PLANE_TEST_PROJECT_NAME"]) <= 255:
        fail("PLANE_TEST_PROJECT_NAME must contain between 1 and 255 characters")
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,32}", values["PLANE_TEST_FIXTURE_VERSION"]):
        fail("PLANE_TEST_FIXTURE_VERSION is invalid")


def model_has_field(model, field_name: str) -> bool:
    return any(field.name == field_name for field in model._meta.concrete_fields)


def supported_fields(model, values: dict[str, object]) -> dict[str, object]:
    return {key: value for key, value in values.items() if model_has_field(model, key)}


def save_changed(instance, updates: dict[str, object]) -> None:
    changed: list[str] = []
    for field_name, value in updates.items():
        if model_has_field(type(instance), field_name) and getattr(instance, field_name) != value:
            setattr(instance, field_name, value)
            changed.append(field_name)
    if changed:
        instance.save(update_fields=changed)


def ensure_user(email: str, password: str, role_name: str) -> User:
    normalized_email = email.casefold().strip()
    user = User.objects.filter(email__iexact=normalized_email).first()
    if user is None:
        username = f"plane-test-{role_name}-{hashlib.sha256(normalized_email.encode()).hexdigest()[:12]}"
        user = User.objects.create(
            **supported_fields(
                User,
                {
                    "email": normalized_email,
                    "username": username,
                    "display_name": f"Plane Test {role_name.title()}",
                    "first_name": "Plane Test",
                    "last_name": role_name.title(),
                    "is_active": True,
                    "is_email_verified": True,
                    "is_password_autoset": False,
                },
            )
        )

    save_changed(
        user,
        {
            "is_active": True,
            "is_email_verified": True,
            "is_password_autoset": False,
            "is_password_expired": False,
            "is_password_reset_required": False,
        },
    )
    if not user.check_password(password):
        user.set_password(password)
        user.save(update_fields=["password"])
    Profile.objects.get_or_create(user=user)
    return user


def ensure_membership(model, role: int, **lookup):
    membership, _ = model.objects.get_or_create(**lookup, defaults={"role": role, "is_active": True})
    save_changed(membership, {"role": role, "is_active": True})
    return membership


@transaction.atomic
def seed(values: dict[str, str]) -> None:
    instance = Instance.objects.order_by("created_at").first()
    if instance is None:
        fail("Plane instance registration is missing after migrations")

    admin = ensure_user(values["PLANE_TEST_ADMIN_EMAIL"], values["PLANE_TEST_ADMIN_PASSWORD"], "admin")
    member = ensure_user(values["PLANE_TEST_MEMBER_EMAIL"], values["PLANE_TEST_MEMBER_PASSWORD"], "member")
    guest = ensure_user(values["PLANE_TEST_GUEST_EMAIL"], values["PLANE_TEST_GUEST_PASSWORD"], "guest")

    save_changed(instance, {"is_setup_done": True, "instance_name": "Plane Test"})
    instance_admin, _ = InstanceAdmin.objects.get_or_create(instance=instance, user=admin, defaults={"role": ROLE_ADMIN})
    save_changed(instance_admin, {"role": ROLE_ADMIN, "is_verified": True})

    workspace_slug = values["PLANE_TEST_WORKSPACE_SLUG"]
    workspace, _ = Workspace.objects.get_or_create(
        slug=workspace_slug,
        defaults={"name": values["PLANE_TEST_WORKSPACE_NAME"], "owner": admin},
    )
    save_changed(workspace, {"name": values["PLANE_TEST_WORKSPACE_NAME"], "owner": admin})

    memberships = ((admin, ROLE_ADMIN), (member, ROLE_MEMBER), (guest, ROLE_GUEST))
    for user, role in memberships:
        ensure_membership(WorkspaceMember, role, workspace=workspace, member=user)
        profile, _ = Profile.objects.get_or_create(user=user)
        save_changed(
            profile,
            {
                "is_onboarded": True,
                "is_tour_completed": True,
                "last_workspace_id": workspace.id,
                "onboarding_step": {
                    "profile_complete": True,
                    "workspace_create": True,
                    "workspace_invite": True,
                    "workspace_join": True,
                },
            },
        )

    identifier = values["PLANE_TEST_PROJECT_IDENTIFIER"].upper()
    project = Project.objects.filter(workspace=workspace, identifier__iexact=identifier).first()
    if project is None:
        project = Project.objects.create(
            **supported_fields(
                Project,
                {
                    "workspace": workspace,
                    "name": values["PLANE_TEST_PROJECT_NAME"],
                    "identifier": identifier,
                    "project_lead": admin,
                    "created_by": admin,
                },
            )
        )
    save_changed(
        project,
        {
            "name": values["PLANE_TEST_PROJECT_NAME"],
            "project_lead": admin,
            "archived_at": None,
        },
    )
    ProjectIdentifier.objects.get_or_create(
        workspace=workspace,
        project=project,
        defaults={"name": identifier},
    )

    for user, role in memberships:
        ensure_membership(ProjectMember, role, workspace=workspace, project=project, member=user)

    state_by_group: dict[str, State] = {}
    for name, color, sequence, group, is_default in DEFAULT_STATES:
        state, _ = State.objects.get_or_create(
            workspace=workspace,
            project=project,
            name=name,
            defaults={
                "color": color,
                "sequence": sequence,
                "group": group,
                "default": is_default,
                "created_by": admin,
            },
        )
        save_changed(state, {"color": color, "group": group, "default": is_default})
        state_by_group[group] = state

    for name, group, priority in DEFAULT_ISSUES:
        issue = Issue.objects.filter(workspace=workspace, project=project, name=name).first()
        if issue is None:
            Issue.objects.create(
                workspace=workspace,
                project=project,
                name=name,
                state=state_by_group[group],
                priority=priority,
                created_by=admin,
            )


fixture_config = read_fixture_config()
validate_fixture_config(fixture_config)
seed(fixture_config)
print(fixture_config["PLANE_TEST_FIXTURE_VERSION"])
