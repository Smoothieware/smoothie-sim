#!/usr/bin/env bash
# release-notes.sh VERSION: prints the CHANGELOG.md section of that version (without its heading).
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
awk -v v="$1" '
  /^## \[/ { if (on) exit; on = index($0, "## [" v "]") == 1; next }
  on { print }' "$ROOT/CHANGELOG.md" | sed -e :a -e '/^\n*$/{$d;N;ba' -e '}'
