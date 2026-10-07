from __future__ import annotations

import hashlib
import json

from pharma_intel.governance.schemas import Citation, EntityAliasFact, EntityReference


def name_facts(subject: EntityReference, aliases: list[str], *, resource: str) -> tuple[EntityAliasFact, ...]:
    identifier = subject.external_ids["chembl"]
    return tuple(
        EntityAliasFact(
            fact_kind="entity_alias",
            subject=subject,
            alias=alias,
            citation=Citation(
                locator=f"{resource}:{identifier}:alias:{hashlib.sha256(alias.encode()).hexdigest()[:16]}",
                quote=json.dumps(
                    {"chembl_id": identifier, "pref_name": subject.name, "alias": alias}, ensure_ascii=False
                ),
                confidence=1,
            ),
        )
        for alias in aliases
    )
