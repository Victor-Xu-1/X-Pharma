from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pharma_intel.db import set_tenant_context
from pharma_intel.models import (
    Entity,
    EvidenceClaim,
    KnowledgeCitation,
    KnowledgeLink,
    KnowledgePage,
    KnowledgePageStatus,
    KnowledgePageVersion,
    OutboxEvent,
    ReviewStatus,
    SourceDocument,
)

COMPILER_VERSION = "1.0.0"


@dataclass(frozen=True)
class CompilationResult:
    page_id: str
    version_id: str
    version_number: int
    changed: bool
    content_sha256: str


class KnowledgeCompiler:
    def __init__(self, session: Session, tenant_id: str) -> None:
        self.session = session
        self.tenant_id = tenant_id
        set_tenant_context(session, tenant_id)

    def compile_entity(self, entity_id: str, run_id: str | None = None) -> CompilationResult:
        entity = self.session.scalar(select(Entity).where(Entity.id == entity_id, Entity.tenant_id == self.tenant_id))
        if entity is None:
            raise LookupError("Entity not found")
        claims = list(
            self.session.scalars(
                select(EvidenceClaim)
                .where(
                    EvidenceClaim.tenant_id == self.tenant_id,
                    EvidenceClaim.subject_id == entity.id,
                    EvidenceClaim.review_status == ReviewStatus.VERIFIED,
                )
                .order_by(EvidenceClaim.predicate, EvidenceClaim.created_at, EvidenceClaim.id)
            )
        )
        source_ids = sorted({claim.source_document_id for claim in claims})
        sources = (
            {
                source.id: source
                for source in self.session.scalars(
                    select(SourceDocument).where(
                        SourceDocument.tenant_id == self.tenant_id,
                        SourceDocument.id.in_(source_ids),
                    )
                )
            }
            if source_ids
            else {}
        )
        object_ids = sorted({claim.object_id for claim in claims if claim.object_id})
        objects = (
            {
                item.id: item
                for item in self.session.scalars(
                    select(Entity).where(Entity.tenant_id == self.tenant_id, Entity.id.in_(object_ids))
                )
            }
            if object_ids
            else {}
        )

        citation_keys: list[tuple[str, str | None, str | None]] = []
        fact_rows: list[dict[str, Any]] = []
        for claim in claims:
            citation_key = (claim.source_document_id, claim.source_locator, claim.quote)
            if citation_key not in citation_keys:
                citation_keys.append(citation_key)
            citation_number = citation_keys.index(citation_key) + 1
            fact_rows.append(
                {
                    "id": claim.id,
                    "predicate": claim.predicate,
                    "object_entity": _entity_json(objects[claim.object_id]) if claim.object_id in objects else None,
                    "value": claim.value,
                    "confidence": claim.confidence,
                    "citation": citation_number,
                }
            )
        content = {
            "schema_version": "1.0",
            "entity": _entity_json(entity),
            "facts": fact_rows,
            "sources": [
                {
                    "number": index,
                    "document_id": document_id,
                    "title": sources[document_id].title if document_id in sources else "Unavailable source",
                    "source_uri": sources[document_id].source_uri if document_id in sources else None,
                    "locator": locator,
                    "quote": quote,
                }
                for index, (document_id, locator, quote) in enumerate(citation_keys, start=1)
            ],
        }
        markdown = _render_markdown(content)
        content_sha256 = hashlib.sha256(
            json.dumps(content, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
        ).hexdigest()
        page_key = f"entity/{entity.entity_type.value}/{entity.id}"
        page = self.session.scalar(
            select(KnowledgePage).where(
                KnowledgePage.tenant_id == self.tenant_id,
                KnowledgePage.page_key == page_key,
            )
        )
        if page is None:
            page = KnowledgePage(
                tenant_id=self.tenant_id,
                page_key=page_key,
                page_type=entity.entity_type.value,
                title=entity.name,
                subject_entity_id=entity.id,
            )
            self.session.add(page)
            self.session.flush()
        current = self.session.get(KnowledgePageVersion, page.current_version_id) if page.current_version_id else None
        if current is not None and current.content_sha256 == content_sha256:
            return CompilationResult(page.id, current.id, current.version_number, False, content_sha256)
        version_number = (
            int(
                self.session.scalar(
                    select(func.coalesce(func.max(KnowledgePageVersion.version_number), 0)).where(
                        KnowledgePageVersion.tenant_id == self.tenant_id,
                        KnowledgePageVersion.knowledge_page_id == page.id,
                    )
                )
                or 0
            )
            + 1
        )
        version = KnowledgePageVersion(
            tenant_id=self.tenant_id,
            knowledge_page_id=page.id,
            version_number=version_number,
            compiler_version=COMPILER_VERSION,
            content_json=content,
            rendered_markdown=markdown,
            content_sha256=content_sha256,
            source_snapshot_at=datetime.now(UTC),
            created_by_run_id=run_id,
        )
        self.session.add(version)
        self.session.flush()
        for ordinal, (document_id, locator, quote) in enumerate(citation_keys, start=1):
            matching_claim = next(
                claim
                for claim in claims
                if (claim.source_document_id, claim.source_locator, claim.quote) == (document_id, locator, quote)
            )
            self.session.add(
                KnowledgeCitation(
                    tenant_id=self.tenant_id,
                    page_version_id=version.id,
                    ordinal=ordinal,
                    source_document_id=document_id,
                    evidence_claim_id=matching_claim.id,
                    source_locator=locator,
                    quote=quote,
                )
            )
        linked: set[str] = set()
        for claim in claims:
            if not claim.object_id or claim.object_id in linked or claim.object_id not in objects:
                continue
            linked.add(claim.object_id)
            target = objects[claim.object_id]
            target_page = self.session.scalar(
                select(KnowledgePage).where(
                    KnowledgePage.tenant_id == self.tenant_id,
                    KnowledgePage.subject_entity_id == target.id,
                )
            )
            self.session.add(
                KnowledgeLink(
                    tenant_id=self.tenant_id,
                    page_version_id=version.id,
                    relationship=claim.predicate,
                    target_key=f"entity/{target.entity_type.value}/{target.id}",
                    target_page_id=target_page.id if target_page else None,
                    target_entity_id=target.id,
                    confidence=claim.confidence,
                )
            )
        page.current_version_id = version.id
        page.status = KnowledgePageStatus.PUBLISHED
        page.title = entity.name
        self.session.add(
            OutboxEvent(
                tenant_id=self.tenant_id,
                aggregate_type="knowledge_page",
                aggregate_id=page.id,
                event_type="knowledge.page.compiled",
                payload={"knowledge_page_id": page.id, "version_id": version.id},
            )
        )
        self.session.commit()
        return CompilationResult(page.id, version.id, version_number, True, content_sha256)

    def export_page(self, page_id: str, export_root: Path) -> Path:
        page = self.session.scalar(
            select(KnowledgePage).where(
                KnowledgePage.id == page_id,
                KnowledgePage.tenant_id == self.tenant_id,
            )
        )
        if page is None or not page.current_version_id:
            raise LookupError("Compiled knowledge page not found")
        version = self.session.get(KnowledgePageVersion, page.current_version_id)
        if version is None:
            raise LookupError("Current knowledge page version not found")
        root = export_root.resolve()
        destination = (root / page.page_type / f"{_safe_name(page.title)}--{page.id}.md").resolve()
        if not destination.is_relative_to(root):
            raise ValueError("Knowledge export path escaped its configured root")
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.tmp")
        try:
            with temporary.open("x", encoding="utf-8", newline="\n") as handle:
                handle.write(version.rendered_markdown)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, destination)
        finally:
            temporary.unlink(missing_ok=True)
        return destination


