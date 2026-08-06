## Why

The production Plane instance currently publishes its bundled proxy directly on host ports 80 and 443 and advertises the server IP as its public URL. The instance must instead be available at `https://plane.tmlab.top`, with host Nginx owning the standard web ports and Plane reachable only through a loopback-bound upstream on port 6767.

## What Changes

- Change the production Compose overlay so the Plane proxy publishes only `127.0.0.1:6767` and no longer publishes host ports 80 or 443.
- Configure the existing production environment to advertise `https://plane.tmlab.top` for application URLs, CORS, generated links, and secure object-storage URLs.
- Add a host Nginx virtual host that terminates TLS for `plane.tmlab.top`, redirects HTTP to HTTPS, forwards requests and WebSocket upgrades to `127.0.0.1:6767`, and preserves forwarding headers.
- Update release deployment and preflight automation to pass the public URL and internal bind port explicitly and verify both the loopback upstream and public HTTPS route.
- Provide a controlled rollout that backs up the current environment and Plane data before changing ingress, with rollback to the previous direct-port configuration if the cutover fails.

## Capabilities

### New Capabilities

- `production-domain-ingress`: Production Plane ingress, TLS termination, loopback port binding, health verification, and safe rollout/rollback behavior.

### Modified Capabilities

None.

## Impact

- **Affected modules**: `.github/workflows`, `deployments/production`, the production host Nginx installation, and the deployed Plane environment file under `$HOME/plane`.
- **Applicable standards**: `docs/spec/README.md`, `docs/spec/general-development.md`, `docs/spec/testing-quality.md`, and `docs/spec/module-structure.md`.
- **Runtime contracts**: The public origin changes from the server IP over HTTP to `https://plane.tmlab.top`; the Plane proxy host binding changes from ports 80/443 to loopback port 6767; Nginx becomes the only public ingress and TLS terminator.
- **API and authorization**: No API schema, endpoint, authentication, or authorization behavior changes. Forwarded host and scheme headers must preserve existing session and CSRF behavior.
- **Realtime protocol**: No protocol change; Nginx must preserve WebSocket upgrade behavior for `/live/`.
- **Data migration**: No database schema or persistent-volume migration. Existing external Docker volumes remain unchanged and are backed up before cutover.
- **Dependencies**: The production host gains Nginx and an ACME client such as Certbot. No application package dependency changes.
- **AGPL**: No licensing or source-availability change.
- **Non-goals**: Replacing Plane's bundled Caddy routing, exposing port 6767 publicly, changing Docker image names, modifying application features, or moving persistent data.
- **Acceptance**: Parse the merged Compose configuration, validate workflow and shell syntax, confirm the Plane proxy listens only on `127.0.0.1:6767`, verify HTTP redirects to HTTPS, load the workspace and `/god-mode/`, call the API health route, and verify the realtime WebSocket route through `https://plane.tmlab.top`.
