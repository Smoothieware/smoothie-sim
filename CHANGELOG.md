# Changelog

## [Unreleased]

### Added
- README: one-line dependency install commands for nine Linux distributions, and the easily missed assumptions (GCC with a matching `gcov`, bash, GNU userland, network at first build, `patch` and `gh` for the PR replay).

## [0.1.0] - 2026-10-20

### Fixed
- The simulator no longer crashes on any console message of 64 characters or more (the module workload died on `M115`): upstream `StreamOutput::printf` reuses a consumed `va_list`, which is harmless on ARM but undefined on x86-64. A stage patch now gives the second `vsnprintf` its own copy.

### Added (releases and packages)
- Every `v*` tag publishes a GitHub release through `.github/workflows/release.yml`: `smoothie-sim-VERSION.tar.gz`, a `.deb`, an `.rpm`, `install.sh` and `SHA256SUMS`, plus a multi-architecture container image `ghcr.io/smoothieware/smoothie-sim` (amd64 and arm64). Pushes to `main` and pull requests run the same packaging and a full build-and-check smoke test without publishing.
- The new `smoothie-sim` command (`packaging/smoothie-sim`) wraps the installed tree: `smoothie-sim build` builds `./build/smoothie-sim` from a cached shallow clone of Smoothieware `edge` (or `SMOOTHIE_SRC`), `smoothie-sim check` runs the checkers and writes `./out/report.html`.
- `VERSION` file, `Dockerfile`, and `packaging/` scripts (`stage.sh` is the single install layout, `build-packages.sh`, `install.sh`, `release-notes.sh`). See [Installation](documentation/installation.md).
- Linux only. macOS is not supported: the firmware core is built with GNU g++ flags and gcov, which have not been tried with Apple's compiler.

