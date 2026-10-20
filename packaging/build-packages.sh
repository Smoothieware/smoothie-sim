#!/usr/bin/env bash
# build-packages.sh OUTDIR: writes smoothie-sim-<version>.tar.gz, smoothie-sim_<version>_all.deb,
# smoothie-sim-<version>-1.noarch.rpm and SHA256SUMS to OUTDIR. Needs dpkg-deb and rpmbuild.
# The package contents are architecture independent: the simulator is compiled on the user's machine.
set -euo pipefail
[ $# -eq 1 ] || { echo "usage: build-packages.sh OUTDIR" >&2; exit 2; }
ROOT=$(cd "$(dirname "$0")/.." && pwd)
VERSION=$(tr -d '[:space:]' < "$ROOT/VERSION")
OUT=$(mkdir -p "$1" && cd "$1" && pwd)
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
EPOCH=$(git -C "$ROOT" log -1 --format=%ct 2>/dev/null || date +%s)
DEPENDS_DEB="g++, make, python3, git, ca-certificates"
URL=https://github.com/Smoothieware/smoothie-sim
SUMMARY="Run the real Smoothieware firmware core on a PC and check G-code, planning and memory behaviour"

# Tarball: <name>/{bin,share/smoothie-sim}, consumed by packaging/install.sh.
"$ROOT/packaging/stage.sh" "$WORK/tar/smoothie-sim-$VERSION" ""
tar --sort=name --owner=0 --group=0 --numeric-owner --mtime="@$EPOCH" -C "$WORK/tar" -czf "$OUT/smoothie-sim-$VERSION.tar.gz" "smoothie-sim-$VERSION"

# deb
D="$WORK/deb"
"$ROOT/packaging/stage.sh" "$D" /usr
install -d "$D/DEBIAN" "$D/usr/share/doc/smoothie-sim"
install -m 644 "$ROOT/LICENSE" "$D/usr/share/doc/smoothie-sim/copyright"
cat > "$D/DEBIAN/control" <<CONTROL
Package: smoothie-sim
Version: $VERSION
Section: devel
Priority: optional
Architecture: all
Depends: $DEPENDS_DEB
Recommends: binutils-arm-none-eabi
Maintainer: Smoothieware contributors <$URL>
Homepage: $URL
Description: $SUMMARY
 smoothie-sim compiles the real Smoothieware Kernel, Robot, Planner, Conveyor,
 StepTicker and G-code dispatch for the PC, then runs checkers over the result.
 The simulator is built on this machine with 'smoothie-sim build'.
CONTROL
dpkg-deb --root-owner-group -Zxz --build "$D" "$OUT/smoothie-sim_${VERSION}_all.deb" >/dev/null

# rpm
R="$WORK/rpm"
mkdir -p "$R"/{BUILD,RPMS,SRPMS,SPECS,BUILDROOT}
"$ROOT/packaging/stage.sh" "$WORK/rpmroot" /usr
cat > "$R/SPECS/smoothie-sim.spec" <<SPEC
Name: smoothie-sim
Version: $VERSION
Release: 1
Summary: $SUMMARY
License: GPL-2.0-or-later
URL: $URL
BuildArch: noarch
AutoReqProv: no
Requires: gcc-c++, make, python3, git, ca-certificates
%global debug_package %{nil}
%description
smoothie-sim compiles the real Smoothieware Kernel, Robot, Planner, Conveyor,
StepTicker and G-code dispatch for the PC, then runs checkers over the result.
The simulator is built on this machine with 'smoothie-sim build'.
%install
mkdir -p %{buildroot}/usr
cp -a $WORK/rpmroot/usr/. %{buildroot}/usr/
%files
/usr/bin/smoothie-sim
/usr/share/smoothie-sim
SPEC
rpmbuild -bb --quiet --define "_topdir $R" --define "_buildhost localhost" --define "source_date_epoch_from_changelog 0" "$R/SPECS/smoothie-sim.spec"
cp "$R"/RPMS/noarch/*.rpm "$OUT/"

(cd "$OUT" && sha256sum smoothie-sim-"$VERSION".tar.gz smoothie-sim_"${VERSION}"_all.deb smoothie-sim-"$VERSION"-1.noarch.rpm > SHA256SUMS)
ls -l "$OUT"
