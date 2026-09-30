from __future__ import annotations

import hashlib
import json
from collections import Counter
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pharma_intel.db import set_tenant_context
from pharma_intel.models import KnowledgeLink, KnowledgePage, KnowledgePageVersion
from pharma_intel.schemas import (
    KnowledgeFactChangeRead,
    KnowledgePageCoverageRead,
    KnowledgePredicateCoverageRead,
    KnowledgeSourceChangeRead,
    KnowledgeVersionDiffRead,
    KnowledgeVersionSummaryRead,
)

MAX_DIFF_ITEMS_PER_KIND = 100


class KnowledgeReadError(Exception):
    pass


class KnowledgePageNotFound(KnowledgeReadError):
    pass


class KnowledgeVersionNotFound(KnowledgeReadError):
    pass


class KnowledgeReadService:
    def __init__(self, session: Session, tenant_id: str) -> None:
        self.session = session
        self.tenant_id = tenant_id
        set_tenant_context(session, tenant_id)

    def coverage(self, page_id: str) -> KnowledgePageCoverageRead:
        page = self._page(page_id)
        if not page.current_version_id:
            raise KnowledgeVersionNotFound("Knowledge page has no current version")
        version = self.session.scalar(
            select(KnowledgePageVersion).where(
                KnowledgePageVersion.id == page.current_version_id,
                KnowledgePageVersion.tenant_id == self.tenant_id,
                KnowledgePageVersion.knowledge_page_id == page.id,
            )
        )
        if version is None:
            raise KnowledgeVersionNotFound("Knowledge page current version is unavailable")

        facts = _object_list(version.content_json.get("facts"))
        sources = _object_list(version.content_json.get("sources"))
        source_numbers = {
            number for source in sources if (number := _positive_integer(source.get("number"))) is not None
        }
        predicate_counts: Counter[str] = Counter()
        cited_predicate_counts: Counter[str] = Counter()
        cited_fact_count = 0
        for fact in facts:
            predicate = str(fact.get("predicate") or "unclassified")
            predicate_counts[predicate] += 1
            if _positive_integer(fact.get("citation")) in source_numbers:
                cited_fact_count += 1
                cited_predicate_counts[predicate] += 1
        linked_entity_count = int(
            self.session.scalar(
                select(func.count(func.distinct(KnowledgeLink.target_key))).where(
                    KnowledgeLink.tenant_id == self.tenant_id,
                    KnowledgeLink.page_version_id == version.id,
                )
            )
            or 0
        )
        return KnowledgePageCoverageRead(
            page_id=page.id,
            version_id=version.id,
            version_number=version.version_number,
            fact_count=len(facts),
            cited_fact_count=cited_fact_count,
            uncited_fact_count=len(facts) - cited_fact_count,
            source_count=len({_source_identity(source) for source in sources}),
            linked_entity_count=linked_entity_count,
            predicates=[
                KnowledgePredicateCoverageRead(
                    predicate=predicate,
                    fact_count=count,
                    cited_fact_count=cited_predicate_counts[predicate],
                )
                for predicate, count in sorted(predicate_counts.items())
            ],
            source_snapshot_at=version.source_snapshot_at,
        )

    def version_history(self, page_id: str, limit: int) -> list[KnowledgeVersionSummaryRead]:
        page = self._page(page_id)
        versions = list(
            self.session.scalars(
                select(KnowledgePageVersion)
                .where(
                    KnowledgePageVersion.tenant_id == self.tenant_id,
                    KnowledgePageVersion.knowledge_page_id == page.id,
                )
                .order_by(KnowledgePageVersion.version_number.desc())
                .limit(limit + 1)
            )
        )
        selected = versions[:limit]
        by_number = {version.version_number: version for version in versions}
        history: list[KnowledgeVersionSummaryRead] = []
        for version in selected:
            previous = by_number.get(version.version_number - 1)
            counts = _diff_counts(previous.content_json if previous else None, version.content_json)
            history.append(
                KnowledgeVersionSummaryRead(
                    version_id=version.id,
                    version_number=version.version_number,
                    compiler_version=version.compiler_version,
                    content_sha256=version.content_sha256,
                    source_snapshot_at=version.source_snapshot_at,
                    created_at=version.created_at,
                    created_by_run_id=version.created_by_run_id,
                    is_current=version.id == page.current_version_id,
                    previous_version_number=previous.version_number if previous else None,
                    fact_count=len(_object_list(version.content_json.get("facts"))),
                    source_count=len(_source_map(version.content_json)),
                    **counts,
                )
            )
        return history

    def version_diff(
        self,
        page_id: str,
        version_number: int,
        compare_to_version_number: int | None,
    ) -> KnowledgeVersionDiffRead:
        page = self._page(page_id)
        target = self._version(page.id, version_number)
        base_number = compare_to_version_number if compare_to_version_number is not None else version_number - 1
        if base_number < 1:
            base = None
            base_number = 0
        else:
            base = self._version(page.id, base_number)

        old_facts = _fact_map(base.content_json if base else {})
        new_facts = _fact_map(target.content_json)
        old_sources = _source_map(base.content_json if base else {})
        new_sources = _source_map(target.content_json)
        added_fact_keys = sorted(new_facts.keys() - old_facts.keys())
        removed_fact_keys = sorted(old_facts.keys() - new_facts.keys())
        added_source_keys = sorted(new_sources.keys() - old_sources.keys())
        removed_source_keys = sorted(old_sources.keys() - new_sources.keys())
        truncated = any(
            len(items) > MAX_DIFF_ITEMS_PER_KIND
            for items in (added_fact_keys, removed_fact_keys, added_source_keys, removed_source_keys)
        )
        return KnowledgeVersionDiffRead(
            page_id=page.id,
            from_version_number=base.version_number if base else None,
            to_version_number=target.version_number,
            added_fact_count=len(added_fact_keys),
            removed_fact_count=len(removed_fact_keys),
            added_source_count=len(added_source_keys),
            removed_source_count=len(removed_source_keys),
            added_facts=[
                _fact_change(key, new_facts[key], new_sources) for key in added_fact_keys[:MAX_DIFF_ITEMS_PER_KIND]
            ],
            removed_facts=[
                _fact_change(key, old_facts[key], old_sources) for key in removed_fact_keys[:MAX_DIFF_ITEMS_PER_KIND]
            ],
            added_sources=[_source_change(new_sources[key]) for key in added_source_keys[:MAX_DIFF_ITEMS_PER_KIND]],
            removed_sources=[_source_change(old_sources[key]) for key in removed_source_keys[:MAX_DIFF_ITEMS_PER_KIND]],
            truncated=truncated,
        )

    def _page(self, page_id: str) -> KnowledgePage:
        page = self.session.scalar(
            select(KnowledgePage).where(
                KnowledgePage.id == page_id,
                KnowledgePage.tenant_id == self.tenant_id,
            )
        )
        if page is None:
            raise KnowledgePageNotFound("Knowledge page not found")
        return page

    def _version(self, page_id: str, version_number: int) -> KnowledgePageVersion:
        version = self.session.scalar(
            select(KnowledgePageVersion).where(
                KnowledgePageVersion.tenant_id == self.tenant_id,
                KnowledgePageVersion.knowledge_page_id == page_id,
                KnowledgePageVersion.version_number == version_number,
            )
        )
        if version is None:
            raise KnowledgeVersionNotFound("Knowledge page version not found")
        return version


