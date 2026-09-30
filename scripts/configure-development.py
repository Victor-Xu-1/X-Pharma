"""Create an independent, private development environment from the public template."""

from __future__ import annotations

import base64
import os
import secrets
from pathlib import Path

SECRET_FIELDS = (
    "POSTGRES_PASSWORD",
    "POSTGRES_RUNTIME_PASSWORD",
    "JWT_SECRET",
    "INTERNAL_SERVICE_JWT_SECRET",
    "TENANT_CONTEXT_SIGNING_SECRET",
    "API_KEY_HASH_SALT",
    "MCP_CURSOR_SIGNING_SECRET",
    "MCP_CORRELATION_HMAC_SECRET",
    "BILLING_STATEMENT_SIGNING_SECRET",
    "EXPORT_MANIFEST_SIGNING_SECRET",
    "PARSER_SERVICE_TOKEN",
    "OCR_SERVICE_TOKEN",
)


def render_environment(template: str) -> str:
    lines = template.splitlines()
    defaults = dict(line.split("=", 1) for line in lines if line and not line.startswith("#") and "=" in line)
    missing = set(SECRET_FIELDS) - defaults.keys()
    if missing:
        raise ValueError(f"Environment template is missing required fields: {', '.join(sorted(missing))}")
    if defaults.get("APP_ENV") != "development":
        raise ValueError("This command only creates development environments")

    values = {key: secrets.token_hex(32) for key in SECRET_FIELDS}
    values["LLM_CREDENTIALS_ENCRYPTION_KEY"] = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()
    database_url = (
        f"postgresql+psycopg://{defaults['POSTGRES_RUNTIME_USER']}:{values['POSTGRES_RUNTIME_PASSWORD']}"
        f"@postgres:5432/{defaults['POSTGRES_DB']}"
    )
    values.update(DATABASE_URL=database_url, RUNTIME_DATABASE_URL=database_url)
    rendered = []
    for line in lines:
        key = line.split("=", 1)[0]
        rendered.append(f"{key}={values[key]}" if not line.startswith("#") and key in values else line)
    return "\n".join(rendered) + "\n"


def configure(root: Path) -> Path:
    target = root / ".env"
    if target.exists() or target.is_symlink():
        raise FileExistsError(".env already exists; configuration was preserved")
    rendered = render_environment((root / ".env.example").read_text(encoding="utf-8"))
    (root / "data" / "sources" / "empty").mkdir(mode=0o750, parents=True, exist_ok=True)
    descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(rendered)
    return target


def main() -> None:
    try:
        target = configure(Path(__file__).resolve().parents[1])
    except (OSError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc
    print(f"Created private development configuration: {target.name}")
    print("AI calls remain disabled. Configure authorized sources and bootstrap your own account before use.")


if __name__ == "__main__":
    main()
