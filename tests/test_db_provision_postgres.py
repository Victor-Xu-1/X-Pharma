from __future__ import annotations

import os

import psycopg
import pytest
from sqlalchemy.engine import make_url

from pharma_intel import db_provision
from pharma_intel.config import Settings
from tests.support.postgres_safety import require_disposable_postgres_url

pytestmark = pytest.mark.integration


def _psycopg_url(url: str) -> str:
    parsed = make_url(url)
    return parsed.set(drivername="postgresql").render_as_string(hide_password=False)


def test_openbao_dynamic_runtime_role_is_nologin_least_privilege_group(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_url = os.environ.get("TEST_DB_PROVISION_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_DB_PROVISION_DATABASE_URL is not configured")
    require_disposable_postgres_url(database_url, "TEST_DB_PROVISION_DATABASE_URL")
    role = "pharma_dynamic_test"
    settings = Settings(
        database_url=database_url,
        database_credentials_mode="openbao_dynamic",
        postgres_runtime_user=role,
        tenant_context_signing_secret="integration-tenant-context-secret",  # noqa: S106
    )
    monkeypatch.setattr(db_provision, "get_settings", lambda: settings)

    with psycopg.connect(_psycopg_url(database_url), autocommit=True) as connection:

        def drop_test_role() -> None:
            exists = connection.execute(
                "SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = %s)",
                (role,),
            ).fetchone()
            if exists == (True,):
                connection.execute(f'DROP OWNED BY "{role}"', prepare=False)
                connection.execute(f'DROP ROLE "{role}"', prepare=False)

        drop_test_role()
        try:
            db_provision.provision()

            attributes = connection.execute(
                "SELECT rolcanlogin, rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls "
                "FROM pg_roles WHERE rolname = %s",
                (role,),
            ).fetchone()
            table_access = connection.execute(
                "SELECT has_table_privilege(%s, 'public.tenants', 'SELECT,INSERT,UPDATE,DELETE')",
                (role,),
            ).fetchone()

            assert attributes == (False, False, False, False, False, False)
            assert table_access == (True,)
        finally:
            drop_test_role()
