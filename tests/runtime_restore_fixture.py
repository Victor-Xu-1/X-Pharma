"""Stateful synthetic Docker transport for clean-target ownership tests only."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import cast

Resource = dict[str, str]
State = dict[str, dict[str, Resource]]
OWNER = "io.pharma.runtime-restore-owner="


def option(arguments: list[str], flag: str) -> str:
    return arguments[arguments.index(flag) + 1]


def owner_label(arguments: list[str]) -> str:
    return next((value.removeprefix(OWNER) for value in arguments if value.startswith(OWNER)), "foreign")


def selected(arguments: list[str], resource: Resource) -> bool:
    for index, argument in enumerate(arguments):
        if argument != "--filter":
            continue
        value = arguments[index + 1]
        if value.startswith("label=" + OWNER) and resource["owner"] != value.removeprefix("label=" + OWNER):
            return False
        if value.startswith("name=^") and resource["name"] != value.removeprefix("name=^").removesuffix("$"):
            return False
    return True


def volume_command(arguments: list[str], state: State, mode: str) -> int:
    volumes = state["volumes"]
    action = arguments[1]
    if action == "create":
        name = arguments[-1]
        if name not in volumes:
            volumes[name] = {
                "name": name,
                "owner": "foreign" if mode == "volume-collision" else owner_label(arguments),
                "created": "2026-10-24T00:00:00Z",
                "inspections": "0",
            }
        print(name)
        return 124 if mode == "volume-lost-reply" else 0
    if action == "ls":
        for resource in volumes.values():
            if selected(arguments, resource):
                print(resource["name"])
        return 0
    name = arguments[-1]
    if name not in volumes:
        return 1
    resource = volumes[name]
    if action == "inspect":
        resource["inspections"] = str(int(resource["inspections"]) + 1)
        if int(resource["inspections"]) > 1:
            if mode == "volume-replaced":
                resource["owner"] = "foreign"
            if mode == "volume-identity-changed":
                resource["created"] = "2026-10-24T01:00:00Z"
        print(resource["name"], resource["owner"], resource["created"])
        return 0
    if action == "rm":
        assert "-f" not in arguments and "--force" not in arguments
        if mode == "volume-retained":
            return 9
        del volumes[name]
        return 0
    return 99


def container_command(arguments: list[str], state: State, mode: str) -> int:
    containers = state["containers"]
    action = arguments[0]
    if action == "create":
        name = option(arguments, "--name")
        probe = name.endswith("-rls")
        identity = ("b" if probe else "a") * 64
        image = next(value for value in arguments if value.startswith("sha256:"))
        containers[identity] = {
            "id": identity,
            "name": name,
            "owner": "foreign" if mode == "container-collision" else owner_label(arguments),
            "image": "sha256:" + "9" * 64 if mode == "container-identity-changed" else image,
            "status": "exited" if probe else "running",
            "code": "7" if probe and mode == "probe-nonzero" else "0",
        }
        print(identity)
        return 125 if mode == "container-collision" else 124 if mode == "container-lost-reply" else 0
    if action == "container" and arguments[1] == "ls":
        if mode == "daemon-error":
            return 19
        for resource in containers.values():
            if selected(arguments, resource):
                print(resource["id"], resource["name"])
        return 0
    identity = arguments[-1]
    if identity not in containers:
        return 1
    resource = containers[identity]
    if action == "inspect":
        if ".State.Status" in option(arguments, "--format"):
            print(resource["status"], resource["code"])
        else:
            print(identity, "/" + resource["name"], resource["image"], resource["owner"])
        return 0
    if action == "stop":
        if mode == "stop-failure":
            return 9
        resource["status"], resource["code"] = "exited", "0"
        return 0
    if action == "rm":
        if mode == "container-retained":
            return 9
        assert arguments[1] == "-f"
        del containers[identity]
        return 0
    return 99


def main() -> int:
    arguments = sys.argv[1:]
    path = Path(os.environ["RESTORE_RESOURCE_STATE"])
    trace = Path(os.environ["RESTORE_RESOURCE_TRACE"])
    state = cast(State, json.loads(path.read_text()) if path.exists() else {"containers": {}, "volumes": {}})
    with trace.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(arguments) + "\n")
    try:
        mode = os.environ.get("RESTORE_RESOURCE_MODE", "normal")
        return (
            volume_command(arguments, state, mode)
            if arguments[0] == "volume"
            else container_command(arguments, state, mode)
        )
    finally:
        path.write_text(json.dumps(state), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
