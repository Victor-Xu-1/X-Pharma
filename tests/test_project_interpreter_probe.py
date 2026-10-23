from __future__ import annotations

import importlib
import json
import subprocess
from pathlib import Path

import pytest

from pharma_intel.platform.environment_interpreter import project_python_probe


def venv_fixture(tmp_path: Path, *, managed: bool = False) -> tuple[Path, Path]:
    repository = tmp_path / "repository"
    repository.mkdir()
    environment = tmp_path / "environments" / "python" if managed else repository / ".venv"
    (environment / "bin").mkdir(parents=True)
    (environment / "bin/python").write_text("controlled non-executable fixture", encoding="utf-8")
    (environment / "pyvenv.cfg").write_text("include-system-site-packages = false\n", encoding="utf-8")
    if managed:
        (repository / ".venv").symlink_to(environment, target_is_directory=True)
    return repository, environment


def mock_probe(monkeypatch: pytest.MonkeyPatch, prefix: Path, captured: dict[str, object]) -> None:
    def invoke(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        captured.update(kwargs)
        captured["command"] = command
        return subprocess.CompletedProcess(
            command,
            0,
            json.dumps({"python": "3.13.16", "prefix": str(prefix), "packages": {"SQLAlchemy": "2.0.50"}}).encode(),
            b"",
        )

    monkeypatch.setattr(subprocess, "run", invoke)


def approve_store(monkeypatch: pytest.MonkeyPatch, store: Path) -> None:
    # Bind the policy to the function's sole owner across an implementation-module extraction.
    owner = importlib.import_module(project_python_probe.__module__)
    monkeypatch.setattr(owner, "_MANAGED_ENVIRONMENT_ROOT", store, raising=False)


def test_reads_the_project_owned_managed_native_venv_without_using_system_python(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository, environment = venv_fixture(tmp_path, managed=True)
    approve_store(monkeypatch, environment.parent)
    captured: dict[str, object] = {}
    mock_probe(monkeypatch, environment, captured)
    payload = project_python_probe(repository)
    assert payload is not None and payload["python"] == "3.13.16"
    assert payload["packages"] == {"SQLAlchemy": "2.0.50"}
    command = captured["command"]
    assert isinstance(command, list) and command[0] == str(environment / "bin/python")


def test_diagnostic_does_not_inherit_provider_secrets_or_write_import_bytecode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository, environment = venv_fixture(tmp_path)
    captured: dict[str, object] = {}
    mock_probe(monkeypatch, environment, captured)
    monkeypatch.setenv("UNRELATED_PROVIDER_TOKEN", "controlled-not-a-secret")
    assert project_python_probe(repository) is not None
    inherited = captured["env"]
    assert isinstance(inherited, dict) and "UNRELATED_PROVIDER_TOKEN" not in inherited
    command = captured["command"]
    assert isinstance(command, list) and "-I" in command and "-B" in command
    assert captured["stdin"] == subprocess.DEVNULL
    assert captured["timeout"] == 5


def test_refuses_an_interpreter_reporting_a_system_prefix_even_if_its_version_matches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository, _environment = venv_fixture(tmp_path)
    mock_probe(monkeypatch, Path("/usr"), {})
    assert project_python_probe(repository) is None


def test_refuses_a_python_file_without_the_project_virtual_environment_configuration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository, environment = venv_fixture(tmp_path)
    (environment / "pyvenv.cfg").unlink()
    mock_probe(monkeypatch, environment, {})
    assert project_python_probe(repository) is None


def test_unapproved_symlink_targets_do_not_start_a_process(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repository, environment = venv_fixture(tmp_path, managed=True)
    approve_store(monkeypatch, tmp_path / "different-approved-store")

    def forbidden(*_args: object, **_kwargs: object) -> None:
        pytest.fail("Unapproved environments must not be executed")

    monkeypatch.setattr(subprocess, "run", forbidden)
    assert project_python_probe(repository) is None
    assert environment.exists()


@pytest.mark.parametrize("relative", ["bin", "pyvenv.cfg"])
def test_managed_environment_writable_boundaries_do_not_start_a_process(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, relative: str
) -> None:
    repository, environment = venv_fixture(tmp_path, managed=True)
    approve_store(monkeypatch, environment.parent)
    (environment / relative).chmod(0o777)

    def forbidden(*_args: object, **_kwargs: object) -> None:
        pytest.fail("Writable managed interpreter boundaries must not be executed")

    monkeypatch.setattr(subprocess, "run", forbidden)
    assert project_python_probe(repository) is None


@pytest.mark.parametrize(
    ("stdout", "returncode"),
    [
        (b"not JSON", 0),
        (b"[]", 0),
        (b'{"python":"3.13.16","packages":{}}', 0),
        (b'{"python":"3.13.16","prefix":"relative-path","packages":{}}', 0),
        (b" " * (64 * 1024 + 1), 0),
        (b"{}", 1),
    ],
)
def test_invalid_incomplete_and_oversize_diagnostics_remain_unverified(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stdout: bytes, returncode: int
) -> None:
    repository, _environment = venv_fixture(tmp_path)

    def invalid(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[bytes]:
        return subprocess.CompletedProcess(command, returncode, stdout, b"")

    monkeypatch.setattr(subprocess, "run", invalid)
    assert project_python_probe(repository) is None


def test_timeout_remains_unverified_without_a_system_interpreter_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository, _environment = venv_fixture(tmp_path)
    calls = 0

    def timeout(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[bytes]:
        nonlocal calls
        calls += 1
        raise subprocess.TimeoutExpired(command, 5)

    monkeypatch.setattr(subprocess, "run", timeout)
    assert project_python_probe(repository) is None
    assert calls == 1
