from __future__ import annotations

import argparse
import json
from pathlib import Path

from pharma_intel.api import app

OPENAPI_CONTRACT_VERSION = "3.1.2"
DEFAULT_CONTRACT_PATH = Path("docs/openapi.json")


def render_contract() -> bytes:
    document = app.openapi()
    if document.get("openapi") != OPENAPI_CONTRACT_VERSION:
        raise RuntimeError(f"Expected OpenAPI {OPENAPI_CONTRACT_VERSION}, got {document.get('openapi', '<missing>')}")
    return (json.dumps(document, indent=2, sort_keys=True, ensure_ascii=True) + "\n").encode()


def run() -> None:
    parser = argparse.ArgumentParser(description="Generate or verify the internal OpenAPI release contract")
    parser.add_argument("--output", type=Path, default=DEFAULT_CONTRACT_PATH)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    rendered = render_contract()
    if args.check:
        if not args.output.is_file() or args.output.read_bytes() != rendered:
            parser.error(f"OpenAPI contract is stale; regenerate {args.output}")
        return
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(f"{args.output.suffix}.tmp")
    temporary.write_bytes(rendered)
    temporary.replace(args.output)


if __name__ == "__main__":
    run()
