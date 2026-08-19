## ADDED Requirements

### Requirement: Installable Plane Skill

The Plane integration SHALL be distributed as a Codex Skill containing its guidance, references, and explicit setup and doctor scripts, without requiring a separate Plane npm installer.

#### Scenario: Skill is installed from the supported source

- **WHEN** a user installs the Plane Skill through the documented Codex Skill installation mechanism
- **THEN** Codex can discover the Skill and its setup and doctor scripts without modifying Plane MCP configuration automatically

### Requirement: Environment preflight

The setup workflow SHALL detect the supported Codex environment and current Plane MCP configuration before attempting changes.

#### Scenario: Codex is available and Plane MCP is absent

- **WHEN** setup runs in a supported Codex environment with no `plane` MCP entry
- **THEN** setup proceeds to collect and validate the Plane connection inputs

#### Scenario: Required Codex capability is unavailable

- **WHEN** setup cannot find the required Codex MCP configuration capability
- **THEN** setup stops with a specific prerequisite error and does not alter configuration

### Requirement: Secure connection input

Setup MUST accept a Plane workspace URL and API token without placing the token in Skill content, prompts, repository files, command history, or non-secret profile data.

#### Scenario: Token is entered during setup

- **WHEN** setup needs a Plane API token
- **THEN** it obtains the token from an approved environment value or masked terminal input and does not echo it

#### Scenario: User attempts chat-based token entry

- **WHEN** the Skill determines that a token is missing
- **THEN** it directs the user to the masked setup workflow rather than requesting the token in conversation

### Requirement: Connection validation before configuration

Setup SHALL validate the Plane origin, token identity, and workspace access before registering the remote MCP server.

#### Scenario: Valid workspace URL and token

- **WHEN** the workspace URL resolves to an accessible Plane origin and the token user can access the parsed workspace
- **THEN** setup registers the `<plane-origin>/mcp` endpoint and stores only the non-secret origin and workspace profile

#### Scenario: Invalid token

- **WHEN** Plane rejects the supplied token
- **THEN** setup reports an authentication failure and leaves Codex MCP configuration unchanged

#### Scenario: Workspace is inaccessible

- **WHEN** the token is valid but the parsed workspace is missing or inaccessible to that user
- **THEN** setup reports the workspace failure and leaves Codex MCP configuration unchanged

### Requirement: Idempotent MCP registration

Setup SHALL add or update only the Plane MCP entry and SHALL preserve unrelated Codex configuration.

#### Scenario: Matching Plane MCP entry already exists

- **WHEN** setup finds an existing `plane` MCP entry with the expected endpoint and credential reference
- **THEN** it validates and reuses the entry without creating a duplicate

#### Scenario: Different Plane MCP entry exists

- **WHEN** setup finds a conflicting `plane` MCP entry
- **THEN** it presents a clear replacement decision and makes no replacement without confirmation

### Requirement: Actionable restart state

Setup SHALL report whether the configured credential and MCP entry are usable by the current Codex process or require a restart or new task.

#### Scenario: Environment change is not visible to the current process

- **WHEN** setup persists a credential reference that the running Codex process has not inherited
- **THEN** setup reports that Codex must be restarted or a new task opened before MCP use

### Requirement: Connection diagnosis

The Skill SHALL provide a doctor workflow that distinguishes local configuration, server reachability, authentication, workspace authorization, and tool availability failures without revealing credentials.

#### Scenario: Healthy connection

- **WHEN** doctor checks a correctly configured and reachable Plane MCP connection
- **THEN** it reports the Plane origin, authenticated user, workspace, MCP availability, and tool availability without printing the token

#### Scenario: MCP server is unreachable

- **WHEN** the configured `/mcp` endpoint cannot be reached
- **THEN** doctor reports a network, DNS, TLS, or server-availability category and preserves the existing configuration
