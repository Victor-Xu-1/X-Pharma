#!/usr/bin/env bash
set -Eeuo pipefail

umask 077

reviewed=false
case "${1:-}" in
  --reviewed) reviewed=true; shift ;;
  "") ;;
  *) echo 'Usage: bootstrap-wsl-chrome.sh [--reviewed]' >&2; exit 2 ;;
esac
[[ $# -eq 0 ]] || { echo 'Unexpected Chrome bootstrap argument' >&2; exit 2; }
root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)

cache_root=${PHARMA_CHROME_CACHE_DIR:-"$HOME/.cache/pharma-intelligence/google-chrome"}
repository_origin="https://dl.google.com/linux/chrome/deb"
signing_key_url="https://dl.google.com/linux/linux_signing_key.pub"
expected_primary_fingerprint="EB4C1BFD4F042F6DDDCCEC917721F63BD38B4796"

for command in curl dpkg-deb gpg gpgv mktemp mv python3 realpath sha256sum stat; do
  command -v "$command" >/dev/null 2>&1 || {
    echo "required command is unavailable: $command" >&2
    exit 1
  }
done

mkdir -p "$cache_root/releases"
cache_root=$(realpath "$cache_root")
workspace=$(mktemp -d -t pharma-google-chrome.XXXXXX)
export GNUPGHOME="$workspace/gnupg"
mkdir -m 0700 "$GNUPGHOME"
cleanup() {
  status=$?
  trap - EXIT INT TERM
  case "$workspace" in
    "${TMPDIR:-/tmp}"/pharma-google-chrome.*) rm -rf -- "$workspace" ;;
    *) echo "refusing to clean unexpected Chrome workspace: $workspace" >&2 ;;
  esac
  exit "$status"
}
trap cleanup EXIT INT TERM

