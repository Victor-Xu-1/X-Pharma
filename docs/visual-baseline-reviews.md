# Visual baseline reviews

## 2026-10-02: tablet dense results

Only `research-dense-results-tablet-1024.png` is maintained in this review.
The viewport is 1024×768 and the table-shell image is 724×646.

- Current canonical SHA-256: `b871674923e9aeb30c7584db6068c81728ab6a23d032b54f942091bf7ba04693`, the restored original repository reference.
- Withdrawn intermediate SHA-256: `94b90c8ab9e4e24dcc9167e23bef18c0c0343b04898559a1d37e79f06f456119`.
- Intermediate source: the actual image from [automatic CI run 36963858242](https://github.com/Victor-Xu-1/X-Pharma/actions/runs/36963858242), commit `ed953406eb6e1f128f975c7c37b8de3895da63a6`. It is retained as diagnostic evidence, not the current reference.
- Data: only the existing synthetic 205-result pagination fixture; the existing alias-match mask is unchanged. No production data or third-party brand assets are added.

The old reference, CI actual and diff were visually inspected. Columns,
controls, sort direction, names, row heights, counts and clipping agree;
the rejected pixels predominantly concern a one-pixel fixed-column paint
phase. Repeated focused real-PG runs reproduced the same 5,811-pixel
rejection against the old reference. The CI and local real-PG fixed-column
pixels agree. A direct SQLite navigation can paint that column differently
even with identical computed fonts and bounds for 23 relevant elements.
The initial paint/scroll hypothesis was insufficient: after restoring the
original row positioning, local Chrome 154.0.8037.92 produced the previous
reference byte for byte. The CI installation log proves that its actual
browser is 154.0.8037.97, while the previous manifest and local browser used
154.0.8037.92. A signed, independently cached Chrome 154.0.8037.97 then passed
all four focused real-PG paths with the reviewed reference in 31.9 seconds.
That was only a browser/reference profile correction, not proof of a
pagination/data-correctness fix or complete-suite stability. Automatic run
36982327415 still finished at 139/140: with both runtime and reference at
154.0.8037.97, its actual PNG byte-matched the previous b871 reference.
Version alignment alone therefore did not explain or resolve the failure.
The profile remains 154.0.8037.97; other assets are historical captures, not
claims of 19 fresh screenshots.

Changing virtual rows from `translateY` to `top`, resetting the outer scroll
and explicitly aligning the locator did not resolve the rejection. Those
experiments are removed. Product row positioning, CSS and virtualization
remain unchanged; no screenshot-only product renderer is introduced.

The other 19 PNGs are unchanged in this review. The original mask,
`maxDiffPixelRatio: 0.001`, LCP ≤ 2,500 ms, INP ≤ 200 ms and CLS ≤ 0.1
remain enforced. The regular workbench stage and focused real-PG checks
consume the same `dense-results-visual` implementation. Focused checks do
not replace the registered 140-scenario acceptance guard. Current acceptance
must be reported against the actual new commit and automatic CI result;
this reference review alone is not a successful release or production claim.

`scripts.browser_visual_profile` uses the reference manifest's one metadata
validator. CI checks the installed Chrome before starting the stack, and the
local runner resolves and checks its browser before crossing the Docker
fixture boundary. Version drift fails with an actionable diagnostic; it
never refreshes references automatically. Explicit Chrome reference review
is still distinct from acceptance, Edge cannot update Chrome references,
and explicit interrupted-fixture recovery does not depend on a matching
browser. No older browser is installed over a user's current one to conceal
profile drift.

### Reflow/process-isolation evidence

The actual CI order runs keyboard reflow before the visual workbench flow.
With the same .97 binary and real PG, adding only public/internal login
prefixes passed 12/12 and did not reproduce the issue. Adding the original
320/720/360 CSS-pixel reflow flow produced 15/16 in 44.3 seconds, including
the identical 5,811-pixel tablet rejection. Retaining that entire sequence
but giving the visual flow its own worker passed 16/16 in 45.6 seconds.
Neither the PNG nor mask, pixel, action, case or performance budget changed.

The worker-isolation hypothesis was then checked against the original
complete staged workbench flow, not just the four initial helpers. That
broader focused run still finished at 15/16 (5.1 minutes), with the same
tablet rejection. The worker fixture is therefore withdrawn: it was not a
complete fix. Browser/context/page setup and teardown remain entirely
framework-owned. The original keyboard flow and shared reflow checks have
one reusable implementation used by official registration and focused
reproduction. Discovery still registers 140 tests in the same four files.

This is process-isolation evidence, not a claim that the next automatic
full-suite run has already passed. Full-suite and downstream MCP conclusions
must still come from the actual new commit's automatic CI.

### Canonical full-flow validation and rollback

Directly invoking only the initial helpers was not equivalent to the
official staged orchestration for pixel-reference selection. The current
complete staged flow and automatic CI actual both byte-matched the original
b871 reference. Restoring that already-reviewed original, and removing the
ineffective worker fork, passed 16/16 focused real-PG scenarios in 6.5 minutes:
original keyboard reflow, both login prefixes and the complete original
workbench flow at all four viewports. All original assertions, snapshots,
timings and the complete-coverage guard remain enforced. CSS containment,
3D/layer and pixel-translation experiments stayed private and are not product
or screenshot-only rendering paths.

The intermediate 94b90 reference is withdrawn rather than claimed as a
product fix. The sole shared reflow implementation is retained so focused
reproduction can use the actual official flow. Partial helper results must
not replace complete-flow or actual automatic-CI acceptance evidence.
