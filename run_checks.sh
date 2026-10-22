#!/usr/bin/env bash
# Runs the simulator checkers against one firmware tree and writes the report.
#   run_checks.sh [SIM_BINARY [FIRMWARE_SRC [BASE_SRC [OUTDIR [REF_ELF CAND_ELF]]]]]
# Defaults (what plain `make` builds): build/smoothie-sim, fw, -, out.
# Env: BASE_SIM=simulator built from BASE_SRC (runtime findings it also shows are listed as existing, collapsed), REPLAY=path of regress.json (adds the old-PR table), SIZE_TOOL_PREFIX (default arm-none-eabi-; empty uses the host binutils).
# LPC_LAYOUT=memory layout JSON from tools/lpc_memory_layout.py (needs an ARM build) turns on the heap/AHB model; without it the report says "not measured".
# SOURCE_URL=https://github.com/OWNER/REPO/blob/REV/{path} sets where file links in the report point (default: the firmware tree's git origin and commit).
# BASE_SRC may be "-" to skip the new-vs-base static comparison. REF_ELF/CAND_ELF enable the RAM/flash check.
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
SIM=${1:-$HERE/build/smoothie-sim}; SRC=${2:-$HERE/fw}; BASE=${3:--}; OUT=${4:-$HERE/out}; REF_ELF=${5:-}; CAND_ELF=${6:-}
HERE=$(cd "$(dirname "$0")" && pwd); C=$HERE/cases; mkdir -p "$OUT"; rc=0
python3 "$HERE/checkers/gcode_to_blocks.py" --sim "$SIM" --config "$C/cartesian/config.txt" --gcode "$C/cartesian/square.gcode" --workdir "$OUT/w1" --cartesian --out "$OUT/gcode_to_blocks.result.json" || rc=1
python3 "$HERE/checkers/blocks_to_steps.py" --sim "$SIM" --config "$C/cartesian/config.txt" --gcode "$C/cartesian/square.gcode" --workdir "$OUT/w2" --out "$OUT/gcode_to_steps.result.json" || rc=1
BASEARG=(); [ "$BASE" != "-" ] && BASEARG=(--base-src "$BASE")
BASESIMARG=(); [ -n "${BASE_SIM:-}" ] && BASESIMARG=(--base-sim "$BASE_SIM")
python3 "$HERE/checkers/modules_check.py" --sim "$SIM" --src "$SRC" "${BASEARG[@]}" "${BASESIMARG[@]}" --config "$C/modules/config.txt" --workload "$C/modules/workload.gcode" --extra-run "$C/modules/panel-config.txt" "$C/modules/panel-workload.gcode" --motion "$C/cartesian/square.gcode" "$C/cartesian/mixed.gcode" --workdir "$OUT/w3" --out "$OUT/modules.result.json" || rc=1
python3 "$HERE/checkers/fault_check.py" --sim "$SIM" --config "$C/modules/config.txt" --workdir "$OUT/w5" --out "$OUT/faults.result.json" || rc=1
python3 "$HERE/checkers/memory_check.py" --sim "$SIM" --config "$C/modules/config.txt" --gcode "$C/modules/workload.gcode" ${LPC_LAYOUT:+--layout "$LPC_LAYOUT"} --workdir "$OUT/w4" --out "$OUT/memory.result.json" || rc=1
SIZEARG=(); REPLAYARG=(); [ -n "${REPLAY:-}" ] && REPLAYARG=(--replay "$REPLAY")   # REPLAY = regress.json from tools/regress_prs.py
if [ -n "$REF_ELF" ] && [ -n "$CAND_ELF" ]; then
  python3 "$HERE/checkers/size_check.py" --ref-elf "$REF_ELF" --cand-elf "$CAND_ELF" --tool-prefix "${SIZE_TOOL_PREFIX-arm-none-eabi-}" --out "$OUT/size.result.json" || rc=1
  SIZEARG=(--size "$OUT/size.result.json")
fi
# File links in the report: SOURCE_URL (template with {path}) or, when the firmware tree is a git checkout of a GitHub repo, a link pinned to its commit.
SRCURLARG=()
if [ -n "${SOURCE_URL:-}" ]; then SRCURLARG=(--source-url "$SOURCE_URL")
elif REMOTE=$(git -C "$SRC" remote get-url origin 2>/dev/null) && REV=$(git -C "$SRC" rev-parse HEAD 2>/dev/null); then
  SLUG=$(printf '%s' "$REMOTE" | sed -E 's#^(git@github\.com:|https://github\.com/)##; s#\.git$##')
  case "$REMOTE" in *github.com*) SRCURLARG=(--source-url "https://github.com/$SLUG/blob/$REV/{path}" --subject-link "https://github.com/$SLUG/tree/$REV");; esac
fi
python3 "$HERE/checkers/report.py" "${SRCURLARG[@]}" --results "$OUT"/gcode_to_blocks.result.json "$OUT"/gcode_to_steps.result.json "$OUT"/modules.result.json "$OUT"/memory.result.json "$OUT"/faults.result.json "${SIZEARG[@]}" "${REPLAYARG[@]}" \
  --sim-json "$OUT/w1/gcode_to_blocks.json" --subject "${SUBJECT:-}" --run-url "${RUN_URL:-}" \
  --html "$OUT/report.html" --summary-md "$OUT/summary.md" --comment-md "$OUT/comment.md"
exit $rc
