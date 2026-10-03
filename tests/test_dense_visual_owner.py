from pathlib import Path

ROOT = Path(__file__).parents[1]
NAVIGATION = ROOT / "apps/web/e2e/workspace/navigation"


def test_dense_visual_has_one_owner_and_preserves_original_quality_thresholds() -> None:
    owner = (NAVIGATION / "dense-results-visual.ts").read_text(encoding="utf-8")
    stage = (NAVIGATION / "dense-result-and-landscape.ts").read_text(encoding="utf-8")
    assert 'toHaveScreenshot("research-dense-results.png"' in owner
    assert "toHaveScreenshot" not in stage
    assert "await verifyDenseResultsVisual(context)" in stage
    assert "maxDiffPixelRatio: 0.001" in owner
    assert "toBeLessThanOrEqual(2_500)" in owner
    assert "inp_ms).toBeLessThanOrEqual(200)" in owner
    assert "cls).toBeLessThanOrEqual(0.1)" in owner
    assert 'maskColor: "#dce4e7"' in owner


def test_dense_capture_preserves_virtual_offsets_without_scroll_workarounds() -> None:
    owner = (NAVIGATION / "dense-results-visual.ts").read_text(encoding="utf-8")
    table = (ROOT / "apps/web/src/components/VirtualDataTable.tsx").read_text(encoding="utf-8")
    assert "height: virtualRow.size, transform: `translateY(${virtualRow.start}px)`" in table
    assert "height: virtualRow.size, top: virtualRow.start" not in table
    assert "scrollIntoViewIfNeeded" not in owner
    assert "window.scrollTo" not in owner


def test_reflow_reproduction_and_official_suite_use_the_same_owned_flow_and_budgets() -> None:
    registration = (ROOT / "apps/web/e2e/accessibility.spec.ts").read_text(encoding="utf-8")
    reflow = (ROOT / "apps/web/e2e/accessibility/reflow-keyboard.ts").read_text(encoding="utf-8")
    assert "verifyKeyboardReflow," in registration
    assert "effectiveZoomViewports" not in registration
    assert "async function expectNamedKeyboardScrollableTables" not in registration
    assert "testInfo.setTimeout(120_000)" in reflow
    assert "width: 320" in reflow
    assert "width: 720" in reflow
    assert "width: 360" in reflow


def test_visual_acceptance_has_one_framework_owned_worker_boundary() -> None:
    fixture = (ROOT / "apps/web/e2e/fixtures/workbench-visual.ts").read_text(encoding="utf-8")
    registration = (ROOT / "apps/web/e2e/workspace.spec.ts").read_text(encoding="utf-8")
    assert 'workbenchVisualWorker: ["workbench-visual", { scope: "worker", auto: true }]' in fixture
    assert "workbenchVisualTest(\n" in registration
    assert registration.count("[workspace-navigation][workspace-isolation]") == 1
    assert ".launch(" not in fixture
    assert ".newContext(" not in fixture
    assert ".newPage(" not in fixture
    assert "maxDiffPixelRatio" not in fixture
