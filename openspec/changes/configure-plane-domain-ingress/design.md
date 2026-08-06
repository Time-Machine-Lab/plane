## Context

Production currently uses the upstream community Compose file plus `deployments/production/docker-compose.override.yml`. The bundled Plane Caddy proxy publishes container ports 80 and 443 directly on the host, and the release workflow passes `http://SERVER_IP` to `deploy.sh`. The first production deployment has completed successfully and uses stable external volumes under the `plane-production` Compose project.

The required topology is a public HTTPS origin at `plane.tmlab.top`, with a host-managed Nginx instance sharing ports 80/443 across domains and Plane isolated behind `127.0.0.1:6767`. DNS already resolves the hostname to the production server.

## Goals / Non-Goals

**Goals:**

- Serve Plane at `https://plane.tmlab.top` with a valid automatically renewed certificate.
- Make host Nginx the only public listener for Plane on ports 80/443.
- Bind the Plane proxy only to `127.0.0.1:6767`.
- Preserve HTTP routing, uploads, API behavior, authentication cookies, and realtime WebSocket traffic.
- Keep all existing database and storage volumes unchanged and recoverable during cutover.
- Make future release deployments validate the internal upstream and public HTTPS origin.

**Non-Goals:**

- Replacing the bundled Plane Caddy router between the public ingress and application services.
- Exposing port 6767 through the cloud firewall or public network interface.
- Changing application APIs, authentication rules, database schema, or image naming.
- Installing or reconfiguring Nginx during every application release.

## Decisions

### Host Nginx terminates public TLS

Nginx SHALL listen on host ports 80 and 443 for `plane.tmlab.top`, redirect HTTP to HTTPS, and proxy HTTPS traffic to `http://127.0.0.1:6767`. The configuration will forward `Host`, `X-Real-IP`, `X-Forwarded-For`, and `X-Forwarded-Proto`, use HTTP/1.1, and preserve WebSocket upgrade headers.

This keeps ingress ownership outside the Plane application stack and allows the host to serve additional domains. Running a second ingress container was rejected because certificate persistence and host port coordination would add another Compose lifecycle to the application deployment. Allowing the bundled Caddy proxy to retain 80/443 was rejected because it prevents Nginx from becoming the shared host ingress.

Nginx and the ACME client are one-time host infrastructure and will be configured directly during the migration, not from the normal release workflow. The canonical virtual-host configuration remains in `deployments/production` for auditability and repeatability.

### Plane uses a loopback-only upstream

The production Compose override SHALL replace the base proxy port list with one binding from host `127.0.0.1:6767` to container port 80. It SHALL not publish container port 443. A Compose override tag will be used to replace rather than append to the upstream port sequence; server preflight must verify the installed Compose version supports that merge behavior before cutover.

The bundled Caddy proxy remains configured with `SITE_ADDRESS=:80`, so it performs application routing over plain HTTP inside the trusted host boundary and does not request its own public certificate.

### Public origin and bind address are separate contracts

The release workflow SHALL pass `https://plane.tmlab.top` as the public origin. `deploy.sh` SHALL update both newly created and existing production environment files with:

- `APP_DOMAIN=plane.tmlab.top`
- `WEB_URL=https://plane.tmlab.top`
- `CORS_ALLOWED_ORIGINS=https://plane.tmlab.top`
- `SITE_ADDRESS=:80`
- `LISTEN_HTTP_PORT=6767`
- `MINIO_ENDPOINT_SSL=1`

Application secrets, database credentials, message-broker credentials, and object-storage credentials SHALL not be regenerated or overwritten. No public package, API, data, or event contract changes.

### Configuration rollback accompanies image rollback

The existing deployment backup occurs before changing release coordinates or public-origin settings. The backup includes `.env`, PostgreSQL, uploads, Redis, RabbitMQ, and proxy data. On deployment failure, rollback SHALL restore the pre-deployment `.env` as well as the previous image version before restarting services. Database migrations remain forward-only; the existing database backup is the recovery boundary if a migration itself is not backward compatible.

During the one-time ingress cutover, the current Nginx configuration and Plane environment will be backed up. If Nginx, ACME issuance, or external HTTPS validation fails, Nginx will be stopped and the prior Plane port configuration restored.

### Health checks cover both boundaries

