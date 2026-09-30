from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

SourceVersionReplayStage = Literal["auto", "malware_scan", "parse", "governance", "retrieval"]


@dataclass(frozen=True)
class ScanInput:
    tenant_id: str
    data_source_id: str
    workflow_id: str


@dataclass(frozen=True)
class ProcessInput:
    tenant_id: str
    source_version_id: str
    ingestion_run_id: str | None = None
    from_stage: SourceVersionReplayStage = "malware_scan"
