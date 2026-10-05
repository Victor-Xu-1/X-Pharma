from __future__ import annotations

from pharma_intel.public_research.metadata import identifier, rows, text, total
from pharma_intel.public_research.transport import PublicTransport
from pharma_intel.schemas.public_research import PublicResearchQuery, PublicResearchRecord, PublicResearchSourceResult


def search_chembl(transport: PublicTransport, query: PublicResearchQuery) -> PublicResearchSourceResult:
    target = query.topic == "targets"
    resource = "target" if target else "molecule"
    key = "targets" if target else "molecules"
    data = transport.json(
        f"https://www.ebi.ac.uk/chembl/api/data/{resource}/search.json",
        {
            "q": query.q,
            "limit": str(query.limit),
            "offset": "0",
            "only": "target_chembl_id,pref_name,organism,target_type"
            if target
            else "molecule_chembl_id,pref_name,molecule_type,max_phase,molecule_synonyms",
        },
    )
    records: list[PublicResearchRecord] = []
    for row in rows(data, key)[: query.limit]:
        record_id = identifier(row.get(f"{resource}_chembl_id"), r"CHEMBL[0-9]+")
        fields = {"ChEMBL": record_id}
        if target:
            fields.update({"物种": text(row.get("organism")), "靶点类型": text(row.get("target_type"))})
        else:
            fields.update({"分子类型": text(row.get("molecule_type")), "最高研究阶段": text(row.get("max_phase"))})
            synonyms = rows(row, "molecule_synonyms") if "molecule_synonyms" in row else []
            names = [text(item.get("molecule_synonym"), limit=120) for item in synonyms[:5]]
            fields["来源别名"] = " · ".join(name for name in names if name)
        records.append(
            PublicResearchRecord(
                record_id=record_id,
                category="target" if target else "drug",
                title=text(row.get("pref_name") or record_id, required=True, limit=1200),
                url=f"https://www.ebi.ac.uk/chembl/explore/{'target' if target else 'compound'}/{record_id}",
                fields=fields,
            )
        )
    return PublicResearchSourceResult(
        topic=query.topic,
        provider="ChEMBL",
        status="available" if records else "empty",
        records=records,
        total=total((data.get("page_meta") or {}).get("total_count")),
        source_query_url=f"https://www.ebi.ac.uk/chembl/explore/{'targets' if target else 'compounds'}",
        scope_note="ChEMBL公开名称检索；不同物种与复合靶点分别列出。最高阶段不代表当前在研状态或获批适应症。",
        license_notice="ChEMBL CC BY-SA 3.0；来源数据许可独立于X-Pharma Apache-2.0源码许可。",
    )
