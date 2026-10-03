from __future__ import annotations

import hashlib
import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session, sessionmaker

from pharma_intel.accounts.identity import create_account
from pharma_intel.commercial.accounting import (
    BillingStatementCommand,
    CommercialAccountingConflict,
    CommercialAccountingService,
    ReversalCommand,
    UsageAdjustmentCommand,
)
from pharma_intel.commercial.admin import CommercialAdminService, ProvisionClientCommand
from pharma_intel.commercial.billing import (
    BillingProviderReceipt,
    BillingStatementSigner,
    SignedBillingManifest,
)
from pharma_intel.commercial.billing_consumer import BillingProviderConsumer
from pharma_intel.commercial.billing_operations import BillingOperationsService
from pharma_intel.commercial.cursor import SignedCursorCodec
from pharma_intel.commercial.disputes import (
    BillingDisputeService,
    CreateBillingDisputeCommand,
    TransitionBillingDisputeCommand,
)
from pharma_intel.commercial.exports import (
    CommercialExportService,
    CreateExportCommand,
    ExportManifestSigner,
    default_export_field_policy,
)
from pharma_intel.commercial.operations import CommercialOperationsService
from pharma_intel.commercial.service import (
    CommercialAccessDenied,
    CommercialUsageService,
    InsufficientCredits,
    ReservationConflict,
    ReserveCommand,
    SettleCommand,
)
from pharma_intel.config import Settings
from pharma_intel.db import set_tenant_context
from pharma_intel.governance.lifecycle import DataLifecycleService
from pharma_intel.models import (
    AgentClient,
    AgentClientSubject,
    BillingAccount,
    BillingAdjustment,
    BillingDispute,
    BillingDisputeEvent,
    BillingPeriodStatement,
    CommercialCoverageRecord,
    CommercialExportPolicy,
    CommercialPolicyEvent,
    CommercialReconciliationRun,
    CommercialRiskCase,
    CommercialRiskPolicy,
    DataExportJob,
    DataLifecycleEvent,
    DataSource,
    DataSourceType,
    Entity,
    EntityType,
    InvoiceReference,
    ProjectionDelivery,
    ProjectionDeliveryState,
    RateCardVersion,
    SourceAsset,
    SourceAssetState,
    SourceVersion,
    Tenant,
    UserRole,
)
from pharma_intel.object_store import FileSystemObjectStore
from pharma_intel.security import Principal
from tests.support.commercial import seed_commercial_contract
from tests.support.postgres_safety import require_disposable_postgres_url

POSTGRES_BILLING_SIGNING_SECRET = "postgres-billing-signing-secret-with-32-bytes"  # noqa: S105


class _PostgresBillingAdapter:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.calls: list[str] = []

    def create_invoice(
        self,
        manifest: SignedBillingManifest,
        *,
        idempotency_key: str,
        customer_reference: str,
    ) -> BillingProviderReceipt:
        with self._lock:
            self.calls.append(idempotency_key)
        assert customer_reference == "CUSTOMER-POSTGRES-1"
        return BillingProviderReceipt(
            "approved-erp",
            "INV-POSTGRES-BILLING-1",
            "issued",
            Decimal("12.50"),
            "CNY",
            {"provider_request_id": f"request-{manifest.sha256[:16]}"},
        )


