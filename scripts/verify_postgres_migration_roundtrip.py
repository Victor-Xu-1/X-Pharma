from __future__ import annotations

import argparse
import json
import os
import secrets
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import psycopg
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from dotenv import dotenv_values
from psycopg import sql
from sqlalchemy import URL, create_engine, text

from pharma_intel.config import get_settings

DATABASE_PREFIX = "pharma_migration_contract_"
PRE_HTTP_MANIFEST_REVISION = "7f3b9d2a6c81"
RISK_QUEUE_INDEX = "ix_commercial_policy_risk_queue"
MALWARE_SCAN_COLUMNS = {
    "malware_scan_status",
    "malware_scanner",
    "malware_signature_version",
    "malware_scanned_at",
}
SOURCE_AUTHORIZATION_COLUMNS = {"authorization_valid_from", "authorization_valid_until"}
TRIAL_RESULT_EVALUATION_COLUMN = "result_evaluation"
TRIAL_RESULT_EVALUATION_CONSTRAINT = "ck_clinical_trial_result_evaluation"
TRIAL_RESULT_EVALUATION_INDEX = "ix_clinical_trial_profiles_result_evaluation"
TRIAL_ENTITY_ROLE_TABLE = "clinical_trial_entity_roles"
TRIAL_DISCLOSURE_TABLE = "clinical_trial_result_disclosures"
TRIAL_ENTITY_ROLE_CONSTRAINT = "ck_clinical_trial_entity_role"
TRIAL_DISCLOSURE_VERSION_CONSTRAINT = "ck_clinical_trial_disclosure_version"
TRIAL_DISCLOSURE_TYPE_CONSTRAINT = "ck_clinical_trial_disclosure_type"
TRIAL_DISCLOSURE_EVALUATION_CONSTRAINT = "ck_clinical_trial_disclosure_evaluation"
TRIAL_ENTITY_ROLE_INDEX = "ix_clinical_trial_entity_roles_lookup"
TRIAL_DISCLOSURE_INDEX = "ix_clinical_trial_disclosures_trial_date"
DEAL_PARTY_TABLE = "deal_party_associations"
DEAL_ASSET_TABLE = "deal_asset_associations"
DEAL_RIGHT_TABLE = "deal_rights"
PATIENT_POPULATION_TABLE = "patient_populations"
PATIENT_POPULATION_LINK_TABLE = "patient_population_entity_links"
WORKSPACE_DOMAIN_EXPORT_COLUMNS = {"export_kind", "dataset", "query_json"}
WORKSPACE_DOMAIN_EXPORT_CONSTRAINTS = {
    "ck_workspace_export_event_kind",
    "ck_workspace_export_event_subject",
}
WORKSPACE_DOMAIN_EXPORT_INDEXES = {
    "ix_workspace_export_events_export_kind",
    "ix_workspace_export_events_dataset",
}
DEAL_PROFILE_COLUMNS = {
    "status",
    "direction",
    "direction_reference_jurisdiction",
    "terminated_at",
    "source_updated_at",
}
REGULATORY_INTELLIGENCE_COLUMNS = {
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
}
REGULATORY_INTELLIGENCE_CONSTRAINTS = {
    "ck_regulatory_designation_type",
    "ck_regulatory_label_change_type",
    "ck_regulatory_safety_signal_type",
    "ck_regulatory_safety_severity",
    "ck_regulatory_safety_status",
    "ck_regulatory_safety_confirmation_window",
    "ck_regulatory_safety_resolution_window",
}
REGULATORY_INTELLIGENCE_INDEXES = {
    "ix_regulatory_designation_lookup",
    "ix_regulatory_label_lookup",
    "ix_regulatory_safety_lookup",
}
PIPELINE_REGIONAL_COLUMNS = {
    "global_phase",
    "china_phase",
    "global_phase_started_at",
    "china_phase_started_at",
    "development_rights_regions",
    "commercialization_rights_regions",
    "program_tags",
}
PIPELINE_REGIONAL_CONSTRAINTS = {
    "ck_program_global_phase",
    "ck_program_china_phase",
    "ck_program_global_phase_date_requires_phase",
    "ck_program_china_phase_date_requires_phase",
}
PIPELINE_REGIONAL_INDEXES = {
    "ix_development_programs_global_phase",
    "ix_development_programs_china_phase",
    "ix_development_programs_global_phase_started_at",
    "ix_development_programs_china_phase_started_at",
    "ix_program_regional_phase",
}
PROGRAM_TARGET_TABLE = "development_program_targets"
PROGRAM_TARGET_COLUMNS = {
    "tenant_id",
    "program_id",
    "target_set_version",
    "target_entity_id",
    "role",
    "position",
    "source_document_id",
}
PROGRAM_TARGET_CONSTRAINTS = {
    "ck_program_target_set_version",
    "ck_program_target_position",
    "uq_program_target_version_entity",
    "uq_program_target_version_position",
}
PROGRAM_TARGET_INDEXES = {
    "ix_program_targets_current_lookup",
    "ix_program_targets_target_lookup",
}
PROGRAM_ORGANIZATION_TABLE = "development_program_organizations"
PROGRAM_ORGANIZATION_COLUMNS = {
    "tenant_id",
    "program_id",
    "organization_set_version",
    "organization_entity_id",
    "role",
    "country_region",
    "organization_type",
    "position",
    "source_document_id",
}
PROGRAM_ORGANIZATION_CONSTRAINTS = {
    "ck_program_org_set_version",
    "ck_program_org_position",
    "ck_program_org_role",
    "uq_program_org_entity",
    "uq_program_org_position",
}
PROGRAM_ORGANIZATION_INDEXES = {
    "ix_program_orgs_current_lookup",
    "ix_program_orgs_entity_lookup",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify Alembic upgrade/downgrade on an isolated PostgreSQL DB")
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5433)
    return parser.parse_args()


