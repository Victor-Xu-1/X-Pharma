from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

from pharma_intel.operational_metrics import OPERATIONAL_METRIC_NAMES

DEFAULT_CONTRACT = Path("deploy/operations/operations-contract.yaml")
# The pinned FastAPI instrumentation currently emits this semantic-convention name.
# Upgrading that convention must update the versioned contract and acceptance evidence.
STANDARD_METRICS = frozenset({"http.server.duration"})
REQUIRED_SERVICES = frozenset(
    {
        "workspace",
        "api",
        "mcp",
        "data-factory",
        "search-projector",
        "search-maintenance",
        "billing-provider",
        "parser",
        "clamav",
    }
)
REQUIRED_RESPONSIBILITIES = frozenset(
    {
        "on_call",
        "incident_command",
        "customer_communications",
        "data_quality",
        "model_budget",
        "billing_support",
        "security_incidents",
        "change_approval",
    }
)


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Service(ContractModel):
    id: str = Field(pattern=r"^[a-z][a-z0-9-]{1,63}$")
    owner: str = Field(pattern=r"^[a-z][a-z0-9-]{2,79}$")
    escalation_policy: str = Field(pattern=r"^role://[a-z0-9-]+/[a-z0-9-]+$")


class Indicator(ContractModel):
    metric: str
    measurement: str = Field(pattern=r"^[a-z][a-z0-9_]{2,79}$")
    filters: dict[str, str]


class Objective(ContractModel):
    id: str = Field(pattern=r"^[a-z][a-z0-9-]{2,79}$")
    service: str
    indicator: Indicator
    target: float = Field(gt=0)
    window: str = Field(pattern=r"^[1-9][0-9]*(?:m|h|d)$")
    error_budget_policy: str = Field(pattern=r"^[a-z][a-z0-9_]{2,79}$")


class Alert(ContractModel):
    id: str = Field(pattern=r"^[a-z][a-z0-9-]{2,79}$")
    objective: str
    severity: Literal["warning", "critical"]
    threshold: float = Field(ge=0)
    lookback: str = Field(pattern=r"^[1-9][0-9]*(?:m|h|d)$")
    runbook: str


class OperationsContract(ContractModel):
    schema_version: Literal[1]
    services: list[Service]
    objectives: list[Objective]
    alerts: list[Alert]
    responsibilities: dict[str, str]


class OperationsContractError(ValueError):
    pass


def load_operations_contract(contract_path: Path) -> OperationsContract:
    try:
        raw = yaml.safe_load(contract_path.read_text(encoding="utf-8"))
        return OperationsContract.model_validate(raw)
    except (OSError, yaml.YAMLError, ValueError) as exc:
        raise OperationsContractError(f"Operations contract is invalid: {exc}") from exc


def _unique(values: list[str], label: str) -> None:
    if len(values) != len(set(values)):
        raise OperationsContractError(f"Operations contract contains duplicate {label}")


def verify_operations_contract(contract_path: Path, repository: Path) -> dict[str, object]:
    repository = repository.resolve(strict=True)
    contract_path = contract_path.resolve(strict=True)
    contract = load_operations_contract(contract_path)

    service_ids = [service.id for service in contract.services]
    objective_ids = [objective.id for objective in contract.objectives]
    alert_ids = [alert.id for alert in contract.alerts]
    _unique(service_ids, "service IDs")
    _unique(objective_ids, "objective IDs")
    _unique(alert_ids, "alert IDs")
    missing_services = sorted(REQUIRED_SERVICES - set(service_ids))
    if missing_services:
        raise OperationsContractError(f"Operations contract is missing services: {', '.join(missing_services)}")
    missing_responsibilities = sorted(REQUIRED_RESPONSIBILITIES - set(contract.responsibilities))
    if missing_responsibilities:
        raise OperationsContractError(
            f"Operations contract is missing responsibilities: {', '.join(missing_responsibilities)}"
        )
    if any(not value.strip() or "example" in value.casefold() for value in contract.responsibilities.values()):
        raise OperationsContractError("Operations responsibilities cannot be blank or placeholders")

    allowed_metrics = OPERATIONAL_METRIC_NAMES | STANDARD_METRICS
    for objective in contract.objectives:
        if objective.service not in service_ids:
            raise OperationsContractError(f"Objective {objective.id} references an unknown service")
        if objective.indicator.metric not in allowed_metrics:
            raise OperationsContractError(f"Objective {objective.id} references an unknown metric")
        if any(len(key) > 80 or len(value) > 80 for key, value in objective.indicator.filters.items()):
            raise OperationsContractError(f"Objective {objective.id} contains an unbounded filter")

    alert_objectives: set[str] = set()
    runbooks: set[str] = set()
    for alert in contract.alerts:
        if alert.objective not in objective_ids:
            raise OperationsContractError(f"Alert {alert.id} references an unknown objective")
        alert_objectives.add(alert.objective)
        relative = Path(alert.runbook)
        if relative.is_absolute() or ".." in relative.parts or not alert.runbook.startswith("runbooks/"):
            raise OperationsContractError(f"Alert {alert.id} has an unsafe runbook path")
        runbook = (repository / relative).resolve(strict=True)
        if not runbook.is_relative_to(repository / "runbooks") or not runbook.is_file():
            raise OperationsContractError(f"Alert {alert.id} runbook is unavailable")
        runbooks.add(alert.runbook)
    missing_alerts = sorted(set(objective_ids) - alert_objectives)
    if missing_alerts:
        raise OperationsContractError(f"Objectives without alerts: {', '.join(missing_alerts)}")

    return {
        "schema_version": 1,
        "status": "passed",
        "contract": str(contract_path.relative_to(repository)),
        "service_count": len(contract.services),
        "objective_count": len(contract.objectives),
        "alert_count": len(contract.alerts),
        "metrics": sorted({objective.indicator.metric for objective in contract.objectives}),
        "runbooks": sorted(runbooks),
        "responsibilities": sorted(contract.responsibilities),
        "production_claim": False,
    }


def _write_report(path: Path, report: dict[str, object]) -> None:
    parent = path.parent.resolve()
    parent.mkdir(parents=True, exist_ok=True)
    if path.exists() or path.is_symlink():
        raise OperationsContractError(f"Operations report already exists: {path}")
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        temporary.chmod(0o600)
        os.link(temporary, parent / path.name, follow_symlinks=False)
    finally:
        temporary.unlink(missing_ok=True)


def run() -> None:
    parser = argparse.ArgumentParser(description="Verify the machine-readable operations and SLO contract")
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    try:
        report = verify_operations_contract(arguments.contract, arguments.repository)
        if arguments.output:
            _write_report(arguments.output, report)
    except (OSError, OperationsContractError) as exc:
        parser.error(str(exc))
    print(json.dumps(report, sort_keys=True))