@pytest.mark.integration
def test_postgres_data_lifecycle_purge_is_rls_isolated_and_append_only(tmp_path: Path) -> None:
    database_url = os.getenv("TEST_COMMERCIAL_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_COMMERCIAL_DATABASE_URL is not configured")
    engine = create_engine(database_url, pool_pre_ping=True)
    tenant_id = str(uuid.uuid4())
    other_tenant_id = str(uuid.uuid4())
    store = FileSystemObjectStore(tmp_path / "objects")

    with Session(engine, expire_on_commit=False) as session:
        set_tenant_context(session, tenant_id)
        tenant = Tenant(id=tenant_id, slug=f"lifecycle-{tenant_id}", name="Lifecycle PostgreSQL")
        user = create_account(
            tenant_id=tenant_id,
            email=f"lifecycle-{tenant_id}@example.test",
            normalized_email=f"lifecycle-{tenant_id}@example.test",
            display_name="Lifecycle Administrator",
            password_hash="not-used",  # noqa: S106
            role=UserRole.ADMIN,
        )
        session.add_all([tenant, user])
        session.commit()
        contract = seed_commercial_contract(
            session,
            tenant,
            billing_classes={"export.data": ("data.export", 100)},
        )
        job_id = str(uuid.uuid4())
        artifact = b'{"id":"postgres-record"}\n'
        manifest = b'{"schema":"postgres-manifest"}'
        artifact_sha = hashlib.sha256(artifact).hexdigest()
        manifest_sha = hashlib.sha256(manifest).hexdigest()
        stored_artifact = store.put_bytes(tenant.id, f"exports-{job_id}", artifact, artifact_sha, ".jsonl")
        stored_manifest = store.put_bytes(
            tenant.id,
            f"export-manifests-{job_id}",
            manifest,
            manifest_sha,
            ".json",
        )
        completed_at = datetime.now(UTC) - timedelta(hours=2)
        job = DataExportJob(
            id=job_id,
            tenant_id=tenant.id,
            billing_account_id=contract.subscription.billing_account_id,
            subscription_id=contract.subscription.id,
            agent_client_id=contract.client.id,
            actor_type="agent",
            subject_id="postgres-lifecycle-agent",
            idempotency_key="postgres-lifecycle-export-1",
            request_sha256="a" * 64,
            dataset="entities",
            license_policy_version="test-v1",
            license_policy_sha256="b" * 64,
            license_attribution="PostgreSQL lifecycle test",
            export_format="jsonl",
            filters_json={},
            fields_json=["id"],
            max_records=10,
            max_billable_units=Decimal("10"),
            state="completed",
            approval_required=False,
            workflow_id=f"data-export-{job_id}",
            record_count=1,
            artifact_uri=stored_artifact.uri,
            artifact_sha256=artifact_sha,
            artifact_bytes=len(artifact),
            manifest_uri=stored_manifest.uri,
            manifest_sha256=manifest_sha,
            manifest_signature="postgres-signature",
            manifest_key_id="postgres-key",
            requested_at=completed_at,
            completed_at=completed_at,
            expires_at=completed_at + timedelta(minutes=5),
        )
        session.add(job)
        session.commit()
        principal = Principal(tenant.id, user.id, "user", frozenset({"commercial:read", "commercial:write"}))
        lifecycle = DataLifecycleService(session, store)
        lifecycle.upsert_export_policy(
            principal,
            retention_seconds=300,
            legal_basis="PostgreSQL integration retention policy",
            geographic_scope=["CN"],
            active=True,
            request_id="postgres-lifecycle-policy",
        )
        outcome = lifecycle.purge_export(
            principal,
            job.id,
            idempotency_key="postgres-lifecycle-purge-1",
            reason="approved integration-test purge",
            request_id="postgres-lifecycle-purge",
        )
        assert outcome.event.outcome == "succeeded"
        source = DataSource(
            tenant_id=tenant.id,
            name=f"PostgreSQL source {tenant.id}",
            source_type=DataSourceType.FOLDER,
            root_uri=f"/postgres-source/{tenant.id}",
            owner="Research Operations",
            authorization_scopes=["contract:postgres-lifecycle"],
            dataset_key="literature",
        )
        session.add(source)
        session.flush()
        source_asset = SourceAsset(
            tenant_id=tenant.id,
            data_source_id=source.id,
            logical_path="withdrawn.md",
            source_uri="file:///postgres-source/withdrawn.md",
            file_name="withdrawn.md",
            extension=".md",
            processing_mode="parse",
            state=SourceAssetState.MISSING,
            first_seen_at=completed_at - timedelta(days=1),
            last_seen_at=completed_at,
            missing_since=completed_at,
        )
        session.add(source_asset)
        session.flush()
        raw_source = b"PostgreSQL source lifecycle evidence"
        raw_source_sha = hashlib.sha256(raw_source).hexdigest()
        stored_source = store.put_bytes(tenant.id, "raw", raw_source, raw_source_sha, ".md")
        source_version = SourceVersion(
            tenant_id=tenant.id,
            source_asset_id=source_asset.id,
            version_number=1,
            content_sha256=raw_source_sha,
            size_bytes=len(raw_source),
            raw_object_uri=stored_source.uri,
        )
        session.add(source_version)
        session.flush()
        source_asset.current_version_id = source_version.id
        session.commit()
        lifecycle.upsert_source_policy(
            principal,
            retention_seconds=300,
            legal_basis="PostgreSQL source lifecycle policy",
            geographic_scope=["CN"],
            active=True,
            request_id="postgres-source-lifecycle-policy",
        )
        source_outcome = lifecycle.purge_source_asset(
            principal,
            source_asset.id,
            idempotency_key="postgres-source-lifecycle-purge-1",
            reason="approved source lifecycle purge",
            request_id="postgres-source-lifecycle-purge",
        )
        assert source_outcome.event.outcome == "succeeded"
        session.refresh(source_asset)
        assert source_asset.state == SourceAssetState.DELETED
        reauthorized = lifecycle.reauthorize_source_asset(
            principal,
            source_asset.id,
            idempotency_key="postgres-source-reauthorize-1",
            reason="approved source path reauthorization",
            request_id="postgres-source-reauthorize",
        )
        assert reauthorized.event.action == "reauthorize"
        assert reauthorized.event.outcome == "succeeded"
        reauthorized_asset = session.get(SourceAsset, source_asset.id, populate_existing=True)
        assert reauthorized_asset is not None
        assert reauthorized_asset.state == SourceAssetState.MISSING

        restored_source = store.put_bytes(tenant.id, "raw", raw_source, raw_source_sha, ".md")
        restored_version = SourceVersion(
            tenant_id=tenant.id,
            source_asset_id=source_asset.id,
            version_number=2,
            content_sha256=raw_source_sha,
            size_bytes=len(raw_source),
            raw_object_uri=restored_source.uri,
        )
        session.add(restored_version)
        session.flush()
        source_asset.current_version_id = restored_version.id
        source_asset.state = SourceAssetState.ACTIVE
        session.commit()
        assert source_version.content_sha256 == restored_version.content_sha256
        assert source_version.id != restored_version.id
        event_id = reauthorized.event.id

    with Session(engine) as immutable_session:
        set_tenant_context(immutable_session, tenant_id)
        event = immutable_session.get(DataLifecycleEvent, event_id)
        assert event is not None
        event.reason = "tampered"
        with pytest.raises(DBAPIError, match="append-only"):
            immutable_session.commit()
        immutable_session.rollback()

    with Session(engine) as wrong_tenant_session:
        set_tenant_context(wrong_tenant_session, other_tenant_id)
        assert wrong_tenant_session.get(DataLifecycleEvent, event_id) is None
    engine.dispose()


