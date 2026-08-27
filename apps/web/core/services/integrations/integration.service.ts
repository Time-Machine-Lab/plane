/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { API_BASE_URL } from "@plane/constants";
import type {
  IAppIntegration,
  IImporterService,
  IWorkspaceIntegration,
  IExportServiceResponse,
  IMuticaConnection,
  IMuticaConnectionInput,
  IMuticaDelegation,
  IMuticaDelegationContext,
  IMuticaProvisioningResponse,
} from "@plane/types";
import { APIService } from "@/services/api.service";
// types
// helper

export class IntegrationService extends APIService {
  constructor() {
    super(API_BASE_URL);
  }

  async getAppIntegrationsList(): Promise<IAppIntegration[]> {
    return this.get(`/api/integrations/`)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async getWorkspaceIntegrationsList(workspaceSlug: string): Promise<IWorkspaceIntegration[]> {
    return this.get(`/api/workspaces/${workspaceSlug}/workspace-integrations/`)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async deleteWorkspaceIntegration(workspaceSlug: string, integrationId: string): Promise<any> {
    return this.delete(`/api/workspaces/${workspaceSlug}/workspace-integrations/${integrationId}/provider/`)
      .then((res) => res?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async getImporterServicesList(workspaceSlug: string): Promise<IImporterService[]> {
    return this.get(`/api/workspaces/${workspaceSlug}/importers/`)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }
  async getExportsServicesList(
    workspaceSlug: string,
    cursor: string,
    per_page: number
  ): Promise<IExportServiceResponse> {
    return this.get(`/api/workspaces/${workspaceSlug}/export-issues`, {
      params: {
        per_page,
        cursor,
      },
    })
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async deleteImporterService(workspaceSlug: string, service: string, importerId: string): Promise<any> {
    return this.delete(`/api/workspaces/${workspaceSlug}/importers/${service}/${importerId}/`)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async getMuticaConnection(workspaceSlug: string): Promise<IMuticaConnection | null> {
    return this.get(`/api/workspaces/${workspaceSlug}/mutica/connection/`).then((response) => response?.data);
  }

  async connectMutica(workspaceSlug: string, data: IMuticaConnectionInput): Promise<IMuticaProvisioningResponse> {
    return this.post(`/api/workspaces/${workspaceSlug}/mutica/connection/`, data).then((response) => response?.data);
  }

  async verifyMuticaConnection(workspaceSlug: string): Promise<IMuticaConnection> {
    return this.post(`/api/workspaces/${workspaceSlug}/mutica/connection/verify/`).then((response) => response?.data);
  }

  async rotateMuticaServiceToken(workspaceSlug: string): Promise<{ service_token: string }> {
    return this.post(`/api/workspaces/${workspaceSlug}/mutica/connection/service-token/rotate/`).then(
      (response) => response?.data
    );
  }

  async disconnectMutica(workspaceSlug: string): Promise<void> {
    return this.delete(`/api/workspaces/${workspaceSlug}/mutica/connection/`).then(() => undefined);
  }

  async getMuticaDelegation(
    workspaceSlug: string,
    projectId: string,
    issueId: string
  ): Promise<IMuticaDelegationContext> {
    return this.get(`/api/workspaces/${workspaceSlug}/projects/${projectId}/issues/${issueId}/mutica-delegation/`).then(
      (response) => response?.data
    );
  }

  async getMuticaAssistantAvailability(
    workspaceSlug: string
  ): Promise<Pick<IMuticaDelegationContext, "available" | "assistant">> {
    return this.get(`/api/workspaces/${workspaceSlug}/mutica/assistant/`).then((response) => response?.data);
  }

  async delegateIssueToMutica(workspaceSlug: string, projectId: string, issueId: string): Promise<IMuticaDelegation> {
    return this.post(
      `/api/workspaces/${workspaceSlug}/projects/${projectId}/issues/${issueId}/mutica-delegation/`
    ).then((response) => response?.data);
  }

  async retryMuticaDelegation(workspaceSlug: string, projectId: string, issueId: string): Promise<IMuticaDelegation> {
    return this.post(
      `/api/workspaces/${workspaceSlug}/projects/${projectId}/issues/${issueId}/mutica-delegation/retry/`
    ).then((response) => response?.data);
  }

  async clearMuticaDelegation(workspaceSlug: string, projectId: string, issueId: string): Promise<void> {
    return this.delete(
      `/api/workspaces/${workspaceSlug}/projects/${projectId}/issues/${issueId}/mutica-delegation/`
    ).then(() => undefined);
  }
}
