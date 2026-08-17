## ADDED Requirements

### Requirement: Configure an OpenAI-compatible connection

The system SHALL allow an authenticated instance administrator to configure an API key, an optional OpenAI-compatible Base URL, an editable model list, one default model, and an optional reasoning effort from God Mode.

#### Scenario: Save a custom compatible endpoint

- **GIVEN** an instance administrator is viewing the God Mode AI settings
- **WHEN** the administrator submits a valid HTTPS Base URL, API key, model list, default model, and reasoning effort
- **THEN** the system persists the complete configuration and confirms that the settings were saved
- **AND** reloading the page shows the persisted non-secret values and indicates that an API key is configured without revealing the key

#### Scenario: Use an arbitrary newer model identifier

- **GIVEN** an OpenAI-compatible endpoint exposes a model identifier that is not built into Plane, including a GPT-5.6 Sol model identifier
- **WHEN** an instance administrator adds that identifier to the model list and selects it as the default
- **THEN** the system accepts and persists the model without requiring a Plane code change or built-in allowlist entry

#### Scenario: Edit the model catalog and default

- **GIVEN** the AI configuration contains multiple distinct model identifiers
- **WHEN** an instance administrator adds, renames, reorders, or removes model identifiers and selects a valid default
- **THEN** the saved model catalog and selected default match the submitted configuration

#### Scenario: Select or customize reasoning effort

- **GIVEN** the configured endpoint supports a reasoning effort value
- **WHEN** an instance administrator selects a common preset or enters a valid endpoint-specific effort value
- **THEN** the system persists that value for subsequent AI requests

### Requirement: Validate AI configuration atomically

The system MUST validate the merged AI configuration before changing any persisted AI setting and MUST preserve the last valid configuration when validation fails.

#### Scenario: Reject an invalid Base URL

- **GIVEN** a valid AI configuration is already stored
- **WHEN** an instance administrator submits a Base URL with a missing host or a scheme other than HTTP or HTTPS
- **THEN** the system rejects the update with an actionable field error
- **AND** none of the submitted AI settings replace the stored configuration

#### Scenario: Reject an invalid model catalog

- **GIVEN** an instance administrator is editing AI settings
- **WHEN** the submitted model list is empty, contains blank or duplicate identifiers, or does not contain the selected default model
- **THEN** the system rejects the update and identifies the model configuration error
- **AND** no partial AI configuration is persisted

#### Scenario: Reject an invalid reasoning effort

- **GIVEN** a valid AI configuration is already stored
- **WHEN** an instance administrator submits an empty custom value, control characters, or a value beyond the supported configuration length
- **THEN** the system rejects the update with an actionable field error
- **AND** the previously stored reasoning effort remains unchanged

#### Scenario: Preserve an unchanged secret

- **GIVEN** the settings page indicates that an API key is already configured without returning its value
- **WHEN** an instance administrator changes other AI fields without entering a replacement key
- **THEN** the stored API key remains unchanged

### Requirement: Enforce configuration authorization and secrecy

The system MUST apply the existing instance-administrator permission boundary to AI configuration and MUST NOT disclose the stored API key through configuration responses, completion responses, errors, or logs.

#### Scenario: Reject a non-administrator update

- **GIVEN** an authenticated user is not an instance administrator
- **WHEN** the user attempts to read or update instance AI configuration
- **THEN** the system rejects the request using the existing authorization response
- **AND** no configuration value is disclosed or changed

#### Scenario: Redact the API key

- **GIVEN** an API key has been stored for the AI connection
- **WHEN** an authorized administrator reads the AI configuration or an AI request fails
- **THEN** the response indicates whether a key is configured without containing the plaintext key
- **AND** application logs and error messages do not contain the key

### Requirement: Apply configured values to AI requests

The system SHALL use the configured Base URL, default model, and optional reasoning effort for existing workspace and project AI completion requests without changing their successful response shape.

#### Scenario: Route a request to a custom endpoint

- **GIVEN** a valid custom Base URL, API key, model catalog, and default model are configured
- **WHEN** an authorized workspace or project member invokes an existing AI completion action
- **THEN** the outbound request targets the configured OpenAI-compatible endpoint and uses the configured default model
- **AND** the existing completion endpoint returns its established success response shape

#### Scenario: Send configured reasoning effort

- **GIVEN** a non-empty reasoning effort is configured
- **WHEN** Plane sends an AI completion request
- **THEN** the outbound request includes that reasoning effort value in the OpenAI-compatible request

#### Scenario: Omit unconfigured reasoning effort

- **GIVEN** reasoning effort is not configured
- **WHEN** Plane sends an AI completion request
- **THEN** the outbound request omits the reasoning effort field

#### Scenario: Keep configuration after an upstream failure

- **GIVEN** a valid AI configuration is stored and the configured endpoint is temporarily unavailable or returns an error
- **WHEN** a member invokes an AI completion action
- **THEN** Plane returns its established sanitized failure response
- **AND** the stored AI configuration remains unchanged for a later retry

### Requirement: Preserve existing OpenAI configuration compatibility

The system SHALL continue to support installations that only have the existing `LLM_API_KEY` and `LLM_MODEL` values.

#### Scenario: Fall back to the official endpoint

- **GIVEN** no custom Base URL is configured
- **WHEN** Plane sends an AI completion request
- **THEN** Plane uses the OpenAI SDK's official default endpoint

#### Scenario: Derive a catalog from a legacy model

- **GIVEN** an existing installation has an `LLM_MODEL` value but no configured model list
- **WHEN** the configuration is loaded or used
- **THEN** the system treats the existing model as the sole model-list entry and default model
- **AND** no database schema migration or administrator action is required

### Requirement: Protect outbound endpoint access

The system MUST validate custom endpoint targets using Plane's outbound URL-security policy before persistence and before use, block unsafe targets by default, and permit trusted private targets only when an operator explicitly allowlists them.

#### Scenario: Accept a safe public endpoint

- **GIVEN** a custom HTTP or HTTPS endpoint resolves only to permitted public addresses
- **WHEN** an instance administrator saves the endpoint
- **THEN** the system accepts the endpoint when all other AI settings are valid

#### Scenario: Block an unsafe target

- **GIVEN** a custom endpoint resolves to loopback, link-local, cloud metadata, or another blocked address and is not operator-allowlisted
- **WHEN** an instance administrator saves or Plane attempts to use the endpoint
- **THEN** the system rejects the target without sending credentials or request content to it
- **AND** the response does not disclose internal network details

#### Scenario: Permit an explicitly trusted private gateway

- **GIVEN** an operator has explicitly allowlisted a private gateway host or network through deployment configuration
- **WHEN** an instance administrator saves and uses an otherwise valid endpoint on that target
- **THEN** the system permits the endpoint while continuing to block other private targets