curl_args=(--fail --silent --show-error --location --proto '=https' --tlsv1.2 --connect-timeout 15 --max-time 300 --retry 2 --retry-all-errors)
if [[ "$reviewed" == true ]]; then
  # Frozen official archive metadata is bound to the reviewed visual manifest.
  # It is not represented as a package in Google's current rolling signed index.
  mapfile -t package_metadata < <(cd "$root" && python3 -m scripts.reviewed_chrome_metadata)
  [[ ${#package_metadata[@]} -eq 5 ]] || {
    echo 'Reviewed Chrome artifact validation failed; no latest fallback is permitted' >&2
    exit 1
  }
else
curl "${curl_args[@]}" "$signing_key_url" --output "$workspace/google-linux-signing-key.pub"
mapfile -t fingerprints < <(
  gpg --batch --show-keys --with-colons "$workspace/google-linux-signing-key.pub" \
    | awk -F: '$1 == "fpr" { print $10 }'
)
[[ " ${fingerprints[*]} " == *" $expected_primary_fingerprint "* ]] || {
  echo "Google Linux signing key primary fingerprint is not trusted" >&2
  exit 1
}
untrusted_keyring="$workspace/google-linux-signing-key.untrusted.gpg"
trusted_keyring="$workspace/google-linux-signing-key.gpg"
gpg --batch --no-default-keyring --keyring "$untrusted_keyring" \
  --import "$workspace/google-linux-signing-key.pub" >/dev/null 2>&1
gpg --batch --no-default-keyring --keyring "$untrusted_keyring" \
  --export "$expected_primary_fingerprint" > "$trusted_keyring"
[[ -s "$trusted_keyring" ]] || {
  echo "Google Linux signing key export failed" >&2
  exit 1
}
mapfile -t trusted_primary_fingerprints < <(
  gpg --batch --show-keys --with-colons "$trusted_keyring" \
    | awk -F: '$1 == "pub" { in_primary = 1; next } $1 == "sub" { in_primary = 0 } $1 == "fpr" && in_primary { print $10; in_primary = 0 }'
)
[[ ${#trusted_primary_fingerprints[@]} -eq 1 && "${trusted_primary_fingerprints[0]}" == "$expected_primary_fingerprint" ]] || {
  echo "trusted Google Linux signing keyring contains an unexpected primary key" >&2
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
  echo "Google Chrome repository metadata omitted the Packages digest" >&2
  exit 1
}
[[ "$(sha256sum "$workspace/Packages" | awk '{print $1}')" == "$published_packages_sha256" ]] || {
  echo "Google Chrome Packages digest validation failed" >&2
  exit 1
}

mapfile -t package_metadata < <(
  python3 - "$workspace/Packages" <<'PY'
from pathlib import Path, PurePosixPath
import re
import sys

required = {"Package", "Version", "Architecture", "Filename", "Size", "SHA256"}
for paragraph in Path(sys.argv[1]).read_text(encoding="utf-8").split("\n\n"):
    fields = {}
    for line in paragraph.splitlines():
        if ": " in line:
            key, value = line.split(": ", 1)
            fields[key] = value
    if fields.get("Package") != "google-chrome-stable":
        continue
    if not required.issubset(fields) or fields["Architecture"] != "amd64":
        raise SystemExit("Google Chrome package metadata is incomplete")
    filename = PurePosixPath(fields["Filename"])
    if filename.is_absolute() or ".." in filename.parts or not str(filename).startswith("pool/main/g/google-chrome-stable/"):
        raise SystemExit("Google Chrome package path is unsafe")
    if not re.fullmatch(r"[0-9]+(?:\.[0-9]+){3}-[0-9]+", fields["Version"]):
        raise SystemExit("Google Chrome package version is invalid")
    if not re.fullmatch(r"[0-9a-f]{64}", fields["SHA256"]):
        raise SystemExit("Google Chrome package digest is invalid")
    if not fields["Size"].isdigit() or not 10_000_000 <= int(fields["Size"]) <= 500_000_000:
        raise SystemExit("Google Chrome package size is invalid")
    print(fields["Version"])
    print(filename)
    print(fields["Size"])
    print(fields["SHA256"])
    break
else:
    raise SystemExit("google-chrome-stable package was not found")
PY
)
[[ ${#package_metadata[@]} -eq 4 ]] || {
  echo "Google Chrome package metadata parsing failed" >&2
  exit 1
}
fi
version=${package_metadata[0]}
package_path=${package_metadata[1]}
package_size=${package_metadata[2]}
package_sha256=${package_metadata[3]}
executable_sha256=${package_metadata[4]:-}
release_root="$cache_root/releases/$version"
chrome_executable="$release_root/opt/google/chrome/google-chrome"

if [[ ! -x "$chrome_executable" ]]; then
  curl "${curl_args[@]}" --max-filesize "$package_size" "$repository_origin/$package_path" --output "$workspace/google-chrome.deb"
  [[ "$(stat -c %s "$workspace/google-chrome.deb")" == "$package_size" ]] || {
    echo "Google Chrome package size validation failed" >&2
    exit 1
  }
  [[ "$(sha256sum "$workspace/google-chrome.deb" | awk '{print $1}')" == "$package_sha256" ]] || {
    echo "Google Chrome package digest validation failed" >&2
    exit 1
  }
  dpkg-deb --extract "$workspace/google-chrome.deb" "$workspace/release"
  [[ -x "$workspace/release/opt/google/chrome/google-chrome" ]] || {
    echo "Google Chrome package did not contain the expected executable" >&2
    exit 1
  }
  [[ ! -e "$release_root" && ! -L "$release_root" ]] || {
    echo "refusing to replace an existing incomplete Chrome release: $release_root" >&2
    exit 1
  }
  mv "$workspace/release" "$release_root"
fi

if [[ -n "$executable_sha256" ]]; then
  [[ "$(sha256sum "$release_root/opt/google/chrome/chrome" | awk '{print $1}')" == "$executable_sha256" ]] || {
    echo 'Reviewed Chrome executable integrity differs from the frozen artifact' >&2
    exit 1
  }
fi

reported_version=$($chrome_executable --version)
while [[ "$reported_version" == *[[:space:]] ]]; do
  reported_version=${reported_version%?}
done
[[ "$reported_version" == "Google Chrome ${version%-*}" ]] || {
  echo "Google Chrome executable version does not match selected validated metadata" >&2
  exit 1
}
current_partial="$cache_root/current.partial.$$"
printf '%s\n' "$version" > "$current_partial"
chmod 0600 "$current_partial"
mv -f "$current_partial" "$cache_root/current"

printf 'chrome_executable=%s\n' "$chrome_executable"
printf 'chrome_version=%s\n' "${version%-*}"
printf 'chrome_package_sha256=%s\n' "$package_sha256"
printf 'chrome_package_size=%s\n' "$package_size"
printf 'chrome_package_path=%s\n' "$package_path"
