from __future__ import annotations

import re

import psycopg
from psycopg import sql
from sqlalchemy.engine import make_url

from pharma_intel.config import get_settings

ROLE_PATTERN = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")


def validate_runtime_role(role: str) -> str:
    if not ROLE_PATTERN.fullmatch(role):
        raise ValueError("POSTGRES_RUNTIME_USER must be a lowercase PostgreSQL identifier")
    return role


def _psycopg_dsn(sqlalchemy_url: str) -> str:
    url = make_url(sqlalchemy_url)
    if url.get_backend_name() != "postgresql":
        raise RuntimeError("Database provisioning requires PostgreSQL")
    return url.set(drivername="postgresql").render_as_string(hide_password=False)


def provision() -> None:
    settings = get_settings()
    role = validate_runtime_role(settings.postgres_runtime_user)
    password = settings.postgres_runtime_password
    dynamic_credentials = settings.database_credentials_mode == "openbao_dynamic"
    if not dynamic_credentials and not password:
        raise RuntimeError("POSTGRES_RUNTIME_PASSWORD is required")

    with psycopg.connect(_psycopg_dsn(settings.database_url), autocommit=True) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_database(), current_user")
            database_name, migration_role = cursor.fetchone() or (None, None)
            if not isinstance(database_name, str) or not isinstance(migration_role, str):
                raise RuntimeError("Could not determine PostgreSQL migration identity")

            cursor.execute("SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = %s)", (role,))
            exists = bool((cursor.fetchone() or (False,))[0])
            role_identifier = sql.Identifier(role)
            password_literal = sql.Literal(password)
            if exists:
                if dynamic_credentials:
                    cursor.execute(
                        sql.SQL(
                            "ALTER ROLE {} WITH NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS"
                        ).format(role_identifier)
                    )
                else:
                    cursor.execute(
                        sql.SQL(
                            "ALTER ROLE {} WITH LOGIN PASSWORD {} NOSUPERUSER NOCREATEDB "
                            "NOCREATEROLE NOREPLICATION NOBYPASSRLS"
                        ).format(role_identifier, password_literal)
                    )
            else:
                if dynamic_credentials:
                    cursor.execute(
                        sql.SQL(
                            "CREATE ROLE {} WITH NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS"
                        ).format(role_identifier)
                    )
                else:
                    cursor.execute(
                        sql.SQL(
                            "CREATE ROLE {} WITH LOGIN PASSWORD {} NOSUPERUSER NOCREATEDB "
                            "NOCREATEROLE NOREPLICATION NOBYPASSRLS"
                        ).format(role_identifier, password_literal)
                    )

            cursor.execute(
                sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(sql.Identifier(database_name), role_identifier)
            )
            cursor.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(role_identifier))
            cursor.execute(
                sql.SQL("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {}").format(
                    role_identifier
                )
            )
            cursor.execute(
                sql.SQL("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {}").format(role_identifier)
            )
            cursor.execute(
                sql.SQL(
                    "ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA public "
                    "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {}"
                ).format(sql.Identifier(migration_role), role_identifier)
            )
            cursor.execute(
                sql.SQL(
                    "ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO {}"
                ).format(sql.Identifier(migration_role), role_identifier)
            )
            cursor.execute(
                "INSERT INTO platform_private.runtime_secrets (secret_name, secret_value) "
                "VALUES ('tenant_context', %s) "
                "ON CONFLICT (secret_name) DO UPDATE SET secret_value = EXCLUDED.secret_value",
                (settings.effective_tenant_context_signing_secret,),
            )
            cursor.execute(sql.SQL("REVOKE ALL ON SCHEMA platform_private FROM {}").format(role_identifier))
            cursor.execute(sql.SQL("ALTER ROLE {} SET statement_timeout = '60s'").format(role_identifier))
            cursor.execute(sql.SQL("ALTER ROLE {} SET lock_timeout = '10s'").format(role_identifier))


def run() -> None:
    provision()


if __name__ == "__main__":
    run()
