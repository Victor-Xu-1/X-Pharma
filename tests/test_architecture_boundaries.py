from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

CORE_RUNTIME_FILES = (
    "src/pharma_intel/api.py",
    "src/pharma_intel/bootstrap.py",
    "src/pharma_intel/config.py",
    "src/pharma_intel/dataset_repository.py",
    "src/pharma_intel/ingest/activities.py",
    "src/pharma_intel/ingest/cli.py",
    "src/pharma_intel/ingest/data_factory.py",
    "src/pharma_intel/ingest/temporal_worker.py",
    "src/pharma_intel/ingest/workflows.py",
)

DEPLOYMENT_FILES = (
    ".env.example",
    "compose.yaml",
    "compose.dev.yaml",
    "deploy/kubernetes/base/config-map.yaml",
)


def test_ragflow_is_absent_from_core_runtime_and_deployment_contracts() -> None:
    for relative_path in (*CORE_RUNTIME_FILES, *DEPLOYMENT_FILES):
        content = (ROOT / relative_path).read_text(encoding="utf-8").casefold()
        assert "ragflow" not in content, f"RAGFlow leaked into core runtime contract: {relative_path}"
        assert "evidence_search_backend" not in content, f"Legacy evidence backend switch remains: {relative_path}"


def test_ragflow_access_is_read_only_and_isolated_to_offline_migration_package() -> None:
    migration = (ROOT / "src/pharma_intel/migration/ragflow_export.py").read_text(encoding="utf-8")
    assert "class ReadOnlyRagflowMigrationClient" in migration
    assert "upload_document" not in migration
    assert "parse_document" not in migration
    assert 'pharma-ragflow-migration-export = "pharma_intel.migration.ragflow_export:run"' in (
        ROOT / "pyproject.toml"
    ).read_text(encoding="utf-8")


def test_human_workbenches_have_independent_entrypoints_and_feature_graphs() -> None:
    web = ROOT / "apps/web"
    research = (web / "src/ResearchApp.tsx").read_text(encoding="utf-8")
    internal = (web / "src/InternalApp.tsx").read_text(encoding="utf-8")
    research_views = (
        "ChemistryView",
        "CollectionsView",
        "EvidenceView",
        "ExplorerView",
        "KnowledgeView",
        "MonitoringView",
        "OverviewView",
        "TargetView",
    )
    internal_views = ("CommercialView", "DataFactoryView", "EnterpriseView", "GovernanceView")

    assert 'src="/src/research-main.tsx"' in (web / "research.html").read_text(encoding="utf-8")
    assert 'src="/src/internal-main.tsx"' in (web / "internal.html").read_text(encoding="utf-8")
    assert 'data-workbench="research"' in (web / "research.html").read_text(encoding="utf-8")
    assert 'data-workbench="internal"' in (web / "internal.html").read_text(encoding="utf-8")
    assert not (web / "src/App.tsx").exists()
    assert not (web / "src/main.tsx").exists()
    package = (web / "package.json").read_text(encoding="utf-8")
    verifier = (web / "scripts/verify-workbench-build.mjs").read_text(encoding="utf-8")
    assert "node scripts/verify-workbench-build.mjs" in package
    assert "pharma.workbench-build-boundary.v1" in verifier
    assert "web-vitals@6.0.1/node_modules/web-vitals/dist/web-vitals.js" in verifier
    assert "approvedDeferredEntryModules" in verifier
    assert "verifyDeferredAsset" in verifier
    assert "research and internal workbenches share an application entry chunk" in verifier

    for view_name in research_views:
        assert f'import("./views/{view_name}")' in research
        assert view_name not in internal
    for view_name in internal_views:
        assert f'import("./views/{view_name}")' in internal
        assert view_name not in research
