#!/usr/bin/env python3
"""Package the working tree and deploy it over an authenticated SSH session."""

from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import secrets
import shlex
import subprocess
import sys
import tarfile
import time
from urllib.parse import urlparse


REQUIRED_CONFIG = (
    "PLANE_TEST_HOST",
    "PLANE_TEST_SSH_USER",
    "PLANE_TEST_SSH_PASSWORD",
    "PLANE_TEST_SSH_HOST_KEY_SHA256",
    "PLANE_TEST_REMOTE_ROOT",
    "PLANE_TEST_COMPOSE_PROJECT",
    "PLANE_TEST_BASE_URL",
)

FIXTURE_DEFAULTS = {
    "PLANE_TEST_ADMIN_EMAIL": "admin@plane.test",
    "PLANE_TEST_MEMBER_EMAIL": "member@plane.test",
    "PLANE_TEST_GUEST_EMAIL": "guest@plane.test",
    "PLANE_TEST_WORKSPACE_NAME": "AI Test Workspace",
    "PLANE_TEST_WORKSPACE_SLUG": "ai-test",
    "PLANE_TEST_PROJECT_NAME": "AI Acceptance",
    "PLANE_TEST_PROJECT_IDENTIFIER": "AITEST",
    "PLANE_TEST_FIXTURE_VERSION": "1",
}
FIXTURE_PASSWORD_KEYS = (
    "PLANE_TEST_ADMIN_PASSWORD",
    "PLANE_TEST_MEMBER_PASSWORD",
    "PLANE_TEST_GUEST_PASSWORD",
)
FIXTURE_KEYS = (*FIXTURE_DEFAULTS, *FIXTURE_PASSWORD_KEYS)


def die(message: str, exit_code: int = 1) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(exit_code)


def load_config(path: Path) -> dict[str, str]:
    if not path.is_file():
        die(f"Configuration file does not exist: {path}", 2)

    values: dict[str, str] = {}
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            die(f"Invalid configuration line {line_number} in {path}", 2)
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        values[key] = value

    if not values.get("PLANE_TEST_HTTP_PORT") and values.get("PLANE_TEST_PUBLIC_PORT"):
        values["PLANE_TEST_HTTP_PORT"] = values["PLANE_TEST_PUBLIC_PORT"]
    if (
        not values.get("PLANE_TEST_BASE_URL")
        and values.get("PLANE_TEST_HOST")
        and values.get("PLANE_TEST_HTTP_PORT")
    ):
        values["PLANE_TEST_BASE_URL"] = (
            f"http://{values['PLANE_TEST_HOST']}:{values['PLANE_TEST_HTTP_PORT']}"
        )

    missing = [key for key in REQUIRED_CONFIG if not values.get(key)]
    if not values.get("PLANE_TEST_HTTP_PORT"):
        missing.append("PLANE_TEST_HTTP_PORT (or PLANE_TEST_PUBLIC_PORT)")
    if missing:
        die(f"Configuration is missing required keys: {', '.join(missing)}", 2)

    validate_config(values)
    return values


def prepare_config(path: Path) -> None:
    """Normalize stable test identities without exposing generated passwords."""
    config = load_config(path)
    managed = {key: config.get(key) or value for key, value in FIXTURE_DEFAULTS.items()}
    managed["PLANE_TEST_BASE_URL"] = "http://localhost:8000"
    for key in FIXTURE_PASSWORD_KEYS:
        managed[key] = config.get(key) or secrets.token_urlsafe(24)

    managed_keys = set(managed)
    retained_lines: list[str] = []
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        stripped = raw_line.strip()
        key = stripped.split("=", 1)[0].strip() if "=" in stripped else ""
        if key not in managed_keys:
            retained_lines.append(raw_line)
    while retained_lines and not retained_lines[-1].strip():
        retained_lines.pop()

    output_lines = [
        *retained_lines,
        "",
        "# Stable test identities and fixtures (managed by deploy-test.ps1).",
        *(f"{key}={value}" for key, value in managed.items()),
    ]
    temporary_path = path.with_name(f".{path.name}.tmp")
    temporary_path.write_text("\n".join(output_lines) + "\n", encoding="utf-8", newline="\n")
    try:
        os.chmod(temporary_path, 0o600)
    except OSError:
        pass
    os.replace(temporary_path, path)
    print("Normalized private test configuration fields: " + ", ".join(managed))


