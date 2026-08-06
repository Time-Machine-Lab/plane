#!/usr/bin/env bash

set -Eeuo pipefail

die() {
  echo "ERROR: $*" >&2
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || die "Required command not found: $1"
}

upsert_env() {
  local key="$1"
  local value="$2"
  local temporary

  case "${key}" in
    APP_RELEASE | APP_DOMAIN | WEB_URL | CORS_ALLOWED_ORIGINS | SITE_ADDRESS | LISTEN_HTTP_PORT | LISTEN_HTTPS_PORT | \
      CERT_EMAIL | CERT_ACME_CA | CERT_ACME_DNS | ADMIN_BASE_URL | SPACE_BASE_URL | APP_BASE_URL | LIVE_BASE_URL) ;;
    *) die "Refusing to update unsupported environment key: ${key}" ;;
  esac

  temporary="$(mktemp "${shared_env}.tmp.XXXXXX")"
  awk -v key="${key}" -v value="${value}" '
    BEGIN { updated = 0 }
    $0 ~ "^" key "=" {
      if (!updated) {
        print key "=" value
        updated = 1
      }
      next
    }
    { print }
    END { if (!updated) print key "=" value }
  ' "${shared_env}" >"${temporary}"
  chmod 600 "${temporary}"
  mv -f "${temporary}" "${shared_env}"
}

create_env() {
  local postgres_password rabbitmq_password aws_access_key aws_secret_key secret_key live_secret

  postgres_password="$(openssl rand -hex 32)"
  rabbitmq_password="$(openssl rand -hex 32)"
  aws_access_key="plane$(openssl rand -hex 12)"
  aws_secret_key="$(openssl rand -hex 32)"
  secret_key="$(openssl rand -hex 64)"
  live_secret="$(openssl rand -hex 32)"

  umask 077
  cat >"${shared_env}" <<EOF
COMPOSE_PROJECT_NAME=${project}
APP_RELEASE=${bootstrap_release}
DEBUG=0
APP_DOMAIN=${app_domain}
WEB_URL=${base_url}
CORS_ALLOWED_ORIGINS=${cors_origins}
SITE_ADDRESS=:80
LISTEN_HTTP_PORT=${http_port}
LISTEN_HTTPS_PORT=${https_port}
CERT_EMAIL=
CERT_ACME_CA=https://acme-v02.api.letsencrypt.org/directory
CERT_ACME_DNS=
POSTGRES_USER=plane
POSTGRES_PASSWORD=${postgres_password}
POSTGRES_DB=plane
POSTGRES_HOST=plane-db
POSTGRES_PORT=5432
DATABASE_URL=postgresql://plane:${postgres_password}@plane-db:5432/plane
REDIS_HOST=plane-redis
REDIS_PORT=6379
REDIS_URL=redis://plane-redis:6379/
RABBITMQ_HOST=plane-mq
RABBITMQ_PORT=5672
RABBITMQ_USER=plane
RABBITMQ_PASSWORD=${rabbitmq_password}
RABBITMQ_VHOST=plane
AMQP_URL=amqp://plane:${rabbitmq_password}@plane-mq:5672/plane
USE_MINIO=1
AWS_REGION=
AWS_ACCESS_KEY_ID=${aws_access_key}
AWS_SECRET_ACCESS_KEY=${aws_secret_key}
AWS_S3_ENDPOINT_URL=http://plane-minio:9000
AWS_S3_BUCKET_NAME=uploads
MINIO_ENDPOINT_SSL=0
SECRET_KEY=${secret_key}
LIVE_SERVER_SECRET_KEY=${live_secret}
FILE_SIZE_LIMIT=5242880
API_KEY_RATE_LIMIT=60/minute
WEBHOOK_ALLOWED_IPS=
WEBHOOK_ALLOWED_HOSTS=
ADMIN_BASE_URL=${base_url}
ADMIN_BASE_PATH=/god-mode
SPACE_BASE_URL=${base_url}
SPACE_BASE_PATH=/spaces
APP_BASE_URL=${base_url}
APP_BASE_PATH=
LIVE_BASE_URL=${base_url}
LIVE_BASE_PATH=/live
COOKIE_DOMAIN=
EOF
  chmod 600 "${shared_env}"
  echo "Created an isolated Plane test environment file with generated application secrets."
}

