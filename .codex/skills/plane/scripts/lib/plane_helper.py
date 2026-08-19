#!/usr/bin/env python3
"""Structured helpers for the POSIX Plane Skill scripts."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from urllib.parse import unquote, urlsplit


SLUG_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
RESERVED_SLUGS = {"api", "mcp", "god-mode", "spaces"}


def normalize_url(value: str, explicit_slug: str | None) -> dict[str, str]:
    parsed = urlsplit(value)
    if not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Workspace URL has an invalid authority.")
    loopback_hosts = {"localhost", "127.0.0.1", "::1"}
    is_loopback_http = parsed.scheme == "http" and parsed.hostname.lower() in loopback_hosts
    if parsed.scheme != "https" and not is_loopback_http:
        raise ValueError("Workspace URL must use HTTPS unless it targets a loopback address.")
    if parsed.query or parsed.fragment:
        raise ValueError("Workspace URL must not contain a query string or fragment.")

    segments = [unquote(segment) for segment in parsed.path.split("/") if segment]
    slug = explicit_slug or (segments[0] if segments else "")
    if not slug:
        raise ValueError("Workspace slug is missing. Add it to the URL path or pass --workspace-slug.")
    if not SLUG_PATTERN.fullmatch(slug):
        raise ValueError("Workspace slug contains unsupported characters.")
    if slug.lower() in RESERVED_SLUGS:
        raise ValueError("Workspace slug cannot be a reserved Plane path.")
    if explicit_slug and segments and segments[0] != slug:
        raise ValueError("Workspace slug does not match the workspace URL path.")

    hostname = parsed.hostname
    if ":" in hostname and not hostname.startswith("["):
        hostname = f"[{hostname}]"
    authority = hostname
    if parsed.port is not None:
        authority = f"{authority}:{parsed.port}"
    origin = f"{parsed.scheme}://{authority}"
    return {"origin": origin, "workspace_slug": slug, "mcp_url": f"{origin}/mcp"}


def read_json_stream() -> object:
    return json.load(sys.stdin)


def write_profile(path: Path, origin: str, slug: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"origin": origin, "workspace_slug": slug}
    descriptor, temporary_name = tempfile.mkstemp(prefix="profile.", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def load_profile(path: Path) -> dict[str, str]:
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    origin = payload.get("origin")
    slug = payload.get("workspace_slug")
    if not isinstance(origin, str) or not isinstance(slug, str):
        raise ValueError("Plane profile is invalid. Run setup again.")
    normalized = normalize_url(f"{origin}/{slug}", None)
    if normalized["origin"] != origin or normalized["workspace_slug"] != slug:
        raise ValueError("Plane profile is not normalized. Run setup again.")
    return normalized


def user_label(path: Path) -> str:
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    for field in ("display_name", "name", "email", "id"):
        value = payload.get(field)
        if value is not None and str(value).strip():
            return str(value)
    return "authenticated user"


def redact(text: str) -> str:
    token = os.environ.get("PLANE_API_TOKEN", "")
    if token:
        text = text.replace(token, "[REDACTED]")
    text = re.sub(
        r"(?i)(Authorization\s*:\s*Bearer\s+)[^\s,;]+",
        r"\1[REDACTED]",
        text,
    )
    return re.sub(r"(?i)(X-Api-Key\s*:\s*)[^\s,;]+", r"\1[REDACTED]", text)


def validate_token() -> None:
    token = os.environ.get("PLANE_API_TOKEN", "")
    if not token:
        raise ValueError("PLANE_API_TOKEN is not available in this process.")
    if any(ord(character) < 32 or ord(character) == 127 for character in token):
        raise ValueError("Plane API token contains unsafe characters.")
    if '"' in token or "\\" in token:
        raise ValueError("Plane API token contains unsafe characters.")


def plane_status_request(slug: str) -> dict[str, object]:
    return {
        "jsonrpc": "2.0",
        "id": "plane-doctor-status",
        "method": "tools/call",
        "params": {"name": "plane_status", "arguments": {"workspace_slug": slug}},
    }


def validate_plane_status_response(path: Path, slug: str) -> tuple[bool, str]:
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict) or "error" in payload:
        return False, "The Plane MCP endpoint returned a JSON-RPC error."
    result = payload.get("result")
    if not isinstance(result, dict):
        return False, "The Plane MCP endpoint returned an invalid plane_status result."
    structured = result.get("structuredContent")
    if result.get("isError") is True:
        error = structured.get("error") if isinstance(structured, dict) else None
        raw_code = error.get("code") if isinstance(error, dict) else None
        code = raw_code if isinstance(raw_code, str) and re.fullmatch(r"[a-z_]+", raw_code) else "tool_error"
        return False, f"plane_status returned a {code} error."
    if not isinstance(structured, dict):
        return False, "The Plane MCP endpoint returned an invalid plane_status result."
    if structured.get("available") is not True or structured.get("workspace") != slug:
        return False, "plane_status did not confirm the configured workspace."
    return True, "plane_status confirmed the configured workspace."


def parse_checks(path: Path) -> list[dict[str, str]]:
    checks: list[dict[str, str]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            name, status, category, detail = line.rstrip("\n").split("\t", 3)
            checks.append(
                {"name": name, "status": status, "category": category, "detail": detail}
            )
    return checks


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    normalize = subparsers.add_parser("normalize-url")
    normalize.add_argument("--url", required=True)
    normalize.add_argument("--slug")

    match = subparsers.add_parser("config-match")
    match.add_argument("--url", required=True)

    write = subparsers.add_parser("profile-write")
    write.add_argument("--path", required=True)
    write.add_argument("--origin", required=True)
    write.add_argument("--slug", required=True)

    read = subparsers.add_parser("profile-read")
    read.add_argument("--path", required=True)

    label = subparsers.add_parser("user-label")
    label.add_argument("--path", required=True)

    subparsers.add_parser("redact")
    subparsers.add_parser("validate-token")

    probe_request = subparsers.add_parser("probe-request")
    probe_request.add_argument("--slug", required=True)

    probe = subparsers.add_parser("probe-valid")
    probe.add_argument("--path", required=True)
    probe.add_argument("--slug", required=True)

    doctor = subparsers.add_parser("doctor-output")
    doctor.add_argument("--checks", required=True)
    doctor.add_argument("--origin", default="")
    doctor.add_argument("--slug", default="")
    doctor.add_argument("--user", default="")
    doctor.add_argument("--human", action="store_true")

    setup = subparsers.add_parser("setup-output")
    setup.add_argument("--origin", required=True)
    setup.add_argument("--slug", required=True)
    setup.add_argument("--user", required=True)
    setup.add_argument("--mcp-state", required=True)
    setup.add_argument("--token-source", required=True)
    setup.add_argument("--profile-path", required=True)
    setup.add_argument("--human", action="store_true")

    args = parser.parse_args()
    try:
        if args.command == "normalize-url":
            profile = normalize_url(args.url, args.slug)
            print(profile["origin"])
            print(profile["workspace_slug"])
            print(profile["mcp_url"])
        elif args.command == "config-match":
            config = read_json_stream()
            transport = config.get("transport", {}) if isinstance(config, dict) else {}
            matches = (
                config.get("enabled") is not False
                and transport.get("type") == "streamable_http"
                and str(transport.get("url", "")).rstrip("/") == args.url.rstrip("/")
                and transport.get("bearer_token_env_var") == "PLANE_API_TOKEN"
            )
            return 0 if matches else 1
        elif args.command == "profile-write":
            write_profile(Path(args.path), args.origin, args.slug)
        elif args.command == "profile-read":
            profile = load_profile(Path(args.path))
            print(profile["origin"])
            print(profile["workspace_slug"])
            print(profile["mcp_url"])
        elif args.command == "user-label":
            print(user_label(Path(args.path)))
        elif args.command == "redact":
            sys.stdout.write(redact(sys.stdin.read()))
        elif args.command == "validate-token":
            validate_token()
        elif args.command == "probe-request":
            print(json.dumps(plane_status_request(args.slug), separators=(",", ":")))
        elif args.command == "probe-valid":
            valid, detail = validate_plane_status_response(Path(args.path), args.slug)
            print(detail)
            return 0 if valid else 1
        elif args.command == "doctor-output":
            checks = parse_checks(Path(args.checks))
            healthy = not any(item["status"] == "fail" for item in checks)
            if args.human:
                for item in checks:
                    print(f"[{item['status'].upper()}] {item['name']}: {item['detail']}")
                print(f"Plane doctor result: {'healthy' if healthy else 'unhealthy'}.")
            else:
                print(
                    json.dumps(
                        {
                            "status": "healthy" if healthy else "unhealthy",
                            "origin": args.origin or None,
                            "workspace_slug": args.slug or None,
                            "authenticated_user": args.user or None,
                            "checks": checks,
                        },
                        separators=(",", ":"),
                    )
                )
            return 0 if healthy else 1
        elif args.command == "setup-output":
            payload = {
                "status": "configured",
                "origin": args.origin,
                "workspace_slug": args.slug,
                "authenticated_user": args.user,
                "mcp_configuration": args.mcp_state,
                "configuration_changed": args.mcp_state != "reused",
                "token_source": args.token_source,
                "token_persisted": False,
                "profile_path": args.profile_path,
                "new_task_required": True,
                "restart_note": "Open a new Codex task; restart Codex if it was launched before PLANE_API_TOKEN was available.",
            }
            if args.human:
                print(f"Plane MCP is configured for {args.origin}/{args.slug}.")
                print(f"MCP entry: {args.mcp_state}; token persisted: no.")
                print(payload["restart_note"])
            else:
                print(json.dumps(payload, separators=(",", ":")))
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as error:
        print(redact(str(error)), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