@pytest.fixture(autouse=True)
def _guard_commercial_test_database() -> None:
    database_url = os.getenv("TEST_COMMERCIAL_DATABASE_URL")
    if database_url:
        require_disposable_postgres_url(database_url, "TEST_COMMERCIAL_DATABASE_URL")


@pytest.mark.integration
def test_postgres_billing_consumer_claims_once_and_keeps_delivery_rls_isolated() -> None:
    database_url = os.getenv("TEST_COMMERCIAL_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_COMMERCIAL_DATABASE_URL is not configured")
    engine = create_engine(database_url, pool_pre_ping=True)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    tenant_id = str(uuid.uuid4())
    with Session(engine, expire_on_commit=False) as setup_session:
        tenant = Tenant(id=tenant_id, slug=f"billing-{uuid.uuid4()}", name="Billing Consumer Test")
        set_tenant_context(setup_session, tenant.id)
        setup_session.add(tenant)
        setup_session.commit()
        contract = seed_commercial_contract(setup_session, tenant)
        account = setup_session.get(BillingAccount, contract.subscription.billing_account_id)
        assert account is not None
        account.external_customer_reference = "CUSTOMER-POSTGRES-1"
        setup_session.commit()
        now = datetime.now(UTC)
        statement = CommercialAccountingService(
            setup_session,
            tenant,
            actor_id="FIN-POSTGRES-BILLING",
            statement_signer=BillingStatementSigner(
                POSTGRES_BILLING_SIGNING_SECRET,
                key_id="postgres-billing-v1",
            ),
        ).create_statement(
            BillingStatementCommand(
                "test-subscription",
                f"statement-{uuid.uuid4()}",
                now - timedelta(hours=1),
                now - timedelta(seconds=1),
                1,
                f"postgres-billing-{uuid.uuid4()}",
            ),
            now=now,
        )
        statement_id = statement.id

    settings = Settings(
        _env_file=None,
        internal_service_jwt_secret="postgres-internal-test-secret-with-32-bytes",  # noqa: S106
        billing_statement_signing_secret=POSTGRES_BILLING_SIGNING_SECRET,
        billing_statement_signing_key_id="postgres-billing-v1",
        billing_provider_enabled=True,
        billing_provider_name="approved-erp",
    )
    adapter = _PostgresBillingAdapter()
    workers = [
        BillingProviderConsumer(factory, adapter, settings, worker_id=f"postgres-billing-{index}") for index in range(2)
    ]
    barrier = threading.Barrier(2)

    def drain(consumer: BillingProviderConsumer) -> int:
        barrier.wait(timeout=10)
        return consumer.drain_once().succeeded

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(drain, workers))

    assert sum(outcomes) == 1
    assert len(adapter.calls) == 1
    assert adapter.calls[0].startswith(f"statement:{statement_id}:")
    with Session(engine) as verification_session:
        set_tenant_context(verification_session, tenant_id)
        invoice = verification_session.scalar(
            select(InvoiceReference).where(InvoiceReference.statement_id == statement_id)
        )
        delivery = verification_session.scalar(select(ProjectionDelivery))
        assert invoice is not None
        assert invoice.external_invoice_id == "INV-POSTGRES-BILLING-1"
        assert delivery is not None
        assert delivery.state == ProjectionDeliveryState.SUCCEEDED
        assert (
            verification_session.scalar(select(BillingPeriodStatement).where(BillingPeriodStatement.id == statement_id))
            is not None
        )
        billing_operations = BillingOperationsService(
            verification_session,
            Principal(tenant_id, "postgres-billing-operator", "user", frozenset({"commercial:read"})),
        )
        accounts = billing_operations.list_accounts()
        assert accounts[0]["statement_count"] == 1
        assert accounts[0]["invoice_count"] == 1
        assert accounts[0]["unresolved_statement_count"] == 0
        assert accounts[0]["external_customer_reference_masked"].endswith("ES-1")
        deliveries = billing_operations.list_deliveries(state="succeeded")
        assert len(deliveries) == 1
        assert deliveries[0]["external_invoice_id"] == "INV-POSTGRES-BILLING-1"
    with Session(engine) as wrong_tenant_session:
        wrong_tenant_id = str(uuid.uuid4())
        set_tenant_context(wrong_tenant_session, wrong_tenant_id)
        assert wrong_tenant_session.scalar(select(InvoiceReference).limit(1)) is None
        assert wrong_tenant_session.scalar(select(ProjectionDelivery).limit(1)) is None
        assert (
            BillingOperationsService(
                wrong_tenant_session,
                Principal(wrong_tenant_id, "wrong-tenant", "user", frozenset({"commercial:read"})),
            ).list_accounts()
            == []
        )
    engine.dispose()


