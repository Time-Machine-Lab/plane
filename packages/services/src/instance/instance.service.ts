/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// plane imports
import { API_BASE_URL } from "@plane/constants";
import type {
  IDiscordConfiguration,
  IDiscordConfigurationUpdate,
  IDiscordTestMessageResponse,
  IDiscordWorkspaceMember,
  IFormattedInstanceConfiguration,
  IInstance,
  IInstanceAdmin,
  IInstanceConfiguration,
  IInstanceInfo,
  TPage,
  TStorageProfile,
  TStorageProfilePayload,
  TStorageProbe,
} from "@plane/types";
// api service
import { APIService } from "../api.service";

/**
 * Service class for managing instance-related operations
 * Handles retrieval of instance information and changelog
 * @extends {APIService}
 */
export class InstanceService extends APIService {
  /**
   * Creates an instance of InstanceService
   * Initializes the service with the base API URL
   */
  constructor() {
    super(API_BASE_URL);
  }

  /**
   * Retrieves information about the current instance
   * @returns {Promise<IInstanceInfo>} Promise resolving to instance information
   * @throws {Error} If the API request fails
   * @remarks This method uses the validateStatus: null option to bypass interceptors for unauthorized errors.
   */
  async info(): Promise<IInstanceInfo> {
    return this.get("/api/instances/", { validateStatus: null })
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  /**
   * Fetches the changelog for the current instance
   * @returns {Promise<TPage>} Promise resolving to the changelog page data
   * @throws {Error} If the API request fails
   */
  async changelog(): Promise<TPage> {
    return this.get("/api/instances/changelog/")
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  /**
   * Fetches the list of instance admins
   * @returns {Promise<IInstanceAdmin[]>} Promise resolving to an array of instance admins
   * @throws {Error} If the API request fails
   * @remarks This method uses the validateStatus: null option to bypass interceptors for unauthorized errors.
   */
  async admins(): Promise<IInstanceAdmin[]> {
    return this.get("/api/instances/admins/", { validateStatus: null })
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  /**
   * Updates the instance information
   * @param {Partial<IInstance>} data Data to update the instance with
   * @returns {Promise<IInstance>} Promise resolving to the updated instance information
   * @throws {Error} If the API request fails
   */
  async update(data: Partial<IInstance>): Promise<IInstance> {
    return this.patch("/api/instances/", data)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  /**
   * Fetches the list of instance configurations
   * @returns {Promise<IInstanceConfiguration[]>} Promise resolving to an array of instance configurations
   * @throws {Error} If the API request fails
   */
  async configurations(): Promise<IInstanceConfiguration[]> {
    return this.get("/api/instances/configurations/")
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  /**
   * Updates the instance configurations
   * @param {Partial<IFormattedInstanceConfiguration>} data Data to update the instance configurations with
   * @returns {Promise<IInstanceConfiguration[]>} The updated instance configurations
   * @throws {Error} If the API request fails
   */
  async updateConfigurations(data: Partial<IFormattedInstanceConfiguration>): Promise<IInstanceConfiguration[]> {
    return this.patch("/api/instances/configurations/", data)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async storageProfiles(): Promise<TStorageProfile[]> {
    return this.get("/api/instances/storage-profiles/")
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async createStorageProfile(data: TStorageProfilePayload): Promise<TStorageProfile> {
    return this.post("/api/instances/storage-profiles/", data)
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async updateStorageProfile(id: string, data: Partial<TStorageProfilePayload>): Promise<TStorageProfile> {
    return this.patch(`/api/instances/storage-profiles/${id}/`, data)
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async startStorageProbe(id: string): Promise<TStorageProbe> {
    return this.post(`/api/instances/storage-profiles/${id}/probe/`)
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async completeStorageProbe(id: string): Promise<TStorageProfile> {
    return this.post(`/api/instances/storage-profiles/${id}/probe/complete/`)
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async activateStorageProfile(id: string): Promise<TStorageProfile> {
    return this.post(`/api/instances/storage-profiles/${id}/activate/`)
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async rollbackStorageProfile(): Promise<{ status: "legacy" }> {
    return this.post("/api/instances/storage-profiles/rollback/")
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  /**
   * Sends a test email to the specified receiver to test SMTP configuration
   * @param {string} receiverEmail Email address to send the test email to
   * @returns {Promise<void>} Promise resolving to void
   * @throws {Error} If the API request fails
   */
  async sendTestEmail(receiverEmail: string): Promise<void> {
    return this.post("/api/instances/email-credentials-check/", {
      receiver_email: receiverEmail,
    })
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  /**
   * Disables the email configuration
   * @returns {Promise<void>} Promise resolving to void
   * @throws {Error} If the API request fails
   */
  async disableEmail(): Promise<void> {
    return this.delete("/api/instances/configurations/disable-email-feature/")
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async discordConfiguration(): Promise<IDiscordConfiguration> {
    return this.get("/api/instances/discord-configuration/")
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async updateDiscordConfiguration(data: IDiscordConfigurationUpdate): Promise<IDiscordConfiguration> {
    return this.patch("/api/instances/discord-configuration/", data)
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async discordWorkspaceMembers(workspaceId: string): Promise<IDiscordWorkspaceMember[]> {
    return this.get("/api/instances/discord-configuration/members/", {
      params: { workspace_id: workspaceId },
    })
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async sendDiscordTestMessage(webhookUrl?: string): Promise<IDiscordTestMessageResponse> {
    return this.post("/api/instances/discord-configuration/test/", webhookUrl ? { webhook_url: webhookUrl } : {})
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }
}
