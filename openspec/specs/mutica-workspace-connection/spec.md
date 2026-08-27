## Purpose

Define how a Plane workspace securely connects to an existing Mutica environment and manages its shared assistant, service identity, credentials, and lifecycle.

## Requirements

### Requirement: Connect an existing Mutica environment

Plane SHALL let a workspace administrator connect an already deployed Mutica environment by configuring and verifying its delivery endpoint, signing secret, and one default assistant without deploying or installing Mutica software.

#### Scenario: Administrator connects Mutica

- **WHEN** a workspace administrator submits valid Mutica connection values and the non-destructive verification succeeds
- **THEN** Plane enables one workspace-wide Mutica connection and its default assistant for that workspace

#### Scenario: Connection verification fails

- **WHEN** the endpoint is invalid, unsafe, unreachable, or rejects the verification request
- **THEN** Plane does not enable delegation and returns an actionable error without exposing credentials or internal network details

#### Scenario: Non-administrator attempts connection

- **WHEN** a workspace member without workspace administration permission attempts to connect or reconfigure Mutica
- **THEN** Plane rejects the operation and leaves the connection unchanged

### Requirement: Workspace service identity

Plane SHALL provision Mutica with a dedicated non-human service identity and revocable API token bound to the connected workspace instead of using a member's personal identity or an instance-wide credential.

#### Scenario: Service credential is created

- **WHEN** an administrator successfully connects Mutica
- **THEN** Plane creates or activates one Mutica service identity with access to the connected workspace and returns the new raw service token only through the credential provisioning response

#### Scenario: Service token accesses its workspace

- **WHEN** Mutica uses the active service token through Plane MCP for a project in the connected workspace
- **THEN** Plane executes the operation as the Mutica service identity and applies the existing project authorization rules

#### Scenario: Service token targets another workspace

- **WHEN** the workspace-bound service token is used for any other workspace
- **THEN** Plane rejects the request without returning cross-workspace data even if the service user is accidentally associated with that workspace

#### Scenario: Personal token inventory is viewed

- **WHEN** any user lists or manages personal API tokens
- **THEN** the Mutica service token is not returned or modifiable through the personal-token interface

### Requirement: Shared default assistant

Plane SHALL expose the connected default Mutica assistant as a workspace resource shared by authorized members rather than requiring per-member assistant or token configuration.

#### Scenario: Member opens an eligible work item

- **WHEN** Mutica is connected and the member can edit the work item
- **THEN** Plane offers the enabled default Mutica assistant without asking the member for Mutica or Plane credentials

#### Scenario: Mutica is not connected

- **WHEN** a workspace has no active Mutica connection
- **THEN** Plane does not offer a selectable Mutica assistant on its work items

### Requirement: Secret lifecycle

Plane MUST keep Mutica delivery secrets and Plane service tokens out of ordinary API responses, logs, activities, and user-visible errors, and SHALL support service-token rotation and connection removal.

#### Scenario: Administrator rotates the service token

- **WHEN** a workspace administrator rotates the Mutica Plane credential
- **THEN** Plane issues a replacement token once, revokes the previous token, and preserves the connection and delegation history

#### Scenario: Administrator disconnects Mutica

- **WHEN** a workspace administrator disconnects Mutica
- **THEN** Plane disables the assistant, revokes its active service token, stops new delegation delivery, and preserves existing work items and delegation history

#### Scenario: Connection request is logged

- **WHEN** Plane records connection, verification, delivery, or authentication diagnostics
- **THEN** no raw token, signing secret, authorization header, or sensitive response body is persisted