The deployment script SHALL check the Plane proxy locally through `http://127.0.0.1:6767` with the production Host header and verify the API health response inside the API container. The release workflow SHALL separately request `https://plane.tmlab.top` with certificate validation enabled. Migration acceptance will also cover `/god-mode/`, `/api/`, upload routing, and the `/live/` WebSocket upgrade path.

## Module Boundaries And Contracts

- `.github/workflows/release-deploy.yml` supplies immutable release coordinates and the public origin, transfers deployment assets, and verifies the public HTTPS boundary. It does not own Nginx installation.
- `deployments/production/docker-compose.override.yml` owns image coordinates, persistent external-volume names, and the host binding of the bundled Plane proxy.
- `deployments/production/deploy.sh` owns server `.env` migration, backup, Compose lifecycle, local health, and rollback.
- `deployments/production/nginx/plane.tmlab.top.conf` owns the host virtual-host contract from ports 80/443 to loopback port 6767.
- Nginx depends only on the stable loopback HTTP endpoint. Plane services do not depend on Nginx starting successfully and can be validated locally before public cutover.

## Standards Compliance

- `docs/spec/README.md`: The affected paths select the deployment, Compose, proxy, and CI standards only; no application-module guide is required.
- `docs/spec/general-development.md`: Changes remain in the production extension layer, preserve upstream files where possible, validate external inputs, avoid secrets in source control, and document rollout and rollback.
- `docs/spec/testing-quality.md`: Acceptance includes YAML and workflow linting, shell syntax checks, merged Compose parsing, live container startup, internal health, public HTTPS, API, admin route, upload route, and realtime smoke evidence.
- `docs/spec/module-structure.md`: New assets remain under `deployments/production`, and workflow changes remain under `.github/workflows`.

## Risks / Trade-offs

- **Nginx cannot start while Plane owns 80/443** -> Stage packages and configuration first, then perform an ordered cutover with a rollback command ready.
- **Compose sequence merging could append port 6767 instead of replacing 80/443** -> Require a Compose version supporting explicit sequence override and inspect `docker compose config` before recreating the proxy.
- **Certificate issuance can fail because of firewall or DNS propagation** -> Verify DNS and public port 80 before cutover; retain the prior direct ingress until prerequisites pass.
- **Incorrect forwarded scheme can break secure cookies or redirects** -> Set `X-Forwarded-Proto=https` and validate sign-in and `/god-mode/` over the public origin.
- **WebSocket headers can be lost at the new proxy boundary** -> Include upgrade headers and run a realtime connection smoke test.
- **Port 6767 could become publicly reachable** -> Bind it explicitly to `127.0.0.1` and verify external connection attempts fail.
- **A failed migration may leave forward database changes** -> Preserve the existing pre-deployment database backup; automatic rollback restores images and configuration but does not reverse migrations.

## Migration Plan

1. Inspect the host OS, Compose version, existing listeners, Nginx state, firewall, current Plane containers, public DNS, and current `.env` without mutation.
2. Back up the current Plane data and environment, and back up any existing Nginx configuration.
3. Install Nginx and the platform-appropriate ACME client if absent; stage and syntax-check the virtual host without taking port ownership.
4. Upload the revised production Compose override and deployment script.
5. Reconfigure and recreate the Plane proxy on `127.0.0.1:6767`; confirm the merged Compose config contains no host 80/443 publication and pass local HTTP/API checks.
6. Start Nginx on port 80, obtain the certificate for `plane.tmlab.top`, enable HTTPS on 443, and reload Nginx.
7. Verify HTTP redirect, valid HTTPS, workspace UI, `/god-mode/`, API health, upload routing, and realtime connectivity.
8. Leave ports 80/443 open for Nginx and keep 6767 closed publicly.

Rollback: stop Nginx, restore its previous configuration, restore the backed-up Plane `.env` and prior Compose port behavior, recreate the Plane proxy on its previous ports, and run the local and external health checks. Persistent volumes are never deleted.

## Local And Production Test Environment

- Local static environment: Windows workspace with Bash, PyYAML, and actionlint; Docker Compose parsing is performed on the production Linux host if Docker is unavailable locally.
- Production fixtures: the existing Plane release and external volumes; no synthetic production records are created.
- Evidence: command output for `bash -n`, actionlint, YAML parsing, `docker compose config`, `ss`, `nginx -t`, certificate inspection, HTTP status/redirects, API health JSON, and container state.

## Open Questions

None. The public endpoint is `https://plane.tmlab.top`, Nginx owns 80/443, and Plane is loopback-bound on port 6767.
