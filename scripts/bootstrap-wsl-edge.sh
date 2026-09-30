#!/usr/bin/env bash
set -Eeuo pipefail

umask 077

track=current
if [[ ${1:-} == --track && $# -eq 2 ]]; then
  track=$2
elif [[ $# -ne 0 ]]; then
  echo "Usage: bootstrap-wsl-edge.sh [--track current|previous]" >&2
  exit 2
fi
[[ $track == current || $track == previous ]] || {
  echo "Edge track must be current or previous" >&2
  exit 2
}

cache_root=${PHARMA_EDGE_CACHE_DIR:-"$HOME/.cache/pharma-intelligence/microsoft-edge"}
repository_origin="https://packages.microsoft.com/repos/edge"
signing_key_url="https://packages.microsoft.com/keys/microsoft.asc"
expected_primary_fingerprint="BC528686B50D79E339D3721CEB3E94ADBE1229CF"

for command in curl dpkg-deb gpg gpgv mktemp mv python3 realpath sha256sum stat; do
  command -v "$command" >/dev/null 2>&1 || {
    echo "required command is unavailable: $command" >&2
    exit 1
  }
done

mkdir -p "$cache_root/releases"
cache_root=$(realpath "$cache_root")
workspace=$(mktemp -d -t pharma-microsoft-edge.XXXXXX)
export GNUPGHOME="$workspace/gnupg"
mkdir -m 0700 "$GNUPGHOME"
cleanup() {
  status=$?
  trap - EXIT INT TERM
  case "$workspace" in
    /tmp/pharma-microsoft-edge.*) rm -rf -- "$workspace" ;;
    *) echo "refusing to clean unexpected Edge workspace: $workspace" >&2 ;;
  esac
  exit "$status"
}
trap cleanup EXIT INT TERM

curl_args=(--fail --silent --show-error --location --proto '=https' --tlsv1.2 --connect-timeout 15 --max-time 300 --retry 2 --retry-all-errors)
curl "${curl_args[@]}" "$signing_key_url" --output "$workspace/microsoft.asc"
mapfile -t fingerprints < <(
  gpg --batch --show-keys --with-colons "$workspace/microsoft.asc" | awk -F: '$1 == "fpr" { print $10 }'
)
[[ " ${fingerprints[*]} " == *" $expected_primary_fingerprint "* ]] || {
  echo "Microsoft signing key primary fingerprint is not trusted" >&2
  exit 1
}
untrusted_keyring="$workspace/microsoft.untrusted.gpg"
trusted_keyring="$workspace/microsoft.gpg"
gpg --batch --no-default-keyring --keyring "$untrusted_keyring" --import "$workspace/microsoft.asc" >/dev/null 2>&1
gpg --batch --no-default-keyring --keyring "$untrusted_keyring" \
  --export "$expected_primary_fingerprint" > "$trusted_keyring"
[[ -s "$trusted_keyring" ]] || {
  echo "Microsoft signing key export failed" >&2
  exit 1
}
mapfile -t trusted_primary_fingerprints < <(
  gpg --batch --show-keys --with-colons "$trusted_keyring" \
    | awk -F: '$1 == "pub" { in_primary = 1; next } $1 == "sub" { in_primary = 0 } $1 == "fpr" && in_primary { print $10; in_primary = 0 }'
)
[[ ${#trusted_primary_fingerprints[@]} -eq 1 && "${trusted_primary_fingerprints[0]}" == "$expected_primary_fingerprint" ]] || {
  echo "trusted Microsoft signing keyring contains an unexpected primary key" >&2
  exit 1
}

curl "${curl_args[@]}" "$repository_origin/dists/stable/InRelease" --output "$workspace/InRelease"
curl "${curl_args[@]}" "$repository_origin/dists/stable/main/binary-amd64/Packages" --output "$workspace/Packages"
gpgv --keyring "$trusted_keyring" "$workspace/InRelease" >/dev/null

published_packages_sha256=$(
  python3 - "$workspace/InRelease" <<'PY'
from pathlib import Path
import sys

in_sha256 = False
for line in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines():
    if line == "SHA256:":
        in_sha256 = True
        continue
    if in_sha256 and line and not line.startswith(" "):
        break
    if in_sha256:
        fields = line.split()
        if len(fields) == 3 and fields[2] == "main/binary-amd64/Packages":
            print(fields[0])
            break
PY
)
[[ "$published_packages_sha256" =~ ^[0-9a-f]{64}$ ]] || {
  echo "Microsoft Edge repository metadata omitted the Packages digest" >&2
  exit 1
}
[[ "$(sha256sum "$workspace/Packages" | awk '{print $1}')" == "$published_packages_sha256" ]] || {
  echo "Microsoft Edge Packages digest validation failed" >&2
  exit 1
}

mapfile -t package_metadata < <(
  python3 - "$workspace/Packages" "$track" <<'PY'
from pathlib import Path, PurePosixPath
import re
import sys

rows = []
required = {"Package", "Version", "Architecture", "Filename", "Size", "SHA256"}
for paragraph in Path(sys.argv[1]).read_text(encoding="utf-8").split("\n\n"):
    fields = {}
    for line in paragraph.splitlines():
        if ": " in line:
            key, value = line.split(": ", 1)
            fields[key] = value
    if fields.get("Package") != "microsoft-edge-stable":
        continue
    if not required.issubset(fields) or fields["Architecture"] != "amd64":
        raise SystemExit("Microsoft Edge package metadata is incomplete")
    filename = PurePosixPath(fields["Filename"])
    if filename.is_absolute() or ".." in filename.parts or not str(filename).startswith("pool/main/m/microsoft-edge-stable/"):
        raise SystemExit("Microsoft Edge package path is unsafe")
    match = re.fullmatch(r"([0-9]+)(?:\.([0-9]+)){3}-([0-9]+)", fields["Version"])
    if match is None:
        raise SystemExit("Microsoft Edge package version is invalid")
    if not re.fullmatch(r"[0-9a-f]{64}", fields["SHA256"]):
        raise SystemExit("Microsoft Edge package digest is invalid")
    if not fields["Size"].isdigit() or not 10_000_000 <= int(fields["Size"]) <= 500_000_000:
        raise SystemExit("Microsoft Edge package size is invalid")
    numeric = tuple(int(part) for part in fields["Version"].rsplit("-", 1)[0].split("."))
    rows.append((numeric, fields))

if not rows:
    raise SystemExit("microsoft-edge-stable package was not found")
majors = sorted({numeric[0] for numeric, _ in rows}, reverse=True)
track = sys.argv[2]
if track == "previous" and len(majors) < 2:
    raise SystemExit("Microsoft Edge repository does not retain the previous major")
selected_major = majors[0] if track == "current" else majors[1]
_, selected = max(row for row in rows if row[0][0] == selected_major)
print(selected["Version"])
print(selected["Filename"])
print(selected["Size"])
print(selected["SHA256"])
PY
)
[[ ${#package_metadata[@]} -eq 4 ]] || {
  echo "Microsoft Edge package metadata parsing failed" >&2
  exit 1
}
version=${package_metadata[0]}
package_path=${package_metadata[1]}
package_size=${package_metadata[2]}
package_sha256=${package_metadata[3]}
release_root="$cache_root/releases/$version"
edge_executable="$release_root/opt/microsoft/msedge/msedge"

if [[ ! -x "$edge_executable" ]]; then
  curl "${curl_args[@]}" "$repository_origin/$package_path" --output "$workspace/microsoft-edge.deb"
  [[ "$(stat -c %s "$workspace/microsoft-edge.deb")" == "$package_size" ]] || {
    echo "Microsoft Edge package size validation failed" >&2
    exit 1
  }
  [[ "$(sha256sum "$workspace/microsoft-edge.deb" | awk '{print $1}')" == "$package_sha256" ]] || {
    echo "Microsoft Edge package digest validation failed" >&2
    exit 1
  }
  dpkg-deb --extract "$workspace/microsoft-edge.deb" "$workspace/release"
  [[ -x "$workspace/release/opt/microsoft/msedge/msedge" ]] || {
    echo "Microsoft Edge package did not contain the expected executable" >&2
    exit 1
  }
  [[ ! -e "$release_root" && ! -L "$release_root" ]] || {
    echo "refusing to replace an existing incomplete Edge release: $release_root" >&2
    exit 1
  }
  mv "$workspace/release" "$release_root"
fi

reported_version=$($edge_executable --version)
while [[ "$reported_version" == *[[:space:]] ]]; do
  reported_version=${reported_version%?}
done
[[ "$reported_version" == "Microsoft Edge ${version%-*}" || "$reported_version" == "Microsoft Edge ${version%-*} unknown" ]] || {
  echo "Microsoft Edge executable version does not match signed repository metadata" >&2
  exit 1
}
track_partial="$cache_root/$track.partial.$$"
printf '%s\n' "$version" > "$track_partial"
chmod 0600 "$track_partial"
mv -f "$track_partial" "$cache_root/$track"

printf 'edge_track=%s\n' "$track"
printf 'edge_executable=%s\n' "$edge_executable"
printf 'edge_version=%s\n' "${version%-*}"
