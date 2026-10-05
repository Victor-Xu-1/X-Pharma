from __future__ import annotations

from urllib.parse import urlencode

from pharma_intel.public_research.metadata import identifier, literal_query, rows, text, total
from pharma_intel.public_research.transport import PublicTransport
from pharma_intel.schemas.public_research import PublicResearchQuery, PublicResearchRecord, PublicResearchSourceResult


def search_literature(transport: PublicTransport, query: PublicResearchQuery) -> PublicResearchSourceResult:
    patent = query.topic == "patents"
    term = literal_query(query.q) + (" AND SRC:PAT" if patent else " AND NOT SRC:PAT")
    data = transport.json(
        "https://www.ebi.ac.uk/europepmc/webservices/rest/search",
        {
            "query": term,
            "format": "json",
            "resultType": "lite",
            "pageSize": str(query.limit),
            "cursorMark": "*",
        },
    )
    result_list = data.get("resultList")
    if not isinstance(result_list, dict):
        raise ValueError("Europe PMC response is missing resultList")
    records: list[PublicResearchRecord] = []
    for row in rows(result_list, "result")[: query.limit]:
        source = identifier(row.get("source"), r"[A-Z][A-Z0-9_]{0,15}")
        record_id = identifier(row.get("id"), r"[A-Za-z0-9_.-]{1,120}")
        if patent and source != "PAT":
            raise ValueError("Europe PMC patent search returned a non-patent record")
        records.append(
            PublicResearchRecord(
                record_id=f"{source}:{record_id}",
                category="patent_bibliography" if patent else "publication",
                title=text(row.get("title"), required=True, limit=1200),
                url=f"https://europepmc.org/article/{source}/{record_id}",
                published_on=text(row.get("firstPublicationDate") or row.get("pubYear")) or None,
                fields={
                    "来源标识": record_id,
                    "作者/来源署名": text(row.get("authorString")),
                    "期刊/类型": text(row.get("journalTitle") or row.get("pubType")),
                    "DOI": text(row.get("doi")),
                },
            )
        )
    return PublicResearchSourceResult(
        topic=query.topic,
        provider="Europe PMC · 历史专利著录" if patent else "Europe PMC",
        status="available" if records else "empty",
        records=records,
        total=total(data.get("hitCount")),
        source_query_url="https://europepmc.org/search?" + urlencode({"query": term}),
        scope_note=(
            "Europe PMC历史专利摘要集合，日期以每条记录为准，不代表覆盖最新专利、家族、权利要求或法律状态。"
            if patent
            else "生命科学文献著录检索；不下载或重新分发非开放许可全文，不把文献结论当作已验证研发事实。"
        ),
        license_notice="Europe PMC及原著录来源条款适用；开放API不授予全部文章或专利正文再分发权。",
    )
