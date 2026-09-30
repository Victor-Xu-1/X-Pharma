from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from pharma_intel.licensing import DeliveryChannel, EvidenceLicensePolicy
from pharma_intel.models import TenantDataset
from pharma_intel.security import Principal


class DatasetSelectionError(ValueError):
    pass


class DatasetAccessDenied(PermissionError):
    pass


@dataclass(frozen=True)
class ResolvedDataset:
    key: str
    license_policy: EvidenceLicensePolicy


class DatasetRepository:
    def __init__(self, session: Session, tenant_id: str) -> None:
        self.session = session
        self.tenant_id = tenant_id

    def resolve_for_principal(
        self,
        principal: Principal,
        requested_keys: list[str],
        *,
        allow_empty: bool = False,
        at: datetime | None = None,
    ) -> list[ResolvedDataset]:
        normalized_keys = list(dict.fromkeys(key.strip() for key in requested_keys if key.strip()))
        channel: DeliveryChannel = "web" if principal.actor_type == "user" else "mcp"
        evaluated_at = at or datetime.now(UTC)
        statement = select(TenantDataset).where(
            TenantDataset.tenant_id == self.tenant_id,
            TenantDataset.active.is_(True),
        )
        if normalized_keys:
            statement = statement.where(TenantDataset.dataset_key.in_(normalized_keys))
        datasets = list(self.session.scalars(statement.order_by(TenantDataset.dataset_key)))

        if normalized_keys:
            found = {dataset.dataset_key for dataset in datasets}
            missing = sorted(set(normalized_keys) - found)
            if missing:
                raise DatasetSelectionError(f"Datasets are unavailable: {', '.join(missing)}")

        allowed: list[ResolvedDataset] = []
        denied: list[str] = []
        for dataset in datasets:
            try:
                license_policy = EvidenceLicensePolicy.model_validate(dataset.license_policy)
            except ValidationError as exc:
                raise DatasetSelectionError(f"Dataset {dataset.dataset_key} has an invalid license policy") from exc
            required = frozenset(dataset.required_scopes)
            has_scope = "*" in principal.scopes or required.issubset(principal.scopes)
            if has_scope and license_policy.permits(channel, evaluated_at):
                allowed.append(
                    ResolvedDataset(
                        dataset.dataset_key,
                        license_policy,
                    )
                )
            elif dataset.dataset_key in normalized_keys:
                denied.append(dataset.dataset_key)

        if denied:
            raise DatasetAccessDenied("The caller is not licensed for one or more requested datasets")
        if not allowed and not allow_empty:
            raise DatasetSelectionError("No authorized evidence datasets are configured")
        return allowed
