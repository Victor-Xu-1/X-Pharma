from __future__ import annotations

import hashlib
import re
from datetime import UTC
from email.utils import parsedate_to_datetime
from urllib.parse import quote, urlsplit

import httpx

from pharma_intel.ingest.connectors import ConnectorTransportError
from pharma_intel.ingest.xml import parse_xml
from pharma_intel.public_research.metadata import text
from pharma_intel.public_research.transport import PublicResearchUnavailable, PublicTransport
from pharma_intel.schemas.public_research import PublicResearchQuery, PublicResearchRecord, PublicResearchSourceResult

_FEEDS = (
    ("Revolution Medicines", "https://ir.revmed.com/rss/news-releases.xml"),
    ("Kura Oncology", "https://ir.kuraoncology.com/rss/news-releases.xml"),
)


def search_disclosures(transport: PublicTransport, query: PublicResearchQuery) -> PublicResearchSourceResult:
    records: dict[str, PublicResearchRecord] = {}
    warnings: list[str] = []
    pattern = re.compile(r"(?<!\w)" + re.escape(query.q) + r"(?!\w)", re.IGNORECASE)
    for provider, feed in _FEEDS:
        try:
            xml = transport.read(feed, {}, xml=True).decode("utf-8")
            if "<!DOCTYPE" in xml.upper() or "<!ENTITY" in xml.upper():
                raise ValueError("Official RSS must not declare DTDs or entities")
            root = parse_xml(xml.encode("utf-8"), "Official company RSS")
            if root.tag != "rss":
                raise ValueError("Official company feed must use RSS")
            for item in root.findall("./channel/item")[:50]:
                title = text(item.findtext("title"), required=True, limit=1200)
                if not pattern.search(title) and not pattern.search(provider):
                    continue
                uri = text(item.findtext("link"), required=True, limit=2000)
                parsed = urlsplit(uri)
                if (
                    parsed.scheme != "https"
                    or parsed.hostname != urlsplit(feed).hostname
                    or parsed.username
                    or parsed.port
                ):
                    raise ValueError("Official feed item URL is outside the company origin")
                published = item.findtext("pubDate")
                date = parsedate_to_datetime(published).astimezone(UTC).date().isoformat() if published else None
                key = hashlib.sha256(uri.encode()).hexdigest()
                records[key] = PublicResearchRecord(
                    record_id=f"announcement:{key}",
                    category="company_disclosure",
                    title=title,
                    url=uri,
                    published_on=date,
                    fields={"发布机构": provider, "记录性质": "公司公告；未核验为规范交易合同"},
                )
        except (PublicResearchUnavailable, httpx.HTTPError, ValueError, ConnectorTransportError):
            warnings.append(f"{provider}公告来源暂不可读取，结果可能不完整。")
    ordered = sorted(records.values(), key=lambda row: (row.published_on or "", row.record_id), reverse=True)
    return PublicResearchSourceResult(
        topic=query.topic,
        provider="公司官方公告 RSS",
        status="available" if records else "unavailable" if warnings else "empty",
        records=ordered[: query.limit],
        total=None,
        source_query_url="https://www.sec.gov/edgar/search/#q=" + quote(query.q, safe=""),
        scope_note="仅检索Revolution Medicines、Kura Oncology官方RSS当前发布页中的标题与日期，非全市场交易库。"
        "可用英文药物/公司/合作关键词；公告不代表已确认交易、完整金额或地域权利。SEC自动接口受限，仅提供官方全文检索入口。",
        license_notice="公司原网页条款适用；仅展示标题、日期、原文链接，不重新分发公告正文。",
        warnings=warnings,
        error_code="upstream_unavailable" if warnings and not records else None,
    )
