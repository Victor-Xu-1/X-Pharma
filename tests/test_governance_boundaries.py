from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "src/pharma_intel/governance"


def test_governance_dependencies_do_not_cycle_back_to_the_orchestrator() -> None:
    modules = {path.stem: ast.parse(path.read_text(encoding="utf-8")) for path in ROOT.glob("*.py")}
    edges: dict[str, set[str]] = {name: set() for name in modules}
    helpers = {
        "adapter_context",
        "adapter_clinicaltrials",
        "adapter_nextpharma",
        "adapter_chembl",
        "contracts",
        "temporal_merge",
        "fact_identity",
        "citations",
        "source_profiles",
        "policy",
        "model_audit",
        "materialization_context",
        "materialization",
        "materialize_targets",
        "materialize_chemistry",
        "materialize_programs",
        "materialize_trials",
        "materialize_assets",
        "materialize_events",
    }
    for name, tree in modules.items():
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or not node.module:
                continue
            dependency = (
                node.module.split(".")[2]
                if node.module.startswith("pharma_intel.governance.")
                else node.module.split(".")[0]
                if node.level == 1
                else None
            )
            if dependency is None:
                continue
            assert dependency in modules, (name, dependency)
            assert name not in helpers or dependency != "service", (name, dependency)
            edges[name].add(dependency)
    visited: set[str] = set()
    active: set[str] = set()

    def visit(name: str) -> None:
        assert name not in active, f"Governance dependency cycle at {name}"
        if name in visited:
            return
        active.add(name)
        for dependency in edges[name]:
            visit(dependency)
        active.remove(name)
        visited.add(name)

    for name in modules:
        visit(name)


def test_governance_helper_definitions_have_exactly_one_owner() -> None:
    expected = {
        "GovernanceError": "contracts",
        "GovernanceBudgetError": "contracts",
        "DocumentSegment": "contracts",
        "SourceQuoteMatch": "contracts",
        "PreparedSegmentFact": "contracts",
        "_validated_datetime": "temporal_merge",
        "_normalize_phase": "temporal_merge",
        "_fact_identity": "fact_identity",
        "_quote_source_match": "citations",
        "_profiled_model_text": "source_profiles",
        "governance_policy_manifest": "policy",
        "governance_policy_sha256": "policy",
        "_extraction_audit": "model_audit",
        "materialize_structured_fact": "materialization",
        "materialize_program": "materialize_programs",
        "materialize_trial": "materialize_trials",
        "govern_clinicaltrials_gov": "adapter_clinicaltrials",
        "govern_nextpharma": "adapter_nextpharma",
        "govern_chembl": "adapter_chembl",
    }
    owners: dict[str, list[str]] = {name: [] for name in expected}
    for path in ROOT.glob("*.py"):
        for node in ast.parse(path.read_text(encoding="utf-8")).body:
            if isinstance(node, ast.FunctionDef | ast.ClassDef) and node.name in owners:
                owners[node.name].append(path.stem)
    assert owners == {name: [owner] for name, owner in expected.items()}


def test_orchestrator_does_not_reintroduce_domain_projection_methods() -> None:
    service = ast.parse((ROOT / "service.py").read_text(encoding="utf-8"))
    assert not any(
        isinstance(node, ast.FunctionDef)
        and node.name.startswith(
            (
                "_materialize_",
                "_sync_program_",
                "_append_program_",
                "_target_combination_key",
                "_govern_clinicaltrials_gov",
                "_govern_nextpharma",
                "_govern_chembl",
            )
        )
        for node in ast.walk(service)
    )
