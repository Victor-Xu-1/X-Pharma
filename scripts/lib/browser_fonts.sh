#!/usr/bin/env bash

BROWSER_FONT_PACKAGE=fonts-noto-cjk
BROWSER_FONT_VERSION=1:20230817+repack1-3

verify_browser_fonts() {
  command -v fc-match >/dev/null 2>&1 || {
    echo 'Browser acceptance requires fontconfig and the project Noto CJK font profile' >&2
    return 1
  }
  local family resolved
  for family in 'Noto Sans CJK SC' 'Noto Serif CJK SC'; do
    resolved=$(fc-match --format='%{family}' "$family") || return 1
    if [[ "$resolved" != *"$family"* ]]; then
      printf 'Required browser font is missing: %s. Install %s=%s before capturing baselines.\n' \
        "$family" "$BROWSER_FONT_PACKAGE" "$BROWSER_FONT_VERSION" >&2
      return 1
    fi
  done
}
