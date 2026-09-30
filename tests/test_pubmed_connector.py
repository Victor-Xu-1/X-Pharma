from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest

from pharma_intel.config import Settings
from pharma_intel.ingest.connectors import ConnectorTransportError
from pharma_intel.ingest.pubmed import PUBMED_EUTILITIES_ROOT, PubMedSourceConnector
from pharma_intel.models import DataSource, DataSourceType


def _source() -> DataSource:
    return DataSource(
        id="pubmed-source",
        tenant_id="tenant-1",
        name="PubMed EGFR",
        source_type=DataSourceType.PUBMED,
        root_uri=PUBMED_EUTILITIES_ROOT,
        owner="Literature Data Operations",
        data_classification="public",
        authorization_scopes=["public:ncbi-pubmed-metadata"],
        dataset_key="literature",
        include_globs=["articles/*.md"],
        exclude_globs=[],
        routing_rules=[{"query_term": "EGFR", "max_records": 2, "page_size": 2, "include_abstract": False}],
        stable_seconds=0,
        max_file_bytes=1_000_000,
        scan_interval_seconds=86_400,
        expected_freshness_seconds=172_800,
        rate_limit_per_minute=180,
    )


def _search_xml(count: int = 2) -> bytes:
    return (
        f"<eSearchResult><Count>{count}</Count><QueryKey>1</QueryKey>"
        "<WebEnv>test-history</WebEnv><IdList /></eSearchResult>"
    ).encode()


def _fetch_xml() -> bytes:
    return b"""<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation><PMID>12345678</PMID><DateRevised><Year>2026</Year><Month>07</Month><Day>28</Day></DateRevised>
      <Article><ArticleTitle>EGFR inhibitor resistance</ArticleTitle>
        <Abstract><AbstractText>Copyrighted abstract is not included by policy.</AbstractText></Abstract>
        <AuthorList><Author><LastName>Zhang</LastName><Initials>W</Initials></Author></AuthorList>
        <Journal><JournalIssue><PubDate><Year>2026</Year><Month>Jul</Month></PubDate></JournalIssue>
          <Title>Precision Oncology</Title></Journal>
        <PublicationTypeList><PublicationType>Journal Article</PublicationType></PublicationTypeList>
      </Article>
      <MeshHeadingList><MeshHeading><DescriptorName>ErbB Receptors</DescriptorName></MeshHeading></MeshHeadingList>
    </MedlineCitation>
    <PubmedData><ArticleIdList><ArticleId IdType="doi">10.1000/egfr.1</ArticleId></ArticleIdList></PubmedData>
  </PubmedArticle>
  <PubmedArticle>
    <MedlineCitation><PMID>87654321</PMID><DateCompleted><Year>2026</Year><Month>07</Month><Day>27</Day></DateCompleted>
      <Article><ArticleTitle>Second EGFR record</ArticleTitle><Journal><JournalIssue>
        <PubDate><MedlineDate>2026 Jul</MedlineDate></PubDate></JournalIssue><Title>Drug Discovery</Title></Journal>
      </Article>
    </MedlineCitation>
  </PubmedArticle>
</PubmedArticleSet>"""


def test_pubmed_connector_uses_history_hashes_and_omits_abstract_by_default() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        payload = _search_xml() if request.url.path.endswith("esearch.fcgi") else _fetch_xml()
        return httpx.Response(200, headers={"content-type": "text/xml; charset=UTF-8"}, content=payload)

    connector = PubMedSourceConnector(
        Settings(source_ncbi_tool="pharma_tests", source_ncbi_email="data-ops@example.test"),
        transport=httpx.MockTransport(handler),
    )
    batch = connector.discover(_source())

    assert [item.logical_path for item in batch.objects] == ["articles/12345678.md", "articles/87654321.md"]
    assert batch.cursor["object_count"] == 2
    assert batch.cursor["reported_total_count"] == 2
    assert len(str(batch.cursor["inventory_sha256"])) == 64
    assert requests[0].url.params["usehistory"] == "y"
    assert requests[0].url.params["term"] == "EGFR"
    assert requests[1].url.params["WebEnv"] == "test-history"
    first = batch.objects[0]
    assert first.modified_at == datetime(2026, 7, 28, tzinfo=UTC)
    with connector.materialize(first) as snapshot:
        rendered = snapshot.read_text(encoding="utf-8")
        assert "EGFR inhibitor resistance" in rendered
        assert "10.1000/egfr.1" in rendered
        assert "ErbB Receptors" in rendered
        assert "Copyrighted abstract" not in rendered
        assert "Omitted by source policy" in rendered
        snapshot_path = snapshot
    assert not snapshot_path.exists()


