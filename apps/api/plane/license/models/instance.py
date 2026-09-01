# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Python imports
from enum import Enum

# Django imports
from django.db import models
from django.conf import settings

# Module imports
from plane.db.models import BaseModel
from plane.utils.secret_encryption import decrypt_secret, encrypt_secret

ROLE_CHOICES = ((20, "Admin"),)


class InstanceEdition(Enum):
    PLANE_COMMUNITY = "PLANE_COMMUNITY"


class Instance(BaseModel):
    # General information
    instance_name = models.CharField(max_length=255)
    whitelist_emails = models.TextField(blank=True, null=True)
    instance_id = models.CharField(max_length=255, unique=True)
    current_version = models.CharField(max_length=255)
    latest_version = models.CharField(max_length=255, null=True, blank=True)
    edition = models.CharField(max_length=255, default=InstanceEdition.PLANE_COMMUNITY.value)
    domain = models.TextField(blank=True)
    # Instance specifics
    last_checked_at = models.DateTimeField()
    namespace = models.CharField(max_length=255, blank=True, null=True)
    # telemetry and support
    is_telemetry_enabled = models.BooleanField(default=True)
    is_support_required = models.BooleanField(default=True)
    # is setup done
    is_setup_done = models.BooleanField(default=False)
    # signup screen
    is_signup_screen_visited = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    is_test = models.BooleanField(default=False)
    # field for validating if the current version is deprecated
    is_current_version_deprecated = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Instance"
        verbose_name_plural = "Instances"
        db_table = "instances"
        ordering = ("-created_at",)


class InstanceAdmin(BaseModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="instance_owner",
    )
    instance = models.ForeignKey(Instance, on_delete=models.CASCADE, related_name="admins")
    role = models.PositiveIntegerField(choices=ROLE_CHOICES, default=20)
    is_verified = models.BooleanField(default=False)

    class Meta:
        unique_together = ["instance", "user"]
        verbose_name = "Instance Admin"
        verbose_name_plural = "Instance Admins"
        db_table = "instance_admins"
        ordering = ("-created_at",)


class InstanceConfiguration(BaseModel):
    # The instance configuration variables
    key = models.CharField(max_length=100, unique=True)
    value = models.TextField(null=True, blank=True, default=None)
    category = models.TextField()
    is_encrypted = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Instance Configuration"
        verbose_name_plural = "Instance Configurations"
        db_table = "instance_configurations"
        ordering = ("-created_at",)


class StorageProfile(BaseModel):
    """Versioned object-storage location used by newly-created file assets."""

    class Provider(models.TextChoices):
        ALIYUN_OSS = "ALIYUN_OSS", "Aliyun OSS"
        S3 = "S3", "Amazon S3"

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        VERIFIED = "VERIFIED", "Verified"
        ACTIVE = "ACTIVE", "Active"
        RETIRED = "RETIRED", "Retired"

    instance = models.ForeignKey(Instance, on_delete=models.CASCADE, related_name="storage_profiles")
    provider = models.CharField(max_length=32, choices=Provider.choices, default=Provider.ALIYUN_OSS)
    bucket = models.CharField(max_length=255)
    region = models.CharField(max_length=128)
    endpoint = models.URLField(max_length=500, blank=True)
    access_key_id = models.CharField(max_length=255)
    access_key_secret = models.TextField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    file_size_limit = models.PositiveBigIntegerField(default=104857600)
    object_prefix = models.CharField(max_length=255, default="plane-assets/")
    verified_at = models.DateTimeField(null=True, blank=True)
    verification_error = models.TextField(blank=True, default="")
    last_probe_at = models.DateTimeField(null=True, blank=True)
    probe_object_key = models.CharField(max_length=800, blank=True, default="")

    class Meta:
        db_table = "instance_storage_profiles"
        ordering = ("-created_at",)
        indexes = [models.Index(fields=["instance", "status"], name="storage_profile_status_idx")]

    @property
    def effective_endpoint(self):
        if self.endpoint:
            return self.endpoint.rstrip("/")
        if self.provider == self.Provider.ALIYUN_OSS:
            return f"https://oss-{self.region}.aliyuncs.com"
        return f"https://s3.{self.region}.amazonaws.com"

    def set_secret(self, value: str):
        self.access_key_secret = encrypt_secret(value)

    def get_secret(self) -> str:
        return decrypt_secret(self.access_key_secret)


class ChangeLog(BaseModel):
    """Change Log model to store the release changelogs made in the application."""

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    version = models.CharField(max_length=255)
    tags = models.JSONField(default=list)
    release_date = models.DateTimeField(null=True)
    is_release_candidate = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Change Log"
        verbose_name_plural = "Change Logs"
        db_table = "changelogs"
        ordering = ("-created_at",)
