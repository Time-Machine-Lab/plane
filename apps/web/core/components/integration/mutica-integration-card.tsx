/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { useParams } from "next/navigation";
import useSWR from "swr";
import { Bot, CheckCircle2, Copy, RefreshCw, Unplug } from "lucide-react";
import { useTranslation } from "@plane/i18n";
import { Button } from "@plane/propel/button";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import type { IMuticaConnectionInput } from "@plane/types";
import { Input, Loader } from "@plane/ui";
import { copyTextToClipboard } from "@plane/utils";
import { IntegrationService } from "@/services/integrations";

const integrationService = new IntegrationService();

const initialValues: IMuticaConnectionInput = {
  endpoint_url: "",
  signing_secret: "",
  agent_external_id: "",
  agent_display_name: "Mutica Assistant",
  agent_avatar_url: null,
};

export function MuticaIntegrationCard() {
  const { t } = useTranslation();
  const { workspaceSlug } = useParams();
  const slug = workspaceSlug?.toString();
  const key = slug ? `mutica-connection-${slug}` : null;
  const {
    data: connection,
    error,
    isLoading,
    mutate,
  } = useSWR(key, () => (slug ? integrationService.getMuticaConnection(slug) : null));
  const [values, setValues] = useState<IMuticaConnectionInput>(initialValues);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isVerifying, setIsVerifying] = useState(false);
  const [isDisconnecting, setIsDisconnecting] = useState(false);
  const [serviceToken, setServiceToken] = useState<string | null>(null);

  const updateValue = (field: keyof IMuticaConnectionInput, value: string) =>
    setValues((current) => ({ ...current, [field]: value }));

  const connect = async () => {
    if (!slug) return;
    setIsSubmitting(true);
    try {
      const response = await integrationService.connectMutica(slug, values);
      const { service_token: provisionedToken, ...safeConnection } = response;
      setServiceToken(provisionedToken);
      setValues(initialValues);
      await mutate(safeConnection, false);
      setToast({ type: TOAST_TYPE.SUCCESS, title: t("success"), message: t("mutica.connection.connected") });
    } catch (requestError) {
      setToast({
        type: TOAST_TYPE.ERROR,
        title: t("error"),
        message: (requestError as { error?: string })?.error ?? t("mutica.connection.failed"),
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const verify = async () => {
    if (!slug) return;
    setIsVerifying(true);
    try {
      const response = await integrationService.verifyMuticaConnection(slug);
      await mutate(response, false);
      setToast({ type: TOAST_TYPE.SUCCESS, title: t("success"), message: t("mutica.connection.verified") });
    } catch {
      setToast({ type: TOAST_TYPE.ERROR, title: t("error"), message: t("mutica.connection.failed") });
    } finally {
      setIsVerifying(false);
    }
  };

  const rotate = async () => {
    if (!slug) return;
    setIsSubmitting(true);
    try {
      const response = await integrationService.rotateMuticaServiceToken(slug);
      setServiceToken(response.service_token);
    } catch {
      setToast({ type: TOAST_TYPE.ERROR, title: t("error"), message: t("mutica.token.rotation_failed") });
    } finally {
      setIsSubmitting(false);
    }
  };

  const disconnect = async () => {
    if (!slug) return;
    setIsDisconnecting(true);
    try {
      await integrationService.disconnectMutica(slug);
      setServiceToken(null);
      await mutate();
    } catch {
      setToast({ type: TOAST_TYPE.ERROR, title: t("error"), message: t("mutica.connection.failed") });
    } finally {
      setIsDisconnecting(false);
    }
  };

  if (isLoading)
    return (
      <div className="border-b border-subtle bg-surface-1 px-4 py-6">
        <Loader.Item height="40px" width="100%" />
      </div>
    );

  return (
    <div className="border-b border-subtle bg-surface-1 px-4 py-6">
      <div className="flex items-start justify-between gap-4">
        <div className="flex min-w-0 items-start gap-4">
          <div className="grid size-10 shrink-0 place-items-center rounded-sm border border-subtle bg-layer-1">
            <Bot className="size-5 text-secondary" />
          </div>
          <div className="min-w-0">
            <h3 className="flex items-center gap-2 text-body-xs-medium">
              Mutica
              {connection?.is_enabled && <CheckCircle2 className="size-3.5 text-success-primary" />}
            </h3>
            <p className="text-body-xs-regular text-secondary">
              {connection?.is_enabled
                ? t("mutica.connection.connected_description")
                : t("mutica.connection.description")}
            </p>
          </div>
        </div>
      </div>

      {error && <p className="mt-4 text-body-xs-regular text-danger-primary">{t("mutica.connection.load_failed")}</p>}

      {!connection?.is_enabled && (
        <div className="mt-5 grid max-w-2xl gap-3 sm:grid-cols-2">
          <Input
            type="url"
            value={values.endpoint_url}
            onChange={(event) => updateValue("endpoint_url", event.target.value)}
            placeholder={t("mutica.connection.endpoint")}
            aria-label={t("mutica.connection.endpoint")}
          />
          <Input
            type="password"
            value={values.signing_secret}
            onChange={(event) => updateValue("signing_secret", event.target.value)}
            placeholder={t("mutica.connection.signing_secret")}
            aria-label={t("mutica.connection.signing_secret")}
          />
          <Input
            value={values.agent_external_id}
            onChange={(event) => updateValue("agent_external_id", event.target.value)}
            placeholder={t("mutica.connection.assistant_id")}
            aria-label={t("mutica.connection.assistant_id")}
          />
          <Input
            value={values.agent_display_name}
            onChange={(event) => updateValue("agent_display_name", event.target.value)}
            placeholder={t("mutica.connection.assistant_name")}
            aria-label={t("mutica.connection.assistant_name")}
          />
          <div className="sm:col-span-2">
            <Button
              onClick={connect}
              loading={isSubmitting}
              disabled={
                !values.endpoint_url ||
                !values.signing_secret ||
                !values.agent_external_id ||
                !values.agent_display_name
              }
            >
              {t("mutica.connection.connect")}
            </Button>
          </div>
        </div>
      )}

      {connection?.is_enabled && (
        <div className="mt-5 flex flex-wrap items-center gap-2">
          <span className="mr-2 text-body-xs-regular text-secondary">
            {connection.assistant?.display_name ?? t("mutica.assistant")}
          </span>
          <Button
            variant="secondary"
            onClick={verify}
            loading={isVerifying}
            disabled={isSubmitting || isDisconnecting}
            prependIcon={<RefreshCw />}
          >
            {t("mutica.connection.verify")}
          </Button>
          <Button
            variant="secondary"
            onClick={rotate}
            loading={isSubmitting}
            disabled={isVerifying || isDisconnecting}
            prependIcon={<RefreshCw />}
          >
            {t("mutica.token.rotate")}
          </Button>
          <Button
            variant="error-fill"
            onClick={disconnect}
            loading={isDisconnecting}
            disabled={isSubmitting || isVerifying}
            prependIcon={<Unplug />}
          >
            {t("mutica.connection.disconnect")}
          </Button>
        </div>
      )}

      {serviceToken && (
        <div className="mt-5 max-w-2xl border-t border-subtle pt-4">
          <p className="text-body-xs-medium">{t("mutica.token.one_time_title")}</p>
          <p className="mt-1 text-body-xs-regular text-secondary">{t("mutica.token.one_time_description")}</p>
          <div className="mt-3 flex items-center gap-2">
            <code className="min-w-0 grow truncate rounded-sm border border-subtle bg-layer-1 px-3 py-2 text-body-xs-regular">
              {serviceToken}
            </code>
            <Button
              variant="secondary"
              onClick={() => copyTextToClipboard(serviceToken)}
              aria-label={t("mutica.token.copy")}
              prependIcon={<Copy />}
            >
              {t("mutica.token.copy")}
            </Button>
            <Button variant="secondary" onClick={() => setServiceToken(null)}>
              {t("close")}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