write_compose_override() {
  local override="${release_dir}/docker-compose.test.override.yml"
  if [[ "${bootstrap_mode}" == true ]]; then
    printf 'services: {}\n' >"${override}"
    return
  fi
  printf 'services:\n' >"${override}"

  for frontend in web admin space; do
    if [[ -n "${selected[${frontend}]:-}" ]]; then
      cat >>"${override}" <<EOF
  ${frontend}:
    image: "${project}-${frontend}:${release}"
    build:
      context: "${release_dir}"
      dockerfile: "./apps/${frontend}/Dockerfile.${frontend}"
      args:
        VITE_API_BASE_URL: "${base_url}"
        VITE_WEB_BASE_URL: "${base_url}"
        VITE_ADMIN_BASE_URL: "${base_url}"
        VITE_ADMIN_BASE_PATH: "/god-mode"
        VITE_SPACE_BASE_URL: "${base_url}"
        VITE_SPACE_BASE_PATH: "/spaces"
        VITE_LIVE_BASE_URL: "${base_url}"
        VITE_LIVE_BASE_PATH: "/live"
EOF
    fi
  done

  if [[ -n "${selected[api]:-}" || -n "${selected[worker]:-}" || -n "${selected[beat-worker]:-}" ]]; then
    cat >>"${override}" <<EOF
  api:
    image: "${project}-api:${release}"
    build:
      context: "${release_dir}/apps/api"
      dockerfile: "Dockerfile.api"
  worker:
    image: "${project}-api:${release}"
  beat-worker:
    image: "${project}-api:${release}"
  migrator:
    image: "${project}-api:${release}"
EOF
  fi

  if [[ -n "${selected[live]:-}" ]]; then
    cat >>"${override}" <<EOF
  live:
    image: "${project}-live:${release}"
    build:
      context: "${release_dir}"
      dockerfile: "./apps/live/Dockerfile.live"
EOF
  fi

  if [[ -n "${selected[proxy]:-}" ]]; then
    cat >>"${override}" <<EOF
  proxy:
    image: "${project}-proxy:${release}"
    build:
      context: "${release_dir}/apps/proxy"
      dockerfile: "Dockerfile.ce"
EOF
  fi
}

wait_for_database() {
  local postgres_user postgres_database
  postgres_user="$(sed -n 's/^POSTGRES_USER=//p' "${shared_env}" | tail -n 1)"
  postgres_database="$(sed -n 's/^POSTGRES_DB=//p' "${shared_env}" | tail -n 1)"
  for _ in $(seq 1 60); do
    if "${compose[@]}" exec -T plane-db pg_isready -U "${postgres_user}" -d "${postgres_database}" >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
  done
  die "PostgreSQL did not become ready within 120 seconds"
}

health_check() {
  local local_url="http://127.0.0.1:${http_port}/"
  for _ in $(seq 1 45); do
    if curl --fail --silent --max-time 10 "${local_url}" >/dev/null 2>&1 \
      && "${compose[@]}" exec -T api python -c \
        "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/', timeout=10).read()" >/dev/null 2>&1; then
      echo "Proxy and API health checks passed."
      return 0
    fi
    sleep 4
  done
  return 1
}

