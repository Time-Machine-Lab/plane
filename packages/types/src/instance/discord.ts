/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

export type TDiscordEventKey =
  | "work_item.created"
  | "work_item.assignee_added"
  | "work_item.completed"
  | "work_item.daily_reminder";

export interface IDiscordMemberMapping {
  plane_user_id: string;
  discord_user_id: string;
}

export interface IDiscordWorkspaceOption {
  id: string;
  name: string;
  slug: string;
}

export interface IDiscordWorkspaceMember {
  id: string;
  display_name: string;
}

export interface IDiscordConfiguration {
  enabled: boolean;
  workspace_id: string | null;
  webhook_configured: boolean;
  enabled_events: TDiscordEventKey[];
  member_mappings: IDiscordMemberMapping[];
  workspaces: IDiscordWorkspaceOption[];
}

export interface IDiscordConfigurationUpdate {
  enabled: boolean;
  workspace_id: string | null;
  webhook_url?: string;
  enabled_events: TDiscordEventKey[];
  member_mappings: IDiscordMemberMapping[];
}

export interface IDiscordTestMessageResponse {
  accepted: boolean;
  error?: string;
  category?: string;
}