def parse_port(value: str, name: str) -> int:
    try:
        port = int(value)
    except ValueError:
        die(f"{name} must be an integer", 2)
    if not 1 <= port <= 65535:
        die(f"{name} must be between 1 and 65535", 2)
    return port


def validate_config(config: dict[str, str]) -> None:
    parse_port(config.get("PLANE_TEST_SSH_PORT", "22"), "PLANE_TEST_SSH_PORT")
    parse_port(config["PLANE_TEST_HTTP_PORT"], "PLANE_TEST_HTTP_PORT")
    parse_port(config.get("PLANE_TEST_HTTPS_PORT", "8443"), "PLANE_TEST_HTTPS_PORT")

    remote_root = PurePosixPath(config["PLANE_TEST_REMOTE_ROOT"])
    if not remote_root.is_absolute() or len(remote_root.parts) < 3 or ".." in remote_root.parts:
        die("PLANE_TEST_REMOTE_ROOT must be an absolute dedicated directory such as /opt/plane-test", 2)
    if not config["PLANE_TEST_COMPOSE_PROJECT"].startswith("plane-test"):
        die("PLANE_TEST_COMPOSE_PROJECT must start with 'plane-test'", 2)

    base_url = urlparse(config["PLANE_TEST_BASE_URL"])
    if base_url.scheme not in {"http", "https"} or not base_url.hostname or base_url.path not in {"", "/"}:
        die("PLANE_TEST_BASE_URL must be an HTTP(S) origin without a path", 2)
    fingerprint = config["PLANE_TEST_SSH_HOST_KEY_SHA256"]
    if not fingerprint.startswith("SHA256:") or len(fingerprint) != 50:
        die("PLANE_TEST_SSH_HOST_KEY_SHA256 must be an OpenSSH SHA256 fingerprint", 2)
    bootstrap_release = config.get("PLANE_TEST_BOOTSTRAP_RELEASE", "stable")
    if not bootstrap_release or any(
        character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
        for character in bootstrap_release
    ):
        die("PLANE_TEST_BOOTSTRAP_RELEASE is not a valid container image tag", 2)


def git_paths(repo: Path) -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    paths: list[Path] = []
    for raw_path in result.stdout.split(b"\0"):
        if not raw_path:
            continue
        relative = Path(os.fsdecode(raw_path))
        posix = relative.as_posix()
        parts = relative.parts
        if not parts or any(
            part in {".git", ".runtime", ".secrets", "node_modules", "runtime", "__pycache__"}
            for part in parts
        ):
            continue
        if relative.name == ".env" or relative.name.endswith((".pem", ".key", ".pfx", ".p12")):
            continue
        if posix == "scripts/test/test-environment.env":
            continue
        full_path = repo / relative
        if full_path.exists() or full_path.is_symlink():
            paths.append(relative)
    return sorted(set(paths), key=lambda item: item.as_posix())


def git_metadata(repo: Path) -> tuple[str, bool]:
    commit = subprocess.run(
        ["git", "rev-parse", "--short=12", "HEAD"], cwd=repo, check=True, text=True, capture_output=True
    ).stdout.strip()
    dirty = bool(
        subprocess.run(["git", "status", "--porcelain"], cwd=repo, check=True, capture_output=True).stdout
    )
    return commit, dirty


