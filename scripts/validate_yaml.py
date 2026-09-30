from __future__ import annotations

import argparse
import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import yaml
from yaml.constructor import ConstructorError
from yaml.nodes import MappingNode
from yaml.resolver import BaseResolver


class UniqueKeyLoader(yaml.SafeLoader):
    """Safe loader whose mapping constructor rejects ambiguous duplicate keys."""


def _construct_unique_mapping(
    loader: UniqueKeyLoader,
    node: MappingNode,
    deep: bool = False,
) -> dict[Any, Any]:
    loader.flatten_mapping(node)
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        try:
            duplicate = key in mapping
        except TypeError as exc:
            raise ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                "found an unhashable mapping key",
                key_node.start_mark,
            ) from exc
        if duplicate:
            raise ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                f"found duplicate key {key!r}",
                key_node.start_mark,
            )
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


UniqueKeyLoader.add_constructor(BaseResolver.DEFAULT_MAPPING_TAG, _construct_unique_mapping)


def _yaml_files(inputs: Iterable[Path]) -> list[Path]:
    files: set[Path] = set()
    for candidate in inputs:
        if candidate.is_dir():
            files.update(path for pattern in ("*.yaml", "*.yml") for path in candidate.rglob(pattern))
        elif candidate.is_file() and candidate.suffix.casefold() in {".yaml", ".yml"}:
            files.add(candidate)
        else:
            raise ValueError(f"YAML input does not exist or has an unsupported extension: {candidate}")
    if not files:
        raise ValueError("No YAML files were selected")
    return sorted((path.resolve() for path in files), key=str)


def validate_yaml(inputs: Iterable[Path]) -> dict[str, int]:
    files = _yaml_files(inputs)
    document_count = 0
    for path in files:
        try:
            with path.open("r", encoding="utf-8") as handle:
                document_count += sum(1 for _ in yaml.load_all(handle, Loader=UniqueKeyLoader))
        except (OSError, UnicodeError, yaml.YAMLError) as exc:
            raise ValueError(f"Invalid YAML in {path}: {exc}") from exc
    return {"file_count": len(files), "document_count": document_count}


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate YAML syntax and reject duplicate mapping keys")
    parser.add_argument("paths", nargs="+", type=Path, help="YAML files or directories")
    arguments = parser.parse_args()
    try:
        result = validate_yaml(arguments.paths)
    except ValueError as exc:
        parser.error(str(exc))
    print(json.dumps({"status": "passed", **result}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
