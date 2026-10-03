# Visual baseline reviews

Current tablet dense-results reference:
`577f39c0e3ef678454f950d313c4296514bf3d5835f8ce524993622ac71898cc`.
It belongs to the real bounded natural-flow product layout below, not either
of the two former transform-rendering paint phases.

## 2026-10-03: failed isolation and bounded natural-flow review

Automatic [run 36996101760](https://github.com/Victor-Xu-1/X-Pharma/actions/runs/36996101760)
for `46ad22e16beec681668d36bce74f652245b88742` ended at 139/140, not a
successful acceptance. Its tablet dense-results actual byte-matched the
withdrawn 94b90 intermediate; the canonical b871 original remained unchanged.
The previous 16-case focused run omitted the two preceding official
accessibility audits, so it did not reproduce the complete CI prefix.

The narrower reproduction now uses the original official registrations:
both accessibility audits, keyboard reflow, three branding cases, browser
identity, both login entries and the complete staged workbench navigation.
With the same Chrome 154.0.8037.97, real PostgreSQL, application image and
original reference, these ten tablet cases first produced 9/10 in 56.2
seconds, with the same 5,811-pixel rejection. Adding an automatic worker
fixture only to the workbench navigation registration then passed 10/10 in
2.4 minutes. No helper-only replacement or shortened workbench flow was used.

The worker boundary did not establish stability. After clean image build
and exact deployment of the local `8be8f53` candidate, the same official
ten-case prefix again produced 9/10 in 1.2 minutes with 5,811 different
pixels. The worker fixture is withdrawn; the original registration and all
framework-owned browser/context/page/device/tracing/teardown behavior remain.
No isolation experiment is reported as a complete fix.

Private geometry diagnostics retained both outcomes: recording before the
first capture passed 10/10, while recording only afterward produced 9/10.
The after-capture geometry JSONs were identical. Small document-scroll
changes affected only the bottom crop edge, not the fixed-column rejection.
Pixel analysis showed approximately one vertical pixel of displacement in
fixed-column text, with ordinary row columns unchanged. Fixed-column/font
assertions alone also produced 9/10. These observations do not prove a
Chromium internal mechanism, and all private diagnostic imports are removed.

The product layout now uses one bounded natural-flow canvas: the existing
virtualizer owns the visible window and total height; the body uses the
first visible offset as top padding and rows retain their fixed height.
Per-row absolute positioning and transforms are removed, not retained as a
fallback. Shared layout checks verify fonts, fixed header/body columns,
horizontal scrolling, bounded rows and the middle-window offset, then
restore both original scroll offsets before the existing pixel assertion.
This is a product layout change, not screenshot-only CSS.

The two directly affected unit regressions first failed on the old layout;
all eight table tests then passed, including both densities, bounded DOM,
sorting, preferences and row selection. Twelve related engineering guards,
strict application/E2E types and scoped formatting pass. All twenty PNGs,
masks, pixel/performance thresholds and case/action budgets are still
unchanged at this point in the review. Listing 140 scenarios does not execute them.
The canonical coverage guard correctly rejects the ten-case run as full
acceptance. The natural-flow candidate's exact-image deployment and automatic CI must
still establish their own results; downstream MCP and production acceptance
must not be inferred from this focused browser pass.

### Reviewed natural-flow asset identity

Clean candidate `35cdf9dac6fea53e0a9649a8a29910e6e8a2c8fb` ran on exact image
`sha256:9b7b1f5f6a2e0a12507e76063d248afad0bdc7a5dc8f0d530a303b7a549f047f`.
The four-viewport affected-layout check and the original ten-case tablet
prefix both produced the same tablet PNG, SHA-256 `577f39c0e3ef678454f950d313c4296514bf3d5835f8ce524993622ac71898cc`.
The latter retained the full original staged navigation and first passed both
accessibility audits, keyboard reflow, branding/browser identity and logins;
it then correctly rejected the changed product layout against the former
reference (9/10, 55.1 seconds). The horizontal-column and middle-window
geometry assertions passed before that pixel rejection.

The actual natural-flow image was visually reviewed. Layout bounds, rows,
columns, controls, counts and clipping are preserved; this is an intentional
row-rendering implementation change, not a data/result correctness fix.
Only that tablet PNG is adopted. The other nineteen PNGs remain unchanged.
The canonical manifest-generation block in `run-browser-acceptance.sh` was
reused for the reviewed asset identity; no full snapshot-refresh run or
coverage bypass occurred. Its new manifest generation date is not a claim
of twenty fresh screenshots. Pixel masks, 0.001 tolerance, all performance,
resource and action/case budgets remain unchanged.

The initial four-size layout run also exposed a new assertion's invalid
assumption that wide desktops must overflow horizontally. Wide layouts now
still verify column/font alignment and zero scroll, while actual overflowing
layouts retain the horizontal-motion assertions. The canonical coverage
guard remains mandatory; final exact-head browser and automatic-CI results
must be reported separately from this reference maintenance.

## 2026-10-02: tablet dense results

Only `research-dense-results-tablet-1024.png` is maintained in this review.
The viewport is 1024×768 and the table-shell image is 724×646.

- Historical end-of-review SHA-256: `b871674923e9aeb30c7584db6068c81728ab6a23d032b54f942091bf7ba04693`, the restored original transform-rendering reference, superseded by the natural-flow review above.
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