def required(values: Mapping[str, str | None], name: str) -> str:
    value = values.get(name)
    if not value:
        raise RuntimeError(f"{name} is required in the migration verification environment file")
    return value


def migration_config(repository_root: Path) -> Config:
    return Config(str(repository_root / "alembic.ini"))


def database_url(username: str, password: str, host: str, port: int, database: str) -> str:
    return URL.create(
        "postgresql+psycopg",
        username=username,
        password=password,
        host=host,
        port=port,
        database=database,
    ).render_as_string(hide_password=False)


def enum_labels(url: str) -> list[str]:
    engine = create_engine(url)
    try:
        with engine.connect() as connection:
            return list(
                connection.scalars(
                    text(
                        "SELECT enumlabel FROM pg_enum "
                        "JOIN pg_type ON pg_type.oid = pg_enum.enumtypid "
                        "WHERE pg_type.typname = 'datasourcetype' ORDER BY enumsortorder"
                    )
                )
            )
    finally:
        engine.dispose()


def current_revision(url: str) -> str:
    engine = create_engine(url)
    try:
        with engine.connect() as connection:
            revision = connection.scalar(text("SELECT version_num FROM alembic_version"))
            if not isinstance(revision, str):
                raise RuntimeError("Alembic revision is not available")
            return revision
    finally:
        engine.dispose()


def table_columns(url: str, table_name: str) -> set[str]:
    engine = create_engine(url)
    try:
        with engine.connect() as connection:
            return set(
                connection.scalars(
                    text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_schema = 'public' AND table_name = :table_name"
                    ),
                    {"table_name": table_name},
                )
            )
    finally:
        engine.dispose()


def table_exists(url: str, table_name: str) -> bool:
    engine = create_engine(url)
    try:
        with engine.connect() as connection:
            return bool(
                connection.scalar(
                    text("SELECT to_regclass(:qualified_name) IS NOT NULL"),
                    {"qualified_name": f"public.{table_name}"},
                )
            )
    finally:
        engine.dispose()


def constraint_exists(url: str, table_name: str, constraint_name: str) -> bool:
    engine = create_engine(url)
    try:
        with engine.connect() as connection:
            return bool(
                connection.scalar(
                    text(
                        "SELECT EXISTS (SELECT 1 FROM information_schema.table_constraints "
                        "WHERE table_schema = 'public' AND table_name = :table_name "
                        "AND constraint_name = :constraint_name)"
                    ),
                    {"table_name": table_name, "constraint_name": constraint_name},
                )
            )
    finally:
        engine.dispose()