rollback_on_error() {
  local exit_code=$?
  trap - ERR
  set +e
  echo "Deployment ${release} failed (exit ${exit_code})." >&2
  "${compose[@]}" logs --tail=100 api proxy >&2
  if [[ -n "${previous_release_dir}" && -d "${previous_release_dir}" && "${#previous_images[@]}" -gt 0 ]]; then
    echo "Restoring the previously running images for the affected Plane services." >&2
    ln -sfn "${previous_release_dir}" "${root}/current"
    local rollback_override="${root}/shared/rollback-${release}.yml"
    printf 'services:\n' >"${rollback_override}"
    local service image_name
    for service in "${!previous_images[@]}"; do
      image_name="${previous_images[${service}]}"
      if [[ ! "${image_name}" =~ ^[A-Za-z0-9._/@:-]+$ ]]; then
        echo "Cannot safely restore invalid image name for ${service}." >&2
        continue
      fi
      printf '  %s:\n    image: "%s"\n' "${service}" "${image_name}" >>"${rollback_override}"
    done
    local -a previous_compose=(
      docker compose --project-name "${project}" --env-file "${shared_env}"
      --file "${previous_release_dir}/deployments/cli/community/docker-compose.yml"
      --file "${previous_release_dir}/docker-compose.test.override.yml"
      --file "${rollback_override}"
    )
    "${previous_compose[@]}" up -d --no-build "${start_services[@]}" >&2
  else
    echo "No previously running affected images are available for automatic application rollback." >&2
    if [[ "${bootstrap_mode:-false}" == true ]]; then
      echo "Removing failed Plane application containers while preserving infrastructure and volumes." >&2
      "${compose[@]}" rm -s -f proxy web admin space live api worker beat-worker >&2
    fi
  fi
  exit "${exit_code}"
}

usage() {
  echo "Usage: remote-deploy.sh --archive FILE --release ID --root DIR --project NAME --http-port PORT --https-port PORT --base-url URL --services CSV --keep N --local-origins CSV --bootstrap-release TAG" >&2
}

archive=""
release=""
root=""
project=""
http_port=""
https_port=""
base_url=""
services_csv=""
keep=""
local_origins=""
bootstrap_release="stable"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --archive) archive="${2:-}"; shift 2 ;;
    --release) release="${2:-}"; shift 2 ;;
    --root) root="${2:-}"; shift 2 ;;
    --project) project="${2:-}"; shift 2 ;;
    --http-port) http_port="${2:-}"; shift 2 ;;
    --https-port) https_port="${2:-}"; shift 2 ;;
    --base-url) base_url="${2:-}"; shift 2 ;;
    --services) services_csv="${2:-}"; shift 2 ;;
    --keep) keep="${2:-}"; shift 2 ;;
    --local-origins) local_origins="${2:-}"; shift 2 ;;
    --bootstrap-release) bootstrap_release="${2:-}"; shift 2 ;;
    *) usage; die "Unknown argument: $1" ;;
  esac
done

[[ -n "${archive}" && -n "${release}" && -n "${root}" && -n "${project}" && -n "${http_port}" \
  && -n "${https_port}" && -n "${base_url}" && -n "${services_csv}" && -n "${keep}" ]] || {
  usage
  exit 2
}

for command_name in awk curl docker flock openssl realpath sed seq sha256sum tar timeout; do
  require_command "${command_name}"
done
docker compose version >/dev/null 2>&1 || die "Docker Compose v2 is required"

[[ "${root}" =~ ^/[A-Za-z0-9._/-]+$ && "${root}" != "/" && "${root}" != "/opt" && "${root}" != "/srv" ]] \
  || die "Remote root is not a safe dedicated absolute path"
