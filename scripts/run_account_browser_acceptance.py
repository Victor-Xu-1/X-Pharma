from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.error import URLError
from urllib.request import urlopen

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from pharma_intel.models import Base, Tenant, User, UserRole
from pharma_intel.security import hash_password

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "apps" / "web"
PROJECTS = ("desktop-1440", "desktop-1920", "tablet-1024", "mobile-390")


def seed(database: Path, prefix: str, password: str) -> None:
    engine = create_engine(f"sqlite:///{database}")
    try:
        Base.metadata.create_all(engine)
        with Session(engine) as session:
            tenant = Tenant(slug="account-browser-acceptance", name="Disposable account acceptance")
            session.add(tenant)
            session.flush()
            for project in PROJECTS:
                email = f"{prefix}-{project}@example.test"
                session.add(
                    User(
                        tenant_id=tenant.id,
                        email=email,
                        normalized_email=email,
                        display_name="Acceptance administrator",
                        role=UserRole.ADMIN,
                        password_hash=hash_password(password),
                    )
                )
            session.commit()
    finally:
        engine.dispose()


def environment(state: Path, origin: str, port: int, prefix: str, password: str) -> dict[str, str]:
    values = dict(os.environ)
    values.update(
        {
            "APP_ENV": "test",
            "APP_HOST": "127.0.0.1",
            "APP_PORT": str(port),
            "DATABASE_URL": f"sqlite:///{state / 'accounts.db'}",
            "WEB_ROOT": str(WEB / "dist"),
            "PUBLIC_BASE_URL": origin,
            "MCP_AUTH_ISSUER_URL": origin,
            "MCP_RESOURCE_SERVER_URL": f"{origin}/mcp",
            "AGENT_API_BASE_URL": origin,
            "HUMAN_AUTH_MODE": "local",
            "HUMAN_SELF_REGISTRATION_ENABLED": "true",
            "SEARCH_BACKEND": "database",
            "SEARCH_PROJECTION_ENABLED": "false",
            "OPENSEARCH_MAX_RETRIES": "0",
            "OPENSEARCH_REQUEST_TIMEOUT_SECONDS": "1",
            "TEMPORAL_ENABLED": "false",
            "OTEL_ENABLED": "false",
            "AI_GOVERNANCE_ENABLED": "false",
            "MALWARE_SCAN_ENABLED": "false",
            "PARSER_SERVICE_ENABLED": "false",
            "OBJECT_STORE_ROOT": str(state / "objects"),
            "MARKDOWN_EXPORT_ROOT": str(state / "wiki"),
            "SOURCE_ROOTS": str(state / "sources"),
            "E2E_BASE_URL": origin,
            "E2E_EMAIL_PREFIX": prefix,
            "E2E_PASSWORD": password,
        }
    )
    for key in ("JWT_SECRET", "INTERNAL_SERVICE_JWT_SECRET", "TENANT_CONTEXT_SIGNING_SECRET", "API_KEY_HASH_SALT"):
        values[key] = secrets.token_urlsafe(48)
    return values


def ready(process: subprocess.Popen[bytes], origin: str) -> None:
    for _ in range(50):
        if process.poll() is not None:
            raise RuntimeError("Disposable account gateway exited during startup")
        try:
            with urlopen(f"{origin}/health/live", timeout=1) as response:  # noqa: S310  # Generated loopback origin only.
                if response.status == 200:
                    return
        except (URLError, TimeoutError):
            pass
        time.sleep(0.2)
    raise RuntimeError("Disposable account gateway readiness timed out")


def main() -> None:
    parser = argparse.ArgumentParser(description="Real Chrome registration/logout acceptance in an isolated database")
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    if not (WEB / "dist" / "index.html").is_file():
        raise RuntimeError("Build apps/web before running account browser acceptance")
    manager = json.loads((WEB / "package.json").read_text())["packageManager"]
    if not isinstance(manager, str) or re.fullmatch(r"pnpm@[0-9]+\.[0-9]+\.[0-9]+", manager) is None:
        raise RuntimeError("apps/web/package.json must pin the pnpm version")
    corepack = shutil.which("corepack")
    if corepack is None:
        raise RuntimeError("Corepack is required for browser acceptance")
    with TemporaryDirectory(prefix="x-pharma-account-browser-") as temporary:
        state = Path(temporary)
        for name in ("sources", "objects", "wiki"):
            (state / name).mkdir()
        prefix, password = f"e2e-{secrets.token_hex(12)}", secrets.token_urlsafe(48)
        seed(state / "accounts.db", prefix, password)
        with socket.socket() as port_probe:
            port_probe.bind(("127.0.0.1", 0))
            port = port_probe.getsockname()[1]
        origin = f"http://127.0.0.1:{port}"
        child_environment = environment(state, origin, port, prefix, password)
        with (state / "gateway.log").open("wb") as log:
            process = subprocess.Popen(  # noqa: S603  # Fixed interpreter and module; no shell or caller command.
                [sys.executable, "-c", "from pharma_intel.gateway import run; run()"],
                cwd=state,
                env=child_environment,
                stdout=log,
                stderr=log,
            )
            try:
                ready(process, origin)
                subprocess.run(  # noqa: S603  # Resolved executable, validated pin and fixed argument boundaries.
                    [
                        corepack,
                        manager,
                        "--dir",
                        str(WEB),
                        "exec",
                        "playwright",
                        "test",
                        "--config",
                        "playwright.accounts.config.ts",
                        "--output",
                        str(state / "browser-output"),
                    ],
                    cwd=ROOT,
                    env=child_environment,
                    timeout=300,
                    check=True,
                )
            except Exception:
                diagnostic = (state / "gateway.log").read_text(errors="replace")[-6000:]
                for key in (
                    "JWT_SECRET",
                    "INTERNAL_SERVICE_JWT_SECRET",
                    "TENANT_CONTEXT_SIGNING_SECRET",
                    "API_KEY_HASH_SALT",
                    "E2E_PASSWORD",
                ):
                    diagnostic = diagnostic.replace(child_environment[key], "[redacted]")
                sys.stderr.write(diagnostic)
                raise
            finally:
                process.terminate()
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)
        report = {
            "schema": "x-pharma.account-browser-acceptance.v1",
            "passed": True,
            "projects": list(PROJECTS),
            "isolated_database": True,
        }
        if arguments.output:
            arguments.output.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report))


if __name__ == "__main__":
    main()