def index_exists(url: str, table_name: str, index_name: str) -> bool:
    engine = create_engine(url)
    try:
        with engine.connect() as connection:
            return bool(
                connection.scalar(
                    text(
                        "SELECT EXISTS (SELECT 1 FROM pg_indexes "
                        "WHERE schemaname = 'public' AND tablename = :table_name "
                        "AND indexname = :index_name)"
                    ),
                    {"table_name": table_name, "index_name": index_name},
                )
            )
    finally:
        engine.dispose()


def forced_tenant_policy_exists(url: str, table_name: str) -> bool:
    engine = create_engine(url)
    try:
        with engine.connect() as connection:
            row = connection.execute(
                text(
                    "SELECT c.relrowsecurity, c.relforcerowsecurity, p.qual, p.with_check "
                    "FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                    "JOIN pg_policies p ON p.schemaname = n.nspname AND p.tablename = c.relname "
                    "WHERE n.nspname = 'public' AND c.relname = :table_name "
                    "AND p.policyname = 'tenant_isolation'"
                ),
                {"table_name": table_name},
            ).one_or_none()
            return bool(
                row
                and row.relrowsecurity
                and row.relforcerowsecurity
                and "app_current_tenant_id" in row.qual
                and "app_current_tenant_id" in row.with_check
            )
    finally:
        engine.dispose()


def trigger_exists(url: str, table_name: str, trigger_name: str) -> bool:
    engine = create_engine(url)
    try:
        with engine.connect() as connection:
            return bool(
                connection.scalar(
                    text(
                        "SELECT EXISTS (SELECT 1 FROM pg_trigger t "
                        "JOIN pg_class c ON c.oid = t.tgrelid "
                        "JOIN pg_namespace n ON n.oid = c.relnamespace "
                        "WHERE n.nspname = 'public' AND c.relname = :table_name "
                        "AND t.tgname = :trigger_name AND NOT t.tgisinternal AND t.tgenabled = 'O')"
                    ),
                    {"table_name": table_name, "trigger_name": trigger_name},
                )
            )
    finally:
        engine.dispose()


def patient_population_contract_exists(url: str) -> bool:
    return (
        table_exists(url, PATIENT_POPULATION_TABLE)
        and table_exists(url, PATIENT_POPULATION_LINK_TABLE)
        and "patient_population_id" in table_columns(url, "epidemiology_observations")
        and forced_tenant_policy_exists(url, PATIENT_POPULATION_TABLE)
        and forced_tenant_policy_exists(url, PATIENT_POPULATION_LINK_TABLE)
    )


def workspace_domain_export_contract_exists(url: str) -> bool:
    return (
        WORKSPACE_DOMAIN_EXPORT_COLUMNS.issubset(table_columns(url, "workspace_export_events"))
        and all(
            constraint_exists(url, "workspace_export_events", constraint)
            for constraint in WORKSPACE_DOMAIN_EXPORT_CONSTRAINTS
        )
        and all(index_exists(url, "workspace_export_events", index) for index in WORKSPACE_DOMAIN_EXPORT_INDEXES)
    )


def trial_result_relationship_contract_exists(url: str) -> bool:
    role_columns = table_columns(url, TRIAL_ENTITY_ROLE_TABLE)
    disclosure_columns = table_columns(url, TRIAL_DISCLOSURE_TABLE)
    return (
        {"trial_id", "entity_id", "role", "source_document_id"}.issubset(role_columns)
        and {
            "trial_id",
            "disclosure_key",
            "version",
            "disclosure_type",
            "external_id",
            "disclosed_at",
            "conference_name",
            "is_key_result",
            "result_evaluation",
            "source_locator",
            "source_quote",
            "source_document_id",
        }.issubset(disclosure_columns)
        and constraint_exists(url, TRIAL_ENTITY_ROLE_TABLE, TRIAL_ENTITY_ROLE_CONSTRAINT)
        and constraint_exists(url, TRIAL_DISCLOSURE_TABLE, TRIAL_DISCLOSURE_VERSION_CONSTRAINT)
        and constraint_exists(url, TRIAL_DISCLOSURE_TABLE, TRIAL_DISCLOSURE_TYPE_CONSTRAINT)
        and constraint_exists(url, TRIAL_DISCLOSURE_TABLE, TRIAL_DISCLOSURE_EVALUATION_CONSTRAINT)
        and index_exists(url, TRIAL_ENTITY_ROLE_TABLE, TRIAL_ENTITY_ROLE_INDEX)
        and index_exists(url, TRIAL_DISCLOSURE_TABLE, TRIAL_DISCLOSURE_INDEX)
        and forced_tenant_policy_exists(url, TRIAL_ENTITY_ROLE_TABLE)
        and forced_tenant_policy_exists(url, TRIAL_DISCLOSURE_TABLE)
    )


