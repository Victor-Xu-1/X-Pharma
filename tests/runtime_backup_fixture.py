"""Stateful controlled transport for fresh-backup management, never real Docker."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

IDS = {name: digit * 64 for name, digit in (("api", "1"), ("worker", "2"), ("temporal", "3"))}


def invoke(tool: str, arguments: list[str], state: dict[str, Any], mode: str) -> int:
    if tool == "systemd-run":
        state["watchdog"] = True
        return 18 if mode == "arm-failure" else 0
    if tool == "systemctl":
        if "stop" in arguments:
            if mode == "stop-failure":
                return 19
            state["watchdog"] = False
            return 0
        assert "is-active" in arguments
        if "--quiet" not in arguments:
            if mode == "timer-unknown":
                return 20
            print("active" if state.get("watchdog") else "inactive")
        return 0 if state.get("watchdog") else 3
    assert tool == "docker"
    action = arguments[0]
    if action == "compose":
        if mode == "inventory-failure":
            return 21
        print(IDS["api" if mode == "duplicate" else arguments[-1]])
        return 0
    if action == "inspect":
        if mode == "hang":
            time.sleep(30)
        if mode == "inspect-failure" and state.get("attempted"):
            return 22
        identity = arguments[-1]
        service = next(name for name, value in IDS.items() if value == identity)
        project = (
            "foreign-project"
            if mode == "replaced" and state.get("attempted") and service == "api"
            else "x-pharma-controlled"
        )
        paused = state.get("paused", {}).get(identity, mode == "already-paused" and service == "api")
        print(identity, project, service, "true", str(paused).lower())
        return 0
    if action == "pause":
        state["attempted"] = True
        for index, identity in enumerate(arguments[1:]):
            if mode == "partial-pause" and index > 0:
                return 23
            state.setdefault("paused", {})[identity] = True
        return 0
    if action == "unpause":
        if mode == "unpause-failure":
            return 24
        if mode != "unpause-retained":
            for identity in arguments[1:]:
                state.setdefault("paused", {})[identity] = False
        return 0
    raise AssertionError(f"unexpected controlled transport command: {tool} {arguments}")


def main() -> int:
    state_path = Path(os.environ["BACKUP_FIXTURE_STATE"])
    trace_path = Path(os.environ["BACKUP_FIXTURE_TRACE"])
    state = json.loads(state_path.read_text()) if state_path.exists() else {}
    trace = json.loads(trace_path.read_text()) if trace_path.exists() else []
    trace.append(sys.argv[1:])
    trace_path.write_text(json.dumps(trace), encoding="utf-8")
    try:
        return invoke(sys.argv[1], sys.argv[2:], state, os.environ.get("BACKUP_FIXTURE_MODE", "normal"))
    finally:
        state_path.write_text(json.dumps(state), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
