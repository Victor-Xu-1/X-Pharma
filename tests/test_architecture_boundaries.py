from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1] / "src/pharma_intel"


@pytest.mark.parametrize("package", ["models", "schemas", "http", "intelligence"])
def test_domain_packages_have_explicit_acyclic_dependencies_and_thin_public_namespaces(package: str) -> None:
    directory = ROOT / package
    modules = {path.stem: ast.parse(path.read_text(encoding="utf-8")) for path in directory.glob("*.py")}
    public = modules.pop("__init__")
    assert not any(isinstance(node, ast.ClassDef | ast.FunctionDef) for node in public.body)
    edges: dict[str, set[str]] = {name: set() for name in modules}
    for name, tree in modules.items():
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            if node.module == f"pharma_intel.{package}" and package == "http":
                # Importing a named submodule is explicit; __init__ exports no contracts.
                for alias in node.names:
                    assert alias.name in modules, f"Unknown HTTP dependency {name} -> {alias.name}"
                    edges[name].add(alias.name)
                continue
            assert node.module != f"pharma_intel.{package}", f"{package}/{name} imports its aggregate namespace"
            if package == "http":
                assert node.module != "pharma_intel.api", "HTTP features must not import the application bootstrap"
            if package == "schemas":
                assert node.module != "pharma_intel.models", "Transport contracts must not load the ORM aggregate"
            if node.level == 1 and node.module:
                dependency = node.module.split(".")[0]
                assert dependency != "__init__"
                assert dependency in modules, f"Unknown domain dependency {name} -> {dependency}"
                edges[name].add(dependency)
            if node.module and node.module.startswith(f"pharma_intel.{package}."):
                dependency = node.module.split(".")[2]
                assert dependency in modules, f"Unknown domain dependency {name} -> {dependency}"
                edges[name].add(dependency)
    visited: set[str] = set()
    active: set[str] = set()

    def visit(name: str, path: tuple[str, ...]) -> None:
        assert name not in active, f"Domain cycle: {' -> '.join((*path, name))}"
        if name in visited:
            return
        active.add(name)
        for dependency in edges[name]:
            visit(dependency, (*path, name))
        active.remove(name)
        visited.add(name)

    for name in modules:
        visit(name, ())


def test_persistence_has_exactly_one_registry_owner() -> None:
    registries: list[str] = []
    for path in (ROOT / "models").glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ClassDef) and any(
                isinstance(base, ast.Name) and base.id == "DeclarativeBase" for base in node.bases
            ):
                registries.append(f"{path.name}:{node.name}")
    assert registries == ["base.py:Base"]


def test_organization_permissions_have_one_persistence_authority() -> None:
    from pharma_intel.models import OrganizationMembership, User

    assert "role" not in User.__table__.c and "tenant_id" not in User.__table__.c
    assert {"role", "active", "token_version", "tenant_id", "user_id"} <= set(OrganizationMembership.__table__.c.keys())
    assert {column.name for column in OrganizationMembership.__table__.primary_key} == {"tenant_id", "user_id"}


def test_application_bootstrap_does_not_own_queries_or_business_routes() -> None:
    tree = ast.parse((ROOT / "api.py").read_text(encoding="utf-8"))
    assert {node.name for node in tree.body if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)} == {
        "create_app",
        "lifespan",
        "run",
    }
    assert not any(
        isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("sqlalchemy")
        for node in ast.walk(tree)
    )


def test_ingestion_commands_do_not_depend_on_transport_or_application_bootstrap() -> None:
    for path in (ROOT / "ingest/commands").glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert not node.module.startswith(("fastapi", "pharma_intel.http", "pharma_intel.api")), path


def test_release_evidence_modules_have_an_explicit_acyclic_authority_graph() -> None:
    directory = ROOT.parents[1] / "scripts/release"
    modules = {
        ".".join(path.relative_to(directory).with_suffix("").parts): ast.parse(path.read_text(encoding="utf-8"))
        for path in directory.rglob("*.py")
    }
    for name in ("__init__", "contracts.__init__"):
        assert not any(isinstance(node, ast.FunctionDef | ast.ClassDef) for node in modules.pop(name).body)
    edges: dict[str, set[str]] = {name: set() for name in modules}
    for name, tree in modules.items():
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert node.module not in {"scripts.release", "scripts.release_evidence"}, name
                if node.module.startswith("scripts.release."):
                    dependency = node.module.removeprefix("scripts.release.")
                    assert dependency in modules, (name, dependency)
                    edges[name].add(dependency)
    visited: set[str] = set()
    active: set[str] = set()

    def visit(name: str) -> None:
        assert name not in active, f"Release evidence dependency cycle at {name}"
        if name in visited:
            return
        active.add(name)
        for dependency in edges[name]:
            visit(dependency)
        active.remove(name)
        visited.add(name)

    for name in modules:
        visit(name)