def deal_intelligence_contract_exists(url: str) -> bool:
    return (
        DEAL_PROFILE_COLUMNS.issubset(table_columns(url, "deal_profiles"))
        and {"deal_id", "party_entity_id", "role", "country_region", "organization_type"}.issubset(
            table_columns(url, DEAL_PARTY_TABLE)
        )
        and {"deal_id", "asset_entity_id", "development_phase_at_transaction"}.issubset(
            table_columns(url, DEAL_ASSET_TABLE)
        )
        and {"deal_id", "holder_entity_id", "right_type", "territory", "exclusive"}.issubset(
            table_columns(url, DEAL_RIGHT_TABLE)
        )
        and constraint_exists(url, "deal_profiles", "ck_deal_profile_status")
        and constraint_exists(url, "deal_profiles", "ck_deal_profile_direction")
        and constraint_exists(url, DEAL_PARTY_TABLE, "ck_deal_party_role")
        and constraint_exists(url, DEAL_ASSET_TABLE, "ck_deal_asset_transaction_phase")
        and constraint_exists(url, DEAL_RIGHT_TABLE, "ck_deal_right_type")
        and index_exists(url, DEAL_PARTY_TABLE, "ix_deal_party_role_lookup")
        and index_exists(url, DEAL_ASSET_TABLE, "ix_deal_asset_phase_lookup")
        and index_exists(url, DEAL_RIGHT_TABLE, "ix_deal_right_lookup")
        and all(
            forced_tenant_policy_exists(url, table) for table in (DEAL_PARTY_TABLE, DEAL_ASSET_TABLE, DEAL_RIGHT_TABLE)
        )
    )


def regulatory_intelligence_contract_exists(url: str) -> bool:
    return (
        REGULATORY_INTELLIGENCE_COLUMNS.issubset(table_columns(url, "regulatory_events"))
        and all(
            constraint_exists(url, "regulatory_events", constraint)
            for constraint in REGULATORY_INTELLIGENCE_CONSTRAINTS
        )
        and all(index_exists(url, "regulatory_events", index) for index in REGULATORY_INTELLIGENCE_INDEXES)
    )


def pipeline_regional_contract_exists(url: str) -> bool:
    return (
        PIPELINE_REGIONAL_COLUMNS.issubset(table_columns(url, "development_programs"))
        and all(
            constraint_exists(url, "development_programs", constraint) for constraint in PIPELINE_REGIONAL_CONSTRAINTS
        )
        and all(index_exists(url, "development_programs", index) for index in PIPELINE_REGIONAL_INDEXES)
    )


def program_target_contract_exists(url: str) -> bool:
    return (
        table_exists(url, PROGRAM_TARGET_TABLE)
        and {"target_set_version", "target_combination_key"}.issubset(table_columns(url, "development_programs"))
        and PROGRAM_TARGET_COLUMNS.issubset(table_columns(url, PROGRAM_TARGET_TABLE))
        and all(constraint_exists(url, PROGRAM_TARGET_TABLE, constraint) for constraint in PROGRAM_TARGET_CONSTRAINTS)
        and all(index_exists(url, PROGRAM_TARGET_TABLE, index) for index in PROGRAM_TARGET_INDEXES)
        and index_exists(url, "development_programs", "ix_program_target_combination_lookup")
        and forced_tenant_policy_exists(url, PROGRAM_TARGET_TABLE)
        and trigger_exists(url, PROGRAM_TARGET_TABLE, "immutable_development_program_targets")
    )


