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


def test_virtual_rows_keep_geometry_without_transforming_sticky_cells() -> None:
    owner = (NAVIGATION / "dense-results-visual.ts").read_text(encoding="utf-8")
    table = (ROOT / "apps/web/src/components/VirtualDataTable.tsx").read_text(encoding="utf-8")
    assert "height: virtualRow.size, top: virtualRow.start" in table
    assert "translateY(${virtualRow.start}px)" not in table
    assert "scrollIntoViewIfNeeded" not in owner
