## 1. Release workflow

- [x] 1.1 Configure `.github/workflows/release-deploy.yml` to pass `https://plane.tmlab.top` and port `6767` to the server deployment command.
- [x] 1.2 Verify the public release health check uses HTTPS certificate validation and resolves the configured hostname to `SERVER_IP`.
- [x] 1.3 Validate the workflow YAML with `actionlint .github/workflows/release-deploy.yml .github/workflows/deploy-preflight.yml`.
- [x] 1.4 Verify the release runner accepts only the manually confirmed production ED25519 host-key fingerprint before writing `known_hosts`.

## 2. Production Compose and deployment lifecycle

- [x] 2.1 Replace the upstream proxy port sequence with only `127.0.0.1:6767 -> 80` in `deployments/production/docker-compose.override.yml`, retaining every fixed external volume.
- [x] 2.2 Update `deployments/production/deploy.sh` to validate the bind port and Compose version and atomically synchronize the public origin, CORS, Caddy listener, host port, and secure MinIO setting without replacing secrets.
- [x] 2.3 Restore the backed-up `.env` and previous immutable image coordinates when deployment health fails; leave external volumes and backup archives untouched.
- [x] 2.4 Update `deployments/production/preflight.sh` to require Compose `2.24.4+` and inspect port `6767`.
- [x] 2.5 Run `bash -n deployments/production/deploy.sh deployments/production/preflight.sh` and `shellcheck deployments/production/deploy.sh deployments/production/preflight.sh`.
- [x] 2.6 Parse the merged configuration with `docker compose --env-file <fixture-env> -f deployments/cli/community/docker-compose.yml -f deployments/production/docker-compose.override.yml config` and assert the proxy publishes only `127.0.0.1:6767` while all production external volumes retain their fixed names.
- [x] 2.7 Verify `deploy.sh` retries the public HTTPS origin through `127.0.0.1` with SNI and certificate validation and enters the existing rollback path when retries are exhausted.

## 3. Host Nginx contract and operations documentation

- [x] 3.1 Add `deployments/production/nginx/plane.tmlab.top.conf` with HTTP-to-HTTPS redirect, trusted certificate paths, forwarding headers, body-size handling, and WebSocket upgrades to `127.0.0.1:6767`.
- [x] 3.2 Document the public access URL, ownership of ports 80/443, loopback-only Plane port, persistent volumes, backup contents, and rollback limits in `deployments/production/README.md`.
- [x] 3.3 Validate the installed server configuration with `nginx -t` before reload.
- [x] 3.4 Document that the server operator independently backs up the active Compose override and Nginx configuration and that the release workflow is enabled only after one-time cutover acceptance.

## 4. Production rollout and final acceptance

- [x] 4.1 Record read-only preflight evidence for DNS, Compose version, listeners, current containers, volumes, Nginx state, firewall, and the current Plane environment.
- [x] 4.2 Create the pre-cutover Plane data/environment backup plus independent active Compose override and Nginx configuration backups, record their exact server paths, then apply the loopback Compose binding and Nginx vhost.
- [x] 4.3 Verify `docker compose config`, `docker compose ps`, `ss -ltnp`, and local `curl` evidence that Plane is healthy only on `127.0.0.1:6767` and does not publish host ports 80/443.
- [ ] 4.4 Verify the HTTP redirect, trusted HTTPS certificate, workspace, `/god-mode/`, public API health, upload route, and `/live/` WebSocket upgrade through `plane.tmlab.top`; verify the public server address cannot reach port 6767.
- [ ] 4.5 Re-read `proposal.md` and `specs/production-domain-ingress/spec.md`, map every scenario to evidence below, and accept the change only when all mandatory scenarios pass.

## Local acceptance record

- Environment: Windows workspace for repository checks; production Linux host for Compose, Nginx, network, and runtime checks
- Date/commit: 2026-08-06, working tree based on `d4952a0`