### Added (module coverage stimuli)
- Workload stimulus lines: a `;@sim` comment in a workload G-code file is read by the simulator instead of the firmware. `pin <port.pin> <0|1>` sets the level of an input pin (panel buttons, SD card detect, bulge sensor), `pulses <port.pin> <count>` delivers rising edges to an interrupt pin (the `InterruptIn` shim now keeps the firmware's handler), `adc <raw>` changes the thermistor reading, `wait <ms>` lets simulated time pass with the main loop and idle running (second ticks, button polling).
- The modules case now enters the handlers the report listed as never run or partly run: `FilamentDetector::on_pin_rise` and the M404 to M407 and M601 paths, jam and bulge alarms; `TemperatureSwitch::on_gcode_received` (new armed switch with `arm_mcode`) and its heat-up branch; `MotorDriverControl` second tick and the M906 to M911 sub-codes; `Panel` select, back, up, down, second tick (external SD) and the public-data message. With this, all 24 event-registering module files are fully exercised.
- `modules_check.py --extra-run CONFIG WORKLOAD` (repeatable) runs another workload with its own config and merges its counters; used for a second panel type (`cases/modules/panel-config.txt`), because the up and down buttons only exist on the plain ST7565 panel and the back button only on the Reprap Discount one.
- `rules.json`: the M600 suspend that the filament detector's jam response starts (`Player::ON_MAIN_LOOP`) is an allowed long handler (it drains the queue with `wait_for_idle`).

### Added (logo)

- smoothie-sim logo (a chip with a pulse line, navy and orange) in `assets/`, at the top of the README, as the report's page icon and in its top bar.

### Changed (report design)
- The HTML report is redesigned as a single self-contained file: hero header with stat cards, sticky navigation with scroll-spy, light/dark theme toggle, Tabler icons (MIT, inlined, no network requests), restyled charts, sortable and filterable tables, copy buttons, and layouts that stack on phone width. Code: `checkers/report.py`, `checkers/report_ui.py`, `checkers/report_coverage.py`.
- Module coverage keeps its table, and gains a summary strip, filters and a "More info" drawer per module: handler functions entered or not with call counts, what each state means, copyable snippets to exercise a module, and links to the source.
- File names and `file:line` locations link to the file on GitHub. `run_checks.sh` pins the links to the firmware tree's git origin and commit; `SOURCE_URL` (a template with `{path}`) or `report.py --source-url` overrides it.

### Added (step traces)
- `checkers/step_trace.py`: `record` turns a simulator result into a compact text step trace (one line per planner block); `compare` checks a trace against a reference, exact for planned steps, emitted step counts, direction bits, direction changes and final positions, with a tolerance for block start, duration and entry/exit speed. Used by smoothie-gate to hold reference traces.

### Changed (reference comparison)
- With a reference tree, the report shows only findings new to the change. Blocking calls in the source, runtime waits and long handlers that the reference firmware already has are kept in collapsed "not caused by this change" sections. Runtime findings need `BASE_SIM`, a simulator built from the reference tree (new `--base-sim` option of `modules_check.py`, `BASE_SIM` variable of `run_checks.sh`).
- The live example report now compares the `pressure-advance` branch with upstream `edge`.

### Changed (defaults)
- With no `SMOOTHIE_SRC`, `make` clones the `edge` branch of the upstream Smoothieware repository into `fw/` (shallow) and builds from it; `SMOOTHIE_REPO` and `SMOOTHIE_BRANCH` override the source. `run_checks.sh` arguments are now optional and default to that build. The README quick start is now `make` then `./run_checks.sh`.
- The modules checker's "no base tree given" message now explains itself.

### Added (publication)
- Live example report at https://smoothie-sim-example.pages.dev/report.html (Smoothieware `edge` branch), linked from the README; `CLAUDE.md` says to keep it updated.
- `LICENSE` (GPL-2.0-or-later; `overlay/` keeps Smoothieware's GPL-3.0-or-later with its own `COPYING`), `CONTRIBUTING.md`, `.gitignore`, `documentation/` (published docs) and an example report image.
- The simulator builds against upstream Smoothieware `edge` again: the per-motor `Block` API (`is_active`/`axis`/`set_active`) is used only when the firmware's `Block.h` has it (`SIM_SPARSE_BLOCKS`, detected by the Makefile).

### Changed (publication)
- `stage_patch.py`, `stage_patch_race.py` and `replay_pr.sh` moved to `tools/`.
- `regress_prs.py` takes `--firmware CHECKOUT`. `replay_pr.sh` uses `JOBS` (default: all CPUs); `make_pr_trees.sh` takes the firmware checkout as a required argument.
- `evidence.json` key `jim` renamed `maintainer_comments`; wording about the maintainer made neutral.
- The GitHub Actions workflow moved out to the smoothie-gate project, which now owns CI and pull-request verification; smoothie-sim stays a self-contained simulator.
- README rewritten as a short front page; details moved to `documentation/`.
- README: jump-link labels match their headings, `Limits` link added, first-run commands explain the `-` argument and the build/output folders, PR-check example says which tree each argument is.

### Changed
- wait_for_idle is now an allowed call (rules.json allowed_calls): never reported statically or at runtime.
- Static scan also covers every file a PR changes (not only src/modules), so waits in src/libs and mbed/ are found.
- Module checker now builds and runs Laser, Spindle, MotorDriverControl and Panel; coverage is 24 of 24 modules.
### Added
- Race mode (RACE=1): step ISR preempts firmware inside Block flag read-modify-writes; options --race-window-us, --race-force-every; stage_patch_race.py, shim/sim_race.h, cases/race/.
- Simulator GPIO ports now remember written pin levels (stage patch on `libs/Pin.h`), so `StepperMotor::is_enabled()` changes and the PR 1227 enable delay is caught at runtime.
- `modules_check.py --static-only` (scan without a simulator, used for old PRs that no longer compile).
- `run_checks.sh` env vars `REPLAY` (add the old-PR replay table to the report) and `SIZE_TOOL_PREFIX` (empty uses host binutils, which read ARM ELF files).
- Report: static hits show function, context and applied rule; "partly exercised" coverage state.
- rules.json is a rules table: every call has a status (forbidden, allowed, ask-maintainer) and a reason; the report names the rule that applied. Short `wait_us` (2 us or less) and `safe_delay_*` are ask-maintainer.
- Static scan reports the function each wait is in and whether it is an event handler / on_idle, startup, or helper; severity follows status and context.
- Handler-duration check now fails (was a warning) unless the handler is on `long_handler_allow` in rules.json, each entry with a written justification.
- Module coverage uses gcov: a module counts as exercised only if every `on_*` handler function was entered; longer workload (`cases/modules/workload.gcode`).
- `EXTRA_FILES` in the Makefile stages files a PR changes outside `src/` (for example mbed/src/cpp/SWSPI.cpp); `replay_pr.sh` passes them.
- PR replay compatibility patch for PR 633 (`cases/pr-replay/633/compat/`) and a synthetic blocking-ADC case standing in for PR 564.
- `tools/regress_prs.py`: regression test replaying the old PRs; `cases/pr-replay/expected.json` records which are runtime-capable. The HTML report has an "Old PR replay" section (`report.py --replay`).
- safe_delay_us is recorded at runtime (stage patch), so safe_delay_ms shows up as ask-maintainer.
- Filament advance (pressure advance): `checkers/advance_check.py` with `cases/filament-advance/`. Runs the real planner and step ticker on a mixed print and a 100 mm move at 500/1000/3000 mm/s^2, and checks net extruder steps, reversals, durations, lead = K x cruise rate and end position. The simulator now also records per-motor direction changes and the advance fields (`advance_lead`, `flip_tick`, `decel_start_adjust`, `advance_motors`) of each block.
- PR replay: cases/pr-replay/ (evidence.json with the maintainer's quotes, per-PR config+workload) and replay_pr.sh, which builds a simulator from an old PR's tree and runs the module checker.
- x86 simulator of the Smoothieware core and modules, built from a copy of the firmware.
- Checkers: G-code to blocks, blocks to steps (and G-code to steps), modules (waits, interference), RAM and flash comparison.
- HTML report, GitHub job summary, optional PR comment, and a manual-dispatch GitHub Actions workflow.

### Fixed
- `size_check.py` ignores linker address markers (e.g. `__end_bss_RAM5`) in the top-symbol table.
- `report.py` no longer crashes on partly exercised modules.
