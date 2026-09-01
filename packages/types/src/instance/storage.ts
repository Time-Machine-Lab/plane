export type TStorageProfileStatus = "DRAFT" | "VERIFIED" | "ACTIVE" | "RETIRED";

export type TStorageProfile = {
  id: string;
  provider: "ALIYUN_OSS" | "S3";
  bucket: string;
  region: string;
  endpoint: string;
  effective_endpoint: string;
  access_key_id: string;
  secret_configured: boolean;
  status: TStorageProfileStatus;
  file_size_limit: number;
  verified_at: string | null;
  verification_error: string;
  last_probe_at: string | null;
};

export type TStorageProfilePayload = Pick<
  TStorageProfile,
  "bucket" | "region" | "endpoint" | "access_key_id" | "file_size_limit"
> & {
  provider?: TStorageProfile["provider"];
  access_key_secret?: string;
};

export type TStorageProbe = {
  profile_id: string;
  probe_object_key: string;
  upload_data: { url: string; fields: Record<string, string> };
};
