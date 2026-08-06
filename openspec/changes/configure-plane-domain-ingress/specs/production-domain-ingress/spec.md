## ADDED Requirements

### Requirement: Public Plane HTTPS origin
The production system SHALL serve Plane at `https://plane.tmlab.top` using a valid publicly trusted TLS certificate and SHALL redirect plaintext HTTP requests for that hostname to HTTPS.

#### Scenario: Workspace loads through HTTPS
- **WHEN** a client requests `https://plane.tmlab.top/`
- **THEN** the system returns a successful Plane workspace response with a valid certificate for `plane.tmlab.top`

#### Scenario: HTTP is redirected
- **WHEN** a client requests `http://plane.tmlab.top/`
- **THEN** the system redirects the client to the equivalent `https://plane.tmlab.top/` URL

### Requirement: Plane upstream isolation
The production system SHALL publish the Plane proxy only on host loopback port 6767 and SHALL reserve host ports 80 and 443 for Nginx.

#### Scenario: Local upstream is reachable
- **WHEN** the production host requests the Plane proxy through `127.0.0.1:6767`
- **THEN** the Plane proxy returns a successful response for the production Host header

#### Scenario: Port 6767 is not public
- **WHEN** a remote client attempts to connect directly to the server's public address on port 6767
- **THEN** the Plane upstream is not reachable

#### Scenario: Plane does not publish standard ports
- **WHEN** the merged production Compose configuration is inspected
- **THEN** the Plane proxy has no host publication for ports 80 or 443

### Requirement: Reverse proxy compatibility
Nginx SHALL preserve the host, client address, original HTTPS scheme, request bodies, and WebSocket upgrade semantics required by Plane routes.

#### Scenario: Admin and API routes remain available
- **WHEN** a client requests `/god-mode/` and the public API health route through `https://plane.tmlab.top`
- **THEN** Nginx routes both requests to Plane and returns their expected responses

#### Scenario: Realtime connection upgrades
- **WHEN** a client initiates a valid WebSocket upgrade on the Plane realtime route
- **THEN** Nginx forwards the upgrade and the realtime service accepts the connection path

#### Scenario: Upload route is proxied securely
- **WHEN** an authenticated client uploads or retrieves an object through the Plane public origin
- **THEN** the request remains on HTTPS and is routed to the configured object-storage service

### Requirement: Production origin configuration
Every production application service SHALL use `https://plane.tmlab.top` as its external origin without changing existing secrets or persistent data.

#### Scenario: Existing environment is migrated
- **WHEN** deployment runs against the existing production environment
- **THEN** public URL, domain, CORS, internal listener, and secure object-storage settings are updated while database, broker, object-storage, and application secrets retain their previous values

#### Scenario: Future release retains ingress settings
- **WHEN** a later immutable application version is deployed
- **THEN** the release uses the same public HTTPS origin and loopback port without reinstalling or replacing Nginx

### Requirement: Safe ingress cutover
The deployment process SHALL create a recoverable backup before modifying the production origin or port binding and SHALL preserve all external Docker volumes throughout deployment and rollback.

#### Scenario: Successful cutover
- **WHEN** backup, local Plane health, Nginx validation, certificate issuance, and public HTTPS verification all succeed
- **THEN** the new ingress remains active and the backup location is recorded

#### Scenario: Plane reconfiguration fails
- **WHEN** the Plane proxy cannot start or pass its local health check on port 6767
- **THEN** deployment stops, restores the previous environment and image coordinates, and leaves persistent volumes untouched

#### Scenario: Public ingress validation fails
- **WHEN** Nginx or public HTTPS validation fails during the one-time cutover
- **THEN** operators can stop Nginx and restore the previous direct Plane ingress using the recorded environment and configuration backups