[[ "${project}" =~ ^plane-test[A-Za-z0-9_-]*$ ]] || die "Compose project must start with plane-test"
[[ "${release}" =~ ^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$ ]] || die "Invalid release identifier"
[[ "${bootstrap_release}" =~ ^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$ ]] || die "Invalid bootstrap image tag"
[[ "${http_port}" =~ ^[0-9]{1,5}$ && "${https_port}" =~ ^[0-9]{1,5}$ ]] || die "Ports must be numeric"
((10#${http_port} >= 1 && 10#${http_port} <= 65535)) || die "HTTP port is out of range"
((10#${https_port} >= 1 && 10#${https_port} <= 65535)) || die "HTTPS port is out of range"
[[ "${keep}" =~ ^[0-9]+$ && "${keep}" -ge 1 && "${keep}" -le 20 ]] || die "Keep count must be between 1 and 20"
[[ "${base_url}" =~ ^https?://(\[[0-9A-Fa-f:]+\]|[A-Za-z0-9.-]+)(:[0-9]{1,5})?$ ]] \
  || die "Base URL must be an HTTP(S) origin without a path"

root="$(realpath -m -- "${root}")"
archive="$(realpath -m -- "${archive}")"
[[ "${archive}" == "${root}/incoming/"* && -f "${archive}" && ! -L "${archive}" ]] \
  || die "Archive must be a regular file inside the dedicated incoming directory"

mkdir -p -- "${root}/incoming" "${root}/releases" "${root}/shared" "${root}/backups"
chmod 700 "${root}" "${root}/incoming" "${root}/releases" "${root}/shared" "${root}/backups"
exec 9>"${root}/.deploy.lock"
flock -n 9 || die "Another Plane test deployment is already running"

release_dir="${root}/releases/${release}"
[[ ! -e "${release_dir}" ]] || die "Release already exists: ${release}"
mkdir -m 700 -- "${release_dir}"

while IFS= read -r entry; do
  [[ "${entry}" != /* && "${entry}" != ../* && "${entry}" != *"/../"* && "${entry}" != */.. ]] \
    || die "Archive contains an unsafe path"
done < <(tar -tzf "${archive}")
tar -xzf "${archive}" -C "${release_dir}" --no-same-owner --no-same-permissions
[[ -f "${release_dir}/docker-compose.yml" \
  && -f "${release_dir}/deployments/cli/community/docker-compose.yml" \
  && -f "${release_dir}/.plane-test-manifest.json" ]] \
  || die "Archive is not a valid Plane source package"

app_domain="${base_url#*://}"
app_domain="${app_domain%%:*}"
cors_origins="${base_url}"
if [[ -n "${local_origins}" ]]; then cors_origins="${cors_origins},${local_origins}"; fi
shared_env="${root}/shared/.env"
if [[ ! -f "${shared_env}" ]]; then
  create_env
else
  [[ ! -L "${shared_env}" ]] || die "Shared environment file must not be a symbolic link"
  chmod 600 "${shared_env}"
  upsert_env APP_RELEASE "${bootstrap_release}"
  upsert_env APP_DOMAIN "${app_domain}"
  upsert_env WEB_URL "${base_url}"
  upsert_env CORS_ALLOWED_ORIGINS "${cors_origins}"
  upsert_env SITE_ADDRESS ":80"
  upsert_env LISTEN_HTTP_PORT "${http_port}"
  upsert_env LISTEN_HTTPS_PORT "${https_port}"
  upsert_env CERT_EMAIL ""
  upsert_env CERT_ACME_CA "https://acme-v02.api.letsencrypt.org/directory"
  upsert_env CERT_ACME_DNS ""
  upsert_env ADMIN_BASE_URL "${base_url}"
  upsert_env SPACE_BASE_URL "${base_url}"
  upsert_env APP_BASE_URL "${base_url}"
  upsert_env LIVE_BASE_URL "${base_url}"
fi
mkdir -p "${release_dir}/apps/api"
ln -sfn "${shared_env}" "${release_dir}/.env"
ln -sfn "${shared_env}" "${release_dir}/apps/api/.env"
[[ "$(realpath -m -- "${release_dir}/.env")" == "${shared_env}" \
  && "$(realpath -m -- "${release_dir}/apps/api/.env")" == "${shared_env}" ]] \
  || die "Release environment links must resolve to the dedicated shared environment file"
previous_release_dir=""
if [[ -L "${root}/current" ]]; then
  previous_release_dir="$(realpath -m -- "${root}/current")"
  [[ "${previous_release_dir}" == "${root}/releases/"* ]] || die "Current release link escapes the dedicated root"
fi
if [[ -z "${previous_release_dir}" ]] \
  && timeout 2 bash -c "exec 3<>/dev/tcp/127.0.0.1/${http_port}" >/dev/null 2>&1; then
  die "HTTP port ${http_port} is already in use; the occupying process was not changed"
fi

IFS=',' read -r -a requested_services <<<"${services_csv}"
declare -A selected=()
for service in "${requested_services[@]}"; do
  case "${service}" in
    all) selected[all]=1 ;;
    web | admin | space | api | worker | beat-worker | live | proxy) selected["${service}"]=1 ;;
    *) die "Unsupported service: ${service}" ;;
  esac
done
bootstrap_mode=false
if [[ -z "${previous_release_dir}" ]]; then
  bootstrap_mode=true
  selected=([all]=1)
elif [[ -n "${selected[all]:-}" ]]; then
  die "Full source builds are disabled on this test server; specify only affected services"
fi

declare -a build_services=()
declare -a start_services=()
run_migrator=false
if [[ "${bootstrap_mode}" == true ]]; then
  start_services=(web admin space api worker beat-worker live proxy)
  run_migrator=true
else
  for service in web admin space live proxy; do
    if [[ -n "${selected[${service}]:-}" ]]; then
      build_services+=("${service}")
      start_services+=("${service}")
    fi
  done
  if [[ -n "${selected[api]:-}" || -n "${selected[worker]:-}" || -n "${selected[beat-worker]:-}" ]]; then
    build_services+=(api)
    start_services+=(api worker beat-worker)
    run_migrator=true
  fi
fi

write_compose_override

declare -a compose=(
  docker compose --project-name "${project}" --env-file "${shared_env}"
  --file "${release_dir}/deployments/cli/community/docker-compose.yml"
  --file "${release_dir}/docker-compose.test.override.yml"
)
"${compose[@]}" config --quiet
declare -A previous_images=()
if [[ "${bootstrap_mode}" == false ]]; then
  for service in "${start_services[@]}"; do
    container_id="$("${compose[@]}" ps -q "${service}" 2>/dev/null || true)"
    if [[ -n "${container_id}" ]]; then
      previous_images["${service}"]="$(docker inspect --format '{{.Config.Image}}' "${container_id}")"
    fi
  done
fi
trap rollback_on_error ERR

"${compose[@]}" up -d --no-build plane-db plane-redis plane-mq plane-minio
wait_for_database

if [[ "${run_migrator}" == true && -n "${previous_release_dir}" ]]; then
  backup_file="${root}/backups/${release}-postgres.dump"
  postgres_user="$(sed -n 's/^POSTGRES_USER=//p' "${shared_env}" | tail -n 1)"
  postgres_database="$(sed -n 's/^POSTGRES_DB=//p' "${shared_env}" | tail -n 1)"
  "${compose[@]}" exec -T plane-db pg_dump -U "${postgres_user}" -d "${postgres_database}" --format=custom >"${backup_file}"
  [[ -s "${backup_file}" ]] || die "Database backup is empty"
  chmod 600 "${backup_file}"
  echo "Created test database backup: ${backup_file}"
fi

if [[ "${bootstrap_mode}" == true ]]; then
  echo "Bootstrapping Plane from prebuilt makeplane images tagged ${bootstrap_release}; no source images will be built."
elif [[ "${#build_services[@]}" -gt 0 ]]; then
  echo "Building only affected source services: ${build_services[*]}"
  "${compose[@]}" build "${build_services[@]}"
fi
if [[ "${run_migrator}" == true ]]; then "${compose[@]}" run --rm migrator; fi
"${compose[@]}" up -d --no-build "${start_services[@]}"
health_check

ln -sfn "${release_dir}" "${root}/current"
trap - ERR
rm -f -- "${archive}" "$0"

mapfile -t old_releases < <(find "${root}/releases" -mindepth 1 -maxdepth 1 -type d -printf '%T@ %p\n' | sort -nr | tail -n +$((keep + 1)) | cut -d' ' -f2-)
for old_release in "${old_releases[@]}"; do
  [[ "${old_release}" == "${root}/releases/"* && "${old_release}" != "${release_dir}" ]] || continue
  rm -rf -- "${old_release}"
done

echo "Plane test release ${release} is running at ${base_url}."