@pytest.mark.integration
def test_postgres_billing_dispute_credit_is_rls_isolated_and_event_history_is_immutable() -> None:
    database_url = os.getenv("TEST_COMMERCIAL_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_COMMERCIAL_DATABASE_URL is not configured")
    engine = create_engine(database_url, pool_pre_ping=True)
    tenant_id = str(uuid.uuid4())
    with Session(engine, expire_on_commit=False) as session:
        tenant = Tenant(id=tenant_id, slug=f"dispute-{uuid.uuid4()}", name="Billing Dispute Test")
        set_tenant_context(session, tenant_id)
        session.add(tenant)
        session.commit()
        contract = seed_commercial_contract(session, tenant, granted_units=Decimal("100"))
        accounting = CommercialAccountingService(
            session,
            tenant,
            actor_id="postgres-dispute-seed",
            statement_signer=BillingStatementSigner(
                POSTGRES_BILLING_SIGNING_SECRET,
                key_id="postgres-billing-v1",
            ),
        )
        accounting.adjust_usage(
            UsageAdjustmentCommand(
                contract.subscription.subscription_key,
                f"postgres.dispute.seed.{uuid.uuid4()}",
                "5",
                "Seed usage for PostgreSQL dispute credit",
                f"postgres-dispute-seed-{uuid.uuid4()}",
            )
        )
        now = datetime.now(UTC)
        statement = accounting.create_statement(
            BillingStatementCommand(
                contract.subscription.subscription_key,
                f"postgres.dispute.statement.{uuid.uuid4()}",
                now - timedelta(hours=1),
                now,
                1,
                f"postgres-dispute-statement-{uuid.uuid4()}",
            ),
            now=now,
        )
        service = BillingDisputeService(
            session,
            Principal(tenant_id, "postgres-finance", "user", frozenset({"commercial:read", "commercial:write"})),
        )
        dispute = service.create(
            CreateBillingDisputeCommand(
                dispute_key=f"postgres.dispute.{uuid.uuid4()}",
                statement_id=statement.id,
                invoice_reference_id=None,
                category="usage",
                disputed_units="2",
                subject="PostgreSQL metering dispute",
                description="Validate tenant isolation and immutable dispute history.",
            ),
            request_id=f"postgres-dispute-open-{uuid.uuid4()}",
            now=now,
        )
        investigated = service.transition(
            dispute["id"],
            TransitionBillingDisputeCommand(
                operation_key=f"postgres.dispute.investigate.{uuid.uuid4()}",
                expected_version=1,
                action="investigate",
                notes="Finance accepted the PostgreSQL dispute case.",
            ),
            request_id=f"postgres-dispute-investigate-{uuid.uuid4()}",
            now=now + timedelta(minutes=1),
        )
        resolved = service.transition(
            dispute["id"],
            TransitionBillingDisputeCommand(
                operation_key=f"postgres.dispute.resolve.{uuid.uuid4()}",
                expected_version=investigated["version"],
                action="resolve_credit",
                notes="PostgreSQL accounting review approved one credit unit.",
                adjustment_key=f"postgres.dispute.credit.{uuid.uuid4()}",
                credit_units="1",
            ),
            request_id=f"postgres-dispute-credit-{uuid.uuid4()}",
            now=now + timedelta(minutes=2),
        )
        assert resolved["status"] == "resolved"
        session.refresh(contract.subscription)
        assert contract.subscription.consumed_units == Decimal("4.00000000")
        event = session.scalar(select(BillingDisputeEvent).where(BillingDisputeEvent.dispute_id == dispute["id"]))
        assert event is not None
        event.note = "tamper"
        with pytest.raises(DBAPIError):
            session.commit()
        session.rollback()

    with Session(engine) as wrong_tenant_session:
        set_tenant_context(wrong_tenant_session, str(uuid.uuid4()))
        assert wrong_tenant_session.scalar(select(BillingDispute).where(BillingDispute.id == dispute["id"])) is None
        assert wrong_tenant_session.scalar(select(BillingDisputeEvent).limit(1)) is None
    engine.dispose()


