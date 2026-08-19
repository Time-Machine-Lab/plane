/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useMemo, useState } from "react";
import { Trash2 } from "lucide-react";
import { Button } from "@plane/propel/button";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import { useTranslation } from "@plane/i18n";
import type {
  IDiscordConfiguration,
  IDiscordConfigurationUpdate,
  IDiscordMemberMapping,
  TDiscordEventKey,
} from "@plane/types";
import { Checkbox, CustomSelect, Input, ToggleSwitch } from "@plane/ui";
// hooks
import { useInstance } from "@/hooks/store";

type Props = {
  config: IDiscordConfiguration;
};

const EVENT_OPTIONS: { key: TDiscordEventKey; label: string; description: string }[] = [
  {
    key: "work_item.created",
    label: "Work item created",
    description: "Send a message when a work item is created.",
  },
  {
    key: "work_item.assignee_added",
    label: "Assignee added",
    description: "Send a message and mention newly assigned mapped members.",
  },
  {
    key: "work_item.completed",
    label: "Work item completed",
    description: "Send a message when a work item moves into a completed state.",
  },
];

const DISCORD_USER_ID_PATTERN = /^\d{17,20}$/;

export function DiscordConfigForm({ config }: Props) {
  const { t } = useTranslation();
  const { discordMembers, fetchDiscordWorkspaceMembers, sendDiscordTestMessage, updateDiscordConfiguration } =
    useInstance();
  const [enabled, setEnabled] = useState(config.enabled);
  const [workspaceId, setWorkspaceId] = useState<string | null>(config.workspace_id);
  const [webhookUrl, setWebhookUrl] = useState("");
  const [enabledEvents, setEnabledEvents] = useState<TDiscordEventKey[]>(config.enabled_events);
  const enabledEventKeys = useMemo(() => new Set(enabledEvents), [enabledEvents]);
  const [memberMappings, setMemberMappings] = useState<IDiscordMemberMapping[]>(config.member_mappings);
  const [error, setError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [isTesting, setIsTesting] = useState(false);
  const [isLoadingMembers, setIsLoadingMembers] = useState(false);

  useEffect(() => {
    if (!workspaceId) return;
    setIsLoadingMembers(true);
    fetchDiscordWorkspaceMembers(workspaceId)
      .catch(() => setError("Unable to load members for the selected workspace."))
      .finally(() => setIsLoadingMembers(false));
  }, [fetchDiscordWorkspaceMembers, workspaceId]);

  const selectedWorkspace = config.workspaces.find((workspace) => workspace.id === workspaceId);
  const mappedPlaneUserIds = useMemo(
    () => new Set(memberMappings.map((mapping) => mapping.plane_user_id)),
    [memberMappings]
  );
  const availableMembers = discordMembers.filter((member) => !mappedPlaneUserIds.has(member.id));
  const memberNames = useMemo(
    () => new Map(discordMembers.map((member) => [member.id, member.display_name])),
    [discordMembers]
  );
  const eventOptions: { key: TDiscordEventKey; label: string; description: string }[] = [
    ...EVENT_OPTIONS,
    {
      key: "work_item.daily_reminder",
      label: t("discord_integration.daily_task_brief.label"),
      description: t("discord_integration.daily_task_brief.description"),
    },
    {
      key: "user.mentioned",
      label: t("discord_integration.user_mentioned.label"),
      description: t("discord_integration.user_mentioned.description"),
    },
    {
      key: "work_item.comment_activity",
      label: t("discord_integration.comment_activity.label"),
      description: t("discord_integration.comment_activity.description"),
    },
  ];

  const handleWorkspaceChange = (nextWorkspaceId: string) => {
    if (nextWorkspaceId === workspaceId) return;
    setWorkspaceId(nextWorkspaceId);
    setMemberMappings([]);
    setError(null);
  };

  const toggleEvent = (eventKey: TDiscordEventKey) => {
    setEnabledEvents((current) =>
      current.includes(eventKey) ? current.filter((key) => key !== eventKey) : [...current, eventKey]
    );
  };

  const addMapping = (planeUserId: string) => {
    if (!planeUserId || mappedPlaneUserIds.has(planeUserId)) return;
    setMemberMappings((current) => [...current, { plane_user_id: planeUserId, discord_user_id: "" }]);
  };

  const updateMapping = (planeUserId: string, discordUserId: string) => {
    setMemberMappings((current) =>
      current.map((mapping) =>
        mapping.plane_user_id === planeUserId ? { ...mapping, discord_user_id: discordUserId.trim() } : mapping
      )
    );
  };

  const validate = () => {
    if (enabled && !workspaceId) return "Select a workspace before enabling Discord notifications.";
    if (enabled && !webhookUrl.trim() && !config.webhook_configured)
      return "Enter a Discord Incoming Webhook URL before enabling the integration.";
    if (webhookUrl.trim() && !webhookUrl.trim().startsWith("https://"))
      return "The Discord Webhook URL must use HTTPS.";
    if (memberMappings.some((mapping) => !DISCORD_USER_ID_PATTERN.test(mapping.discord_user_id)))
      return "Each Discord User ID must contain 17 to 20 digits.";
    if (new Set(memberMappings.map((mapping) => mapping.discord_user_id)).size !== memberMappings.length)
      return "Each Discord User ID can only be mapped once.";
    return null;
  };

  const handleSave = async () => {
    const validationError = validate();
    if (validationError) {
      setError(validationError);
      return;
    }

    const payload: IDiscordConfigurationUpdate = {
      enabled,
      workspace_id: workspaceId,
      enabled_events: enabledEvents,
      member_mappings: memberMappings,
      ...(webhookUrl.trim() ? { webhook_url: webhookUrl.trim() } : {}),
    };
    setError(null);
    setIsSaving(true);
    try {
      await updateDiscordConfiguration(payload);
      setWebhookUrl("");
      setToast({
        type: TOAST_TYPE.SUCCESS,
        title: "Discord settings saved",
        message: "New matching work item events will use this configuration.",
      });
    } catch (requestError) {
      const message =
        requestError && typeof requestError === "object" && "error" in requestError
          ? String(requestError.error)
          : "Unable to save Discord settings.";
      setError(message);
    } finally {
      setIsSaving(false);
    }
  };

  const handleTest = async () => {
    if (!webhookUrl.trim() && !config.webhook_configured) {
      setError("Enter or save a Discord Incoming Webhook URL before sending a test message.");
      return;
    }
    setError(null);
    setIsTesting(true);
    try {
      await sendDiscordTestMessage(webhookUrl.trim() || undefined);
      setToast({
        type: TOAST_TYPE.SUCCESS,
        title: "Test message sent",
        message: "Discord accepted the Plane test message.",
      });
    } catch (requestError) {
      const message =
        requestError && typeof requestError === "object" && "error" in requestError
          ? String(requestError.error)
          : "Discord did not accept the test message.";
      setError(message);
      setToast({ type: TOAST_TYPE.ERROR, title: "Test message failed", message });
    } finally {
      setIsTesting(false);
    }
  };

  return (
    <div className="max-w-4xl space-y-8">
      <section className="space-y-5 border-b border-subtle pb-8">
        <div className="flex items-center justify-between gap-6">
          <div>
            <h2 className="text-15 font-medium text-primary">Discord notifications</h2>
            <p className="mt-1 text-13 text-tertiary">Enable event delivery for one Plane workspace.</p>
          </div>
          <ToggleSwitch value={enabled} onChange={() => setEnabled((current) => !current)} size="sm" />
        </div>

        <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
          <div className="flex min-w-0 flex-col gap-1.5">
            <label className="text-13 text-tertiary" htmlFor="discord-workspace">
              Workspace
            </label>
            <CustomSelect
              value={workspaceId ?? ""}
              label={selectedWorkspace?.name ?? "Select a workspace"}
              onChange={handleWorkspaceChange}
              buttonClassName="w-full rounded-md border-subtle"
              input
            >
              {config.workspaces.map((workspace) => (
                <CustomSelect.Option key={workspace.id} value={workspace.id} className="w-full">
                  {workspace.name}
                </CustomSelect.Option>
              ))}
            </CustomSelect>
          </div>

          <div className="flex min-w-0 flex-col gap-1.5">
            <label className="text-13 text-tertiary" htmlFor="discord-webhook-url">
              Discord Incoming Webhook URL
            </label>
            <Input
              id="discord-webhook-url"
              type="password"
              value={webhookUrl}
              onChange={(event) => setWebhookUrl(event.target.value)}
              placeholder={
                config.webhook_configured
                  ? "Webhook configured - enter a replacement"
                  : "https://discord.com/api/webhooks/..."
              }
              autoComplete="new-password"
            />
            <p className="text-11 text-tertiary">
              {config.webhook_configured
                ? "The saved Webhook is hidden. Leave this empty to keep it."
                : "Create an Incoming Webhook in the target Discord channel."}
            </p>
          </div>
        </div>
      </section>

      <section className="space-y-4 border-b border-subtle pb-8">
        <div>
          <h2 className="text-15 font-medium text-primary">Events</h2>
          <p className="mt-1 text-13 text-tertiary">Choose which work item events are sent.</p>
        </div>
        <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
          {eventOptions.map((option) => (
            <div key={option.key} className="flex items-start gap-2">
              <Checkbox
                id={`discord-event-${option.key}`}
                checked={enabledEventKeys.has(option.key)}
                onChange={() => toggleEvent(option.key)}
              />
              <label className="cursor-pointer" htmlFor={`discord-event-${option.key}`}>
                <span className="block text-13 text-primary">{option.label}</span>
                <span className="mt-0.5 block text-11 text-tertiary">{option.description}</span>
              </label>
            </div>
          ))}
        </div>
      </section>

      <section className="space-y-4">
        <div>
          <h2 className="text-15 font-medium text-primary">Member mappings</h2>
          <p className="mt-1 text-13 text-tertiary">
            Map Plane users to Discord User IDs so assignment messages can mention the right people.
          </p>
        </div>

        <div className="max-w-md">
          <CustomSelect
            value=""
            label={isLoadingMembers ? "Loading members..." : "Add a Plane member"}
            onChange={addMapping}
            buttonClassName="w-full rounded-md border-subtle"
            disabled={!workspaceId || isLoadingMembers || availableMembers.length === 0}
            input
          >
            {availableMembers.map((member) => (
              <CustomSelect.Option key={member.id} value={member.id} className="w-full">
                {member.display_name}
              </CustomSelect.Option>
            ))}
          </CustomSelect>
        </div>

        {memberMappings.length > 0 ? (
          <div className="overflow-x-auto border-y border-subtle">
            <div className="grid min-w-[720px] grid-cols-[1fr_1.35fr_1fr_40px] gap-4 border-b border-subtle px-3 py-2 text-11 font-medium text-tertiary">
              <span>Plane member</span>
              <span>Plane User ID</span>
              <span>Discord User ID</span>
              <span className="sr-only">Actions</span>
            </div>
            {memberMappings.map((mapping) => (
              <div
                key={mapping.plane_user_id}
                className="grid min-w-[720px] grid-cols-[1fr_1.35fr_1fr_40px] items-center gap-4 border-b border-subtle px-3 py-3 last:border-b-0"
              >
                <span className="truncate text-13 text-primary">
                  {memberNames.get(mapping.plane_user_id) ?? "Unavailable member"}
                </span>
                <Input value={mapping.plane_user_id} disabled className="font-mono text-11" />
                <Input
                  value={mapping.discord_user_id}
                  onChange={(event) => updateMapping(mapping.plane_user_id, event.target.value)}
                  placeholder="123456789012345678"
                  inputMode="numeric"
                  aria-label={`Discord User ID for ${memberNames.get(mapping.plane_user_id) ?? mapping.plane_user_id}`}
                />
                <button
                  type="button"
                  title="Remove mapping"
                  aria-label={`Remove mapping for ${memberNames.get(mapping.plane_user_id) ?? mapping.plane_user_id}`}
                  className="flex size-8 items-center justify-center text-tertiary hover:text-danger-primary focus-visible:outline-2 focus-visible:outline-offset-2"
                  onClick={() =>
                    setMemberMappings((current) =>
                      current.filter((item) => item.plane_user_id !== mapping.plane_user_id)
                    )
                  }
                >
                  <Trash2 className="size-4" />
                </button>
              </div>
            ))}
          </div>
        ) : (
          <p className="py-3 text-13 text-tertiary">No members are mapped yet.</p>
        )}
      </section>

      {error && (
        <div
          role="alert"
          className="border-danger-primary border-l-2 bg-danger-subtle px-3 py-2 text-13 text-danger-primary"
        >
          {error}
        </div>
      )}

      <div className="flex flex-wrap items-center gap-3 border-t border-subtle pt-5">
        <Button variant="primary" size="lg" onClick={handleSave} loading={isSaving} disabled={isSaving || isTesting}>
          Save changes
        </Button>
        <Button
          variant="secondary"
          size="lg"
          onClick={handleTest}
          loading={isTesting}
          disabled={isSaving || isTesting || (!config.webhook_configured && !webhookUrl.trim())}
        >
          Send test message
        </Button>
      </div>
    </div>
  );
}
