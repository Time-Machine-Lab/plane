#!/usr/bin/env bash

set -uo pipefail

failures=0
warnings=0

pass() {
  printf '[PASS] %s\n' "$1"
}

warn() {
  warnings=$((warnings + 1))
  printf '[WARN] %s\n' "$1"
}

fail() {
  failures=$((failures + 1))
  printf '[FAIL] %s\n' "$1"
}

printf '%s\n' 'Plane production deployment preflight (read-only)'

os_type="$(uname -s 2>/dev/null || true)"
architecture="$(uname -m 2>/dev/null || true)"
if [[ "$os_type" == "Linux" ]]; then
  os_name="$(awk -F= '$1 == "PRETTY_NAME" {value = substr($0, index($0, "=") + 1); gsub(/^"|"$/, "", value); print value}' /etc/os-release 2>/dev/null || true)"
  pass "Operating system: ${os_name:-Linux}"
else
  fail "Linux is required; detected ${os_type:-unknown}."
fi

case "$architecture" in
  x86_64 | amd64)
    pass "Architecture: amd64"
    ;;
  aarch64 | arm64)
    pass "Architecture: arm64"
    ;;
  *)
    fail "Unsupported architecture: ${architecture:-unknown}."
    ;;
esac

cpu_count="$(getconf _NPROCESSORS_ONLN 2>/dev/null || true)"
if [[ "$cpu_count" =~ ^[0-9]+$ ]]; then
  if ((cpu_count >= 2)); then
    pass "CPU capacity: ${cpu_count} logical CPUs"
  else
    warn "CPU capacity is ${cpu_count}; Plane recommends at least 2 logical CPUs."
  fi
else
  warn "Could not determine CPU capacity."
fi

if command -v docker >/dev/null 2>&1; then
  pass "Docker CLI is installed."
  if docker info >/dev/null 2>&1; then
    docker_version="$(docker version --format '{{.Server.Version}}' 2>/dev/null || true)"
    pass "Docker daemon is reachable by the SSH user (server ${docker_version:-version unknown})."
  else
    fail "Docker daemon is unavailable or the SSH user lacks permission."
  fi
else
  fail "Docker CLI is not installed."
fi

if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  compose_version="$(docker compose version --short 2>/dev/null || true)"
  pass "Docker Compose plugin is available (${compose_version:-version unknown})."
else
  fail "Docker Compose plugin is not available."
fi

memory_total_kb="$(awk '/^MemTotal:/ {print $2}' /proc/meminfo 2>/dev/null || true)"
memory_available_kb="$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo 2>/dev/null || true)"
if [[ "$memory_total_kb" =~ ^[0-9]+$ ]]; then
  memory_total_gib=$((memory_total_kb / 1024 / 1024))
  memory_available_gib=0
  if [[ "$memory_available_kb" =~ ^[0-9]+$ ]]; then
    memory_available_gib=$((memory_available_kb / 1024 / 1024))
  fi
  if ((memory_total_kb >= 4 * 1024 * 1024)); then
    pass "Memory: ${memory_total_gib} GiB total, ${memory_available_gib} GiB available"
  else
    fail "Memory is ${memory_total_gib} GiB; Plane requires at least 4 GiB."
  fi
else
  warn "Could not determine memory capacity."
fi

read -r disk_available_kb disk_used_percent < <(df -Pk / 2>/dev/null | awk 'NR == 2 {print $4, $5}')
if [[ "${disk_available_kb:-}" =~ ^[0-9]+$ ]]; then
  disk_available_gib=$((disk_available_kb / 1024 / 1024))
  if ((disk_available_kb >= 10 * 1024 * 1024)); then
    pass "Root filesystem: ${disk_available_gib} GiB available (${disk_used_percent:-unknown} used)"
  else
    warn "Root filesystem has ${disk_available_gib} GiB available; at least 10 GiB free is recommended."
  fi
else
  warn "Could not determine free disk space on the root filesystem."
fi

listener_count=""
if command -v ss >/dev/null 2>&1; then
  listener_count="$(ss -H -ltn 2>/dev/null | awk '$4 ~ /:80$/ || $4 ~ /:443$/ {count++} END {print count + 0}')"
elif command -v netstat >/dev/null 2>&1; then
  listener_count="$(netstat -ltn 2>/dev/null | awk '$4 ~ /:80$/ || $4 ~ /:443$/ {count++} END {print count + 0}')"
fi

if [[ "$listener_count" =~ ^[0-9]+$ ]]; then
  if ((listener_count == 0)); then
    pass "TCP ports 80 and 443 have no listeners."
  else
    warn "Detected ${listener_count} listener(s) on TCP ports 80 or 443; confirm the deployment proxy can bind its ports."
  fi
else
  warn "Neither ss nor netstat is available; TCP ports 80 and 443 could not be inspected."
fi

if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
  plane_containers="$(docker ps -a --format '{{.Names}}\t{{.Image}}\t{{.State}}' 2>/dev/null | awk 'tolower($0) ~ /plane|makeplane/ {print $1 "\t" $3}')"
  if [[ -n "$plane_containers" ]]; then
    warn "Existing Plane-related containers were found:"
    printf '%s\n' "$plane_containers" | sed 's/^/  /'
  else
    pass "No existing Plane-related containers were found."
  fi

  plane_volumes="$(docker volume ls --format '{{.Name}}' 2>/dev/null | awk 'tolower($0) ~ /plane|(^|[_-])(pgdata|redisdata|uploads|rabbitmq_data|proxy_config|proxy_data|logs_api|logs_worker|logs_beat-worker|logs_migrator)$/ {print}')"
  if [[ -n "$plane_volumes" ]]; then
    warn "Existing Plane-related Docker volumes were found:"
    printf '%s\n' "$plane_volumes" | sed 's/^/  /'
  else
    pass "No existing Plane-related Docker volumes were found."
  fi
else
  warn "Existing Plane containers and volumes could not be inspected without Docker daemon access."
fi

printf '\nPreflight summary: %d failure(s), %d warning(s).\n' "$failures" "$warnings"
if ((failures > 0)); then
  exit 1
fi
