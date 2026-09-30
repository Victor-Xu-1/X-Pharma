# Workbench visual baselines

These PNG files are repository-owned regression assets generated from the real
local runtime by `scripts/run-browser-acceptance.sh`. The scenario authenticates
through the real API and renders a fixed no-result query, a 205-record
PostgreSQL-to-OpenSearch dense result table, and deterministic clinical-result,
patent-timeline, and deal-rights dossier sections without request mocks.

Required viewports are `1440x900`, `1920x1080`, `1024x768`, and `390x844`.
Baselines may only be regenerated after an intentional visual review with:

```bash
./scripts/run-browser-acceptance.sh --update-snapshots
```

The default acceptance command never updates expected images. Every run compares
Google Chrome pixels against the committed full-page no-result,
fixed-height dense-table-shell, clinical outcomes, patent timeline, and deal
rights files and reports all five SHA-256 digests per viewport. The 20 images
contain no production data, credentials, or third-party brand assets.

Microsoft Edge current and previous-major acceptance runs compare against these
same repository-owned images. Edge is deliberately read-only for snapshots so a
browser-specific rendering difference cannot silently replace the Chrome
baseline.

`manifest.json` records the generating Chrome version, viewport, provenance,
license classification, and checksum for each binary. The explicit update
command rewrites the image and manifest together; every default run rejects a
manifest or checksum mismatch.

Authorized third-party reference captures are never copied into this directory
or the source repository. Register a same-viewport comparison with
`scripts/reference_visual_pair.py`; its content-addressed manifest must be
written to an external evidence store and remains a pending human review, not
an automated parity claim. See `docs/release-evidence.md` for the command and
evidence boundary.
