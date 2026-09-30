from __future__ import annotations

from pharma_intel.ingest.contracts import SourceVersionReplayStage
from pharma_intel.models import QuarantineStatus, SourceVersion, StageStatus

MALWARE_FAILURE_CODES = frozenset(
    {
        "malware_detected",
        "malware_scan_rejected",
        "malware_scan_unavailable",
        "snapshot_materialization_failed",
    }
)
PARSE_FAILURE_CODES = frozenset({"parse_failed", "parser_service_unavailable"})
GOVERNANCE_FAILURE_CODES = frozenset({"governance_model_failed", "governance_budget_error", "governance_policy_error"})


def replayable_source_version_stages(
    version: SourceVersion,
    *,
    ai_governance_enabled: bool,
) -> list[SourceVersionReplayStage]:
    if version.snapshot_status != StageStatus.SUCCEEDED or not version.raw_object_uri:
        return []
    if version.quarantine_status not in {
        QuarantineStatus.NOT_APPLICABLE,
        QuarantineStatus.CLEARED,
    }:
        return []
    if version.malware_scan_status == StageStatus.FAILED and version.error_code in MALWARE_FAILURE_CODES:
        return ["malware_scan"]
    if (
        version.error_code in PARSE_FAILURE_CODES
        and version.parse_status in {StageStatus.FAILED, StageStatus.NOT_STARTED}
        and version.malware_scan_status in {StageStatus.SUCCEEDED, StageStatus.SKIPPED}
    ):
        # Keep the original full safety replay available while preferring the
        # narrower parse restart in the operator UI.
        return ["malware_scan", "parse"]
    if (
        ai_governance_enabled
        and version.governance_status == StageStatus.FAILED
        and version.error_code in GOVERNANCE_FAILURE_CODES
        and version.parse_status == StageStatus.SUCCEEDED
        and version.source_document_id is not None
        and version.extracted_text_object_uri is not None
    ):
        return ["governance"]
    if (
        version.retrieval_status == StageStatus.FAILED
        and version.parse_status == StageStatus.SUCCEEDED
        and version.source_document_id is not None
    ):
        return ["retrieval"]
    return []
