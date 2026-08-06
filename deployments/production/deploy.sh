#!/usr/bin/env bash

set -Eeuo pipefail

readonly DEPLOY_DIR="${HOME}/plane"
readonly BASE_COMPOSE_FILE="${DEPLOY_DIR}/docker-compose.yml"
readonly OVERRIDE_COMPOSE_FILE="${DEPLOY_DIR}/docker-compose.override.yml"
readonly ENV_FILE="${DEPLOY_DIR}/.env"
readonly BACKUP_ROOT="${DEPLOY_DIR}/backups"
readonly BACKUP_IMAGE="alpine:3.20.3"
readonly MINIMUM_COMPOSE_VERSION="2.24.4"
readonly -a APP_SERVICES=(api worker beat-worker web space admin live proxy)
readonly -a WRITER_SERVICES=(proxy api worker beat-worker live migrator)
readonly -a INFRA_SERVICES=(plane-db plane-redis plane-mq plane-minio)
readonly -a VOLUME_NAMES=(
  plane-production-pgdata
  plane-production-redisdata
  plane-production-uploads
  plane-production-logs-api
  plane-production-logs-worker
  plane-production-logs-beat-worker
  plane-production-logs-migrator
  plane-production-rabbitmq-data
  plane-production-proxy-config
  plane-production-proxy-data
)

usage() {
  echo "Usage: bash deploy.sh VERSION DOCKER_USERNAME PUBLIC_URL HTTP_PORT" >&2
}

die() {
  echo "ERROR: $*" >&2
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || die "Required command not found: $1"
}

read_env_value() {
  local key="$1"
  local value

  value="$(sed -n "s/^${key}=//p" "${ENV_FILE}" | tail -n 1)"
  printf '%s' "${value%$'\r'}"
}

upsert_env_value() {
  local key="$1"
  local value="$2"
  local temporary_file

  case "${key}" in
    APP_RELEASE | DOCKER_USERNAME | APP_DOMAIN | WEB_URL | CORS_ALLOWED_ORIGINS | SITE_ADDRESS | LISTEN_HTTP_PORT | LISTEN_HTTPS_PORT | MINIO_ENDPOINT_SSL) ;;
    *) die "Refusing to update unsupported environment key: ${key}" ;;
  esac

  temporary_file="$(mktemp "${ENV_FILE}.tmp.XXXXXX")"
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
    END {
      if (!updated) {
        print key "=" value
      }
    }
  ' "${ENV_FILE}" >"${temporary_file}"
  chmod 600 "${temporary_file}"
  mv -f "${temporary_file}" "${ENV_FILE}"
}

random_hex() {
  openssl rand -hex "$1"
}

create_initial_env() {
  local app_domain="$1"
  local public_url="$2"
  local listen_http_port="$3"
  local postgres_password rabbitmq_password aws_access_key aws_secret_key secret_key live_secret
  local temporary_file

  postgres_password="$(random_hex 32)"
  rabbitmq_password="$(random_hex 32)"
  aws_access_key="plane$(random_hex 12)"
  aws_secret_key="$(random_hex 32)"
  secret_key="$(random_hex 64)"
  live_secret="$(random_hex 32)"
  temporary_file="$(mktemp "${DEPLOY_DIR}/.env.tmp.XXXXXX")"

  cat >"${temporary_file}" <<EOF
COMPOSE_PROJECT_NAME=plane-production
APP_RELEASE=${release}
DOCKER_USERNAME=${docker_username}
APP_DOMAIN=${app_domain}
WEB_URL=${public_url}
CORS_ALLOWED_ORIGINS=${public_url}
DEBUG=0
SITE_ADDRESS=:80
LISTEN_HTTP_PORT=${listen_http_port}
LISTEN_HTTPS_PORT=443
CERT_EMAIL=
CERT_ACME_CA=https://acme-v02.api.letsencrypt.org/directory
CERT_ACME_DNS=
POSTGRES_USER=plane
POSTGRES_PASSWORD=${postgres_password}
POSTGRES_DB=plane
PGDATABASE=plane
PGHOST=plane-db
POSTGRES_PORT=5432
PGDATA=/var/lib/postgresql/data
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
AUTHENTICATION_RATE_LIMIT=10/minute
WEBHOOK_ALLOWED_IPS=
WEBHOOK_ALLOWED_HOSTS=
EOF

  chmod 600 "${temporary_file}"
  mv "${temporary_file}" "${ENV_FILE}"
  echo "Created ${ENV_FILE} with generated production secrets."
}

