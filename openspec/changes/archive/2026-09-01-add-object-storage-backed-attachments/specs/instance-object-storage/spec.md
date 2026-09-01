## ADDED Requirements

### Requirement: Configure object storage in God Mode

The system SHALL allow an instance administrator to create and review a private object-storage configuration through a compact provider preset without exposing stored secret values or requiring provider-internal signing choices.

#### Scenario: Open object-storage settings

- **WHEN** an authenticated instance administrator opens the God Mode object-storage page
- **THEN** the system displays the current active profile, legacy-storage status, provider, region, bucket, masked credential state, latest connection result, and configured per-file limit without returning the secret access key

#### Scenario: Save an Aliyun OSS draft profile

- **WHEN** an instance administrator submits a valid AccessKey ID, AccessKey Secret, Bucket, Region, and upload limit using the Aliyun OSS preset
- **THEN** the system stores the secret encrypted, creates or updates a non-active draft profile, and leaves the current upload target unchanged

#### Scenario: Derive Aliyun OSS protocol settings

- **WHEN** the administrator saves an Aliyun OSS profile without expanding advanced settings
- **THEN** the system derives the public Endpoint from Region and applies the provider's supported virtual-hosted addressing, V4 signing, short signed-access lifetimes, and internal object prefix without exposing those values as routine form choices

#### Scenario: Override the derived endpoint

- **WHEN** an administrator supplies a syntactically valid Endpoint in advanced settings
- **THEN** the draft uses that Endpoint while retaining the Aliyun OSS preset's non-configurable signing and addressing safety rules

#### Scenario: Reject invalid configuration input

- **WHEN** an administrator submits a malformed advanced Endpoint, missing Region or Bucket, missing credentials, unsupported scheme, or invalid upload limit
- **THEN** the system rejects the configuration with field-specific errors and does not change the active profile

#### Scenario: Deny non-administrator access

- **WHEN** a non-instance-administrator requests object-storage configuration or mutation
- **THEN** the system denies the request without disclosing profile or credential data

### Requirement: Verify a storage profile before activation

The system MUST verify the real browser-to-storage upload path and server read/delete path for the current profile version before it can become active.

#### Scenario: Complete a successful connection probe

- **WHEN** an administrator starts a probe and the browser can upload the generated bounded object using the returned signed request
- **THEN** the API verifies, reads, and deletes that object, records a sanitized successful result, and enables activation for that unchanged profile version

#### Scenario: Fail a browser CORS probe

- **WHEN** the browser cannot upload the probe because the bucket origin policy or signed request is rejected
- **THEN** the system records a sanitized failed result, keeps the existing active profile, identifies the browser upload stage as the failure, and shows the Plane origin plus minimal OSS CORS methods and headers to configure without adding CORS fields to the storage form

#### Scenario: Fail server verification or cleanup

- **WHEN** the API cannot verify, read, or delete the uploaded probe
- **THEN** the system does not mark the profile verified or activate it and exposes an actionable sanitized failure without credentials or signed URLs

#### Scenario: Change a verified draft

- **WHEN** an administrator changes a location, signing, or credential field after a successful probe
- **THEN** the previous verification becomes stale and the changed profile cannot be activated until it passes a new probe

### Requirement: Activate versioned storage without stranding existing assets

The system SHALL bind each new uploaded asset to the storage profile that accepted it and SHALL continue resolving existing assets through their original profile.

#### Scenario: Activate a verified profile

- **WHEN** an administrator activates a currently verified draft profile
- **THEN** the system atomically makes it the write target for subsequent uploads while retaining the previous and legacy profiles for their existing assets

#### Scenario: Upload after activation

- **WHEN** an authorized user begins an upload after activation
- **THEN** the pending asset records the active profile and all upload, finalize, preview, download, copy, restore, and delete operations resolve that recorded profile

#### Scenario: Read a legacy asset after activation

- **WHEN** an authorized user accesses an existing asset that has no explicit profile reference
- **THEN** the system resolves it through the legacy environment-backed storage configuration

