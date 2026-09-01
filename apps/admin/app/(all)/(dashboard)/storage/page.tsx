/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useRef, useState, type ReactNode } from "react";
import { useTranslation } from "@plane/i18n";
import { Button } from "@plane/propel/button";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import { InstanceService } from "@plane/services";
import type { TStorageProfile, TStorageProfilePayload } from "@plane/types";
import { Input } from "@plane/ui";
import { PageWrapper } from "@/components/common/page-wrapper";

const service = new InstanceService();
const BYTES_PER_MB = 1024 * 1024;
const MAX_FILE_LIMIT_MB = 10_240;

const initial: TStorageProfilePayload = {
  provider: "ALIYUN_OSS",
  access_key_id: "",
  access_key_secret: "",
  bucket: "",
  region: "",
  endpoint: "",
  file_size_limit: 100 * BYTES_PER_MB,
};

type TStorageFormField = "access_key_id" | "access_key_secret" | "bucket" | "region" | "endpoint" | "file_size_limit";
type TStorageFormErrors = Partial<Record<TStorageFormField, string>>;
type TStorageApiError = { error?: unknown; fields?: unknown } & Partial<Record<TStorageFormField, unknown>>;

const STORAGE_FORM_FIELDS: TStorageFormField[] = [
  "access_key_id",
  "access_key_secret",
  "bucket",
  "region",
  "endpoint",
  "file_size_limit",
];

const getErrorText = (value: unknown): string | undefined => {
  if (typeof value === "string") return value;
  if (Array.isArray(value)) return getErrorText(value[0]);
  return undefined;
};

const getApiFieldErrors = (error: unknown, requiredMessage: string): TStorageFormErrors => {
  if (!error || typeof error !== "object") return {};
  const payload = error as TStorageApiError;
  const errors: TStorageFormErrors = {};

  for (const field of STORAGE_FORM_FIELDS) {
    const message = getErrorText(payload[field]);
    if (message) errors[field] = message;
  }
  if (Array.isArray(payload.fields)) {
    for (const field of payload.fields) {
      if (typeof field === "string" && STORAGE_FORM_FIELDS.includes(field as TStorageFormField)) {
        errors[field as TStorageFormField] = requiredMessage;
      }
    }
  }

  return errors;
};

const getProfileForm = (profile: TStorageProfile): TStorageProfilePayload => ({
  provider: profile.provider,
  access_key_id: profile.access_key_id,
  access_key_secret: "",
  bucket: profile.bucket,
  region: profile.region,
  endpoint: profile.endpoint,
  file_size_limit: profile.file_size_limit,
});