@pytest.mark.integration
def test_postgres_export_is_rls_isolated_and_serializes_account_daily_allocation(tmp_path: Path) -> None:
    database_url = os.getenv("TEST_COMMERCIAL_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_COMMERCIAL_DATABASE_URL is not configured")
    engine = create_engine(database_url, pool_pre_ping=True)
    tenant_id = str(uuid.uuid4())
    tenant_slug = f"export-{uuid.uuid4()}"
    with Session(engine, expire_on_commit=False) as setup_session:
        tenant = Tenant(id=tenant_id, slug=tenant_slug, name="Commercial Export Test")
        set_tenant_context(setup_session, tenant_id)
        setup_session.add(tenant)
        setup_session.commit()
        contract = seed_commercial_contract(
            setup_session,
            tenant,
            billing_classes={"export.data": ("data.export", 5000)},
            granted_units=Decimal("1000"),
            subject_id=f"export-subject-{uuid.uuid4()}",
            oauth_client_id=f"export-client-{uuid.uuid4()}",
            max_response_bytes=10_000_000,
        )
        setup_session.add_all(
            Entity(
                tenant_id=tenant_id,
                entity_type=EntityType.TARGET,
                name=name,
                normalized_name=name.casefold(),
            )
            for name in ("EGFR", "KRAS", "BRAF")
        )
        setup_session.commit()
        admin = CommercialAdminService(setup_session, tenant, actor_id="export-test-admin")
        related = admin.provision_client(
            ProvisionClientCommand(
                client_key=f"related-export-{uuid.uuid4()}",
                oauth_client_id=f"related-export-client-{uuid.uuid4()}",
                display_name="Related Export Client",
                actor_type="api_key",
                subject_id=f"related-export-subject-{uuid.uuid4()}",
                account_key="test-account",
                account_name="Test Billing Account",
                subscription_key=f"related-export-subscription-{uuid.uuid4()}",
                rate_card_key="test-plan",
                rate_card_revision=1,
                created_by="export-test-admin",
                export_field_policy=default_export_field_policy(policy_version="test-v1"),
                max_response_bytes=10_000_000,
            )
        )
        admin.grant_credit(
            related.subscription_key,
            Decimal("1000"),
            external_reference=f"export-credit-{uuid.uuid4()}",
            reason="PostgreSQL export concurrency test",
        )
        related_client = setup_session.get(AgentClient, related.agent_client_id)
        assert related_client is not None
        policy = setup_session.scalar(
            select(CommercialExportPolicy).where(
                CommercialExportPolicy.billing_account_id == related.billing_account_id
            )
        )
        assert policy is not None
        policy.daily_record_limit = 5
        setup_session.commit()
        related_binding = setup_session.scalar(
            select(AgentClientSubject).where(AgentClientSubject.agent_client_id == related.agent_client_id)
        )
        assert related_binding is not None
        related_principal = Principal(
            tenant_id,
            related_binding.subject_id,
            "api_key",
            frozenset({"mcp:connect", "data:export"}),
            related_client.oauth_client_id,
        )

    root = tmp_path
    signer = ExportManifestSigner("postgres-export-signing-secret-123456789", key_id="pg-export-v1")
    cursor = SignedCursorCodec("postgres-export-cursor-secret-12345678901")
    with Session(engine, expire_on_commit=False) as session:
        set_tenant_context(session, tenant_id)
        service = CommercialExportService(
            session,
            FileSystemObjectStore(root),
            signer,
            cursor,
            read_page_size_max=25,
        )
        first = service.create(
            contract.principal,
            CreateExportCommand("entities", "jsonl", {}, ["id", "name"], 2, "100", "pg-export-first-001"),
        )
        completed = service.execute(tenant_id, first.id)
        assert completed.state == "completed"
        job_id = completed.id

    barrier = threading.Barrier(2)

    def create_export(principal: Principal, key: str) -> str:
        with Session(engine, expire_on_commit=False) as session:
            set_tenant_context(session, tenant_id)
            service = CommercialExportService(
                session,
                FileSystemObjectStore(root),
                signer,
                cursor,
            )
            barrier.wait(timeout=10)
            try:
                return service.create(
                    principal,
                    CreateExportCommand("entities", "jsonl", {}, ["id", "name"], 2, "100", key),
                ).state
            except CommercialAccessDenied:
                return "denied"

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(
            executor.map(
                lambda item: create_export(*item),
                [
                    (contract.principal, "pg-export-concurrent-a"),
                    (related_principal, "pg-export-concurrent-b"),
                ],
            )
        )
    assert sorted(results) == ["denied", "queued"]

    wrong_tenant_id = str(uuid.uuid4())
    with Session(engine) as session:
        set_tenant_context(session, wrong_tenant_id)
        assert session.get(DataExportJob, job_id) is None


@pytest.mark.integration
def test_postgres_serializes_credit_reservations_enforces_rls_and_immutable_history() -> None:
    database_url = os.getenv("TEST_COMMERCIAL_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_COMMERCIAL_DATABASE_URL is not configured")
    engine = create_engine(database_url, pool_pre_ping=True)
    tenant_slug = f"commercial-{uuid.uuid4()}"
    with Session(engine, expire_on_commit=False) as setup_session:
        tenant = Tenant(id=str(uuid.uuid4()), slug=tenant_slug, name="Commercial Concurrency Test")
        set_tenant_context(setup_session, tenant.id)
        setup_session.add(tenant)
        setup_session.commit()
        contract = seed_commercial_contract(
            setup_session,
            tenant,
            granted_units=Decimal("10.00000000"),
            subject_id=f"subject-{uuid.uuid4()}",
            oauth_client_id=f"client-{uuid.uuid4()}",
        )
        tenant_id = tenant.id
        principal = contract.principal
        rate_card_id = contract.rate_card.id

    barrier = threading.Barrier(2)

    def reserve(index: int) -> tuple[str, str]:
        with Session(engine, expire_on_commit=False) as worker_session:
            set_tenant_context(worker_session, tenant_id)
            barrier.wait(timeout=10)
            try:
                outcome = CommercialUsageService(worker_session, principal).reserve(
                    ReserveCommand(
                        "entity.search",
                        f"concurrent-reserve-{index:02d}",
                        {"q": "EGFR", "worker": index},
                        5,
                        "8",
                        f"concurrent-request-{index}",
                    )
                )
                return "reserved", outcome.reservation.id
            except InsufficientCredits:
                worker_session.rollback()
                return "denied", ""

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(reserve, range(2)))

    assert sorted(state for state, _ in outcomes) == ["denied", "reserved"]
    reservation_id = next(identifier for state, identifier in outcomes if state == "reserved")
    with Session(engine, expire_on_commit=False) as release_session:
        set_tenant_context(release_session, tenant_id)
        CommercialUsageService(release_session, principal).release(
            reservation_id,
            reason="concurrency test complete",
            request_id="concurrency-release",
        )

    with Session(engine) as wrong_tenant_session:
        set_tenant_context(wrong_tenant_session, str(uuid.uuid4()))
        assert wrong_tenant_session.get(RateCardVersion, rate_card_id) is None

    with Session(engine) as immutable_session:
        set_tenant_context(immutable_session, tenant_id)
        card = immutable_session.scalar(select(RateCardVersion).where(RateCardVersion.id == rate_card_id))
        assert card is not None
        card.currency = "USD"
        with pytest.raises(DBAPIError, match="append-only"):
            immutable_session.commit()
        immutable_session.rollback()
    engine.dispose()


