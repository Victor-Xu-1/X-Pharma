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
    probe = (ROOT / "apps/web/e2e/workspace/helpers.ts").read_text(encoding="utf-8")
    assert 'new PerformanceObserver(recordInteractions).observe({ type: "first-input", buffered: true })' in probe
    assert "new PerformanceObserver(recordInteractions).observe(eventOptions)" in probe
    assert "durationThreshold: 16" in probe


def test_dense_capture_uses_one_bounded_natural_flow_without_scroll_workarounds() -> None:
    owner = (NAVIGATION / "dense-results-visual.ts").read_text(encoding="utf-8")
    table = (ROOT / "apps/web/src/components/VirtualDataTable.tsx").read_text(encoding="utf-8")
    assert "height: totalHeight, paddingTop: visibleItems[0]?.start ?? 0" in table
    assert "style={{ height: virtualRow.size }}" in table
    assert "translateY(${virtualRow.start}px)" not in table
    assert "height: virtualRow.size, top: virtualRow.start" not in table
    assert "scrollIntoViewIfNeeded" not in owner
    assert "window.scrollTo" not in owner
    assert "await verifyVirtualRowLayout(denseTableShell)" in owner
    layout = (NAVIGATION / "virtual-row-layout.ts").read_text(encoding="utf-8")
    assert "expect(state.firstOffset).toBe(state.padding)" in layout
    assert "expect(state.count).toBeLessThanOrEqual(state.maximumRows)" in layout
    assert "finally" in layout and "initial.scroll" in layout


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


def test_fixed_column_layout_is_verified_by_the_one_visual_owner() -> None:
    owner = (NAVIGATION / "dense-results-visual.ts").read_text(encoding="utf-8")
    layout = (NAVIGATION / "fixed-column-layout.ts").read_text(encoding="utf-8")
    registration = (ROOT / "apps/web/e2e/workspace.spec.ts").read_text(encoding="utf-8")
    assert "await verifyFixedColumnLayout(denseTableShell)" in owner
    assert owner.index("verifyFixedColumnLayout(denseTableShell)") < owner.index("toHaveScreenshot(")
    assert "document.fonts.ready" in layout
    assert 'expect(cell.position).toBe("sticky")' in layout
    assert "initial.scroll" in layout and "finally" in layout
    assert registration.count("[workspace-navigation][workspace-isolation]") == 1
    assert "workbenchVisualTest" not in registration
    assert ".launch(" not in layout
    assert ".newContext(" not in layout
    assert ".newPage(" not in layout
    assert "maxDiffPixelRatio" not in layout
