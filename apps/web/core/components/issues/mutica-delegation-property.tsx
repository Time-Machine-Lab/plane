/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useRef, useState } from "react";
import useSWR from "swr";
import { AlertCircle, Bot, CheckCircle2, Clock3, RefreshCw, Repeat2, X } from "lucide-react";
import { useTranslation } from "@plane/i18n";
import { Button } from "@plane/propel/button";
import { IconButton } from "@plane/propel/icon-button";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import type { TMuticaDelegationStatus } from "@plane/types";
import { useIssueDetail } from "@/hooks/store/use-issue-detail";
import { IntegrationService } from "@/services/integrations";

const integrationService = new IntegrationService();
const MUTICA_DELEGATION_POLL_INTERVAL_MS = 5_000;
const MUTICA_DELEGATION_POLL_TIMEOUT_MS = 2 * 60 * 1_000;

type PollWindow = {
  delegationId: string;
  startedAt: number;
};

type Props = {
  workspaceSlug: string;
  projectId: string;
  issueId: string;
  disabled: boolean;
};

const STATUS_KEYS = {
  dispatching: "mutica.delegation.status.dispatching",
  handed_off: "mutica.delegation.status.handed_off",
  failed: "mutica.delegation.status.failed",
  superseded: "mutica.delegation.status.superseded",
} as const satisfies Record<TMuticaDelegationStatus, string>;

const StatusIcon = ({ status }: { status: TMuticaDelegationStatus }) => {
  if (status === "handed_off") return <CheckCircle2 className="size-3.5 text-success-primary" />;
  if (status === "failed") return <AlertCircle className="size-3.5 text-danger-primary" />;
  return <Clock3 className="size-3.5 text-secondary" />;
};

export function MuticaDelegationProperty({ workspaceSlug, projectId, issueId, disabled }: Props) {
  const { t } = useTranslation();
  const { activity } = useIssueDetail();
  const key = `mutica-delegation-${issueId}`;
  const pollWindowRef = useRef<PollWindow | null>(null);
  const refreshedTerminalActivityId = useRef<string | null>(null);
  const { data, isLoading, mutate } = useSWR(
    key,
    () => integrationService.getMuticaDelegation(workspaceSlug, projectId, issueId),
    {
      refreshInterval: (latestData) => {
        const current = latestData?.current;
        if (current?.status !== "dispatching") return 0;

        if (pollWindowRef.current?.delegationId !== current.id) {
          pollWindowRef.current = { delegationId: current.id, startedAt: Date.now() };
        }

        const elapsed = Date.now() - pollWindowRef.current.startedAt;
        return elapsed < MUTICA_DELEGATION_POLL_TIMEOUT_MS ? MUTICA_DELEGATION_POLL_INTERVAL_MS : 0;
      },
      onSuccess: (latestData) => {
        const current = latestData?.current;
        if (!current) {
          pollWindowRef.current = null;
          return;
        }
        if (current.status === "dispatching") {
          if (pollWindowRef.current?.delegationId !== current.id) {
            pollWindowRef.current = { delegationId: current.id, startedAt: Date.now() };
          }
          refreshedTerminalActivityId.current = null;
          return;
        }

        pollWindowRef.current = null;
        if (refreshedTerminalActivityId.current === current.id) return;

        refreshedTerminalActivityId.current = current.id;
        void activity.fetchActivities(workspaceSlug, projectId, issueId, "mutate");
      },
    }
  );
  const [action, setAction] = useState<"delegate" | "retry" | "reassign" | "clear" | null>(null);

  const refresh = async () => {
    await Promise.all([mutate(), activity.fetchActivities(workspaceSlug, projectId, issueId, "mutate")]);
  };

  const run = async (nextAction: "delegate" | "retry" | "reassign" | "clear") => {
    setAction(nextAction);
    try {
      if (nextAction === "retry") await integrationService.retryMuticaDelegation(workspaceSlug, projectId, issueId);
      else if (nextAction === "clear")
        await integrationService.clearMuticaDelegation(workspaceSlug, projectId, issueId);
      else await integrationService.delegateIssueToMutica(workspaceSlug, projectId, issueId);
      await refresh();
    } catch (requestError) {
      setToast({
        type: TOAST_TYPE.ERROR,
        title: t("error"),
        message: (requestError as { error?: string })?.error ?? t("mutica.delegation.action_failed"),
      });
    } finally {
      setAction(null);
    }
  };

  if (isLoading) return <span className="px-2 text-body-xs-regular text-placeholder">{t("loading")}</span>;
  if (!data?.available && !data?.current) return <span className="px-2 text-body-xs-regular text-placeholder">-</span>;

  if (!data.current)
    return (
      <Button
        variant="secondary"
        size="sm"
        onClick={() => run("delegate")}
        loading={action === "delegate"}
        disabled={disabled || !data.available}
        prependIcon={<Bot />}
      >
        {t("mutica.delegation.delegate")}
      </Button>
    );

  return (
    <div className="flex min-w-0 grow items-center gap-2 px-2">
      <StatusIcon status={data.current.status} />
      <div className="min-w-0 grow">
        <p className="truncate text-body-xs-regular">{data.current.agent.display_name}</p>
        <p className="truncate text-caption-sm-regular text-secondary">{t(STATUS_KEYS[data.current.status])}</p>
      </div>
      {!disabled && data.available && data.current.status === "failed" && (
        <IconButton
          variant="ghost"
          size="sm"
          onClick={() => run("retry")}
          loading={action === "retry"}
          aria-label={t("mutica.delegation.retry")}
          icon={RefreshCw}
        />
      )}
      {!disabled && data.available && (
        <IconButton
          variant="ghost"
          size="sm"
          onClick={() => run("reassign")}
          loading={action === "reassign"}
          aria-label={t("mutica.delegation.reassign")}
          icon={Repeat2}
        />
      )}
      {!disabled && (
        <IconButton
          variant="ghost"
          size="sm"
          onClick={() => run("clear")}
          loading={action === "clear"}
          aria-label={t("mutica.delegation.clear")}
          icon={X}
        />
      )}
    </div>
  );
}
