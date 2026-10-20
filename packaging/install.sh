#!/bin/sh
# smoothie-sim installer (Linux): downloads a release tarball, checks it against SHA256SUMS and
# installs it under a prefix (default ~/.local).
#   curl -fsSL https://github.com/Smoothieware/smoothie-sim/releases/latest/download/install.sh | sh
# Env: PREFIX (default $HOME/.local), SMOOTHIE_SIM_VERSION (default: latest release, for example 0.1.0),
#      SMOOTHIE_SIM_ARCHIVE (install this local tarball instead of downloading; no checksum check).
set -eu
REPO=Smoothieware/smoothie-sim
PREFIX=${PREFIX:-$HOME/.local}
die() { echo "smoothie-sim install: $*" >&2; exit 1; }
[ "$(uname -s)" = Linux ] || die "only Linux is supported"
for tool in tar; do command -v "$tool" >/dev/null || die "missing $tool"; done

TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
if [ -n "${SMOOTHIE_SIM_ARCHIVE:-}" ]; then
  ARCHIVE=$SMOOTHIE_SIM_ARCHIVE
else
  command -v curl >/dev/null || die "missing curl"
  VERSION=${SMOOTHIE_SIM_VERSION:-}
  if [ -z "$VERSION" ]; then
    LOCATION=$(curl -fsSLI -o /dev/null -w '%{url_effective}' "https://github.com/$REPO/releases/latest") || die "cannot reach GitHub"
    VERSION=${LOCATION##*/v}
    case "$VERSION" in ''|*/*) die "no release found at https://github.com/$REPO/releases" ;; esac
  fi
  BASE="https://github.com/$REPO/releases/download/v$VERSION"
  NAME="smoothie-sim-$VERSION.tar.gz"
  curl -fsSL -o "$TMP/$NAME" "$BASE/$NAME" || die "cannot download $BASE/$NAME"
  curl -fsSL -o "$TMP/SHA256SUMS" "$BASE/SHA256SUMS" || die "cannot download $BASE/SHA256SUMS"
  (cd "$TMP" && grep " $NAME\$" SHA256SUMS | sha256sum -c - >/dev/null) || die "checksum mismatch for $NAME"
  ARCHIVE=$TMP/$NAME
fi

mkdir "$TMP/x" && tar -xzf "$ARCHIVE" -C "$TMP/x" --strip-components=1
[ -f "$TMP/x/share/smoothie-sim/Makefile" ] || die "unexpected archive layout"
mkdir -p "$PREFIX/bin" "$PREFIX/share"
rm -rf "$PREFIX/share/smoothie-sim"
cp -r "$TMP/x/share/smoothie-sim" "$PREFIX/share/smoothie-sim"
install -m 755 "$TMP/x/bin/smoothie-sim" "$PREFIX/bin/smoothie-sim"
echo "Installed smoothie-sim $(cat "$PREFIX/share/smoothie-sim/VERSION") to $PREFIX"
for tool in g++ make python3 git; do command -v "$tool" >/dev/null || echo "Warning: $tool not found; smoothie-sim build needs g++, make, python3 and git." >&2; done
case ":$PATH:" in *":$PREFIX/bin:"*) ;; *) echo "Add $PREFIX/bin to your PATH to run smoothie-sim." ;; esac
echo "Next: smoothie-sim build && smoothie-sim check"