def test_pubmed_connector_fails_closed_on_history_count_mismatch() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = (
            _search_xml()
            if request.url.path.endswith("esearch.fcgi")
            else _fetch_xml()
            .replace(
                b"<PubmedArticle>\n    <MedlineCitation><PMID>87654321</PMID>",
                b"<IgnoredArticle>\n    <MedlineCitation><PMID>87654321</PMID>",
            )
            .replace(b"</PubmedArticle>\n</PubmedArticleSet>", b"</IgnoredArticle>\n</PubmedArticleSet>")
        )
        return httpx.Response(200, headers={"content-type": "application/xml"}, content=payload)

    connector = PubMedSourceConnector(Settings(), transport=httpx.MockTransport(handler))
    with pytest.raises(ConnectorTransportError, match="record count"):
        connector.discover(_source())


def test_pubmed_connector_preserves_safe_http_failure_diagnostics() -> None:
    connector = PubMedSourceConnector(
        Settings(),
        transport=httpx.MockTransport(lambda _request: httpx.Response(429, headers={"content-type": "text/xml"})),
    )
    with pytest.raises(ConnectorTransportError, match="NCBI ESearch request returned HTTP 429"):
        connector.discover(_source())

    failing = PubMedSourceConnector(
        Settings(),
        transport=httpx.MockTransport(lambda _request: (_ for _ in ()).throw(httpx.ConnectTimeout("upstream timeout"))),
    )
    with pytest.raises(ConnectorTransportError, match=r"NCBI ESearch request failed \(ConnectTimeout\)"):
        failing.discover(_source())


def test_pubmed_connector_rejects_untrusted_configuration() -> None:
    connector = PubMedSourceConnector(Settings(source_ncbi_email="invalid"))
    source = _source()
    source.root_uri = "https://example.test/eutils/"
    source.credential_ref = "env://UNEXPECTED"
    source.data_classification = "confidential"
    source.authorization_scopes = []
    source.stable_seconds = 30
    source.rate_limit_per_minute = 181
    source.routing_rules = []

    assert connector.validate_configuration(source) == [
        f"PubMed sources must use {PUBMED_EUTILITIES_ROOT}",
        "PubMed sources do not accept connector credentials in v1",
        "PubMed sources must use the public data classification",
        "PubMed sources require authorization scope public:ncbi-pubmed-metadata",
        "PubMed sources require stable_seconds=0",
        "PubMed sources without an API key cannot exceed 180 requests per minute",
        "SOURCE_NCBI_EMAIL must be a valid email address when configured",
        "PubMed sources require exactly one routing rule",
    ]

    cursor_connector = PubMedSourceConnector(Settings())
    invalid_cursor = _source()
    invalid_cursor.connector_cursor = {
        "schema_version": "1.0",
        "kind": "pubmed",
        "inventory_sha256": "not-a-sha256",
        "object_count": True,
        "reported_total_count": 1,
    }
    assert cursor_connector.validate_configuration(invalid_cursor) == ["PubMed connector cursor is invalid"]


def test_pubmed_connector_requires_explicit_authorization_for_abstract_ingestion() -> None:
    connector = PubMedSourceConnector(Settings())
    source = _source()
    source.routing_rules = [{"query_term": "EGFR", "max_records": 2, "page_size": 2, "include_abstract": True}]

    assert connector.validate_configuration(source) == [
        "PubMed abstract ingestion requires authorization scope public:ncbi-pubmed-abstracts"
    ]

    source.authorization_scopes.append("public:ncbi-pubmed-abstracts")
    assert connector.validate_configuration(source) == []


def test_pubmed_connector_rejects_external_entities() -> None:
    connector = PubMedSourceConnector(
        Settings(),
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                200,
                headers={"content-type": "text/xml"},
                content=b'<!DOCTYPE x [<!ENTITY ext SYSTEM "file:///etc/passwd">]><eSearchResult>&ext;</eSearchResult>',
            )
        ),
    )
    with pytest.raises(ConnectorTransportError):
        connector.discover(_source())