def program_organization_contract_exists(url: str) -> bool:
    return (
        table_exists(url, PROGRAM_ORGANIZATION_TABLE)
        and "organization_set_version" in table_columns(url, "development_programs")
        and PROGRAM_ORGANIZATION_COLUMNS.issubset(table_columns(url, PROGRAM_ORGANIZATION_TABLE))
        and all(
            constraint_exists(url, PROGRAM_ORGANIZATION_TABLE, constraint)
            for constraint in PROGRAM_ORGANIZATION_CONSTRAINTS
        )
        and all(index_exists(url, PROGRAM_ORGANIZATION_TABLE, index) for index in PROGRAM_ORGANIZATION_INDEXES)
        and forced_tenant_policy_exists(url, PROGRAM_ORGANIZATION_TABLE)
        and trigger_exists(
            url,
            PROGRAM_ORGANIZATION_TABLE,
            "immutable_development_program_organizations",
        )
    )


def run() -> dict[str, Any]:
    args = parse_args()
    if args.host not in {"127.0.0.1", "localhost", "::1"}:
        raise RuntimeError("Migration round-trip verification only permits a loopback PostgreSQL host")
    repository_root = Path(__file__).resolve().parents[1]
    env_path = args.env_file if args.env_file.is_absolute() else repository_root / args.env_file
    raw_values = dotenv_values(env_path)
    values = {key: value for key, value in raw_values.items() if isinstance(value, str)}
    username = required(values, "POSTGRES_USER")
    password = required(values, "POSTGRES_PASSWORD")
    database = f"{DATABASE_PREFIX}{secrets.token_hex(6)}"
    if not database.startswith(DATABASE_PREFIX):
        raise RuntimeError("Unsafe migration verification database name")
    url = database_url(username, password, args.host, args.port, database)
    admin_options = {
        "host": args.host,
        "port": args.port,
        "dbname": "postgres",
        "user": username,
        "password": password,
        "autocommit": True,
    }
    with psycopg.connect(**admin_options) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    previous_database_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = url
    config = migration_config(repository_root)
    try:
        heads = ScriptDirectory.from_config(config).get_heads()
        if len(heads) != 1:
            raise RuntimeError(f"Expected one Alembic head, found: {', '.join(heads) or 'none'}")
        head_revision = heads[0]
        get_settings.cache_clear()
        command.upgrade(config, "head")
        upgraded_revision = current_revision(url)
        upgraded_labels = enum_labels(url)
        upgraded_columns = table_columns(url, "source_versions")
        upgraded_source_columns = table_columns(url, "data_sources")
        upgraded_trial_columns = table_columns(url, "clinical_trial_profiles")
        if upgraded_revision != head_revision:
            raise RuntimeError(f"Unexpected upgraded revision: {upgraded_revision}")
        if upgraded_labels != ["FOLDER", "HTTP_MANIFEST", "S3_SNAPSHOT", "SFTP_SNAPSHOT", "SMB_SNAPSHOT"]:
            raise RuntimeError(f"Unexpected upgraded data-source enum: {upgraded_labels}")
        if not MALWARE_SCAN_COLUMNS.issubset(upgraded_columns):
            raise RuntimeError("Malware scan columns are missing after upgrade")
        if not SOURCE_AUTHORIZATION_COLUMNS.issubset(upgraded_source_columns) or not constraint_exists(
            url, "data_sources", "ck_data_source_authorization_window"
        ):
            raise RuntimeError("Source authorization window contract is missing after upgrade")
        if (
            TRIAL_RESULT_EVALUATION_COLUMN not in upgraded_trial_columns
            or not constraint_exists(url, "clinical_trial_profiles", TRIAL_RESULT_EVALUATION_CONSTRAINT)
            or not index_exists(url, "clinical_trial_profiles", TRIAL_RESULT_EVALUATION_INDEX)
        ):
            raise RuntimeError("Clinical trial result evaluation contract is missing after upgrade")
        if not trial_result_relationship_contract_exists(url):
            raise RuntimeError("Clinical trial role and result disclosure contract is missing after upgrade")
        if not deal_intelligence_contract_exists(url):
            raise RuntimeError("Deal role, stage, rights, status and time contract is missing after upgrade")
        if table_exists(url, "research_bundles"):
            raise RuntimeError("Retired research artifact table remains after upgrade")
        if not index_exists(url, "commercial_policy_events", RISK_QUEUE_INDEX):
            raise RuntimeError("Commercial risk queue index is missing after upgrade")
        if not table_exists(url, "regulatory_events"):
            raise RuntimeError("Regulatory intelligence table is missing after upgrade")
        if not regulatory_intelligence_contract_exists(url):
            raise RuntimeError("Regulatory label, designation and safety contract is missing after upgrade")
        if not pipeline_regional_contract_exists(url):
            raise RuntimeError("Pipeline regional phase, rights and tags contract is missing after upgrade")
        if not program_target_contract_exists(url):
            raise RuntimeError("Versioned program target contract is missing after upgrade")
        if not program_organization_contract_exists(url):
            raise RuntimeError("Versioned program organization contract is missing after upgrade")
        if not forced_tenant_policy_exists(url, "regulatory_events"):
            raise RuntimeError("Regulatory intelligence forced tenant RLS policy is missing after upgrade")
        if not table_exists(url, "fact_provenance_links"):
            raise RuntimeError("Fact provenance table is missing after upgrade")
        if not forced_tenant_policy_exists(url, "fact_provenance_links"):
            raise RuntimeError("Fact provenance forced tenant RLS policy is missing after upgrade")
        if not patient_population_contract_exists(url):
            raise RuntimeError("Governed patient population schema or forced tenant RLS is missing after upgrade")
        if not workspace_domain_export_contract_exists(url):
            raise RuntimeError("Governed workspace domain export contract is missing after upgrade")

        get_settings.cache_clear()
        command.downgrade(config, PRE_HTTP_MANIFEST_REVISION)
        downgraded_revision = current_revision(url)
        downgraded_labels = enum_labels(url)
        downgraded_columns = table_columns(url, "source_versions")
        downgraded_trial_columns = table_columns(url, "clinical_trial_profiles")
        downgraded_deal_columns = table_columns(url, "deal_profiles")
        if downgraded_revision != PRE_HTTP_MANIFEST_REVISION:
            raise RuntimeError(f"Unexpected downgraded revision: {downgraded_revision}")
        if downgraded_labels != ["FOLDER"]:
            raise RuntimeError(f"Unexpected downgraded data-source enum: {downgraded_labels}")
        if MALWARE_SCAN_COLUMNS & downgraded_columns:
            raise RuntimeError("Malware scan columns remain after downgrade")
        if TRIAL_RESULT_EVALUATION_COLUMN in downgraded_trial_columns:
            raise RuntimeError("Clinical trial result evaluation column remains after downgrade")
        if table_exists(url, TRIAL_ENTITY_ROLE_TABLE) or table_exists(url, TRIAL_DISCLOSURE_TABLE):
            raise RuntimeError("Clinical trial role or result disclosure tables remain after downgrade")
        if DEAL_PROFILE_COLUMNS & downgraded_deal_columns:
            raise RuntimeError("Expanded deal profile columns remain after downgrade")
        if any(table_exists(url, table) for table in (DEAL_PARTY_TABLE, DEAL_ASSET_TABLE, DEAL_RIGHT_TABLE)):
            raise RuntimeError("Expanded deal intelligence tables remain after downgrade")
        if table_exists(url, PATIENT_POPULATION_TABLE) or table_exists(url, PATIENT_POPULATION_LINK_TABLE):
            raise RuntimeError("Governed patient population tables remain after downgrade")
        if "patient_population_id" in table_columns(url, "epidemiology_observations"):
            raise RuntimeError("Patient population observation link remains after downgrade")
        if table_exists(url, "workspace_export_events") and WORKSPACE_DOMAIN_EXPORT_COLUMNS & table_columns(
            url, "workspace_export_events"
        ):
            raise RuntimeError("Workspace domain export columns remain after downgrade")
        if table_exists(url, PROGRAM_TARGET_TABLE):
            raise RuntimeError("Versioned program target table remains after downgrade")
        if {"target_set_version", "target_combination_key"} & table_columns(url, "development_programs"):
            raise RuntimeError("Versioned program target columns remain after downgrade")
        if table_exists(url, PROGRAM_ORGANIZATION_TABLE):
            raise RuntimeError("Versioned program organization table remains after downgrade")
        if "organization_set_version" in table_columns(url, "development_programs"):
            raise RuntimeError("Versioned program organization column remains after downgrade")

        get_settings.cache_clear()
        command.upgrade(config, "head")
        command.check(config)
        final_revision = current_revision(url)
        final_labels = enum_labels(url)
        final_columns = table_columns(url, "source_versions")
        final_source_columns = table_columns(url, "data_sources")
        final_trial_columns = table_columns(url, "clinical_trial_profiles")
        if final_revision != head_revision or final_labels != [
            "FOLDER",
            "HTTP_MANIFEST",
            "S3_SNAPSHOT",
            "SFTP_SNAPSHOT",
            "SMB_SNAPSHOT",
        ]:
            raise RuntimeError("Final migration state does not match the source connector schema contract")
        if not MALWARE_SCAN_COLUMNS.issubset(final_columns):
            raise RuntimeError("Malware scan columns are missing after final upgrade")
        if not SOURCE_AUTHORIZATION_COLUMNS.issubset(final_source_columns) or not constraint_exists(
            url, "data_sources", "ck_data_source_authorization_window"
        ):
            raise RuntimeError("Source authorization window contract is missing after final upgrade")
        if (
            TRIAL_RESULT_EVALUATION_COLUMN not in final_trial_columns
            or not constraint_exists(url, "clinical_trial_profiles", TRIAL_RESULT_EVALUATION_CONSTRAINT)
            or not index_exists(url, "clinical_trial_profiles", TRIAL_RESULT_EVALUATION_INDEX)
        ):
            raise RuntimeError("Clinical trial result evaluation contract is missing after final upgrade")
        if not trial_result_relationship_contract_exists(url):
            raise RuntimeError("Clinical trial role and result disclosure contract is missing after final upgrade")
        if not deal_intelligence_contract_exists(url):
            raise RuntimeError("Deal role, stage, rights, status and time contract is missing after final upgrade")
        if table_exists(url, "research_bundles"):
            raise RuntimeError("Retired research artifact table returned after migration round-trip")
        if not index_exists(url, "commercial_policy_events", RISK_QUEUE_INDEX):
            raise RuntimeError("Commercial risk queue index is missing after final upgrade")
        if not table_exists(url, "regulatory_events"):
            raise RuntimeError("Regulatory intelligence table is missing after final upgrade")
        if not regulatory_intelligence_contract_exists(url):
            raise RuntimeError("Regulatory label, designation and safety contract is missing after final upgrade")
        if not pipeline_regional_contract_exists(url):
            raise RuntimeError("Pipeline regional phase, rights and tags contract is missing after final upgrade")
        if not program_target_contract_exists(url):
            raise RuntimeError("Versioned program target contract is missing after final upgrade")
        if not program_organization_contract_exists(url):
            raise RuntimeError("Versioned program organization contract is missing after final upgrade")
        if not forced_tenant_policy_exists(url, "regulatory_events"):
            raise RuntimeError("Regulatory intelligence forced tenant RLS policy is missing after final upgrade")
        if not table_exists(url, "fact_provenance_links"):
            raise RuntimeError("Fact provenance table is missing after final upgrade")
        if not forced_tenant_policy_exists(url, "fact_provenance_links"):
            raise RuntimeError("Fact provenance forced tenant RLS policy is missing after final upgrade")
        if not patient_population_contract_exists(url):
            raise RuntimeError("Governed patient population schema or forced tenant RLS is missing after final upgrade")
        if not workspace_domain_export_contract_exists(url):
            raise RuntimeError("Governed workspace domain export contract is missing after final upgrade")
        return {
            "status": "passed",
            "database_kind": "isolated-postgresql",
            "upgrade_revision": upgraded_revision,
            "downgrade_revision": downgraded_revision,
            "final_revision": final_revision,
            "final_enum_labels": final_labels,
        }
    finally:
        get_settings.cache_clear()
        if previous_database_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous_database_url
        with psycopg.connect(**admin_options) as admin:
            admin.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = %s AND pid <> pg_backend_pid()",
                (database,),
            )
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(database)))


def main() -> None:
    print(json.dumps(run(), ensure_ascii=True, sort_keys=True))


if __name__ == "__main__":
    main()
