"""Run actual backup metadata commands against controlled Docker identities, never a daemon."""

from __future__ import annotations

import shlex
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).parents[1]
POSTGRES_IMAGE = "controlled-postgres:current"
API_IMAGE = "controlled-api:current"
POSTGRES_ID = "sha256:" + "1" * 64
API_ID = "sha256:" + "2" * 64
RETAGGED_ID = "sha256:" + "3" * 64

CONTROLLED_DOCKER = r"""
docker() {
  if [[ $# -eq 4 && "$1" == inspect && "$2" == --format ]]; then
    case "$4:$3" in
      "controlled-postgres:{{.Config.Image}}") printf '%s\n' "$postgres_ref" ;;
      "controlled-postgres:{{.Image}}") printf '%s\n' "$postgres_id" ;;
      "controlled-api:{{.Config.Image}}") printf '%s\n' "$api_ref" ;;
      "controlled-api:{{.Image}}") printf '%s\n' "$api_id" ;;
      *) return 90 ;;
    esac
  elif [[ $# -eq 5 && "$1" == image && "$2" == inspect && "$3" == --format && "$4" == '{{.Id}}' ]]; then
    [[ "$tag_state" != removed ]] || return 91
    case "$5" in
      "$postgres_ref")
        if [[ "$tag_state" == postgres || "$tag_state" == both ]]; then
          printf '%s\n' "$retagged_id"
        else
          printf '%s\n' "$postgres_id"
        fi ;;
      "$api_ref")
        if [[ "$tag_state" == api || "$tag_state" == both ]]; then
          printf '%s\n' "$retagged_id"
        else
          printf '%s\n' "$api_id"
        fi ;;
      *) return 92 ;;
    esac
  else
    return 93
  fi
}
"""


def _backup_source() -> str:
    return (ROOT / "scripts/backup-runtime-linux.sh").read_text(encoding="utf-8")


def _assert_running_image_identity(tag_state: str) -> None:
    source = _backup_source()
    start = source.index("\npostgres_image=") + 1
    end = source.index("\nalembic_head=", start)
    commands = source[start:end]
    assert len(commands.splitlines()) == 4, "review the actual backup metadata boundary"
    bash = shutil.which("bash")
    assert bash is not None, "the backup contract requires Bash"
    fixture = "\n".join(
        f"{name}={shlex.quote(value)}"
        for name, value in {
            "tag_state": tag_state,
            "postgres_ref": POSTGRES_IMAGE,
            "api_ref": API_IMAGE,
            "postgres_id": POSTGRES_ID,
            "api_id": API_ID,
            "retagged_id": RETAGGED_ID,
            "postgres_container": "controlled-postgres",
            "api_container": "controlled-api",
        }.items()
    )
    program = (
        "set -euo pipefail\n"
        + fixture
        + "\n"
        + CONTROLLED_DOCKER
        + "\n"
        + commands
        + '\nprintf "%s\\n" "$postgres_image" "$postgres_image_id" "$api_image" "$api_image_id"\n'
    )
    result = subprocess.run(  # noqa: S603 - Actual four production assignments, controlled shell function only.
        [bash, "--noprofile", "--norc", "-c", program],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [POSTGRES_IMAGE, POSTGRES_ID, API_IMAGE, API_ID]


def test_unchanged_tags_preserve_original_image_references_and_container_ids() -> None:
    _assert_running_image_identity("unchanged")


def test_postgres_retag_cannot_change_the_captured_database_image() -> None:
    _assert_running_image_identity("postgres")


def test_api_retag_cannot_change_the_captured_rls_probe_image() -> None:
    _assert_running_image_identity("api")


def test_both_retags_cannot_relabel_a_running_backup() -> None:
    _assert_running_image_identity("both")


def test_removed_tags_do_not_hide_still_running_container_images() -> None:
    _assert_running_image_identity("removed")