def _entity_json(entity: Entity) -> dict[str, Any]:
    return {
        "id": entity.id,
        "type": entity.entity_type.value,
        "name": entity.name,
        "description": entity.description,
        "external_ids": dict(sorted(entity.external_ids.items())),
    }


def _render_markdown(content: dict[str, Any]) -> str:
    entity = content["entity"]
    lines = [
        "---",
        f"id: {json.dumps(entity['id'], ensure_ascii=False)}",
        f"type: {json.dumps(entity['type'], ensure_ascii=False)}",
        f"name: {json.dumps(entity['name'], ensure_ascii=False)}",
        f"schema_version: {json.dumps(content['schema_version'])}",
        "---",
        "",
        f"# {entity['name']}",
        "",
    ]
    if entity.get("description"):
        lines.extend([str(entity["description"]), ""])
    if entity.get("external_ids"):
        lines.extend(["## Identifiers", ""])
        for namespace, value in entity["external_ids"].items():
            lines.append(f"- **{namespace}**: `{value}`")
        lines.append("")
    lines.extend(["## Evidence", ""])
    if not content["facts"]:
        lines.extend(["No verified facts have been published.", ""])
    for fact in content["facts"]:
        rendered_value = fact["object_entity"]["name"] if fact["object_entity"] else _compact_json(fact["value"])
        lines.append(f"- **{fact['predicate']}**: {rendered_value} [^{fact['citation']}]")
    if content["sources"]:
        lines.extend(["", "## Sources", ""])
    for source in content["sources"]:
        locator = f", {source['locator']}" if source.get("locator") else ""
        uri = f" ({source['source_uri']})" if source.get("source_uri") else ""
        lines.append(f"[^{source['number']}]: {source['title']}{locator}{uri}")
    return "\n".join(lines).rstrip() + "\n"


def _compact_json(value: Any) -> str:
    if isinstance(value, dict) and set(value) == {"value"}:
        return str(value["value"])
    return f"`{json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'))}`"


def _safe_name(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9._\-\u4e00-\u9fff]+", "-", value).strip(".-")
    return normalized[:120] or "knowledge-page"