def _object_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)


def _fact_map(content: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for fact in _object_list(content.get("facts")):
        comparable = {
            "id": fact.get("id"),
            "predicate": fact.get("predicate"),
            "object_entity": fact.get("object_entity"),
            "value": fact.get("value"),
            "confidence": fact.get("confidence"),
        }
        digest = hashlib.sha256(_canonical_json(comparable).encode()).hexdigest()
        result[digest] = fact
    return result


def _source_map(content: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {_source_identity(source): source for source in _object_list(content.get("sources"))}


def _source_identity(source: dict[str, Any]) -> str:
    document_id = str(source.get("document_id") or "").strip()
    if document_id:
        return document_id
    return hashlib.sha256(
        _canonical_json(
            {
                "title": source.get("title"),
                "source_uri": source.get("source_uri"),
                "locator": source.get("locator"),
            }
        ).encode()
    ).hexdigest()


def _diff_counts(old_content: dict[str, Any] | None, new_content: dict[str, Any]) -> dict[str, int]:
    old_facts = _fact_map(old_content or {})
    new_facts = _fact_map(new_content)
    old_sources = _source_map(old_content or {})
    new_sources = _source_map(new_content)
    return {
        "added_fact_count": len(new_facts.keys() - old_facts.keys()),
        "removed_fact_count": len(old_facts.keys() - new_facts.keys()),
        "added_source_count": len(new_sources.keys() - old_sources.keys()),
        "removed_source_count": len(old_sources.keys() - new_sources.keys()),
    }


def _positive_integer(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        return None
    return int(value)


def _fact_change(
    change_key: str,
    fact: dict[str, Any],
    sources: dict[str, dict[str, Any]],
) -> KnowledgeFactChangeRead:
    citation_number = _positive_integer(fact.get("citation"))
    source = next(
        (item for item in sources.values() if _positive_integer(item.get("number")) == citation_number),
        None,
    )
    object_entity = fact.get("object_entity")
    return KnowledgeFactChangeRead(
        change_key=change_key,
        fact_id=str(fact["id"]) if fact.get("id") is not None else None,
        predicate=str(fact.get("predicate") or "unclassified"),
        object_entity_name=(
            str(object_entity.get("name"))
            if isinstance(object_entity, dict) and object_entity.get("name") is not None
            else None
        ),
        value=fact.get("value"),
        confidence=float(fact["confidence"]) if isinstance(fact.get("confidence"), int | float) else None,
        citation_number=citation_number,
        source_document_id=str(source.get("document_id")) if source and source.get("document_id") else None,
        source_title=str(source.get("title")) if source and source.get("title") else None,
        source_locator=str(source.get("locator")) if source and source.get("locator") else None,
    )


def _source_change(source: dict[str, Any]) -> KnowledgeSourceChangeRead:
    return KnowledgeSourceChangeRead(
        source_document_id=str(source.get("document_id") or _source_identity(source)),
        title=str(source.get("title") or "Untitled source"),
        source_uri=str(source.get("source_uri")) if source.get("source_uri") else None,
        locator=str(source.get("locator")) if source.get("locator") else None,
    )