@pytest.mark.integration
def test_postgres_allows_only_one_data_execution_claim_per_reservation() -> None:
    database_url = os.getenv("TEST_COMMERCIAL_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_COMMERCIAL_DATABASE_URL is not configured")
    engine = create_engine(database_url, pool_pre_ping=True)
    with Session(engine, expire_on_commit=False) as setup_session:
        tenant = Tenant(id=str(uuid.uuid4()), slug=f"claim-{uuid.uuid4()}", name="Execution Claim Test")
        set_tenant_context(setup_session, tenant.id)
        setup_session.add(tenant)
        setup_session.commit()
        contract = seed_commercial_contract(
            setup_session,
            tenant,
            granted_units=Decimal("100.00000000"),
            subject_id=f"subject-{uuid.uuid4()}",
            oauth_client_id=f"client-{uuid.uuid4()}",
        )
        reservation = (
            CommercialUsageService(setup_session, contract.principal)
            .reserve(
                ReserveCommand(
                    "entity.search",
                    "execution-claim-reservation",
                    {"q": "EGFR", "limit": 5},
                    5,
                    "10",
                    "execution-claim-reserve",
                )
            )
            .reservation
        )
        tenant_id = tenant.id
        principal = contract.principal
        reservation_id = reservation.id

    barrier = threading.Barrier(2)

    def claim(_: int) -> str:
        with Session(engine, expire_on_commit=False) as worker_session:
            set_tenant_context(worker_session, tenant_id)
            barrier.wait(timeout=10)
            try:
                CommercialUsageService(worker_session, principal).authorize_paginated_query(
                    reservation_id,
                    billing_class="entity.search",
                    request_arguments={"q": "EGFR", "limit": 5},
                    page_size=5,
                )
                return "claimed"
            except ReservationConflict:
                worker_session.rollback()
                return "denied"

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(claim, range(2)))

    assert sorted(outcomes) == ["claimed", "denied"]
    with Session(engine, expire_on_commit=False) as cleanup_session:
        set_tenant_context(cleanup_session, tenant_id)
        CommercialUsageService(cleanup_session, principal).release(
            reservation_id,
            reason="execution claim test complete",
            request_id="execution-claim-release",
        )
    engine.dispose()


@pytest.mark.integration
def test_postgres_serializes_exact_unique_record_budget_and_protects_coverage_history() -> None:
    database_url = os.getenv("TEST_COMMERCIAL_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_COMMERCIAL_DATABASE_URL is not configured")
    engine = create_engine(database_url, pool_pre_ping=True)
    with Session(engine, expire_on_commit=False) as setup_session:
        tenant = Tenant(
            id=str(uuid.uuid4()),
            slug=f"coverage-{uuid.uuid4()}",
            name="Coverage Concurrency Test",
        )
        set_tenant_context(setup_session, tenant.id)
        setup_session.add(tenant)
        setup_session.commit()
        contract = seed_commercial_contract(
            setup_session,
            tenant,
            granted_units=Decimal("100.00000000"),
            subject_id=f"subject-{uuid.uuid4()}",
            oauth_client_id=f"client-{uuid.uuid4()}",
            daily_unique_record_limit=5,
        )
        tenant_id = tenant.id
        principal = contract.principal

    barrier = threading.Barrier(2)

    def reserve_coverage(index: int) -> tuple[str, str]:
        with Session(engine, expire_on_commit=False) as worker_session:
            set_tenant_context(worker_session, tenant_id)
            barrier.wait(timeout=10)
            try:
                reservation = (
                    CommercialUsageService(worker_session, principal)
                    .reserve(
                        ReserveCommand(
                            "entity.search",
                            f"coverage-concurrent-{index}",
                            {"q": f"target-{index}", "limit": 3},
                            3,
                            "2",
                            f"coverage-request-{index}",
                        )
                    )
                    .reservation
                )
                return "reserved", reservation.id
            except CommercialAccessDenied:
                return "denied", ""

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(reserve_coverage, range(2)))

    assert sorted(state for state, _ in outcomes) == ["denied", "reserved"]
    reservation_id = next(identifier for state, identifier in outcomes if state == "reserved")
    with Session(engine, expire_on_commit=False) as settle_session:
        set_tenant_context(settle_session, tenant_id)
        settled = CommercialUsageService(settle_session, principal).settle(
            SettleCommand(
                reservation_id,
                3,
                {"items": [{"id": "entity-1"}, {"id": "entity-2"}, {"id": "entity-3"}]},
                {},
                "coverage-settlement",
            )
        )
        assert settled.usage_event.new_unique_record_count == 3
        assert len(settle_session.scalars(select(CommercialCoverageRecord)).all()) == 3
        denied = settle_session.scalar(select(CommercialPolicyEvent).where(CommercialPolicyEvent.decision == "deny"))
        assert denied is not None

        coverage = settle_session.scalar(select(CommercialCoverageRecord).limit(1))
        assert coverage is not None
        coverage.subject_id = "mutated-subject"
        with pytest.raises(DBAPIError, match="append-only"):
            settle_session.commit()
        settle_session.rollback()
    with Session(engine) as wrong_tenant_session:
        set_tenant_context(wrong_tenant_session, str(uuid.uuid4()))
        assert wrong_tenant_session.scalar(select(CommercialCoverageRecord).limit(1)) is None
        assert wrong_tenant_session.scalar(select(CommercialPolicyEvent).limit(1)) is None
    engine.dispose()