validate_existing_secrets() {
  local key value
  local -a required_keys=(
    POSTGRES_USER POSTGRES_PASSWORD POSTGRES_DB DATABASE_URL
    RABBITMQ_USER RABBITMQ_PASSWORD RABBITMQ_VHOST AMQP_URL
    AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY SECRET_KEY LIVE_SERVER_SECRET_KEY
  )

  for key in "${required_keys[@]}"; do
    value="$(read_env_value "${key}")"
    [[ -n "${value}" ]] || die "${ENV_FILE} is missing required production setting ${key}; it was not modified"
  done

  for key in POSTGRES_PASSWORD RABBITMQ_PASSWORD AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY SECRET_KEY LIVE_SERVER_SECRET_KEY; do
    value="$(read_env_value "${key}")"
    case "${value}" in
      plane | access-key | secret-key | change-this-key-on-deployment)
        die "${ENV_FILE} contains an unsafe default for ${key}; it was not modified"
        ;;
    esac
  done
}

wait_for_database() {
  local postgres_user postgres_database

  postgres_user="$(read_env_value POSTGRES_USER)"
  postgres_database="$(read_env_value POSTGRES_DB)"
  for _ in $(seq 1 60); do
    if "${COMPOSE[@]}" exec -T plane-db pg_isready -U "${postgres_user}" -d "${postgres_database}" >/dev/null 2>&1; then
      echo "PostgreSQL is ready."
      return 0
    fi
    sleep 2
  done

  echo "ERROR: PostgreSQL did not become ready within 120 seconds" >&2
  return 1
}

backup_volume() {
  local volume_name="$1"
  local archive_name="$2"

  docker run --rm \
    --volume "${volume_name}:/source:ro" \
    --volume "${backup_dir}:/backup" \
    "${BACKUP_IMAGE}" \
    tar -czf "/backup/${archive_name}" -C /source .
  if [[ ! -s "${backup_dir}/${archive_name}" ]]; then
    echo "ERROR: Backup archive is empty: ${archive_name}" >&2
    return 1
  fi
}

backup_existing_deployment() {
  local postgres_user postgres_database

  backup_dir="${BACKUP_ROOT}/$(date -u +%Y%m%dT%H%M%SZ)"
  mkdir -p "${backup_dir}"
  chmod 700 "${BACKUP_ROOT}" "${backup_dir}"

  echo "Stopping public traffic and application writers before backup."
  "${COMPOSE[@]}" stop "${WRITER_SERVICES[@]}"
  cp "${ENV_FILE}" "${backup_dir}/.env"
  chmod 600 "${backup_dir}/.env"

  postgres_user="$(read_env_value POSTGRES_USER)"
  postgres_database="$(read_env_value POSTGRES_DB)"
  "${COMPOSE[@]}" exec -T plane-db \
    pg_dump --host=/var/run/postgresql -U "${postgres_user}" -d "${postgres_database}" --format=custom \
    >"${backup_dir}/postgres.dump"
  if [[ ! -s "${backup_dir}/postgres.dump" ]]; then
    echo "ERROR: PostgreSQL backup is empty" >&2
    return 1
  fi

  "${COMPOSE[@]}" stop plane-redis plane-mq plane-minio
  backup_volume plane-production-uploads uploads.tar.gz
  backup_volume plane-production-redisdata redisdata.tar.gz
  backup_volume plane-production-rabbitmq-data rabbitmq-data.tar.gz
  backup_volume plane-production-proxy-config proxy-config.tar.gz
  backup_volume plane-production-proxy-data proxy-data.tar.gz

  printf 'created_utc=%s\nrelease=%s\ndocker_username=%s\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${previous_release}" "${previous_docker_username}" \
    >"${backup_dir}/manifest.txt"
  (
    cd "${backup_dir}"
    sha256sum .env postgres.dump uploads.tar.gz redisdata.tar.gz rabbitmq-data.tar.gz \
      proxy-config.tar.gz proxy-data.tar.gz manifest.txt >SHA256SUMS
  )
  echo "Backup completed: ${backup_dir}"
}

restore_environment_backup() {
  local temporary_file

  [[ -f "${backup_dir}/.env" ]] || return 1
  temporary_file="$(mktemp "${ENV_FILE}.rollback.XXXXXX")"
  cp "${backup_dir}/.env" "${temporary_file}"
  chmod 600 "${temporary_file}"
  mv -f "${temporary_file}" "${ENV_FILE}"
  echo "Restored the pre-deployment environment from ${backup_dir}/.env." >&2
}