def create_package(repo: Path, output: Path, manifest_output: Path, dry_run: bool) -> None:
    repo = repo.resolve()
    if not (repo / ".git").exists() or not (repo / "docker-compose.yml").is_file():
        die(f"Not a Plane repository root: {repo}", 2)

    paths = git_paths(repo)
    commit, dirty = git_metadata(repo)
    manifest = {
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "commit": commit,
        "dirty": dirty,
        "file_count": len(paths),
    }
    if dry_run:
        print(f"Would package {len(paths)} files from commit {commit} (dirty={str(dirty).lower()}).")
        return

    output.parent.mkdir(parents=True, exist_ok=True)
    manifest_output.parent.mkdir(parents=True, exist_ok=True)
    manifest_bytes = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")
    with tarfile.open(output, mode="w:gz", format=tarfile.PAX_FORMAT) as archive:
        for relative in paths:
            archive.add(repo / relative, arcname=relative.as_posix(), recursive=False)
        info = tarfile.TarInfo(".plane-test-manifest.json")
        info.size = len(manifest_bytes)
        info.mtime = int(time.time())
        info.mode = 0o600
        archive.addfile(info, io.BytesIO(manifest_bytes))

    manifest["archive_sha256"] = hashlib.sha256(output.read_bytes()).hexdigest()
    manifest_output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Packaged {len(paths)} files from commit {commit} (dirty={str(dirty).lower()}).")


def connect(config: dict[str, str], runtime_root: Path):
    try:
        import paramiko
    except ImportError:
        die("Paramiko is unavailable. Run deploy-test.ps1 so it can bootstrap the private tool environment.", 3)

    ssh = paramiko.SSHClient()
    ssh_state_root = runtime_root.resolve() / "ssh"
    ssh_state_root.mkdir(parents=True, exist_ok=True)
    known_hosts = ssh_state_root / "known_hosts"
    if known_hosts.exists():
        ssh.load_host_keys(str(known_hosts))

    expected_fingerprint = config.get("PLANE_TEST_SSH_HOST_KEY_SHA256", "").strip()
    trust_on_first_use = config.get("PLANE_TEST_TRUST_ON_FIRST_USE", "0") == "1"

    class VerifiedHostKeyPolicy(paramiko.MissingHostKeyPolicy):
        def missing_host_key(self, client, hostname, key):
            actual = "SHA256:" + base64.b64encode(
                hashlib.sha256(key.asbytes()).digest()
            ).decode("ascii").rstrip("=")
            if expected_fingerprint and actual != expected_fingerprint:
                raise paramiko.SSHException(
                    "SSH server host key fingerprint does not match the configured fingerprint"
                )
            if not expected_fingerprint and not trust_on_first_use:
                raise paramiko.SSHException("SSH server host key is not trusted")
            client.get_host_keys().add(hostname, key.get_name(), key)

    ssh.set_missing_host_key_policy(VerifiedHostKeyPolicy())

    try:
        ssh.connect(
            hostname=config["PLANE_TEST_HOST"],
            port=parse_port(config.get("PLANE_TEST_SSH_PORT", "22"), "PLANE_TEST_SSH_PORT"),
            username=config["PLANE_TEST_SSH_USER"],
            password=config["PLANE_TEST_SSH_PASSWORD"],
            look_for_keys=False,
            allow_agent=False,
            timeout=20,
            banner_timeout=20,
            auth_timeout=20,
        )
        remote_key = ssh.get_transport().get_remote_server_key()
        actual_fingerprint = "SHA256:" + base64.b64encode(
            hashlib.sha256(remote_key.asbytes()).digest()
        ).decode("ascii").rstrip("=")
        if expected_fingerprint and actual_fingerprint != expected_fingerprint:
            ssh.close()
            die("SSH server host key fingerprint does not match the configured fingerprint", 4)
        if trust_on_first_use or expected_fingerprint:
            ssh.save_host_keys(str(known_hosts))
    except Exception as error:
        die(f"SSH connection failed: {type(error).__name__}: {error}", 4)
    return ssh