| Requirement/Scenario | Verification | Result | Evidence |
| --- | --- | --- | --- |
| Public Plane HTTPS origin / Workspace loads through HTTPS | `curl --fail --show-error --resolve plane.tmlab.top:443:207.57.124.102 https://plane.tmlab.top/` | pass | Attempt 3 returned HTTP 200 with a trusted certificate valid through 2026-11-04. |
| Public Plane HTTPS origin / HTTP is redirected | `curl --head http://plane.tmlab.top/` | pass | Attempt 3 returned HTTP 301 to HTTPS. |
| Plane upstream isolation / Local upstream is reachable | Host `curl -H 'Host: plane.tmlab.top' http://127.0.0.1:6767/` | pass | Attempt 3 local upstream check succeeded on loopback port 6767. |
| Plane upstream isolation / Port 6767 is not public | Remote TCP/HTTP request to `207.57.124.102:6767` | pass | Attempt 3 direct public connection timed out. |
| Plane upstream isolation / Plane does not publish standard ports | Merged `docker compose config` and host `ss -ltnp` | pass | Attempt 3 showed Plane only on `127.0.0.1:6767`; active Nginx owns host ports 80 and 443. |
| Reverse proxy compatibility / Admin and API routes remain available | HTTPS requests to `/god-mode/` and public API health route | pass | `/god-mode/` returned HTTP 200; `/api/` returned the expected API JSON 404 rather than a proxy error, proving API routing. |
| Reverse proxy compatibility / Realtime connection upgrades | WebSocket client against the production `/live/` route | pass | Attempt 3 returned HTTP 101 Switching Protocols. |
| Reverse proxy compatibility / Upload route is proxied securely | Authenticated upload and retrieval through the public origin | pending | Requires production account and runtime |
| Production origin configuration / Existing environment is migrated | Compare secret hashes and public settings before/after deployment | pass | Attempt 3 synchronized domain, WEB_URL, CORS, listener port, and MINIO TLS settings; all containers remained healthy and persistent volume creation timestamps were unchanged. |
| Production origin configuration / Future release retains ingress settings | Run a later immutable deployment and inspect origin/bind settings | pending | Requires a subsequent release |
| Safe ingress cutover / Successful cutover | Backup manifest, local health, `nginx -t`, certificate, and public smoke output | pass | Attempt 3 succeeded; independent configuration backup is `/root/plane/backups/config-cutover-20260806T080602Z`, Nginx is active and enabled, all containers are healthy, and Certbot dry-run renewal passed. |
| Safe ingress cutover / Plane reconfiguration fails | Controlled failure rehearsal or isolated fixture deployment | pass | Attempt 2 hit the API container startup window during a one-shot manual probe and automatically restored production data and the previous ingress. |
| Safe ingress cutover / Public ingress validation fails | Review and rehearse documented restore commands against an isolated fixture | pass | Attempt 1 failed `nginx -t` on incompatible syntax and automatically restored the previous ingress; Attempt 3 passed after the compatibility correction. |

### Commands

- `go run github.com/rhysd/actionlint/cmd/actionlint@v1.7.7 .github/workflows/release-deploy.yml .github/workflows/deploy-preflight.yml`: pass (exit 0)
- Python `yaml.compose` for both workflows and safe-load parsing for both Compose files with the `!override` tag registered: pass
- `bash -n deployments/production/deploy.sh deployments/production/preflight.sh`: pass
- ShellCheck 0.10.0 on `deploy.sh` and `preflight.sh`: pass with no findings
- Production `docker compose ... config`, `docker compose ps`, and `ss -ltnp`: pass; Plane publishes only `127.0.0.1:6767`, all containers are healthy, and persistent volume creation timestamps are unchanged
- Production Nginx 1.24 `nginx -t`: pass; service is active and enabled on ports 80/443
- Certbot `renew --dry-run`: pass; current certificate is valid through 2026-11-04
- Release SSH ED25519 fingerprint contract assertions: pass
- Server-side public HTTPS polling success/exhaustion test: pass

### Production attempts

- Attempt 1: failed safely during `nginx -t`; Nginx 1.24 rejected the 1.25.1+ standalone `http2 on` syntax. The migration automatically restored the previous Plane ingress, and the certificate had already been issued successfully with validity through 2026-11-04.
- Attempt 2: Nginx 1.24 configuration validation passed, Compose and runtime exposed Plane only on loopback port 6767, and local TLS validation passed. A one-shot manual API check ran during the container startup window and triggered automatic rollback; production data and the previous ingress were restored. The next attempt will use `deploy.sh`'s 30-attempt health polling.
- Attempt 3: cutover succeeded. Independent configuration backup: `/root/plane/backups/config-cutover-20260806T080602Z`. Nginx 1.24 is active and enabled on ports 80/443; Plane is bound only to `127.0.0.1:6767`, and the public port 6767 probe timed out. HTTPS `/` returned 200, HTTP redirected with 301, `/god-mode/` returned 200, `/api/` returned API JSON, and `/live/` upgraded with 101. Certbot renewal dry-run passed, all containers are healthy, persistent volume creation timestamps are unchanged, and the production origin settings are synchronized.

### Residual risks

- Database migrations remain forward-only. Application rollback does not reverse an incompatible migration; recovery uses the timestamped PostgreSQL dump.
- Docker volumes and `~/plane/backups` are stored on the same host until an independent off-host backup policy is configured.
- Authenticated upload and retrieval through the public HTTPS origin still require production runtime evidence.
- Ingress-setting retention across a future immutable application release remains unverified until the next release deployment.
