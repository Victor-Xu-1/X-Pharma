from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from pharma_intel.config import Settings
from pharma_intel.enterprise.llm_providers import effective_ai_settings
from pharma_intel.governance.chembl import ADAPTER_NAME as CHEMBL_PROFILE
from pharma_intel.governance.chembl import adapter_policy_manifest as chembl_policy_manifest
from pharma_intel.governance.clinicaltrials_gov import ADAPTER_NAME as TRIAL_PROFILE
from pharma_intel.governance.clinicaltrials_gov import adapter_policy_manifest as trial_policy_manifest
from pharma_intel.governance.contracts import SCHEMA_VERSION
from pharma_intel.governance.fact_identity import _hash_json
from pharma_intel.governance.nextpharma import ADAPTER_NAME as NEXTPHARMA_PROFILE
from pharma_intel.governance.nextpharma import adapter_policy_manifest as nextpharma_policy_manifest
from pharma_intel.governance.nextpharma import is_authorized_nextpharma_asset
from pharma_intel.governance.policy import governance_policy_sha256
from pharma_intel.models import DataSource, DataSourceType, SourceAsset, SourceVersion


@dataclass(frozen=True)
class SourceGovernancePolicy:
    mode: Literal["deterministic", "model"]
    sha256: str


def source_profile(session: Session, version: SourceVersion) -> str | None:
    context = session.execute(
        select(DataSource, SourceAsset)
        .join(SourceAsset, SourceAsset.data_source_id == DataSource.id)
        .where(
            DataSource.tenant_id == version.tenant_id,
            SourceAsset.tenant_id == version.tenant_id,
            SourceAsset.id == version.source_asset_id,
        )
    ).one_or_none()
    if context is None:
        return None
    source, asset = context
    if source.source_type == DataSourceType.CLINICALTRIALS_GOV:
        return TRIAL_PROFILE
    if source.source_type == DataSourceType.CHEMBL:
        return CHEMBL_PROFILE
    if source.source_type == DataSourceType.PUBMED:
        return "pubmed"
    if is_authorized_nextpharma_asset(
        file_name=asset.file_name,
        extension=asset.extension,
        authorization_scopes=list(source.authorization_scopes or []),
    ):
        return NEXTPHARMA_PROFILE
    return None


def deterministic_policy_sha256(profile: str, settings: Settings) -> str:
    """Preserve existing adapter identities; model configuration is not an official-data policy."""
    if profile == TRIAL_PROFILE:
        return _hash_json(trial_policy_manifest())
    if profile == CHEMBL_PROFILE:
        manifest = chembl_policy_manifest()
        return _hash_json(
            {
                "base_policy_sha256": _hash_json(
                    {
                        "governance_schema": SCHEMA_VERSION,
                        "source_type": DataSourceType.CHEMBL.value,
                        "deterministic_policy": manifest,
                    }
                ),
                "source_profile": manifest,
            }
        )
    if profile == NEXTPHARMA_PROFILE:
        return _hash_json(
            {
                "base_policy_sha256": governance_policy_sha256(settings),
                "source_profile": nextpharma_policy_manifest(),
            }
        )
    raise ValueError("Unknown deterministic governance profile")


def source_governance_policy(
    session: Session, settings: Settings, version: SourceVersion
) -> SourceGovernancePolicy | None:
    profile = source_profile(session, version)
    if profile in {TRIAL_PROFILE, CHEMBL_PROFILE}:
        if not settings.deterministic_governance_enabled:
            return None
        return SourceGovernancePolicy("deterministic", deterministic_policy_sha256(profile, settings))
    if not settings.ai_governance_enabled:
        return None
    if profile == NEXTPHARMA_PROFILE:
        return SourceGovernancePolicy("deterministic", deterministic_policy_sha256(profile, settings))
    model_settings = effective_ai_settings(session, settings, version.tenant_id)
    return SourceGovernancePolicy("model", governance_policy_sha256(model_settings))
