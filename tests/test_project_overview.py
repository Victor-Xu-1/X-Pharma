from html.parser import HTMLParser

from pharma_intel.product import PRODUCT_RELEASE
from scripts.project_overview import ROOT, build_document, escape


def test_architecture_overview_is_self_contained_and_preserves_honest_readiness_boundaries() -> None:
    class SourceInspector(HTMLParser):
        def __init__(self) -> None:
            super().__init__()
            self.external_sources: list[str] = []
            self.domains = 0

        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            values = dict(attrs)
            if tag in {"img", "script", "link"}:
                value = values.get("src") or values.get("href")
                if value and not value.startswith("data:"):
                    self.external_sources.append(value)
            if tag == "details":
                self.domains += 1

    document = build_document()
    inspector = SourceInspector()
    inspector.feed(document)
    assert inspector.domains == 22 and not inspector.external_sources
    assert f"X-Pharma {PRODUCT_RELEASE}" in document
    assert "GOAL.md 契约版本" in document
    assert "OrganizationMembership" in document and "仅源码 ZIP" in document
    assert "不共享原数据" in document and "不提交 GitHub" in document
    assert "不等于" in document and "UAT" in document
    assert 'href="#interaction"' in document and 'id="interaction"' in document
    assert "ResearchReturnControl" in document and "useRouteEntity" in document
    assert "Portal" in document and "筛选、排序、分页和原预览" in document
    assert "TargetView" in document and "useTargetPipeline" in document
    assert escape("<script>alert('unsafe')</script>").startswith("&lt;script&gt;")


def test_committed_project_overview_matches_the_authoritative_capability_matrices() -> None:
    assert (ROOT / "docs/project-overview.html").read_text(encoding="utf-8") == build_document()
