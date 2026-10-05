from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from urllib.parse import urlencode

import httpx

from pharma_intel import __version__
from pharma_intel.product import PRODUCT_NAME
from pharma_intel.public_research.chembl import search_chembl
from pharma_intel.public_research.disclosures import search_disclosures
from pharma_intel.public_research.literature import search_literature
from pharma_intel.public_research.patents import search_compound_patents
from pharma_intel.public_research.transport import PublicResearchUnavailable, PublicTransport
from pharma_intel.public_research.trials import search_trials
from pharma_intel.schemas.public_research import (
    PublicResearchQuery,
    PublicResearchResponse,
    PublicResearchSourceResult,
    PublicResearchTopic,
)

_REQUEST_SLOTS = threading.BoundedSemaphore(2)
_OVERVIEW: tuple[PublicResearchTopic, ...] = ("targets", "drugs", "trials", "patents", "literature")


class PublicResearchBusy(RuntimeError):
    pass


class PublicResearchService:
    def __init__(self, transport: httpx.BaseTransport | None = None) -> None:
        self.transport = transport

    def search(self, query: PublicResearchQuery) -> PublicResearchResponse:
        if not _REQUEST_SLOTS.acquire(blocking=False):
            raise PublicResearchBusy("Public research concurrency budget is occupied")
        try:
            with httpx.Client(
                transport=self.transport,
                timeout=httpx.Timeout(8),
                trust_env=False,
                follow_redirects=False,
                headers={
                    "User-Agent": f"{PRODUCT_NAME}/{__version__} (+https://github.com/Victor-Xu-1/X-Pharma)",
                    "Accept": "application/json",
                },
            ) as client:
                transport = PublicTransport(client, throttle=self.transport is None)
                topics = _OVERVIEW if query.topic == "overview" else (query.topic,)

                def execute(topic: PublicResearchTopic) -> PublicResearchSourceResult:
                    return self._one(transport, query.model_copy(update={"topic": topic}))

                with ThreadPoolExecutor(max_workers=3) as executor:
                    results = list(executor.map(execute, topics))
            return PublicResearchResponse(query=query.q, observed_at=datetime.now(UTC), results=results)
        finally:
            _REQUEST_SLOTS.release()

    @staticmethod
    def _one(transport: PublicTransport, query: PublicResearchQuery) -> PublicResearchSourceResult:
        try:
            if query.topic in {"targets", "drugs"}:
                return search_chembl(transport, query)
            if query.topic in {"trials", "conditions", "organizations"}:
                return search_trials(transport, query)
            if query.topic in {"patents", "literature"}:
                return search_literature(transport, query)
            if query.topic == "compound_patents":
                return search_compound_patents(transport, query)
            if query.topic == "disclosures":
                return search_disclosures(transport, query)
            raise ValueError("Unknown public research topic")
        except (httpx.HTTPError, PublicResearchUnavailable, ValueError, TypeError, KeyError, AttributeError) as error:
            if query.topic in {"targets", "drugs"}:
                provider, link = "ChEMBL", "https://www.ebi.ac.uk/chembl/explore/"
            elif query.topic in {"trials", "conditions", "organizations"}:
                provider, link = (
                    "ClinicalTrials.gov",
                    "https://clinicaltrials.gov/search?" + urlencode({"term": query.q}),
                )
            elif query.topic == "compound_patents":
                provider, link = "PubChem", "https://pubchem.ncbi.nlm.nih.gov/#" + urlencode({"query": query.q})
            elif query.topic == "disclosures":
                provider, link = "公司官方公告 RSS", "https://www.sec.gov/edgar/search/#" + urlencode({"q": query.q})
            else:
                provider, link = "Europe PMC", "https://europepmc.org/search?" + urlencode({"query": query.q})
            return PublicResearchSourceResult(
                topic=query.topic,
                provider=provider,
                status="unavailable",
                source_query_url=link,
                scope_note="来源暂时不可读取或响应不符合合同；这不代表没有相关信息。本地已治理检索仍可用。",
                license_notice="原来源条款适用；未获取到内容，不提供虚构结果。",
                error_code="upstream_unavailable"
                if isinstance(error, httpx.HTTPError | PublicResearchUnavailable)
                else "invalid_response",
            )