export default function ObjectStoragePage() {
  const { t } = useTranslation();
  const [profiles, setProfiles] = useState<TStorageProfile[]>([]);
  const [draft, setDraft] = useState<TStorageProfile>();
  const [form, setForm] = useState(initial);
  const [fieldErrors, setFieldErrors] = useState<TStorageFormErrors>({});
  const [busy, setBusy] = useState<string>();
  const [advanced, setAdvanced] = useState(false);
  const isFormDirtyRef = useRef(false);

  const refresh = async () => {
    const result = await service.storageProfiles();
    setProfiles(result);
    const selected = result.find((profile) => profile.status === "DRAFT" || profile.status === "VERIFIED") ?? result[0];
    setDraft(selected);
    if (selected && !isFormDirtyRef.current) {
      setForm(getProfileForm(selected));
      setFieldErrors({});
    }
  };

  useEffect(() => {
    void refresh();
  }, []);

  const validateField = (field: TStorageFormField, value: TStorageProfilePayload = form): string | undefined => {
    const required = t("common.errors.required");
    if (field === "access_key_id" && !value.access_key_id.trim()) return required;
    if (field === "access_key_secret" && !draft?.secret_configured && !value.access_key_secret?.trim()) return required;
    if (field === "bucket" && !value.bucket.trim()) return required;
    if (field === "region" && !value.region.trim()) return required;

    if (field === "endpoint" && value.endpoint.trim()) {
      try {
        const endpoint = new URL(value.endpoint);
        if (!endpoint.hostname || !["http:", "https:"].includes(endpoint.protocol)) {
          return t("common.url_is_invalid");
        }
      } catch {
        return t("common.url_is_invalid");
      }
    }

    if (field === "file_size_limit") {
      const fileLimitMb = value.file_size_limit / BYTES_PER_MB;
      if (!Number.isFinite(fileLimitMb) || fileLimitMb < 1 || fileLimitMb > MAX_FILE_LIMIT_MB) {
        return t("attachment.file_size_limit_range_error");
      }
    }

    return undefined;
  };

  const validate = (value: TStorageProfilePayload = form): TStorageFormErrors => {
    const errors: TStorageFormErrors = {};
    for (const field of STORAGE_FORM_FIELDS) {
      const error = validateField(field, value);
      if (error) errors[field] = error;
    }
    return errors;
  };

  const validateOnBlur = (field: TStorageFormField) => {
    const error = validateField(field);
    setFieldErrors((current) => {
      const next = { ...current };
      if (error) next[field] = error;
      else delete next[field];
      return next;
    });
  };

  const save = async () => {
    const validationErrors = validate();
    setFieldErrors(validationErrors);
    if (Object.keys(validationErrors).length > 0) return;

    setBusy("save");
    try {
      const payload = {
        ...form,
        access_key_id: form.access_key_id.trim(),
        bucket: form.bucket.trim(),
        region: form.region.trim(),
        endpoint: form.endpoint.trim(),
      };
      if (!payload.access_key_secret) delete payload.access_key_secret;
      const result = draft
        ? await service.updateStorageProfile(draft.id, payload)
        : await service.createStorageProfile(payload);
      isFormDirtyRef.current = false;
      setDraft(result);
      setForm(getProfileForm(result));
      setFieldErrors({});
      setToast({ type: TOAST_TYPE.SUCCESS, title: t("success"), message: "Storage draft saved." });
      await refresh();
    } catch (error) {
      const apiFieldErrors = getApiFieldErrors(error, t("common.errors.required"));
      setFieldErrors(apiFieldErrors);
      const message =
        getErrorText((error as TStorageApiError | undefined)?.error) ??
        Object.values(apiFieldErrors)[0] ??
        t("common.errors.default.message");
      setToast({ type: TOAST_TYPE.ERROR, title: t("error"), message });
    } finally {
      setBusy(undefined);
    }
  };

  const probe = async () => {
    if (!draft) return;
    setBusy("probe");
    try {
      const intent = await service.startStorageProbe(draft.id);
      const body = new FormData();
      Object.entries(intent.upload_data.fields).forEach(([key, value]) => body.append(key, value));
      body.append("file", new Blob(["plane-storage-probe"], { type: "text/plain" }), "probe.txt");
      const response = await fetch(intent.upload_data.url, { method: "POST", body });
      if (!response.ok) throw new Error("Browser upload failed");
      await service.completeStorageProbe(draft.id);
      setToast({
        type: TOAST_TYPE.SUCCESS,
        title: "Connection verified",
        message: "Browser upload, read, and cleanup succeeded.",
      });
      await refresh();
    } catch {
      setToast({
        type: TOAST_TYPE.ERROR,
        title: "Connection failed",
        message: `Allow POST, GET, and HEAD from ${window.location.origin} in the OSS Bucket CORS rules.`,
      });
    } finally {
      setBusy(undefined);
    }
  };

  const activate = async () => {
    if (!draft || !window.confirm(t("confirm"))) return;
    setBusy("activate");
    try {
      await service.activateStorageProfile(draft.id);
      await refresh();
    } finally {
      setBusy(undefined);
    }
  };

  const rollback = async () => {
    if (!window.confirm(t("confirm"))) return;
    setBusy("rollback");
    try {
      await service.rollbackStorageProfile();
      await refresh();
    } finally {
      setBusy(undefined);
    }
  };

  const update = (key: keyof TStorageProfilePayload, value: string | number) => {
    const nextForm = { ...form, [key]: value };
    isFormDirtyRef.current = true;
    setForm(nextForm);
    if (STORAGE_FORM_FIELDS.includes(key as TStorageFormField)) {
      const field = key as TStorageFormField;
      setFieldErrors((current) => {
        if (!current[field]) return current;
        const error = validateField(field, nextForm);
        const next = { ...current };
        if (error) next[field] = error;
        else delete next[field];
        return next;
      });
    }
  };
  const active = profiles.find((profile) => profile.status === "ACTIVE");

  return (
    <PageWrapper
      header={{
        title: t("attachment.object_storage"),
        description: "Send new user uploads directly to a private Aliyun OSS Bucket.",
      }}
    >
      <div className="max-w-3xl space-y-6">
        <div className="grid gap-4 md:grid-cols-2">
          <Field id="access-key-id" label={t("attachment.access_key_id")} error={fieldErrors.access_key_id}>
            <Input
              id="access-key-id"
              value={form.access_key_id}
              hasError={Boolean(fieldErrors.access_key_id)}
              aria-describedby={fieldErrors.access_key_id ? "access-key-id-error" : undefined}
              onChange={(event) => update("access_key_id", event.target.value)}
              onBlur={() => validateOnBlur("access_key_id")}
            />
          </Field>
          <Field id="access-key-secret" label={t("attachment.access_key_secret")} error={fieldErrors.access_key_secret}>
            <Input
              id="access-key-secret"
              type="password"
              placeholder={draft?.secret_configured ? "Configured (leave blank to keep)" : t("required")}
              value={form.access_key_secret ?? ""}
              hasError={Boolean(fieldErrors.access_key_secret)}
              aria-describedby={fieldErrors.access_key_secret ? "access-key-secret-error" : undefined}
              onChange={(event) => update("access_key_secret", event.target.value)}
              onBlur={() => validateOnBlur("access_key_secret")}
            />
          </Field>
          <Field id="bucket" label={t("attachment.bucket")} error={fieldErrors.bucket}>
            <Input
              id="bucket"
              value={form.bucket}
              hasError={Boolean(fieldErrors.bucket)}
              aria-describedby={fieldErrors.bucket ? "bucket-error" : undefined}
              onChange={(event) => update("bucket", event.target.value)}
              onBlur={() => validateOnBlur("bucket")}
            />
          </Field>
          <Field id="region" label={t("attachment.region")} error={fieldErrors.region}>
            <Input
              id="region"
              placeholder="cn-hangzhou"
              value={form.region}
              hasError={Boolean(fieldErrors.region)}
              aria-describedby={fieldErrors.region ? "region-error" : undefined}
              onChange={(event) => update("region", event.target.value)}
              onBlur={() => validateOnBlur("region")}
            />
          </Field>
          <Field id="file-size-limit" label={t("attachment.single_file_limit")} error={fieldErrors.file_size_limit}>
            <Input
              id="file-size-limit"
              type="number"
              min={1}
              max={MAX_FILE_LIMIT_MB}
              value={Math.round(form.file_size_limit / BYTES_PER_MB)}
              hasError={Boolean(fieldErrors.file_size_limit)}
              aria-describedby={fieldErrors.file_size_limit ? "file-size-limit-error" : undefined}
              onChange={(event) => update("file_size_limit", Number(event.target.value) * BYTES_PER_MB)}
              onBlur={() => validateOnBlur("file_size_limit")}
            />
          </Field>
        </div>
        <button type="button" className="text-sm text-link-primary" onClick={() => setAdvanced((value) => !value)}>
          {advanced ? "Hide advanced settings" : "Advanced settings"}
        </button>
        {advanced && (
          <Field id="endpoint" label="Endpoint override" error={fieldErrors.endpoint}>
            <Input
              id="endpoint"
              placeholder={form.region ? `https://oss-${form.region}.aliyuncs.com` : "Derived from Region"}
              value={form.endpoint}
              hasError={Boolean(fieldErrors.endpoint)}
              aria-describedby={fieldErrors.endpoint ? "endpoint-error" : undefined}
              onChange={(event) => update("endpoint", event.target.value)}
              onBlur={() => validateOnBlur("endpoint")}
            />
          </Field>
        )}
        <div className="text-sm rounded border border-subtle bg-layer-1 p-3">
          Active destination: {active ? `${active.bucket} (${active.region})` : "Legacy environment storage"}
        </div>
        <div className="flex flex-wrap gap-2">
          <Button loading={busy === "save"} onClick={save}>
            {t("save")}
          </Button>
          <Button variant="secondary" disabled={!draft} loading={busy === "probe"} onClick={probe}>
            {t("attachment.test_connection")}
          </Button>
          <Button
            variant="secondary"
            disabled={draft?.status !== "VERIFIED"}
            loading={busy === "activate"}
            onClick={activate}
          >
            {t("attachment.activate_storage")}
          </Button>
          <Button variant="secondary" disabled={!active} loading={busy === "rollback"} onClick={rollback}>
            {t("attachment.use_legacy_storage")}
          </Button>
        </div>
      </div>
    </PageWrapper>
  );
}

function Field({ id, label, error, children }: { id: string; label: string; error?: string; children: ReactNode }) {
  return (
    <label htmlFor={id} className="text-sm flex flex-col gap-1">
      <span className="text-secondary">{label}</span>
      {children}
      {error && (
        <span id={`${id}-error`} role="alert" className="text-xs text-danger-primary">
          {error}
        </span>
      )}
    </label>
  );
}

export const meta = () => [{ title: "Object Storage - God Mode" }];
