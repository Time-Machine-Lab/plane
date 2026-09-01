/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { AxiosRequestConfig } from "axios";
import axios from "axios";
// services
import { APIService } from "@/services/api.service";

export class FileUploadService extends APIService {
  private cancelSource: any;

  constructor() {
    super("");
  }

  async uploadFile(
    url: string,
    data: FormData,
    uploadProgressHandler?: AxiosRequestConfig["onUploadProgress"]
  ): Promise<void> {
    this.cancelSource = axios.CancelToken.source();
    return this.post(url, data, {
      headers: {
        "Content-Type": "multipart/form-data",
      },
      cancelToken: this.cancelSource.token,
      withCredentials: false,
      onUploadProgress: uploadProgressHandler,
    })
      .then((response) => response?.data)
      .catch((error) => {
        if (axios.isCancel(error)) {
          console.log(error.message);
        } else {
          throw error?.response?.data;
        }
      });
  }

  async uploadFileWithRetry(
    url: string,
    dataFactory: () => FormData,
    uploadProgressHandler?: AxiosRequestConfig["onUploadProgress"],
    retries = 1
  ): Promise<void> {
    let lastError: unknown;
    for (let attempt = 0; attempt <= retries; attempt += 1) {
      try {
        // Retries are intentionally sequential because each attempt reuses the same upload intent.
        // oxlint-disable-next-line no-await-in-loop
        await this.uploadFile(url, dataFactory(), uploadProgressHandler);
        return;
      } catch (error) {
        lastError = error;
      }
    }
    throw lastError;
  }

  cancelUpload() {
    this.cancelSource.cancel("Upload canceled");
  }
}
