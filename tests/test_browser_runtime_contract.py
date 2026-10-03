from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pharma_intel.api import create_app
from pharma_intel.config import Settings
from pharma_intel.http import runtime


def _bash_executable() -> str | None:
    if os.name == "nt":
        candidates = (
            Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Git" / "bin" / "bash.exe",
            Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Git" / "usr" / "bin" / "bash.exe",
        )
        for candidate in candidates:
            if candidate.is_file():
                return str(candidate)
    return shutil.which("bash")


def _bash_script_path(path: Path) -> str:
    if os.name != "nt":
        return str(path)
    cygpath = shutil.which("cygpath")
    if cygpath is None:
        value = str(path)
        if value.startswith("\\\\"):
            return "//" + value.lstrip("\\").replace("\\", "/")
        return value
    converted = subprocess.run(  # noqa: S603 - fixed path conversion utility.
        [cygpath, "-u", str(path)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert converted.returncode == 0, converted.stderr
    return converted.stdout.strip()


def test_google_chrome_acceptance_uses_a_signed_user_level_distribution() -> None:
    root = Path(__file__).parents[1]
    bootstrap = root / "scripts" / "bootstrap-wsl-chrome.sh"
    acceptance = root / "scripts" / "run-browser-acceptance.sh"
    bootstrap_text = bootstrap.read_text(encoding="utf-8")
    acceptance_text = acceptance.read_text(encoding="utf-8")
    runtime_helper = root / "scripts/lib/browser_runtime.sh"
    runtime_text = runtime_helper.read_text(encoding="utf-8")
    bash = _bash_executable()
    assert bash is not None

    for script in (bootstrap, acceptance, runtime_helper):
        completed = subprocess.run(  # noqa: S603 - fixed repository scripts are syntax checked only.
            [bash, "-n", _bash_script_path(script)],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
        )
        assert completed.returncode == 0, completed.stderr

    assert "https://dl.google.com/linux/chrome/deb" in bootstrap_text
    assert "EB4C1BFD4F042F6DDDCCEC917721F63BD38B4796" in bootstrap_text
    assert '--export "$expected_primary_fingerprint"' in bootstrap_text
    assert "trusted_primary_fingerprints" in bootstrap_text
    assert "gpgv --keyring" in bootstrap_text
    assert "published_packages_sha256" in bootstrap_text
    assert "package_sha256" in bootstrap_text
    assert "sudo " not in bootstrap_text
    assert "pharma.browser-acceptance.v9" in acceptance_text
    assert "The local API container is not running in the selected Docker daemon" in acceptance_text
    assert 'api_runtime_state" != "true healthy"' in acceptance_text
    assert (
        'if [[ "$api_runtime_state" != "true healthy" && "$recover_interrupted_run" != true ]]; then' in acceptance_text
    )
    assert '"accessibility": "[accessibility]"' in acceptance_text
    assert '"accessibility_dossier": "[accessibility-dossier]"' in acceptance_text
    assert "browser_workers=${PHARMA_BROWSER_WORKERS:-4}" in acceptance_text
    assert '"--workers=$browser_workers"' in acceptance_text
    assert "E2E_CHROME_EXECUTABLE" in runtime_text
    assert "browser_projects=(desktop-1440 desktop-1920 tablet-1024 mobile-390)" in acceptance_text
    assert 'E2E_EMAIL_PREFIX="$email_prefix"' in acceptance_text
    assert 'E2E_REGULATORY_SUBJECT_ID="$regulatory_subject_id"' in acceptance_text
    assert "OR entity.id IN (" in acceptance_text
    for fixture_entity_id in (
        "$pipeline_drug_b_id",
        "$pipeline_target_id",
        "$epidemiology_disease_id",
        "$regulatory_subject_id",
        "$regulatory_indication_id",
        "$regulatory_company_id",
    ):
        assert f"'{fixture_entity_id}'" in acceptance_text
    assert 'E2E_REGULATORY_EVENT_ID="$regulatory_event_id"' in acceptance_text
    assert 'E2E_EPIDEMIOLOGY_PATIENT_POPULATION_ID="$epidemiology_patient_population_id"' in acceptance_text
    assert 'E2E_PATENT_FAMILY_ID="$patent_family_id"' in acceptance_text
    assert 'E2E_NEWS_EVENT_ID="$news_event_id"' in acceptance_text
    assert 'E2E_DEAL_ENTITY_ID="$deal_entity_id"' in acceptance_text
    assert 'E2E_DEAL_PROFILE_ID="$deal_profile_id"' in acceptance_text
    assert 'E2E_INGESTION_RUN_ID_DESKTOP_1440="${ingestion_run_ids[desktop-1440]}"' in acceptance_text
    assert "connector_cursor, last_scanned_at, consecutive_failures" in acceptance_text
    assert "normalized_email LIKE :'email_pattern'" in acceptance_text
    assert 'email_pattern="e2e-%@example.test"' in acceptance_text
    assert "fact_key LIKE 'browser-publication-e2e-%'" in acceptance_text
    assert "name LIKE 'Browser replay e2e-%'" in acceptance_text
    assert 'E2E_EMAIL="$email"' not in acceptance_text
    assert 'browser_product="Google Chrome"' in runtime_text
    assert '"research_workbench": "[research-workbench]"' in acceptance_text
    assert '"internal_workbench": "[internal-workbench]"' in acceptance_text
    assert '"ingestion_replay": "[ingestion-replay]"' in acceptance_text
    assert '"external_login": "[external-login]"' in acceptance_text
    assert '"internal_login": "[internal-login]"' in acceptance_text
    assert '"workspace_isolation": "[workspace-isolation]"' in acceptance_text
    assert '"browser_quality": "[browser-quality]"' in acceptance_text
    assert '"web_vitals_rum": "[web-vitals-rum]"' in acceptance_text
    assert '"clinical_linked_program_correctness": "[clinical-linked-program-correctness]"' in acceptance_text
    assert '"professional_deal_query": "[professional-deal-query]"' in acceptance_text
    assert '"professional_regulatory_query": "[professional-regulatory-query]"' in acceptance_text
    assert '"professional_epidemiology_query": "[professional-epidemiology-query]"' in acceptance_text
    assert '"professional_news_query": "[professional-news-query]"' in acceptance_text
    assert '"table_preference_server_continuity": "[table-preference-server-continuity]"' in acceptance_text
    assert '"query_cancellation": "[query-cancellation]"' in acceptance_text
    assert '"professional_query_state_matrix": "[professional-query-state-matrix]"' in acceptance_text
    assert '"professional_error_permission_matrix": "[professional-error-permission-matrix]"' in acceptance_text
    assert '"initial_load_boundary": "[initial-load-boundary]"' in acceptance_text
    assert '"chemistry_real_api": "[chemistry-real-api]"' in acceptance_text
    assert '"real_permission_boundary": "[real-permission-boundary]"' in acceptance_text
    assert '"real_target_dossier": "[real-target-dossier]"' in acceptance_text
    assert "remaining_chemistry_fixtures" in acceptance_text
    assert "temporary_chemistry_fixtures_after=0" in acceptance_text
    assert "remaining_governed_fixtures" in acceptance_text
    assert "temporary_governed_fixtures_after=0" in acceptance_text
    assert "stale_governed_fixtures" in acceptance_text
    assert "Refusing to run with stale governed fixtures" in acceptance_text
    assert acceptance_text.index("stale_governed_fixtures=$(\n") < acceptance_text.index('browser_user_id=""')
    assert "temporary_activity_fixtures_after=0" in acceptance_text
    assert 'E2E_PERMISSION_EMAIL="$permission_email"' in acceptance_text
    assert 'E2E_PERMISSION_PASSWORD="$permission_password"' in acceptance_text
    assert "permission_password_hash" in acceptance_text
    assert "--recover-interrupted-run" in acceptance_text
    assert (
        "BROWSER_ACCEPTANCE_RECOVERY status=passed temporary_accounts_after=0 temporary_entities_after=0"
        in acceptance_text
    )
    assert acceptance_text.index('if [[ "$recover_interrupted_run" == true ]]') < acceptance_text.index(
        "stale_accounts=$("
    )
    assert '"reflow_keyboard": "[reflow-keyboard]"' in acceptance_text
    assert (
        '"scope": "effective-css-viewport-equivalent"' in acceptance_text
        or "effective-css-viewport-equivalent" in acceptance_text
    )
    assert '"desktop-1440": 0' in acceptance_text
    assert '"desktop-1920": 0' in acceptance_text
    assert '"tablet-1024": 0' in acceptance_text
    assert '"mobile-390": 0' in acceptance_text
    assert "pharma.workbench-visual-baselines.v3" in acceptance_text
    assert "research-dense-results-desktop-1440.png" in acceptance_text
    assert "research-trial-outcomes-desktop-1440.png" in acceptance_text
    assert "research-patent-timeline-desktop-1440.png" in acceptance_text
    assert "research-deal-rights-desktop-1440.png" in acceptance_text
    assert '"controlled-dense-results", "table-shell"' in acceptance_text
    assert '"controlled-trial-outcomes", "dossier-section"' in acceptance_text
    assert '"controlled-patent-timeline", "dossier-section"' in acceptance_text
    assert '"controlled-deal-rights", "dossier-section"' in acceptance_text
    assert "visual baseline manifest does not match the committed PNG inventory" in acceptance_text
    assert acceptance_text.count("CREATE TEMP TABLE browser_account_comparison_sets") == 3
    assert "CREATE TEMP TABLE browser_fixture_comparison_sets" in acceptance_text
    assert acceptance_text.index("DELETE FROM comparison_set_members") < acceptance_text.index(
        "DELETE FROM users WHERE normalized_email LIKE :'email_pattern'"
    )
    fixture_cleanup = acceptance_text.index("CREATE TEMP TABLE browser_fixture_entities")
    assert acceptance_text.index("DELETE FROM comparison_set_members", fixture_cleanup) < acceptance_text.index(
        "DELETE FROM entities", fixture_cleanup
    )
    assert acceptance_text.index("DELETE FROM epidemiology_observations", fixture_cleanup) < acceptance_text.index(
        "DELETE FROM patient_populations", fixture_cleanup
    )


def test_windows_browser_fixture_recovery_requires_a_verified_backup_and_explicit_confirmation() -> None:
    root = Path(__file__).parents[1]
    recovery = (root / "scripts" / "recover-interrupted-browser-acceptance.ps1").read_text(encoding="utf-8")

    assert "CLEAN_SYNTHETIC_RUNTIME_DATA" in recovery
    assert "Get-FileHash" in recovery
    assert "BackupSha256 must match the verified postgres.dump checksum." in recovery
    assert "acceptance_fixture" in recovery
    assert "DELETE FROM patient_populations" in recovery
    assert "e2e-%@example.test" in recovery
    assert "temporary_entities_after" in recovery
    assert "temporary_accounts_after" in recovery
    assert "POSTGRES_PASSWORD" not in recovery
    assert "RUNTIME_DATABASE_URL" not in recovery


def test_web_vitals_rum_acceptance_is_authenticated_private_and_export_verified() -> None:
    root = Path(__file__).parents[1]
    script = (root / "scripts" / "verify-web-vitals-rum.sh").read_text(encoding="utf-8")
    makefile = (root / "Makefile").read_text(encoding="utf-8")
    bash = _bash_executable()
    assert bash is not None

    completed = subprocess.run(  # noqa: S603 - fixed repository script is syntax checked only.
        [bash, "-n", _bash_script_path(root / "scripts" / "verify-web-vitals-rum.sh")],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert "BOOTSTRAP_ADMIN_EMAIL" not in script
    assert "BOOTSTRAP_ADMIN_PASSWORD" not in script
    assert "openssl rand -base64 24" in script
    assert 'credentials_path="$temporary_root/credentials.json"' in script
    assert 'hash_password(payload["password"])' in script
    assert "UserRole.ANALYST" in script
    assert "cleanup_account" in script
    assert script.index("account_created=true") < script.index("docker compose exec -T api /app/.venv/bin/python -c")
    assert 'temporary_account_rows": 0' in script
    assert 'client.cookies.get("pharma_csrf"' in script
    assert '"/api/v1/workspace/web-vitals"' in script
    assert "pharma.web.vitals.duration" in script
    assert "baseline_count=$(matching_export_count" in script
    assert "observed_count > baseline_count" in script
    assert "bounds != required_bounds" in script
    assert 'service_name != "pharma-gateway"' in script
    assert '"navigation_type": "prerender"' in script
    assert '"route": "unknown"' in script
    assert "credentials_recorded" in script
    assert "web-vitals-rum-acceptance:" in makefile


def test_microsoft_edge_acceptance_uses_signed_current_and_previous_distributions() -> None:
    root = Path(__file__).parents[1]
    bootstrap = root / "scripts" / "bootstrap-wsl-edge.sh"
    acceptance = root / "scripts" / "run-browser-acceptance.sh"
    bootstrap_text = bootstrap.read_text(encoding="utf-8")
    acceptance_text = acceptance.read_text(encoding="utf-8")
    runtime_text = (root / "scripts/lib/browser_runtime.sh").read_text(encoding="utf-8")
    bash = _bash_executable()
    assert bash is not None

    completed = subprocess.run(  # noqa: S603 - fixed repository script is syntax checked only.
        [bash, "-n", _bash_script_path(bootstrap)],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert "https://packages.microsoft.com/repos/edge" in bootstrap_text
    assert "BC528686B50D79E339D3721CEB3E94ADBE1229CF" in bootstrap_text
    assert "gpgv --keyring" in bootstrap_text
    assert "published_packages_sha256" in bootstrap_text
    assert "package_sha256" in bootstrap_text
    assert 'selected_major = majors[0] if track == "current" else majors[1]' in bootstrap_text
    assert "sudo " not in bootstrap_text
    assert "edge-current" in acceptance_text
    assert "edge-previous" in acceptance_text
    assert "browser_channel=msedge" in runtime_text
    assert 'browser_product="Microsoft Edge"' in runtime_text
    assert "Only Google Chrome may update the repository visual baseline" in acceptance_text
    assert 'browser_launch_executable="$browser_executable"' in runtime_text
    assert 'E2E_BROWSER_EXECUTABLE="$browser_launch_executable"' in acceptance_text
    assert 'PLAYWRIGHT_JSON_OUTPUT_FILE="$playwright_json_output_file"' in acceptance_text
    assert "E2E_PLAYWRIGHT_COMMAND" in acceptance_text
    assert "E2E_PLAYWRIGHT_WORKDIR" in acceptance_text
    assert "sync_updated_snapshots()" in acceptance_text
    assert "shutil.copyfile(source, target)" in acceptance_text
    assert "from datetime import datetime, timezone" in acceptance_text
    assert "datetime.now(timezone.utc)" in acceptance_text


def test_api_serves_both_same_origin_workbench_routes_before_the_static_mount(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "research.html").write_text("<title>Research entry</title>", encoding="utf-8")
    (tmp_path / "internal.html").write_text("<title>Internal entry</title>", encoding="utf-8")
    (tmp_path / "index.html").write_text("<title>Static root</title>", encoding="utf-8")
    monkeypatch.setattr(runtime, "get_settings", lambda: Settings(web_root=tmp_path))
    with TestClient(create_app()) as client:
        for path, expected in (("/workspace/research", "Research entry"), ("/workspace/internal", "Internal entry")):
            response = client.get(path)
            assert response.status_code == 200
            assert expected in response.text and "Static root" not in response.text
            assert response.headers["cache-control"] == "no-cache, must-revalidate"
            assert client.head(path).status_code == 200
        assert "Static root" in client.get("/").text


def test_ci_installs_branded_chrome_instead_of_playwright_chromium() -> None:
    root = Path(__file__).parents[1]
    workflow = (root / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert "playwright install --with-deps chrome" in workflow
    assert "playwright install --with-deps chromium" not in workflow


def test_browser_acceptance_uses_bounded_assertions_without_retries() -> None:
    root = Path(__file__).parents[1]
    config = (root / "apps" / "web" / "playwright.config.ts").read_text(encoding="utf-8")

    assert "retries: 0" in config
    assert "expect: { timeout: 10_000 }" in config
    assert 'snapshotPathTemplate: "{testDir}/visual-baselines/{arg}-{projectName}{ext}"' in config
    assert 'name: "desktop-1440"' in config
    assert 'name: "desktop-1920"' in config
    assert 'name: "tablet-1024"' in config
    assert 'name: "mobile-390"' in config
