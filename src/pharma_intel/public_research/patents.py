from __future__ import annotations

from urllib.parse import quote, urlencode

from pharma_intel.public_research.metadata import identifier, rows, text
from pharma_intel.public_research.transport import PublicRecordNotFound, PublicResearchUnavailable, PublicTransport
from pharma_intel.schemas.public_research import PublicResearchQuery, PublicResearchRecord, PublicResearchSourceResult


def search_compound_patents(transport: PublicTransport, query: PublicResearchQuery) -> PublicResearchSourceResult:
    uri = "https://pubchem.ncbi.nlm.nih.gov/#" + urlencode({"query": query.q})
    note = "PubChem化合物专利交叉引用：请用药物名称或CID；提及化合物不等于权利要求保护、家族或有效法律状态。"
    license_notice = "PubChem及其原数据提供者条款适用；仅展示专利标识、著录标题和来源链接，不再分发正文。"
    namespace = "cid" if query.q.isascii() and query.q.isdigit() else "name"
    try:
        data = transport.json(
            f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/{namespace}/"
            f"{quote(query.q, safe='')}/xrefs/PatentID/JSON",
            {},
        )
    except PublicRecordNotFound:
        return PublicResearchSourceResult(
            topic=query.topic,
            provider="PubChem",
            status="empty",
            source_query_url=uri,
            scope_note=note + " 当前名称未解析为唯一化合物，不能据此判断没有相关专利。",
            license_notice=license_notice,
        )
    information = data.get("InformationList")
    if not isinstance(information, dict):
        raise ValueError("PubChem response is missing InformationList")
    compounds = rows(information, "Information")
    if len(compounds) != 1:
        raise ValueError("PubChem compound identity is ambiguous")
    compound = compounds[0]
    cid = identifier(compound.get("CID"), r"[0-9]+")
    publications = compound.get("PatentID", [])
    if not isinstance(publications, list) or any(not isinstance(item, str) for item in publications):
        raise ValueError("PubChem patent cross-references must be a list")
    publications = list(dict.fromkeys(publications))
    records: list[PublicResearchRecord] = []
    warnings: list[str] = []
    for index, raw_id in enumerate(publications[: query.limit]):
        publication = identifier(raw_id, r"[A-Z]{2}[A-Z0-9-]{1,100}")
        title = f"专利公开文献 {publication}"
        if index < 2:
            try:
                metadata = transport.json(
                    f"https://pubchem.ncbi.nlm.nih.gov/rest/pug_view/data/patent/{publication}/JSON",
                    {"heading": "Record Description"},
                )
                record = metadata.get("Record")
                if not isinstance(record, dict):
                    raise ValueError("PubChem patent metadata is missing Record")
                title = text(record.get("RecordTitle"), required=True, limit=1200)
            except (PublicResearchUnavailable, ValueError):
                if not warnings:
                    warnings.append("部分专利标题未能读取；仍显示已返回的专利标识与官方链接，不补造著录字段。")
        records.append(
            PublicResearchRecord(
                record_id=publication,
                category="compound_patent_reference",
                title=title,
                url=f"https://pubchem.ncbi.nlm.nih.gov/patent/{publication}",
                fields={"专利标识": publication, "关联化合物": f"PubChem CID {cid}", "记录性质": "化合物提及/交叉引用"},
            )
        )
    return PublicResearchSourceResult(
        topic=query.topic,
        provider="PubChem",
        status="available" if records else "empty",
        records=records,
        total=len(publications),
        source_query_url=uri,
        scope_note=note,
        license_notice=license_notice,
        warnings=warnings,
    )
