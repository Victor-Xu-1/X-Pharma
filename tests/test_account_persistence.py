import secrets
from uuid import uuid4

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from pharma_intel.accounts.identity import create_account
from pharma_intel.models import Base, OrganizationMembership, Tenant, User, UserRole


def test_new_organization_identity_and_member_can_commit_atomically_with_real_foreign_keys() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql("PRAGMA foreign_keys = ON")
        Base.metadata.create_all(engine)
        with Session(engine) as session:
            tenant = Tenant(id=str(uuid4()), slug="atomic-account", name="Atomic organization")
            account = create_account(
                tenant_id=tenant.id,
                email="atomic@example.test",
                normalized_email="atomic@example.test",
                display_name="Atomic identity",
                password_hash=secrets.token_urlsafe(32),
                role=UserRole.ANALYST,
            )
            session.add_all([tenant, account])
            session.commit()
            assert session.scalar(select(User.id)) == account.id
            member = session.get(OrganizationMembership, (tenant.id, account.id))
            assert member is not None and member.role == UserRole.ANALYST
    finally:
        engine.dispose()
