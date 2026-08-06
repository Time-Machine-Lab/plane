# Production deployment

The release workflow deploys Plane behind a host-managed Nginx reverse proxy:

```text
Browser -> https://plane.tmlab.top:443 -> Nginx -> http://127.0.0.1:6767 -> Plane proxy
```

Plane's Docker proxy binds only to the host loopback address on port `6767`. It does not publish ports `80` or `443`; those ports remain available for Nginx and TLS termination. The application origin passed to Plane is `https://plane.tmlab.top`, so users access the workspace without adding `:6767` to the URL. The deployment command passes the host bind port through `PLANE_HTTP_PORT`, independently of the public origin stored in Plane's environment.

The server Nginx configuration is intentionally not managed by GitHub Actions. The audited vhost template is stored at `nginx/plane.tmlab.top.conf`; it preserves the incoming `Host`, `X-Real-IP`, `X-Forwarded-For`, and `X-Forwarded-Proto` headers and proxies WebSocket upgrades for `/live/`.

## Initial ingress cutover

The one-time migration is performed independently on the production server, outside the release workflow. Before changing listeners, the server operator backs up the active Compose override and Nginx configuration in addition to Plane's data and environment backup. Record the exact server backup paths in the OpenSpec acceptance record after the migration completes.

Do not enable or trigger the tag-based release workflow until the one-time cutover has passed merged Compose inspection, loopback and public HTTPS health checks, `nginx -t`, route checks, and rollback verification. Subsequent releases retain Nginx as host infrastructure; the workflow updates Plane and verifies HTTPS but does not reinstall or rewrite Nginx.

## Persistent data

Production state uses fixed external Docker volume names, so `docker compose up`, image replacement, and application rollback do not recreate or remove data:

- `plane-production-pgdata`: PostgreSQL data
- `plane-production-uploads`: MinIO uploads
- `plane-production-redisdata`: Redis data
- `plane-production-rabbitmq-data`: RabbitMQ data
- `plane-production-logs-*`: application logs
- `plane-production-proxy-config` and `plane-production-proxy-data`: Plane proxy state

Before an existing deployment is upgraded, `deploy.sh` stops writers and creates a timestamped backup under `~/plane/backups/`. The backup includes a PostgreSQL custom-format dump, persistent volume archives, the deployment environment file, checksums, and a release manifest.

The automatic rollback restores the previous application image tags if local or public HTTPS health checks fail. Database migrations are not automatically reversed. Retain and monitor the pre-deployment backups independently; Docker volumes and backups on the same server are not a disaster-recovery copy.