#### Scenario: Change an active storage location

- **WHEN** an administrator changes the endpoint, region, bucket, or addressing identity of an active profile
- **THEN** the system creates and verifies a new profile version instead of rewriting the location used by existing assets

#### Scenario: Prevent removal of a referenced profile

- **WHEN** an administrator attempts to remove a profile still referenced by assets
- **THEN** the system refuses the destructive operation and reports that the profile must remain available or its assets must be migrated first

### Requirement: Apply an administrator-configured upload limit

The system SHALL enforce an instance per-file limit that defaults to 100 MB for new installations or instances without an explicit value.

#### Scenario: Upload within the configured limit

- **WHEN** an authorized user requests an upload for a non-empty allowed file whose declared size is at or below the configured limit
- **THEN** the API can issue a signed upload whose content-length condition does not exceed that accepted size

#### Scenario: Reject an oversized upload before signing

- **WHEN** a file's declared size exceeds the configured instance limit
- **THEN** the API rejects the upload intent without creating an available asset or issuing a signed upload and returns the effective limit

#### Scenario: Change the instance limit

- **WHEN** an administrator saves a valid new per-file limit in God Mode
- **THEN** subsequent Page and work-item upload intents use the new value while existing assets remain accessible

### Requirement: Finalize direct uploads authoritatively

The system MUST keep user file bytes out of the Plane application server upload path and MUST verify the stored object before exposing it as uploaded.

#### Scenario: Complete a direct upload

- **WHEN** the browser successfully uploads a file to the signed object-store target and requests finalization
- **THEN** the API verifies the bound object exists with the expected size and accepted metadata before marking the asset available

#### Scenario: Detect a missing or mismatched object

- **WHEN** finalization cannot find the object or its stored size does not match the accepted upload intent
- **THEN** the API keeps the asset unavailable, returns a stable verification error, and does not issue preview or download access

#### Scenario: Clean up an abandoned upload

- **WHEN** a pending upload remains incomplete beyond the configured cleanup window
- **THEN** the system removes its pending metadata and any identifiable partial object without affecting completed assets

### Requirement: Protect private asset delivery

The system MUST authorize every preview and download against the asset's bound entity and SHALL deliver private objects only through short-lived signed access.

#### Scenario: Authorized preview request

- **WHEN** a user with access to the bound Page or work item requests a supported preview
- **THEN** the system resolves the asset's profile and returns a short-lived allowlisted preview contract appropriate to that type without exposing credentials or a reusable object location

#### Scenario: Authorized download request

- **WHEN** a user with access to the bound Page or work item requests a download
- **THEN** the system returns short-lived attachment access with the sanitized original filename

#### Scenario: Unauthorized asset request

- **WHEN** a user lacks access to the private Page or work item bound to an asset
- **THEN** the system denies preview and download without revealing the object key, storage profile, or a signed URL

#### Scenario: Request an interactive HTML preview

- **WHEN** an authorized user explicitly starts preview for an allowed bounded HTML attachment
- **THEN** the system supplies authorized content to the isolated HTML renderer without making the OSS signed URL or Plane application origin available to the attachment document

#### Scenario: Request other script-capable content inline

- **WHEN** an authorized user requests inline access for non-HTML script-capable or non-previewable content
- **THEN** the system refuses inline rendering and offers only attachment disposition where the type is otherwise allowed

### Requirement: Roll back storage activation without losing profiled assets

The system SHALL allow database-profile writes to be disabled while preserving read access to assets already bound to those profiles.

#### Scenario: Return writes to legacy storage

- **WHEN** an administrator or rollout control disables the active database profile
- **THEN** subsequent uploads use the legacy environment-backed target and explicitly profiled assets continue to resolve through their recorded profiles

#### Scenario: Active profile becomes unhealthy

- **WHEN** the active profile cannot issue or complete new uploads
- **THEN** the system exposes storage-unavailable errors and profile health without silently writing an asset to a different profile after its upload intent was created
