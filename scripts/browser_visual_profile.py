"""Fail early on Chrome/reference drift; this check is not browser acceptance."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import cast

from scripts.reference_visual_pair import ReferenceVisualPairError, load_visual_baseline_manifest

TARGETS = ("chrome", "edge-current", "edge-previous")


def verify_profile(
    repo: Path, *, browser: str, target: str = "chrome", review_update: bool = False
) -> dict[str, str | bool]:
    if target not in TARGETS:
        raise ReferenceVisualPairError("Unsupported browser target")
    product = "Google Chrome" if target == "chrome" else "Microsoft Edge"
    browser = browser.strip()
    if re.fullmatch(rf"{re.escape(product)} [0-9]+(?:\.[0-9]+){{3}}", browser) is None:
        raise ReferenceVisualPairError("Browser returned an invalid product/version")
    if review_update and target != "chrome":
        raise ReferenceVisualPairError("Only Google Chrome may review updated visual references")
    reference_browser = cast(str, load_visual_baseline_manifest(repo)["browser"])
    if target == "chrome" and not review_update and browser != reference_browser:
        raise ReferenceVisualPairError(
            f"Chrome/reference version drift: runtime {browser}; reviewed {reference_browser}. "
            "Use the reviewed browser or explicitly review new references; "
            "references are never updated automatically."
        )
    return {
        "status": "ready",
        "scope": "browser-visual-profile-only",
        "browser": browser,
        "reference_browser": reference_browser,
        "review_update": review_update,
        "is_release_evidence": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--browser", required=True)
    parser.add_argument("--target", choices=TARGETS, default="chrome")
    parser.add_argument("--review-update", action="store_true")
    arguments = parser.parse_args()
    try:
        result = verify_profile(
            arguments.repo,
            browser=arguments.browser,
            target=arguments.target,
            review_update=arguments.review_update,
        )
    except (ReferenceVisualPairError, OSError) as error:
        print(f"Browser visual profile check failed: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