@pytest.mark.integration
def test_postgres_serializes_cross_client_partition_risk_on_the_billing_account() -> None:
    database_url = os.getenv("TEST_COMMERCIAL_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_COMMERCIAL_DATABASE_URL is not configured")
    engine = create_engine(database_url, pool_pre_ping=True)
    with Session(engine, expire_on_commit=False) as setup_session:
        tenant = Tenant(
            id=str(uuid.uuid4()),
            slug=f"cross-client-risk-{uuid.uuid4()}",
            name="Cross Client Risk Test",
        )
        set_tenant_context(setup_session, tenant.id)
        setup_session.add(tenant)
        setup_session.commit()
        contract = seed_commercial_contract(
            setup_session,
            tenant,
            granted_units=Decimal("100.00000000"),
            subject_id=f"subject-{uuid.uuid4()}",
            oauth_client_id=f"client-{uuid.uuid4()}",
        )
        admin = CommercialAdminService(setup_session, tenant, actor_id="risk-postgres-test")
        related_oauth_client_id = f"client-{uuid.uuid4()}"
        related_subject_id = f"subject-{uuid.uuid4()}"
        related_subscription = admin.provision_client(
            ProvisionClientCommand(
                client_key=f"related-{uuid.uuid4()}",
                oauth_client_id=related_oauth_client_id,
                display_name="Related Risk Client",
                actor_type="api_key",
                subject_id=related_subject_id,
                account_key="test-account",
                account_name="Test Billing Account",
                subscription_key=f"related-{uuid.uuid4()}",
                rate_card_key="test-plan",
                rate_card_revision=1,
                created_by="risk-postgres-test",
                export_field_policy=default_export_field_policy(policy_version="test-v1"),
            )
        )
        admin.grant_credit(
            related_subscription.subscription_key,
            Decimal("100"),
            external_reference=f"risk-credit-{uuid.uuid4()}",
            reason="cross-client risk test",
        )
        policy = setup_session.scalar(
            select(CommercialRiskPolicy).where(
                CommercialRiskPolicy.billing_account_id == contract.subscription.billing_account_id
            )
        )
        assert policy is not None
        policy.max_cross_client_partition_queries_per_window = 3
        setup_session.commit()
        related_principal = Principal(
            tenant_id=tenant.id,
            actor_id=related_subject_id,
            actor_type="api_key",
            scopes=frozenset({"mcp:connect", "entities:read"}),
            client_id=related_oauth_client_id,
        )
        first_service = CommercialUsageService(setup_session, contract.principal)
        first = first_service.reserve(
            ReserveCommand("entity.search", "pg-risk-partition-a", {"q": "A", "limit": 1}, 1, "5", "pg-risk-a")
        ).reservation
        first_service.release(first.id, reason="seed risk event", request_id="pg-risk-release-a")
        related_service = CommercialUsageService(setup_session, related_principal)
        second = related_service.reserve(
            ReserveCommand("entity.search", "pg-risk-partition-b", {"q": "B", "limit": 1}, 1, "5", "pg-risk-b")
        ).reservation
        related_service.release(second.id, reason="seed risk event", request_id="pg-risk-release-b")
        tenant_id = tenant.id
        principals = (contract.principal, related_principal)

    barrier = threading.Barrier(2)

    def reserve_partition(index: int) -> tuple[str, str]:
        with Session(engine, expire_on_commit=False) as worker_session:
            set_tenant_context(worker_session, tenant_id)
            barrier.wait(timeout=10)
            try:
                reservation = (
                    CommercialUsageService(worker_session, principals[index])
                    .reserve(
                        ReserveCommand(
                            "entity.search",
                            f"pg-risk-concurrent-{index}",
                            {"q": ("C", "D")[index], "limit": 1},
                            1,
                            "5",
                            f"pg-risk-concurrent-{index}",
                        )
                    )
                    .reservation
                )
                return "reserved", reservation.id
            except CommercialAccessDenied:
                worker_session.rollback()
                return "denied", ""

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(reserve_partition, range(2)))
    assert sorted(state for state, _ in outcomes) == ["denied", "reserved"]

    with Session(engine, expire_on_commit=False) as verify_session:
        set_tenant_context(verify_session, tenant_id)
        allowed_reservation_id = next(identifier for state, identifier in outcomes if state == "reserved")
        allowed_principal = principals[
            next(index for index, outcome in enumerate(outcomes) if outcome[0] == "reserved")
        ]
        CommercialUsageService(verify_session, allowed_principal).release(
            allowed_reservation_id,
            reason="cross-client concurrency test complete",
            request_id="pg-risk-concurrent-release",
        )
        denial = verify_session.scalar(
            select(CommercialPolicyEvent).where(
                CommercialPolicyEvent.reason_code == "cross_client_partition_enumeration_detected"
            )
        )
        assert denial is not None
        assert denial.details["window_partition_count"] == 4
        assert denial.details["window_partition_client_count"] == 2
        operator = Principal(tenant_id, "postgres-risk-operator", "user", frozenset({"commercial:write"}))
        reviewed = CommercialOperationsService(verify_session, operator).review_risk_event(
            denial.id,
            status="acknowledged",
            notes="PostgreSQL RLS verification",
        )
        assert reviewed["case_status"] == "acknowledged"
        risk_case_id = verify_session.scalar(
            select(CommercialRiskCase.id).where(CommercialRiskCase.policy_event_id == denial.id)
        )
        assert risk_case_id is not None
    with Session(engine) as wrong_tenant_session:
        set_tenant_context(wrong_tenant_session, str(uuid.uuid4()))
        assert wrong_tenant_session.scalar(select(CommercialRiskPolicy).limit(1)) is None
        assert wrong_tenant_session.get(CommercialRiskCase, risk_case_id) is None
    engine.dispose()


