#!/usr/bin/env bash
# Replay one historical PR: build the simulator from the PR's tree, run the module checker with the PR's extra config +
# workload, and write the result. Usage: replay_pr.sh PR TREES_DIR OUT_DIR
# Files the PR changed outside src/ (for example mbed/src/cpp/SWSPI.cpp) are passed to the build as EXTRA_FILES.
# A per-PR compat/port.patch (cases/pr-replay/<PR>/compat/) is applied to a copy of the tree first: it ports a PR written against an
# old firmware API (see cases/pr-replay/633/compat/README.md) without touching the lines the PR is judged on.
set -u
PR=$1; TREES=$2; OUT=$3
HERE=$(cd "$(dirname "$0")/.." && pwd); D=$HERE/cases/pr-replay/$PR
mkdir -p "$OUT/$PR"; TREE=$TREES/$PR
[ -d "$TREE" ] || TREE=$TREES/base   # synthetic case: no tree of its own, the compat patch is applied to a copy of base
if [ -f "$D/compat/port.patch" ]; then
  [ -e "$OUT/$PR/tree" ] || cp -a "$TREE" "$OUT/$PR/tree"; TREE=$OUT/$PR/tree
  ( cd "$TREE" && patch -p1 -s -N -r - --no-backup-if-mismatch < "$D/compat/port.patch" ) > "$OUT/$PR/compat.log" 2>&1 || true
fi
EXTRA=$(python3 -I - "$TREE" "$TREES/base" <<'PY'
import os, sys
t, b = sys.argv[1:3]; out = []
for d, _, fs in os.walk(t):
    for f in fs:
        r = os.path.relpath(os.path.join(d, f), t)
        if r.startswith("src/") or not r.endswith((".cpp", ".c", ".h")): continue
        o = os.path.join(b, r)
        if not os.path.exists(o) or open(o, "rb").read() != open(os.path.join(d, f), "rb").read(): out.append(r)
print(" ".join(sorted(out)))
PY
)
make -C "$HERE" -k -j"${JOBS:-$(nproc)}" SMOOTHIE_SRC="$TREE" BUILD="$OUT/$PR/b" EXTRA_FILES="$EXTRA" > "$OUT/$PR/build.log" 2>&1
SIM=$OUT/$PR/b/smoothie-sim
if [ ! -x "$SIM" ]; then   # PR tree does not build: keep the static result, runtime stays unavailable
  python3 "$HERE/checkers/modules_check.py" --static-only --src "$TREE" --base-src "$TREES/base" --workdir "$OUT/$PR/w" --out "$OUT/$PR/modules.result.json" > "$OUT/$PR/check.log" 2>&1
  echo "exit $? (build failed, static scan only)" > "$OUT/$PR/result.txt"; exit 0
fi
cat "$HERE/cases/modules/config.txt" "$D/config.extra" > "$OUT/$PR/config.txt"
cat "$HERE/cases/modules/workload.gcode" "$D/workload.gcode" > "$OUT/$PR/workload.gcode"
python3 "$HERE/checkers/modules_check.py" --sim "$SIM" --src "$TREE" --base-src "$TREES/base" \
  --config "$OUT/$PR/config.txt" --workload "$OUT/$PR/workload.gcode" --motion "$HERE/cases/cartesian/square.gcode" \
  --workdir "$OUT/$PR/w" --out "$OUT/$PR/modules.result.json" > "$OUT/$PR/check.log" 2>&1
echo "exit $?" > "$OUT/$PR/result.txt"
