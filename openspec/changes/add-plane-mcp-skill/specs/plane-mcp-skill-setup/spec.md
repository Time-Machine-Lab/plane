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

### Requirement: Agent-managed connection input

Setup SHALL let a user provide a Plane workspace URL and dedicated API token to the Agent, and the Agent SHALL complete setup without requiring the user to run a command or configure the operating system.

#### Scenario: User provides connection values

- **WHEN** a user provides a workspace URL and API token in conversation
- **THEN** the Agent invokes the appropriate host adapter, does not repeat the token, and completes validation and MCP registration on the user's behalf

#### Scenario: A connection value is missing

- **WHEN** the workspace URL or API token is unavailable
- **THEN** the Skill asks only for the missing value and does not direct the user to a terminal or operating-system-specific launcher

### Requirement: First-release credential persistence

Setup SHALL persist an explicitly supplied token only in the current Agent client's user-level MCP authentication configuration and SHALL disclose that the token is conversation-visible and locally stored.

#### Scenario: Codex connection is configured

- **WHEN** the Agent validates a workspace URL and token in Codex
- **THEN** setup stores the token as the `plane` MCP entry's static Bearer authorization header, stores no token in the repository or non-secret Plane profile, and recommends a dedicated revocable token

#### Scenario: Setup output is produced

- **WHEN** setup, doctor, or an error reports connection state
- **THEN** the output contains no token value or complete authentication header

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

- **WHEN** setup finds a conflicting `plane` MCP entry after the user explicitly supplied the current workspace URL and token
- **THEN** the Agent replaces only that `plane` entry using the explicit replacement option and preserves all unrelated client configuration

### Requirement: Actionable tool readiness

Setup SHALL report whether the configured MCP entry is usable in the current task or requires a new task to refresh the tool catalog, without requiring a setup command or application relaunch.

#### Scenario: Environment change is not visible to the current process

- **WHEN** the running task cannot refresh its MCP catalog after setup
- **THEN** setup reports that the user should open a new task and confirms that no terminal command or environment configuration is needed

### Requirement: Connection diagnosis

The Skill SHALL provide a doctor workflow that distinguishes local configuration, server reachability, authentication, workspace authorization, and tool availability failures without revealing credentials.

#### Scenario: Healthy connection

- **WHEN** doctor checks a correctly configured and reachable Plane MCP connection
- **THEN** it reports the Plane origin, authenticated user, workspace, MCP availability, and tool availability without printing the token

#### Scenario: MCP server is unreachable

- **WHEN** the configured `/mcp` endpoint cannot be reached
- **THEN** doctor reports a network, DNS, TLS, or server-availability category and preserves the existing configuration
