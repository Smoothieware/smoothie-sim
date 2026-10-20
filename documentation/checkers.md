# Checkers

All checkers live in `checkers/`, print JSONL (`progress`/`summary` lines) on stdout, write a result JSON (`--out`) and exit non-zero on failure.
`./run_checks.sh` runs the first three, and the size check when ELF files are given.

## 1. `gcode_to_blocks.py`

Feeds G-code through the serial path of the simulator and checks the blocks the planner queues: signed steps add up to the final position,
the end point matches an independent G-code parser, per-block limits (rates, acceleration reach, trapezoid order, junction limit),
continuous junction speeds, rest at start and end.

```sh
checkers/gcode_to_blocks.py --sim BUILD/smoothie-sim --config cases/cartesian/config.txt \
  --gcode cases/cartesian/square.gcode --workdir WORK --cartesian --out OUT.json
```

`--reference blocks.json` compares every block field with a stored run (relative tolerance 1e-4). `--cartesian` enables geometry checks valid for Cartesian kinematics.

## 2. `blocks_to_steps.py`

Writes planned blocks in a text format, injects them into the real StepTicker, and checks per-axis step counts, block duration against the trapezoid time, and rates.
`--blocks blocks.json` takes a blocks file; `--gcode file.gcode` runs G-code to steps in one go.

## 3. `modules_check.py`

Three parts:

- **A. Static scan** of `src/modules` and `src/libs` (plus every file a PR changes) for blocking calls, per [`rules.json`](wait-rules.md). With `--base-src` only calls that are new compared with the base tree fail.
  Each hit shows its function and context (event handler, `on_idle`, startup or helper) and the rule that applied. `--static-only` runs only this part, without a simulator.
- **B. Runtime.** Waits observed while a workload runs with all modules loaded, and a handler-duration check: a handler longer than `runtime_long_handler_us` fails unless it is on the `long_handler_allow` list.
- **C. Interference.** The same motion with and without the modules must give identical blocks and final positions.

`handler_coverage.py` reads gcov counters to report which handler functions the workload really ran. `--workload`, `--config`, `--motion` choose the inputs; `--rules` the rules file. `--extra-run CONFIG WORKLOAD` (repeatable) adds a run with another config, for hardware that one config cannot hold (the second panel type); its counters are merged.

A workload can drive what G-code cannot with comment lines that the simulator reads and the firmware never sees:

| Line | Effect |
|---|---|
| `;@sim pin 1.30 1` | set the level the firmware reads on an input pin (`port.pin`): buttons, card detect, sensors |
| `;@sim pulses 0.26 20` | 20 rising edges on an interrupt pin (what the GPIO interrupt delivers) |
| `;@sim adc 200` | raw 12-bit thermistor reading from now on (lower is hotter) |
| `;@sim wait 3000` | 3000 ms of simulated time with the main loop and idle running (second ticks, button polling) |

## 4. `size_check.py`

Compares flash and RAM of a candidate firmware ELF with a reference ELF (`arm-none-eabi-size -A`, per-symbol growth from `nm`). Options: `--ref-elf`, `--cand-elf`, `--tool-prefix`
(empty uses host binutils), `--max-flash-increase`, `--max-ram-increase`, `--top N`. For tests, pre-captured text can be given with `--ref-size-file`/`--cand-size-file` (see `cases/size/`).
Heap and stack are not static and are not counted.

## 5. Feature checkers (need a firmware tree with the feature)

Not part of `run_checks.sh`; run them directly against a simulator built from a tree that has the feature.

- `advance_check.py` — filament advance (pressure advance): net extruder steps, reversals, durations, lead = K x cruise rate, end position. Input: `cases/filament-advance/`. Needs a 3D-printer build with `FilamentAdvance`.
- `backlash_check.py` — backlash compensation (`M425`): reversal steps, switching off and on, `G92`, invalid values, take-up profile.

## `report.py`

Builds the HTML report, the job summary and the PR comment from the result files: `--results ... --html --summary-md --comment-md`, plus `--size`, `--sim-json` (for the plots), `--subject`, `--run-url`, `--replay`.
