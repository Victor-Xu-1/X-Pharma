from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session

from pharma_intel.config import get_settings
from pharma_intel.models import (
    DataSource,
    DataSourceType,
    Entity,
    EntityType,
    EvidenceClaim,
    GovernanceStatus,
    OutboxEvent,
    ReviewStatus,
    SourceAsset,
    SourceDocument,
    StagedFact,
    Tenant,
)


def test_registration_migration_preserves_existing_accounts_and_refuses_invitation_loss(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from pharma_intel.accounts.contracts import InvitationCreate
    from pharma_intel.accounts.service import AccountRegistrationService
    from pharma_intel.models import AccountInvitation, User, UserRole
    from pharma_intel.security import Principal

    url = f"sqlite:///{tmp_path / 'registration-migration.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("HUMAN_AUTH_MODE", "local")
    get_settings.cache_clear()
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    command.upgrade(config, "b6e4c9a2d781")
    engine = create_engine(url)
    unusable_hash = "not-a-login-account"
    try:
        with Session(engine, expire_on_commit=False) as session:
            tenant = Tenant(slug="migration-account-test", name="Migration account test")
            session.add(tenant)
            session.flush()
            user_id = str(uuid.uuid4())
            session.execute(
                text("""
                INSERT INTO users (id, tenant_id, email, normalized_email, display_name,
                    role, password_hash, active, token_version, created_at, updated_at)
                VALUES (:id, :tenant, 'migration@example.test', 'migration@example.test',
                    'Existing administrator', 'ADMIN', :hash, true, 1, :now, :now)
            """),
                {"id": user_id, "tenant": tenant.id, "hash": unusable_hash, "now": datetime.now(UTC)},
            )
            session.commit()
            tenant_id = tenant.id
        command.upgrade(config, "head")
        with Session(engine, expire_on_commit=False) as session:
            existing = session.get(User, user_id)
            assert existing is not None and existing.password_hash == unusable_hash
            assert existing.home_tenant_id == tenant_id and existing.memberships[0].role == UserRole.ADMIN
            issued = AccountRegistrationService(session, "migration-invitation-test").issue_invitation(
                Principal(tenant_id, user_id, "user", frozenset()), InvitationCreate(email="invited@example.test")
            )
            invitation_id = issued.invitation.id
        with pytest.raises(RuntimeError, match="Archive registration invitations"):
            command.downgrade(config, "b6e4c9a2d781")
        with Session(engine) as session:
            assert session.get(AccountInvitation, invitation_id) is not None
            assert session.scalar(text("SELECT id FROM users WHERE id=:id"), {"id": user_id}) == user_id
    finally:
        engine.dispose()
        get_settings.cache_clear()


def test_full_migration_chain_round_trips_and_matches_models(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_path = tmp_path / "migration-roundtrip.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    try:
        command.upgrade(config, "head")
        engine = create_engine(database_url)
        tables = set(inspect(engine).get_table_names())
        assert "research_bundles" not in tables
        assert {
            "agent_clients",
            "billing_accounts",
            "commercial_subscriptions",
            "rate_card_versions",
            "usage_reservations",
            "usage_events",
            "usage_settlements",
            "commercial_ledger_entries",
            "billing_adjustments",
            "commercial_reconciliation_runs",
            "billing_period_statements",
            "invoice_references",
            "billing_disputes",
            "billing_dispute_events",
            "projection_deliveries",
            "commercial_export_policies",
            "data_export_jobs",
            "entity_identifiers",
            "ontology_terms",
            "entity_ontology_mappings",
            "entity_resolution_cases",
            "entity_canonical_links",
            "entity_resolution_decisions",
            "user_groups",
            "user_group_memberships",
            "regulatory_events",
            "epidemiology_observations",
            "news_events",
            "fact_provenance_links",
            "source_version_quarantine_decisions",
            "governance_publication_batches",
            "governance_publication_batch_items",
            "fact_withdrawal_tombstones",
            "projection_maintenance_jobs",
            "data_quality_snapshots",
            "data_quality_issues",
            "data_quality_issue_events",
            "user_sessions",
            "development_program_targets",
        } <= tables
        dataset_columns = {column["name"] for column in inspect(engine).get_columns("tenant_datasets")}
        assert "version" in dataset_columns
        dataset_checks = {
            constraint.get("name") for constraint in inspect(engine).get_check_constraints("tenant_datasets")
        }
        assert "ck_tenant_dataset_version" in dataset_checks
        session_checks = {
            constraint.get("name") for constraint in inspect(engine).get_check_constraints("user_sessions")
        }
        assert "ck_user_session_expiry" in session_checks
        snapshot_checks = {
            constraint.get("name") for constraint in inspect(engine).get_check_constraints("data_quality_snapshots")
        }
        assert "ck_data_quality_snapshot_trigger" in snapshot_checks
        issue_checks = {
            constraint.get("name") for constraint in inspect(engine).get_check_constraints("data_quality_issues")
        }
        assert {
            "ck_data_quality_issue_status",
            "ck_data_quality_issue_severity",
            "ck_data_quality_issue_comparison",
            "ck_data_quality_issue_version",
        } <= issue_checks
        user_uniques = inspect(engine).get_unique_constraints("users")
        assert not any(constraint.get("name") == "uq_users_tenant_id_id" for constraint in user_uniques)
        user_columns = {column["name"] for column in inspect(engine).get_columns("users")}
        assert "home_tenant_id" in user_columns and "role" not in user_columns and "tenant_id" not in user_columns
        assert set(inspect(engine).get_pk_constraint("organization_memberships")["constrained_columns"]) == {
            "tenant_id",
            "user_id",
        }
        membership_foreign_keys = inspect(engine).get_foreign_keys("user_group_memberships")
        assert {tuple(constraint.get("constrained_columns") or []) for constraint in membership_foreign_keys} >= {
            ("tenant_id", "group_id"),
            ("tenant_id", "user_id"),
        }
        staged_fact_columns = {column["name"] for column in inspect(engine).get_columns("staged_facts")}
        assert {"raw_payload", "payload", "normalization_version"} <= staged_fact_columns
        export_policy_columns = {
            column["name"]: column for column in inspect(engine).get_columns("commercial_export_policies")
        }
        assert export_policy_columns["field_policy"]["nullable"] is False
        export_job_columns = {column["name"]: column for column in inspect(engine).get_columns("data_export_jobs")}
        for name in ("license_policy_version", "license_policy_sha256", "license_attribution"):
            assert export_job_columns[name]["nullable"] is False
        source_columns = {column["name"]: column for column in inspect(engine).get_columns("data_sources")}
        for name in (
            "owner",
            "data_classification",
            "authorization_scopes",
            "authorization_valid_from",
            "expected_freshness_seconds",
            "rate_limit_per_minute",
            "connector_cursor",
        ):
            assert source_columns[name]["nullable"] is False
        assert source_columns["authorization_valid_until"]["nullable"] is True
        source_checks = {constraint["name"] for constraint in inspect(engine).get_check_constraints("data_sources")}
        assert "ck_data_source_authorization_window" in source_checks
        source_asset_columns = {column["name"]: column for column in inspect(engine).get_columns("source_assets")}
        assert source_asset_columns["source_fingerprint"]["nullable"] is True
        source_version_uniques = inspect(engine).get_unique_constraints("source_versions")
        assert not any(
            set(constraint.get("column_names") or []) == {"tenant_id", "source_asset_id", "content_sha256"}
            for constraint in source_version_uniques
        )
        source_version_columns = {column["name"] for column in inspect(engine).get_columns("source_versions")}
        assert {"quarantine_status", "quarantine_version", "quarantine_updated_at"} <= source_version_columns
        source_version_checks = {
            constraint["name"] for constraint in inspect(engine).get_check_constraints("source_versions")
        }
        assert "ck_source_version_quarantine_version" in source_version_checks
        source_operation_columns = {
            column["name"] for column in inspect(engine).get_columns("source_version_operations")
        }
        assert "expected_quarantine_version" in source_operation_columns
        publication_checks = {
            constraint["name"] for constraint in inspect(engine).get_check_constraints("governance_publication_batches")
        }
        assert {
            "ck_publication_batch_operation",
            "ck_publication_batch_status",
            "ck_publication_batch_expected_count",
            "ck_publication_batch_blocked_count",
        } <= publication_checks
        maintenance_checks = {
            constraint["name"] for constraint in inspect(engine).get_check_constraints("projection_maintenance_jobs")
        }
        assert {
            "ck_projection_maintenance_attempts",
            "ck_projection_maintenance_operation",
            "ck_projection_maintenance_status",
        } <= maintenance_checks
        maintenance_uniques = inspect(engine).get_unique_constraints("projection_maintenance_jobs")
        assert any(set(constraint.get("column_names") or []) == {"active_key"} for constraint in maintenance_uniques)
        quality_issue_checks = {
            constraint["name"] for constraint in inspect(engine).get_check_constraints("data_quality_issues")
        }
        assert {
            "ck_data_quality_issue_status",
            "ck_data_quality_issue_severity",
            "ck_data_quality_issue_comparison",
            "ck_data_quality_issue_version",
        } <= quality_issue_checks
        retention_checks = {
            constraint["name"] for constraint in inspect(engine).get_check_constraints("data_retention_policies")
        }
        legal_hold_checks = {constraint["name"] for constraint in inspect(engine).get_check_constraints("legal_holds")}
        assert "ck_retention_policy_data_class" in retention_checks
        assert "ck_legal_hold_scope_type" in legal_hold_checks
        lifecycle_action_check = next(
            constraint
            for constraint in inspect(engine).get_check_constraints("data_lifecycle_events")
            if constraint["name"] == "ck_data_lifecycle_event_action"
        )
        assert "reauthorize" in lifecycle_action_check["sqltext"]
        reservation_columns = {column["name"]: column for column in inspect(engine).get_columns("usage_reservations")}
        assert reservation_columns["network_fingerprint"]["nullable"] is True
        assert reservation_columns["credential_fingerprint"]["nullable"] is True
        assert reservation_columns["correlation_key_id"]["nullable"] is False
        reservation_checks = {
            constraint["name"] for constraint in inspect(engine).get_check_constraints("usage_reservations")
        }
        assert {
            "ck_usage_reservation_network_fingerprint",
            "ck_usage_reservation_credential_fingerprint",
        } <= reservation_checks
        dispute_checks = {
            constraint["name"] for constraint in inspect(engine).get_check_constraints("billing_disputes")
        }
        assert {
            "ck_billing_dispute_status",
            "ck_billing_dispute_resolution_state",
            "ck_billing_dispute_adjustment_state",
        } <= dispute_checks
        risk_policy_columns = {
            column["name"]: column for column in inspect(engine).get_columns("commercial_risk_policies")
        }
        assert risk_policy_columns["max_distinct_networks_per_window"]["nullable"] is False
        assert risk_policy_columns["max_distinct_credentials_per_window"]["nullable"] is False
        policy_event_indexes = {
            index["name"]: tuple(index.get("column_names") or [])
            for index in inspect(engine).get_indexes("commercial_policy_events")
        }
        assert policy_event_indexes["ix_commercial_policy_risk_queue"] == (
            "tenant_id",
            "decision",
            "occurred_at",
            "id",
        )
        regulatory_checks = {
            constraint["name"]: constraint["sqltext"]
            for constraint in inspect(engine).get_check_constraints("regulatory_events")
        }
        event_type_check = regulatory_checks["ck_regulatory_event_type"]
        assert "designation" in event_type_check
        assert "safety_signal" in event_type_check
        regulatory_columns = {column["name"]: column for column in inspect(engine).get_columns("regulatory_events")}
        assert {
            "designation_type",
            "label_change_type",
            "label_version",
            "approved_population",
            "has_boxed_warning",
            "safety_signal_type",
            "safety_term",
            "safety_severity",
            "safety_status",
            "risk_actions",
            "source_updated_at",
        } <= regulatory_columns.keys()
        assert regulatory_columns["risk_actions"]["nullable"] is False
        assert {
            "ck_regulatory_designation_type",
            "ck_regulatory_label_change_type",
            "ck_regulatory_safety_signal_type",
            "ck_regulatory_safety_severity",
            "ck_regulatory_safety_status",
            "ck_regulatory_safety_confirmation_window",
            "ck_regulatory_safety_resolution_window",
        } <= regulatory_checks.keys()
        regulatory_indexes = {
            index["name"]: tuple(index.get("column_names") or [])
            for index in inspect(engine).get_indexes("regulatory_events")
        }
        assert regulatory_indexes["ix_regulatory_subject_date"] == (
            "tenant_id",
            "subject_entity_id",
            "decision_date",
        )
        assert regulatory_indexes["ix_regulatory_designation_lookup"] == (
            "tenant_id",
            "designation_type",
            "jurisdiction",
            "subject_entity_id",
        )
        assert regulatory_indexes["ix_regulatory_label_lookup"] == (
            "tenant_id",
            "label_change_type",
            "has_boxed_warning",
            "subject_entity_id",
        )
        assert regulatory_indexes["ix_regulatory_safety_lookup"] == (
            "tenant_id",
            "safety_status",
            "safety_severity",
            "subject_entity_id",
        )
        program_columns = {column["name"]: column for column in inspect(engine).get_columns("development_programs")}
        assert {
            "global_phase",
            "china_phase",
            "global_phase_started_at",
            "china_phase_started_at",
            "development_rights_regions",
            "commercialization_rights_regions",
            "program_tags",
            "target_set_version",
            "target_combination_key",
            "organization_set_version",
        } <= program_columns.keys()
        assert program_columns["development_rights_regions"]["nullable"] is False
        assert program_columns["commercialization_rights_regions"]["nullable"] is False
        assert program_columns["program_tags"]["nullable"] is False
        program_checks = {
            constraint["name"]: constraint["sqltext"]
            for constraint in inspect(engine).get_check_constraints("development_programs")
        }
        assert {
            "ck_program_global_phase",
            "ck_program_china_phase",
            "ck_program_global_phase_date_requires_phase",
            "ck_program_china_phase_date_requires_phase",
            "ck_development_program_target_set_version",
            "ck_development_program_org_set_version",
        } <= program_checks.keys()
        program_indexes = {
            index["name"]: tuple(index.get("column_names") or [])
            for index in inspect(engine).get_indexes("development_programs")
        }
        assert program_indexes["ix_program_regional_phase"] == (
            "tenant_id",
            "global_phase",
            "china_phase",
        )
        assert program_indexes["ix_program_target_combination_lookup"] == (
            "tenant_id",
            "target_combination_key",
        )
        program_target_columns = {
            column["name"]: column for column in inspect(engine).get_columns("development_program_targets")
        }
        assert {
            "tenant_id",
            "program_id",
            "target_set_version",
            "target_entity_id",
            "role",
            "position",
            "source_document_id",
        } <= program_target_columns.keys()
        program_target_checks = {
            constraint["name"] for constraint in inspect(engine).get_check_constraints("development_program_targets")
        }
        assert {"ck_program_target_set_version", "ck_program_target_position"} <= program_target_checks
        program_target_indexes = {
            index["name"]: tuple(index.get("column_names") or [])
            for index in inspect(engine).get_indexes("development_program_targets")
        }
        assert program_target_indexes["ix_program_targets_current_lookup"] == (
            "tenant_id",
            "program_id",
            "target_set_version",
            "position",
        )
        assert program_target_indexes["ix_program_targets_target_lookup"] == (
            "tenant_id",
            "target_entity_id",
            "program_id",
            "target_set_version",
        )
        program_organization_columns = {
            column["name"]: column for column in inspect(engine).get_columns("development_program_organizations")
        }
        assert {
            "tenant_id",
            "program_id",
            "organization_set_version",
            "organization_entity_id",
            "role",
            "country_region",
            "organization_type",
            "position",
            "source_document_id",
        } <= program_organization_columns.keys()
        program_organization_checks = {
            constraint["name"]
            for constraint in inspect(engine).get_check_constraints("development_program_organizations")
        }
        assert {
            "ck_program_org_set_version",
            "ck_program_org_position",
            "ck_program_org_role",
        } <= program_organization_checks
        program_organization_indexes = {
            index["name"]: tuple(index.get("column_names") or [])
            for index in inspect(engine).get_indexes("development_program_organizations")
        }
        assert program_organization_indexes["ix_program_orgs_current_lookup"] == (
            "tenant_id",
            "program_id",
            "organization_set_version",
            "position",
        )
        assert program_organization_indexes["ix_program_orgs_entity_lookup"] == (
            "tenant_id",
            "organization_entity_id",
            "program_id",
            "organization_set_version",
        )
        epidemiology_checks = {
            constraint["name"]: constraint["sqltext"]
            for constraint in inspect(engine).get_check_constraints("epidemiology_observations")
        }
        assert "prevalence" in epidemiology_checks["ck_epidemiology_measure"]
        assert "value >= 0" in epidemiology_checks["ck_epidemiology_value_nonnegative"]
        assert "sample_size > 0" in epidemiology_checks["ck_epidemiology_sample_size_positive"]
        epidemiology_indexes = {
            index["name"]: tuple(index.get("column_names") or [])
            for index in inspect(engine).get_indexes("epidemiology_observations")
        }
        assert epidemiology_indexes["ix_epidemiology_disease_period"] == (
            "tenant_id",
            "disease_entity_id",
            "period_end",
        )
        news_checks = {
            constraint["name"]: constraint["sqltext"]
            for constraint in inspect(engine).get_check_constraints("news_events")
        }
        assert "press_release" in news_checks["ck_news_event_type"]
        assert "conference_abstract" in news_checks["ck_news_event_type"]
        news_indexes = {
            index["name"]: tuple(index.get("column_names") or [])
            for index in inspect(engine).get_indexes("news_events")
        }
        assert news_indexes["ix_news_event_published"] == ("tenant_id", "published_at")
        clinical_trial_columns = {
            column["name"]: column for column in inspect(engine).get_columns("clinical_trial_profiles")
        }
        for name in (
            "study_design",
            "eligibility",
            "arms",
            "status_history",
            "has_results",
            "therapy_lines",
        ):
            assert clinical_trial_columns[name]["nullable"] is False
        assert clinical_trial_columns["acronym"]["nullable"] is True
        assert clinical_trial_columns["initiation_type"]["nullable"] is True
        assert clinical_trial_columns["results_first_posted"]["nullable"] is True
        assert clinical_trial_columns["source_document_id"]["nullable"] is True
        clinical_trial_indexes = {
            index["name"]: tuple(index.get("column_names") or [])
            for index in inspect(engine).get_indexes("clinical_trial_profiles")
        }
        assert clinical_trial_indexes["ix_clinical_trial_profiles_has_results"] == ("has_results",)
        assert clinical_trial_indexes["ix_clinical_trial_profiles_results_first_posted"] == ("results_first_posted",)
        assert clinical_trial_indexes["ix_clinical_trial_profiles_source_document_id"] == ("source_document_id",)
        assert clinical_trial_indexes["ix_clinical_trial_profiles_acronym"] == ("acronym",)
        assert clinical_trial_indexes["ix_clinical_trial_profiles_initiation_type"] == ("initiation_type",)
        clinical_trial_checks = {
            constraint["name"]: constraint["sqltext"]
            for constraint in inspect(engine).get_check_constraints("clinical_trial_profiles")
        }
        assert "iit" in clinical_trial_checks["ck_clinical_trial_initiation_type"]
        assert "ist" in clinical_trial_checks["ck_clinical_trial_initiation_type"]
        clinical_trial_foreign_keys = inspect(engine).get_foreign_keys("clinical_trial_profiles")
        assert any(
            constraint.get("referred_table") == "source_documents"
            and tuple(constraint.get("constrained_columns") or []) == ("source_document_id",)
            for constraint in clinical_trial_foreign_keys
        )
        provenance_indexes = {
            index["name"]: tuple(index.get("column_names") or [])
            for index in inspect(engine).get_indexes("fact_provenance_links")
        }
        assert provenance_indexes["ix_fact_provenance_resource"] == (
            "tenant_id",
            "resource_type",
            "resource_id",
        )
        assert provenance_indexes["ix_fact_provenance_dataset_created"] == (
            "tenant_id",
            "dataset_key",
            "created_at",
        )
        command.check(config)
        command.downgrade(config, "base")
        assert inspect(engine).get_table_names() == ["alembic_version"]
        engine.dispose()
    finally:
        get_settings.cache_clear()


def test_research_bundle_retirement_refuses_to_drop_nonempty_legacy_table(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_path = tmp_path / "nonempty-retired-module.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    engine = create_engine(database_url)
    try:
        command.upgrade(config, "1c4d7e9f2a60")
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO research_bundles "
                    "(id, tenant_id, requested_by_key_id, requested_by_user_id, question, "
                    "resolved_entity_ids, as_of, schema_version, payload, content_sha256, warnings, "
                    "created_at, updated_at) VALUES "
                    "(:id, :tenant_id, :key_id, NULL, :question, :resolved, :as_of, :schema_version, "
                    ":payload, :digest, :warnings, :created_at, :updated_at)"
                ),
                {
                    "id": "legacy-bundle",
                    "tenant_id": "legacy-tenant",
                    "key_id": "legacy-key",
                    "question": "Legacy downstream artifact",
                    "resolved": "[]",
                    "as_of": "2026-07-18T00:00:00+00:00",
                    "schema_version": "2.0",
                    "payload": "{}",
                    "digest": "a" * 64,
                    "warnings": "[]",
                    "created_at": "2026-07-18T00:00:00+00:00",
                    "updated_at": "2026-07-18T00:00:00+00:00",
                },
            )

        with pytest.raises(RuntimeError, match="export and remove legacy rows"):
            command.upgrade(config, "head")

        assert "research_bundles" in inspect(engine).get_table_names()
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT count(*) FROM research_bundles")) == 1
    finally:
        engine.dispose()
        get_settings.cache_clear()


def test_fact_provenance_migration_backfills_duplicate_publication_events_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_path = tmp_path / "provenance-backfill.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    engine = create_engine(database_url)
    try:
        command.upgrade(config, "0b8d3f6a9c42")
        with Session(engine) as session:
            tenant = Tenant(slug="provenance-backfill", name="Provenance Backfill")
            session.add(tenant)
            session.flush()
            source = DataSource(
                tenant_id=tenant.id,
                name="Backfill source",
                source_type=DataSourceType.FOLDER,
                root_uri="/provenance-backfill",
                owner="Research Operations",
                authorization_scopes=["contract:backfill"],
                dataset_key="literature",
            )
            subject = Entity(
                tenant_id=tenant.id,
                entity_type=EntityType.TARGET,
                name="EGFR",
                normalized_name="egfr",
                review_status=ReviewStatus.VERIFIED,
            )
            session.add_all([source, subject])
            session.flush()
            asset = SourceAsset(
                tenant_id=tenant.id,
                data_source_id=source.id,
                logical_path="egfr.pdf",
                source_uri="file:///provenance-backfill/egfr.pdf",
                file_name="egfr.pdf",
                extension=".pdf",
                processing_mode="parse",
            )
            document = SourceDocument(
                tenant_id=tenant.id,
                title="EGFR backfill",
                source_type="folder",
                source_uri=asset.source_uri,
                content_sha256="a" * 64,
            )
            session.add_all([asset, document])
            session.flush()
            version_id = str(uuid.uuid4())
            session.execute(
                text(
                    "INSERT INTO source_versions "
                    "(id, tenant_id, source_asset_id, version_number, content_sha256, size_bytes, discovered_at, "
                    "state, snapshot_status, malware_scan_status, parse_status, retrieval_status, governance_status, "
                    "source_document_id, metadata_json, created_at) VALUES "
                    "(:id, :tenant_id, :source_asset_id, 1, :content_sha256, 1024, CURRENT_TIMESTAMP, "
                    "'DISCOVERED', 'NOT_STARTED', 'NOT_STARTED', 'NOT_STARTED', 'NOT_STARTED', 'NOT_STARTED', "
                    ":source_document_id, '{}', CURRENT_TIMESTAMP)"
                ),
                {
                    "id": version_id,
                    "tenant_id": tenant.id,
                    "source_asset_id": asset.id,
                    "content_sha256": "a" * 64,
                    "source_document_id": document.id,
                },
            )
            extraction_id = str(uuid.uuid4())
            session.execute(
                text(
                    "INSERT INTO extraction_runs "
                    "(id, tenant_id, source_version_id, schema_name, schema_version, model_provider, model_name, "
                    "prompt_sha256, input_sha256, status, validation_errors, created_at) "
                    "VALUES (:id, :tenant_id, :source_version_id, :schema_name, :schema_version, :model_provider, "
                    ":model_name, :prompt_sha256, :input_sha256, 'SUCCEEDED', '[]', CURRENT_TIMESTAMP)"
                ),
                {
                    "id": extraction_id,
                    "tenant_id": tenant.id,
                    "source_version_id": version_id,
                    "schema_name": "pharma_document_facts",
                    "schema_version": "2.2.0",
                    "model_provider": "migration-test",
                    "model_name": "migration-test",
                    "prompt_sha256": "b" * 64,
                    "input_sha256": "c" * 64,
                },
            )
            staged = StagedFact(
                tenant_id=tenant.id,
                extraction_run_id=extraction_id,
                fact_kind="target_profile",
                fact_key="egfr-profile",
                raw_payload={"gene_symbol": "EGFR"},
                payload={"gene_symbol": "EGFR"},
                source_document_id=document.id,
                source_locator="page=3",
                source_quote="EGFR is a receptor tyrosine kinase.",
                confidence=0.99,
                status=GovernanceStatus.PUBLISHED,
            )
            session.add(staged)
            session.flush()
            claim = EvidenceClaim(
                tenant_id=tenant.id,
                subject_id=subject.id,
                predicate="has_target_profile",
                value={"gene_symbol": "EGFR"},
                source_document_id=document.id,
                source_locator=staged.source_locator,
                quote=staged.source_quote,
                confidence=staged.confidence,
                review_status=ReviewStatus.VERIFIED,
            )
            session.add(claim)
            session.flush()
            projection_id = "11111111-1111-4111-8111-111111111111"
            payload = {
                "evidence_claim_id": claim.id,
                "staged_fact_id": staged.id,
                "structured_projections": [
                    {"resource_type": "target_profile", "resource_id": projection_id},
                ],
            }
            session.add_all(
                [
                    OutboxEvent(
                        tenant_id=tenant.id,
                        aggregate_type="evidence_claim",
                        aggregate_id=claim.id,
                        event_type="governance.fact.published",
                        payload=payload,
                    ),
                    OutboxEvent(
                        tenant_id=tenant.id,
                        aggregate_type="evidence_claim",
                        aggregate_id=claim.id,
                        event_type="governance.fact.published",
                        payload=payload,
                    ),
                ]
            )
            session.commit()

        command.upgrade(config, "head")
        with engine.connect() as connection:
            rows = (
                connection.execute(
                    text(
                        "SELECT resource_type, resource_id, source_version_id, source_locator, dataset_key "
                        "FROM fact_provenance_links ORDER BY resource_type"
                    )
                )
                .mappings()
                .all()
            )
        assert len(rows) == 2
        assert {row["resource_type"] for row in rows} == {"evidence_claim", "target_profile"}
        assert {row["source_version_id"] for row in rows} == {version_id}
        assert {row["source_locator"] for row in rows} == {"page=3"}
        assert {row["dataset_key"] for row in rows} == {"literature"}
        command.downgrade(config, "0b8d3f6a9c42")
        assert "fact_provenance_links" not in inspect(engine).get_table_names()
    finally:
        engine.dispose()
        get_settings.cache_clear()
