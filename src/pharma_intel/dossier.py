from __future__ import annotations

DOSSIER_RECORD_COLLECTIONS = (
    "relationships",
    "activities",
    "programs",
    "clinical_trials",
    "patents",
    "deals",
    "regulatory_events",
    "news_events",
    "structures",
    "target_evidence",
)


def dossier_result_capacity(per_domain_limit: int) -> int:
    return 1 + len(DOSSIER_RECORD_COLLECTIONS) * per_domain_limit