def tunnel(args: argparse.Namespace) -> None:
    import select
    import socket
    import socketserver
    import threading

    config = load_config(Path(args.config).resolve())
    ssh = connect(config, Path(args.runtime_root))
    transport = ssh.get_transport()
    if transport is None:
        die("SSH transport is unavailable", 4)

    remote_port = parse_port(config["PLANE_TEST_HTTP_PORT"], "PLANE_TEST_HTTP_PORT")

    class ForwardHandler(socketserver.BaseRequestHandler):
        def handle(self) -> None:
            try:
                channel = transport.open_channel(
                    "direct-tcpip",
                    ("127.0.0.1", remote_port),
                    self.request.getpeername(),
                )
            except Exception as error:
                print(f"Tunnel channel failed: {type(error).__name__}: {error}", file=sys.stderr)
                return
            if channel is None:
                return
            try:
                while True:
                    readable, _, _ = select.select([self.request, channel], [], [], 1.0)
                    if self.request in readable:
                        data = self.request.recv(65536)
                        if not data:
                            break
                        channel.sendall(data)
                    if channel in readable:
                        data = channel.recv(65536)
                        if not data:
                            break
                        self.request.sendall(data)
            finally:
                channel.close()
                self.request.close()

    class ForwardServer(socketserver.ThreadingTCPServer):
        daemon_threads = True
        allow_reuse_address = False

        def server_bind(self) -> None:
            if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            super().server_bind()

    try:
        with ForwardServer((args.bind_host, args.local_port), ForwardHandler) as server:
            print(
                f"SSH tunnel ready at http://{args.bind_host}:{args.local_port} -> remote Plane proxy.",
                flush=True,
            )
            server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    except OSError as error:
        die(f"Could not bind local tunnel port {args.local_port}: {error}", 6)
    finally:
        ssh.close()


def run_remote(ssh, command: str, timeout: int) -> int:
    _, stdout, stderr = ssh.exec_command(command, timeout=timeout, get_pty=False)
    channel = stdout.channel
    while not channel.exit_status_ready():
        if channel.recv_ready():
            sys.stdout.buffer.write(channel.recv(65536))
            sys.stdout.buffer.flush()
        if channel.recv_stderr_ready():
            sys.stderr.buffer.write(channel.recv_stderr(65536))
            sys.stderr.buffer.flush()
        time.sleep(0.05)
    while channel.recv_ready():
        sys.stdout.buffer.write(channel.recv(65536))
    while channel.recv_stderr_ready():
        sys.stderr.buffer.write(channel.recv_stderr(65536))
    return channel.recv_exit_status()