health_check() {
  local app_domain

  app_domain="$(read_env_value APP_DOMAIN)"

  for _ in $(seq 1 30); do
    if curl --fail --silent --show-error --max-time 10 \
      --header "Host: ${app_domain}" "http://127.0.0.1:${listen_http_port}/" >/dev/null \
      && "${COMPOSE[@]}" exec -T api python -c \
        "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/', timeout=10).read()"; then
      echo "Local proxy and API health checks passed."
      return 0
    fi
    sleep 4
  done

  echo "ERROR: Local proxy or API health check failed after 120 seconds" >&2
  return 1
}

public_health_check() {
  for _ in $(seq 1 30); do
    if curl --fail --silent --show-error --max-time 10 \
      --resolve "${app_domain}:443:127.0.0.1" "${public_url}/" >/dev/null; then
      echo "Public HTTPS health check passed."
      return 0
    fi
    sleep 4
  done

  echo "ERROR: Public HTTPS health check failed after 120 seconds" >&2
  return 1
}

rollback_on_error() {
  local exit_code=$?

  trap - ERR
  set +e
  echo "Deployment failed (exit ${exit_code})." >&2
  "${COMPOSE[@]}" logs --tail=100 migrator api proxy >&2

  if [[ "${existing_deployment}" == true && -n "${previous_release}" && -n "${previous_docker_username}" ]]; then
    echo "Attempting application rollback to ${previous_docker_username}:${previous_release}." >&2
    if { [[ -n "${backup_dir}" ]] && restore_environment_backup; } \
      || { upsert_env_value APP_RELEASE "${previous_release}" \
        && upsert_env_value DOCKER_USERNAME "${previous_docker_username}"; }; then
      if "${COMPOSE[@]}" up -d "${INFRA_SERVICES[@]}" \
        && wait_for_database \
        && "${COMPOSE[@]}" up -d "${APP_SERVICES[@]}" \
        && health_check; then
        echo "Previous application images and environment were restored. Database migrations were not reversed." >&2
      else
        echo "Automatic application rollback did not complete; data volumes were left untouched." >&2
      fi
    else
      echo "The pre-deployment environment could not be restored; data volumes were left untouched." >&2
    fi
  else
    echo "No prior application release was available for automatic rollback." >&2
  fi

  exit "${exit_code}"
}

[[ $# -eq 4 ]] || {
  usage
  exit 2
}

release="$1"
docker_username="$2"
public_url="${3%/}"
listen_http_port="$4"

[[ "${release}" =~ ^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$ ]] || die "VERSION is not a valid immutable Docker tag"
case "${release,,}" in
  latest | stable | main | master | develop | development | dev | edge | nightly)
    die "VERSION must be immutable; floating tag '${release}' is not allowed"
    ;;
esac
[[ "${docker_username}" =~ ^[a-z0-9]+([._-][a-z0-9]+)*$ ]] || die "DOCKER_USERNAME is not a valid Docker namespace"

