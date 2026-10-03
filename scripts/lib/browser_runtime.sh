#!/usr/bin/env bash

# One runtime resolver, called before fixtures. Inputs belong to the parent
# runner; outputs keep its existing Chrome/Edge/Windows invocation contract.
resolve_browser_runtime() {
  local browser_version_pattern chrome_cache release_file browser_release unavailable_message edge_track edge_cache
  browser_executable=${E2E_BROWSER_EXECUTABLE:-${E2E_CHROME_EXECUTABLE:-}}
  browser_channel=chrome
  browser_product="Google Chrome"
  browser_version_pattern='^Google Chrome [0-9]+([.][0-9]+){3}$'
  if [[ $browser_target == chrome ]]; then
    if [[ -z "$browser_executable" ]] && command -v google-chrome >/dev/null 2>&1; then
      browser_executable=$(command -v google-chrome)
    fi
    if [[ -z "$browser_executable" ]]; then
      chrome_cache=${PHARMA_CHROME_CACHE_DIR:-"$HOME/.cache/pharma-intelligence/google-chrome"}
      release_file="$chrome_cache/current"
      if [[ -f "$release_file" && ! -L "$release_file" ]]; then
        browser_release=$(<"$release_file")
        [[ "$browser_release" =~ ^[0-9]+([.][0-9]+){3}-[0-9]+$ ]] || {
          echo "user-level Google Chrome current release is invalid" >&2
          return 1
        }
        browser_executable="$chrome_cache/releases/$browser_release/opt/google/chrome/google-chrome"
      fi
    fi
    unavailable_message="Google Chrome is unavailable; run ./scripts/bootstrap-wsl-chrome.sh"
  else
    browser_channel=msedge
    browser_product="Microsoft Edge"
    browser_version_pattern='^Microsoft Edge [0-9]+([.][0-9]+){3}( unknown)?$'
    edge_track=${browser_target#edge-}
    edge_cache=${PHARMA_EDGE_CACHE_DIR:-"$HOME/.cache/pharma-intelligence/microsoft-edge"}
    release_file="$edge_cache/$edge_track"
    if [[ -z "$browser_executable" && -f "$release_file" && ! -L "$release_file" ]]; then
      browser_release=$(<"$release_file")
      [[ "$browser_release" =~ ^[0-9]+([.][0-9]+){3}-[0-9]+$ ]] || {
        echo "user-level Microsoft Edge $edge_track release is invalid" >&2
        return 1
      }
      browser_executable="$edge_cache/releases/$browser_release/opt/microsoft/msedge/msedge"
    fi
    unavailable_message="Microsoft Edge $edge_track is unavailable; run ./scripts/bootstrap-wsl-edge.sh --track $edge_track"
  fi
  [[ -n "$browser_executable" && "$browser_executable" = /* && -x "$browser_executable" ]] || {
    echo "$unavailable_message" >&2
    return 1
  }
  browser_executable=$(realpath "$browser_executable")
  browser_launch_executable="$browser_executable"
  if [[ -n "${MSYSTEM:-}" && -x "$(command -v cygpath || true)" ]]; then
    browser_launch_executable=$(cygpath -w "$browser_executable")
    browser_version="${browser_product} $(powershell.exe -NoProfile -Command "(Get-Item -LiteralPath '$browser_launch_executable').VersionInfo.ProductVersion" | tr -d '\r\n')"
  else
    browser_version=$("$browser_executable" --version)
  fi
  while [[ "$browser_version" == *[[:space:]] ]]; do
    browser_version=${browser_version%?}
  done
  [[ "$browser_version" =~ $browser_version_pattern ]] || {
    echo "$browser_product returned an invalid version string: $browser_version" >&2
    return 1
  }
  browser_version=${browser_version% unknown}
  expected_browser_version=${browser_version#"$browser_product "}
}

verify_browser_visual_profile() {
  local profile_args=(--browser "$browser_version" --target "$browser_target")
  if [[ "$update_snapshots" == true ]]; then profile_args+=(--review-update); fi
  python3 -m scripts.browser_visual_profile "${profile_args[@]}"
}
