/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// All the app integrations that are available
export interface IAppIntegration {
  author: string;
  avatar_url: string | null;
  created_at: string;
  created_by: string | null;
  description: any;
  id: string;
  metadata: any;
  network: number;
  provider: string;
  redirect_url: string;
  title: string;
  updated_at: string;
  updated_by: string | null;
  verified: boolean;
  webhook_secret: string;
  webhook_url: string;
}

export interface IWorkspaceIntegration {
  actor: string;
  api_token: string;
  config: any;
  created_at: string;
  created_by: string;
  id: string;
  integration: string;
  integration_detail: IAppIntegration;
  metadata: any;
  updated_at: string;
  updated_by: string;
  workspace: string;
}

export type TMuticaDelegationStatus = "dispatching" | "handed_off" | "failed" | "superseded";

export interface IMuticaAgent {
  id: string;
  external_id: string;
  display_name: string;
  avatar_url: string | null;
  is_enabled: boolean;
}

export interface IMuticaConnection {
  id: string;
  endpoint_url: string;
  is_enabled: boolean;
  verified_at: string | null;
  disabled_at: string | null;
  assistant: IMuticaAgent | null;
}

export interface IMuticaConnectionInput {
  endpoint_url: string;
  signing_secret: string;
  agent_external_id: string;
  agent_display_name: string;
  agent_avatar_url?: string | null;
}

export interface IMuticaProvisioningResponse extends IMuticaConnection {
  service_token: string;
}

export interface IMuticaDelegation {
  id: string;
  work_item_id: string;
  status: TMuticaDelegationStatus;
  failure_category: string | null;
  agent: IMuticaAgent;
  initiated_by: string | null;
  created_at: string;
  handed_off_at: string | null;
  superseded_at: string | null;
}

export interface IMuticaDelegationContext {
  available: boolean;
  assistant: IMuticaAgent | null;
  current: IMuticaDelegation | null;
  history: IMuticaDelegation[];
}

export interface IMuticaDelegationEvent {
  type: "plane.work_item.delegated";
  schema_version: 1;
  event_id: string;
  delivery_id: string;
  delegation_id: string;
  delegated_at: string;
  plane_origin: string;
  workspace_slug: string;
  project_id: string;
  work_item_id: string;
  work_item_url: string;
  agent_external_id: string;
}

// slack integration
export interface ISlackIntegration {
  id: string;
  created_at: string;
  updated_at: string;
  access_token: string;
  scopes: string;
  bot_user_id: string;
  webhook_url: string;
  data: ISlackIntegrationData;
  team_id: string;
  team_name: string;
  created_by: string;
  updated_by: string;
  project: string;
  workspace: string;
  workspace_integration: string;
}

export interface ISlackIntegrationData {
  ok: boolean;
  team: {
    id: string;
    name: string;
  };
  scope: string;
  app_id: string;
  enterprise: any;
  token_type: string;
  authed_user: string;
  bot_user_id: string;
  access_token: string;
  incoming_webhook: {
    url: string;
    channel: string;
    channel_id: string;
    configuration_url: string;
  };
  is_enterprise_install: boolean;
}
