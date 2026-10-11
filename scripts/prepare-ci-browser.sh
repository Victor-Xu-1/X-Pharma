#!/usr/bin/env bash
set -Eeuo pipefail

# Both mandatory browser jobs consume one reviewed Chrome/font profile.
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
[[ ${GITHUB_ACTIONS:-} == true && ${RUNNER_OS:-} == Linux ]] || {
  echo 'Browser installation is restricted to the ephemeral GitHub Linux runner' >&2
  exit 1
}
: "${RUNNER_TEMP:?RUNNER_TEMP is required}"
: "${GITHUB_ENV:?GITHUB_ENV is required}"
visual_profile_review=${VISUAL_PROFILE_REVIEW:-false}
[[ $visual_profile_review == true || $visual_profile_review == false ]] || {
  echo 'VISUAL_PROFILE_REVIEW must be true or false' >&2
  exit 1
}

sudo --preserve-env=GITHUB_ACTIONS,RUNNER_OS python3 scripts/ci_browser_apt.py
pnpm --dir apps/web exec playwright install-deps chrome
chrome_args=(--reviewed)
profile_args=()
if [[ $visual_profile_review == true ]]; then
  chrome_args=()
  profile_args+=(--review-update)
fi
chrome_output=$(PHARMA_CHROME_CACHE_DIR="$RUNNER_TEMP/x-pharma-chrome" bash scripts/bootstrap-wsl-chrome.sh "${chrome_args[@]}")
chrome_executable=$(printf '%s\n' "$chrome_output" | sed -n 's/^chrome_executable=//p')
test -n "$chrome_executable"
echo "E2E_BROWSER_EXECUTABLE=$chrome_executable" >> "$GITHUB_ENV"
source scripts/lib/browser_fonts.sh
sudo apt-get install --yes --no-install-recommends "$BROWSER_FONT_PACKAGE=$BROWSER_FONT_VERSION"
verify_browser_fonts
uv run --locked python -m scripts.browser_visual_profile --browser "$("$chrome_executable" --version)" "${profile_args[@]}"