if [[ "${public_url}" != http://* && "${public_url}" != https://* ]]; then
  public_url="http://${public_url}"
fi
if [[ "${public_url}" =~ ^(https?)://(\[[0-9A-Fa-f:]+\]|[A-Za-z0-9.-]+)(:([0-9]{1,5}))?$ ]]; then
  public_scheme="${BASH_REMATCH[1]}"
  app_domain="${BASH_REMATCH[2]}"
  public_port="${BASH_REMATCH[4]:-}"
else
  die "PUBLIC_URL must be an HTTP(S) origin without a path, query, or fragment"
fi
if [[ -n "${public_port}" ]]; then
  public_port_number=$((10#${public_port}))
  if ((public_port_number < 1 || public_port_number > 65535)); then
    die "PUBLIC_URL port must be between 1 and 65535"
  fi
fi
if [[ "${public_scheme}" != "https" || ( -n "${public_port}" && "${public_port}" != "443" ) ]]; then
  die "PUBLIC_URL must use HTTPS on the default port"
fi
if [[ ! "${listen_http_port}" =~ ^[0-9]{1,5}$ ]]; then
  die "HTTP_PORT must be a number between 1 and 65535"
fi
listen_http_port_number=$((10#${listen_http_port}))
if ((listen_http_port_number < 1 || listen_http_port_number > 65535)); then
  die "HTTP_PORT must be a number between 1 and 65535"
fi
listen_http_port="${listen_http_port_number}"
export PLANE_HTTP_PORT="${listen_http_port}"

for command_name in awk cp curl docker flock head mktemp openssl sed seq sha256sum sort; do
  require_command "${command_name}"
done
docker compose version >/dev/null 2>&1 || die "Docker Compose v2 is required"
compose_version="$(docker compose version --short 2>/dev/null)"
compose_version="${compose_version#v}"
compose_version="${compose_version%%-*}"
if [[ "$(printf '%s\n%s\n' "${MINIMUM_COMPOSE_VERSION}" "${compose_version}" | sort -V | head -n 1)" != "${MINIMUM_COMPOSE_VERSION}" ]]; then
  die "Docker Compose ${MINIMUM_COMPOSE_VERSION} or newer is required; found ${compose_version:-unknown}"
fi

[[ -d "${DEPLOY_DIR}" ]] || die "Deployment directory does not exist: ${DEPLOY_DIR}"
cd "${DEPLOY_DIR}"
[[ -f "${BASE_COMPOSE_FILE}" ]] || die "Missing ${BASE_COMPOSE_FILE}"
[[ -f "${OVERRIDE_COMPOSE_FILE}" ]] || die "Missing ${OVERRIDE_COMPOSE_FILE}"

exec 9>"${DEPLOY_DIR}/.deploy.lock"
flock -n 9 || die "Another production deployment is already running"
umask 077

if [[ ! -e "${ENV_FILE}" ]]; then
  create_initial_env "${app_domain}" "${public_url}" "${listen_http_port}"
fi
[[ -f "${ENV_FILE}" && ! -L "${ENV_FILE}" ]] || die "${ENV_FILE} must be a regular file"
chmod 600 "${ENV_FILE}"
validate_existing_secrets

previous_release="$(read_env_value APP_RELEASE)"
previous_docker_username="$(read_env_value DOCKER_USERNAME)"
existing_deployment=false
if [[ -n "$(docker container ls -aq --filter label=com.docker.compose.project=plane-production)" ]]; then
  existing_deployment=true
  [[ -n "${previous_release}" && -n "${previous_docker_username}" ]] || \
    die "Existing deployment has no APP_RELEASE or DOCKER_USERNAME to roll back to"
fi
readonly -a COMPOSE=(
  docker compose
  --env-file "${ENV_FILE}"
  --file "${BASE_COMPOSE_FILE}"
  --file "${OVERRIDE_COMPOSE_FILE}"
)

backup_dir=""
trap rollback_on_error ERR
for volume_name in "${VOLUME_NAMES[@]}"; do
  docker volume inspect "${volume_name}" >/dev/null 2>&1 || docker volume create "${volume_name}" >/dev/null
done

"${COMPOSE[@]}" config --quiet
docker image inspect "${BACKUP_IMAGE}" >/dev/null 2>&1 || docker pull "${BACKUP_IMAGE}" >/dev/null
APP_RELEASE="${release}" DOCKER_USERNAME="${docker_username}" \
  "${COMPOSE[@]}" pull web space admin live api worker beat-worker migrator proxy

if [[ "${existing_deployment}" == true ]]; then
  backup_existing_deployment
fi

upsert_env_value APP_RELEASE "${release}"
upsert_env_value DOCKER_USERNAME "${docker_username}"
upsert_env_value APP_DOMAIN "${app_domain}"
upsert_env_value WEB_URL "${public_url}"
upsert_env_value CORS_ALLOWED_ORIGINS "${public_url}"
upsert_env_value SITE_ADDRESS ":80"
upsert_env_value LISTEN_HTTP_PORT "${listen_http_port}"
upsert_env_value LISTEN_HTTPS_PORT "443"
upsert_env_value MINIO_ENDPOINT_SSL "1"
"${COMPOSE[@]}" up -d "${INFRA_SERVICES[@]}"
wait_for_database
"${COMPOSE[@]}" run --rm --no-deps migrator
"${COMPOSE[@]}" up -d "${APP_SERVICES[@]}"
health_check
public_health_check

trap - ERR
echo "Plane ${release} is running at ${public_url}."
if [[ -n "${backup_dir}" ]]; then
  echo "Pre-deployment backup: ${backup_dir}"
fi
