/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import { Bot } from "lucide-react";
import { useTranslation } from "@plane/i18n";
import { useIssueDetail } from "@/hooks/store/use-issue-detail";
import { IssueActivityBlockComponent } from "./helpers/activity-block";

type Props = { activityId: string; ends: "top" | "bottom" | undefined };

const ACTIVITY_KEYS = {
  delegated: "mutica.activity.delegated",
  reassigned: "mutica.activity.reassigned",
  retried: "mutica.activity.retried",
  cleared: "mutica.activity.cleared",
  handed_off: "mutica.activity.handed_off",
  failed: "mutica.activity.failed",
} as const;

export const IssueMuticaActivity = observer(function IssueMuticaActivity({ activityId, ends }: Props) {
  const { t } = useTranslation();
  const {
    activity: { getActivityById },
  } = useIssueDetail();
  const activity = getActivityById(activityId);
  if (!activity) return null;
  const supportedVerb = activity.verb in ACTIVITY_KEYS ? (activity.verb as keyof typeof ACTIVITY_KEYS) : "delegated";
  return (
    <IssueActivityBlockComponent
      icon={<Bot className="size-3.5 text-secondary" aria-hidden="true" />}
      activityId={activityId}
      ends={ends}
    >
      {t(ACTIVITY_KEYS[supportedVerb], { assistant: activity.new_value ?? t("mutica.assistant") })}
    </IssueActivityBlockComponent>
  );
});
