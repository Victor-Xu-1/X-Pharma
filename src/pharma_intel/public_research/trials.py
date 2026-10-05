from __future__ import annotations

import hashlib
from urllib.parse import urlencode

from pharma_intel.public_research.metadata import identifier, literal_query, rows, text, total
from pharma_intel.public_research.transport import PublicTransport
from pharma_intel.schemas.public_research import PublicResearchQuery, PublicResearchRecord, PublicResearchSourceResult


def search_trials(transport: PublicTransport, query: PublicResearchQuery) -> PublicResearchSourceResult:
    data = transport.json(
        "https://clinicaltrials.gov/api/v2/studies",
        {
            "query.term": literal_query(query.q),
            "pageSize": str(query.limit),
            "format": "json",
            "countTotal": "true",
            "fields": (
                "NCTId,BriefTitle,OfficialTitle,OverallStatus,Condition,LeadSponsorName,"
                "CollaboratorName,LastUpdatePostDate"
            ),
        },
    )
    records: dict[str, PublicResearchRecord] = {}
    derived = query.topic != "trials"
    for study in rows(data, "studies")[: query.limit]:
        protocol = study.get("protocolSection") or {}
        identity = protocol.get("identificationModule") or {}
        nct = identifier(identity.get("nctId"), r"NCT[0-9]{8}")
        uri = f"https://clinicaltrials.gov/study/{nct}"
        status = protocol.get("statusModule") or {}
        updated = text((status.get("lastUpdatePostDateStruct") or {}).get("date")) or None
        conditions = protocol.get("conditionsModule") or {}
        sponsors = protocol.get("sponsorCollaboratorsModule") or {}
        if query.topic == "trials":
            records[nct] = PublicResearchRecord(
                record_id=nct,
                category="clinical_trial",
                title=text(
                    identity.get("briefTitle") or identity.get("officialTitle"),
                    required=True,
                    limit=1200,
                ),
                url=uri,
                published_on=updated,
                fields={
                    "注册号": nct,
                    "研究状态": text(status.get("overallStatus")),
                    "主要申办方": text((sponsors.get("leadSponsor") or {}).get("name")),
                },
            )
        else:
            labels = (
                conditions.get("conditions") or []
                if query.topic == "conditions"
                else [
                    (sponsors.get("leadSponsor") or {}).get("name"),
                    *(item.get("name") for item in sponsors.get("collaborators") or []),
                ]
            )
            if not isinstance(labels, list):
                raise ValueError("Official trial labels must be a list")
            for raw_label in labels:
                name = text(raw_label, limit=500)
                if not name:
                    continue
                key = hashlib.sha256(name.casefold().encode()).hexdigest()[:24]
                if key not in records:
                    records[key] = PublicResearchRecord(
                        record_id=f"ctgov:{query.topic}:{key}",
                        title=name,
                        url=uri,
                        published_on=updated,
                        category="study_condition_label" if query.topic == "conditions" else "sponsor_label",
                        fields={"来源试验": nct, "记录性质": "ClinicalTrials.gov来源名称，不作跨来源实体归并"},
                    )
    return PublicResearchSourceResult(
        topic=query.topic,
        provider="ClinicalTrials.gov",
        status="available" if records else "empty",
        records=list(records.values())[: query.limit],
        total=None if derived else total(data.get("totalCount")),
        source_query_url="https://clinicaltrials.gov/search?" + urlencode({"term": query.q}),
        scope_note=(
            "当前试验页中的来源名称，非全量机构/疾病库；研究条件不代表获批适应症，申办方名称不代表核实法律主体。"
            if derived
            else "ClinicalTrials.gov公开注册记录；结果读取不等于独立核实试验结果或药物效果。"
        ),
        license_notice="仅展示公开注册元数据，原注册记录及ClinicalTrials.gov条款适用。",
    )
