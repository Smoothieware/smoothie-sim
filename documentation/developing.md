# Developing

## Layout

| Path | Content |
| --- | --- |
| `Makefile` | Builds the simulator from a firmware checkout. |
| `run_checks.sh` | Runs the checkers and the report. |
| `sim/` | Simulator runtime (x86). |
| `shim/` | Host replacements for mbed / LPC17xx / CMSIS headers. |
| `overlay/` | Firmware files replaced in the staged copy. |
| `tools/` | Stage patches (`stage_patch.py`, `stage_patch_race.py`) and the old-PR replay scripts. |
| `checkers/` | The checkers and the report generator. |
| `cases/` | Configs, G-code workloads, replay cases, size samples. |
| `rules.json` | The [wait rules](wait-rules.md). |
| `documentation/` | Published documentation (this folder). |
| `docs/` | Local notes; not committed (see `.gitignore`). |

## Add a stage patch

Append `(relative_path, old_text, new_text)` to `PATCHES` in `tools/stage_patch.py`. `old_text` must occur exactly once in the firmware file. Prefer inserting a call to a hook declared in `shim/sim_hooks.h`
over changing logic. When upstream moves the code, the build fails with the pattern and its count: update the pattern.

## Add a checker

1. Create `checkers/<name>.py` using `Result` and `write_result` from `checkers/common.py`; print JSONL summary lines; exit non-zero on failure.
2. Call it from `run_checks.sh` and give `report.py` a section for its result file.
3. Document it in [Checkers](checkers.md) and add an entry to `CHANGELOG.md`.

## Add a replay case

Add `cases/pr-replay/<PR>/config.extra` and `workload.gcode`, an entry in `expected.json` and `evidence.json`, and a row in `RESULTS.md`. Run `tools/regress_prs.py OUT --firmware FW --prs <PR>`.

## Test your change

```sh
make -j"$(nproc)"
./run_checks.sh build/edge/smoothie-sim /path/to/Smoothieware - out/edge
tools/regress_prs.py out/replay --firmware /path/to/Smoothieware   # needs gh; rebuilds eight simulators
```