def deploy(args: argparse.Namespace) -> None:
    config = load_config(Path(args.config).resolve())
    archive = Path(args.archive).resolve()
    remote_script = Path(args.remote_script).resolve()
    if not archive.is_file() or not remote_script.is_file():
        die("Deployment archive or remote script is missing", 2)

    remote_root = config["PLANE_TEST_REMOTE_ROOT"].rstrip("/")
    incoming = f"{remote_root}/incoming"
    remote_archive = f"{incoming}/{args.release}.tar.gz"
    remote_runner = f"{incoming}/remote-deploy-{args.release}.sh"
    missing_fixture_keys = [key for key in FIXTURE_KEYS if not config.get(key)]
    if missing_fixture_keys:
        die(
            "Private configuration is missing test identity fields; run the prepare command first: "
            + ", ".join(missing_fixture_keys),
            2,
        )

    fixture_payload = json.dumps(
        {key: config[key] for key in FIXTURE_KEYS}, ensure_ascii=True, separators=(",", ":")
    ).encode("utf-8")
    remote_fixture_config = f"{incoming}/{args.release}.fixtures.json"
    ssh = connect(config, Path(args.runtime_root))
    fixture_uploaded = False
    try:
        mkdir_command = f"install -d -m 700 -- {shlex.quote(remote_root)} {shlex.quote(incoming)}"
        if run_remote(ssh, mkdir_command, 30) != 0:
            die("Could not create the dedicated remote Plane directories", 5)
        sftp = ssh.open_sftp()
        try:
            sftp.put(str(archive), remote_archive)
            sftp.chmod(remote_archive, 0o600)
            sftp.put(str(remote_script), remote_runner)
            sftp.chmod(remote_runner, 0o700)
            with sftp.file(remote_fixture_config, "wb") as fixture_file:
                fixture_file.write(fixture_payload)
            sftp.chmod(remote_fixture_config, 0o600)
            fixture_uploaded = True
        finally:
            sftp.close()

        values = [
            "bash",
            remote_runner,
            "--archive",
            remote_archive,
            "--release",
            args.release,
            "--root",
            remote_root,
            "--project",
            config["PLANE_TEST_COMPOSE_PROJECT"],
            "--http-port",
            config["PLANE_TEST_HTTP_PORT"],
            "--https-port",
            config.get("PLANE_TEST_HTTPS_PORT", "8443"),
            "--base-url",
            config["PLANE_TEST_BASE_URL"],
            "--services",
            args.services,
            "--keep",
            config.get("PLANE_TEST_KEEP_RELEASES", "3"),
            "--local-origins",
            config.get(
                "PLANE_TEST_LOCAL_ORIGINS",
                "http://localhost:3000,http://localhost:3001,http://localhost:3002",
            ),
            "--bootstrap-release",
            config.get("PLANE_TEST_BOOTSTRAP_RELEASE", "stable"),
            "--fixture-config",
            remote_fixture_config,
        ]
        command = " ".join(shlex.quote(value) for value in values)
        exit_code = run_remote(ssh, command, args.timeout)
        if exit_code != 0:
            die(f"Remote deployment failed with exit code {exit_code}", exit_code)
    finally:
        if fixture_uploaded:
            try:
                cleanup_sftp = ssh.open_sftp()
                try:
                    cleanup_sftp.remove(remote_fixture_config)
                finally:
                    cleanup_sftp.close()
            except OSError:
                pass
        ssh.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    package_parser = subparsers.add_parser("package")
    package_parser.add_argument("--repo", required=True)
    package_parser.add_argument("--output", required=True)
    package_parser.add_argument("--manifest", required=True)
    package_parser.add_argument("--dry-run", action="store_true")

    deploy_parser = subparsers.add_parser("deploy")
    deploy_parser.add_argument("--config", required=True)
    deploy_parser.add_argument("--archive", required=True)
    deploy_parser.add_argument("--remote-script", required=True)
    deploy_parser.add_argument("--release", required=True)
    deploy_parser.add_argument("--services", required=True)
    deploy_parser.add_argument("--runtime-root", required=True)
    deploy_parser.add_argument("--timeout", type=int, default=900)

    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--config", required=True)

    prepare_parser = subparsers.add_parser("prepare")
    prepare_parser.add_argument("--config", required=True)

    tunnel_parser = subparsers.add_parser("tunnel")
    tunnel_parser.add_argument("--config", required=True)
    tunnel_parser.add_argument("--bind-host", default="127.0.0.1")
    tunnel_parser.add_argument("--local-port", type=int, default=8000)
    tunnel_parser.add_argument("--runtime-root", required=True)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "package":
        create_package(
            Path(args.repo), Path(args.output), Path(args.manifest), bool(args.dry_run)
        )
    elif args.command == "deploy":
        deploy(args)
    elif args.command == "tunnel":
        tunnel(args)
    elif args.command == "validate":
        load_config(Path(args.config).resolve())
        print("Private test configuration is valid.")
    elif args.command == "prepare":
        prepare_config(Path(args.config).resolve())


if __name__ == "__main__":
    main()