@pytest.mark.integration
def test_postgres_serializes_settlement_reversal_and_protects_reconciliation_history() -> None:
    database_url = os.getenv("TEST_COMMERCIAL_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_COMMERCIAL_DATABASE_URL is not configured")
    engine = create_engine(database_url, pool_pre_ping=True)
    with Session(engine, expire_on_commit=False) as setup_session:
        tenant = Tenant(
            id=str(uuid.uuid4()),
            slug=f"accounting-{uuid.uuid4()}",
            name="Accounting Concurrency Test",
        )
        set_tenant_context(setup_session, tenant.id)
        setup_session.add(tenant)
        setup_session.commit()
        contract = seed_commercial_contract(
            setup_session,
            tenant,
            granted_units=Decimal("100.00000000"),
            subject_id=f"subject-{uuid.uuid4()}",
            oauth_client_id=f"client-{uuid.uuid4()}",
        )
        reservation = (
            CommercialUsageService(setup_session, contract.principal)
            .reserve(
                ReserveCommand(
                    "entity.search",
                    "postgres-accounting-use",
                    {"q": "EGFR", "limit": 1},
                    1,
                    "5",
                    "postgres-accounting-reserve",
                )
            )
            .reservation
        )
        settlement = (
            CommercialUsageService(setup_session, contract.principal)
            .settle(
                SettleCommand(
                    reservation.id,
                    1,
                    {"items": [{"id": "entity-egfr"}]},
                    {},
                    "postgres-accounting-settle",
                )
            )
            .settlement
        )
        tenant_id = tenant.id
        settlement_id = settlement.id

    barrier = threading.Barrier(2)

    def reverse(index: int) -> tuple[str, str]:
        with Session(engine, expire_on_commit=False) as worker_session:
            set_tenant_context(worker_session, tenant_id)
            worker_tenant = worker_session.get(Tenant, tenant_id)
            assert worker_tenant is not None
            barrier.wait(timeout=10)
            try:
                adjustment = CommercialAccountingService(
                    worker_session,
                    worker_tenant,
                    actor_id=f"FIN-{index}",
                ).reverse_settlement(
                    settlement_id,
                    ReversalCommand(
                        f"postgres-settlement-reversal-{index}",
                        "concurrent approved reversal",
                        f"postgres-reversal-{index}",
                    ),
                )
                return "reversed", adjustment.id
            except CommercialAccountingConflict:
                worker_session.rollback()
                return "denied", ""

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(reverse, range(2)))
    assert sorted(state for state, _ in outcomes) == ["denied", "reversed"]

    with Session(engine, expire_on_commit=False) as reconciliation_session:
        set_tenant_context(reconciliation_session, tenant_id)
        reconciliation_tenant = reconciliation_session.get(Tenant, tenant_id)
        assert reconciliation_tenant is not None
        run = CommercialAccountingService(
            reconciliation_session,
            reconciliation_tenant,
            actor_id="FIN-RECONCILE",
        ).reconcile(
            "test-subscription",
            run_key="postgres-reconciliation-0001",
            request_id="postgres-reconciliation-request-id-with-external-trace-context-00000000000000000001",
        )
        assert run.status == "clean"

    with Session(engine) as immutable_session:
        set_tenant_context(immutable_session, tenant_id)
        adjustment = immutable_session.scalar(select(BillingAdjustment).limit(1))
        assert adjustment is not None
        adjustment.reason = "mutated"
        with pytest.raises(DBAPIError, match="append-only"):
            immutable_session.commit()
        immutable_session.rollback()
        stored_run = immutable_session.scalar(select(CommercialReconciliationRun).limit(1))
        assert stored_run is not None
        stored_run.status = "drift"
        with pytest.raises(DBAPIError, match="append-only"):
            immutable_session.commit()
        immutable_session.rollback()

    with Session(engine) as wrong_tenant_session:
        set_tenant_context(wrong_tenant_session, str(uuid.uuid4()))
        assert wrong_tenant_session.scalar(select(BillingAdjustment).limit(1)) is None
        assert wrong_tenant_session.scalar(select(CommercialReconciliationRun).limit(1)) is None
    engine.dispose()
