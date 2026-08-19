## ADDED Requirements

### Requirement: Plane workflow trigger

The base Skill SHALL activate for requests to inspect or operate a configured Plane workspace and SHALL prefer the Plane MCP tools over browser automation or ad hoc HTTP construction.

#### Scenario: User asks for Plane work items

- **WHEN** a user asks Codex to read or change Plane work items
- **THEN** the Skill loads the configured Plane profile and uses the Plane MCP tool catalog

### Requirement: Connection status before work

The base Skill SHALL verify `plane_status` for the configured workspace before starting a Plane workflow when connection state is not already established in the task.

#### Scenario: Status succeeds

- **WHEN** `plane_status` confirms the configured user and workspace
- **THEN** the Skill continues with the requested Plane tools

#### Scenario: Status fails

- **WHEN** `plane_status` returns a connection, authentication, or workspace error
- **THEN** the Skill stops Plane mutations and routes the user to the doctor or setup workflow

### Requirement: Minimal core guidance

The base Skill SHALL contain only connection handling, safe tool-selection guidance, credential rules, and extension routing required for reliable Plane MCP use.

#### Scenario: Core Skill is inspected

- **WHEN** the installed base Skill is reviewed
- **THEN** it does not contain organization-specific work-item lifecycle, approval, deployment, or project rules

### Requirement: Credential-contained behavior

The base Skill SHALL accept an explicitly supplied API token for first-release connection setup but MUST NOT repeat it in responses or place it in command arguments, Plane comments, generated documentation, non-secret profiles, or repository files.

#### Scenario: A tool requires authentication

- **WHEN** the Skill invokes an authenticated Plane MCP tool after setup
- **THEN** authentication is supplied by the user-level MCP connection rather than a model-generated tool argument

### Requirement: Independent extension layers

The base Skill SHALL direct organization-specific practices to a separately maintained team Skill and project-specific rules to the nearest applicable `AGENTS.md`.

#### Scenario: Team adds a work-item lifecycle

- **WHEN** a team wants to define assignment, progress, acceptance, or closure practices
- **THEN** those practices are added outside the vendor-owned Plane core Skill

#### Scenario: Core Skill is updated

- **WHEN** a newer base Plane Skill version is installed
- **THEN** the update does not overwrite a separate team Skill or project `AGENTS.md`
