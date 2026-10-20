#!/usr/bin/env bash
# stage.sh DEST PREFIX: copies the smoothie-sim tree and command to DEST/PREFIX/{bin,share/smoothie-sim}.
# Single source of the install layout, shared by the tarball, deb, rpm and container image.
set -euo pipefail
[ $# -eq 2 ] || { echo "usage: stage.sh DEST PREFIX" >&2; exit 2; }
ROOT=$(cd "$(dirname "$0")/.." && pwd)
TARGET="$1/$2"
SHARE="$TARGET/share/smoothie-sim"
mkdir -p "$TARGET/bin" "$SHARE"
install -m 755 "$ROOT/packaging/smoothie-sim" "$TARGET/bin/smoothie-sim"
for item in Makefile run_checks.sh rules.json VERSION LICENSE README.md CHANGELOG.md checkers sim shim overlay tools cases documentation; do
  cp -r "$ROOT/$item" "$SHARE/"
done
find "$SHARE" -name __pycache__ -prune -exec rm -rf {} +
chmod -R go-w "$SHARE"
