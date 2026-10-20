# Getting started

## Requirements

- Linux, `g++` with GNU C++14 support, `make` and `python3` 3. It is developed and tested on Linux with Python 3.11; the checkers use only the Python standard library. The CI workflow targets Ubuntu 22.04 but has not run yet.
- A checkout of [Smoothieware](https://github.com/Smoothieware/Smoothieware) (the firmware under test). It is never modified.
- Optional: `gcc-arm-none-eabi` and `binutils-arm-none-eabi` for the RAM and flash check (`size_check.py`); `gh` for the old-PR replay.

## Build the simulator

```sh
make -j"$(nproc)"
```

With no `SMOOTHIE_SRC`, the first run downloads the `edge` branch of Smoothieware into `fw/` with `git clone --depth 1` (override with `SMOOTHIE_REPO` and `SMOOTHIE_BRANCH`); later runs reuse `fw/`, so run `git -C fw pull` to update it. To use your own checkout instead: `make SMOOTHIE_SRC=/path/to/Smoothieware BUILD=build/mine`.

`BUILD` is the output folder (default `build`); the binary is `BUILD/smoothie-sim`. The firmware `src/` is copied to `BUILD/stage`, the overlay and
stage patches are applied to the copy, and the result is compiled. Build options:

| Variable | Default | Meaning |
| --- | --- | --- |
| `SMOOTHIE_SRC` | `fw/` | Smoothieware checkout. When unset and `fw/` is empty, the `edge` branch is cloned there. |
| `SMOOTHIE_REPO`, `SMOOTHIE_BRANCH` | upstream, `edge` | What the default clone fetches. |
| `BUILD` | `build` | Output folder. |
| `COVERAGE` | `1` | Build with gcov counters so the modules checker can tell which handler lines the workload ran. |
| `RACE` | `0` | `1` builds [race mode](race-mode.md). |
| `AXIS` | `5` | Number of actuators (`MAX_ROBOT_ACTUATORS`). |
| `NOFLAGS` | `-DNONETWORK` | `-D` flags that remove modules needing hardware the simulator cannot fake. |
| `EXTRA` | empty | Extra compiler flags. |
| `EXTRA_FILES` | empty | Space-separated files outside `src/` (for example `mbed/src/cpp/SWSPI.cpp`) that a PR changes; they are staged under `src/extra/`. |

The simulator adapts to the firmware's `Block` layout: if the firmware's `Block.h` has per-motor axis records (`is_active`), `-DSIM_SPARSE_BLOCKS` is set automatically.

## Run the checkers

```sh
./run_checks.sh [BUILD/smoothie-sim [FIRMWARE_SRC [BASE_SRC_OR_- [OUTDIR [REF_ELF CAND_ELF]]]]]
```

Set `BASE_SIM` to a simulator built from the base tree to also separate runtime findings (waits, long handlers) that the base shows too. Findings the base already has are collapsed in the report and do not count towards its result.

File names in the report link to the file on GitHub. `run_checks.sh` takes the link target from the firmware tree's git `origin` and current commit; set `SOURCE_URL=https://github.com/OWNER/REPO/blob/REV/{path}` to point elsewhere, or when the tree is not a git checkout (then the names are plain text).

Every argument is optional and defaults to what plain `make` builds: `build/smoothie-sim`, `fw`, `-`, `out`.

| Argument | Meaning |
| --- | --- |
| `BUILD/smoothie-sim` | The simulator binary. |
| `/path/to/Smoothieware` | The firmware tree under test (scanned statically by the modules checker). |
| `BASE_SRC_OR_-` | Reference tree, normally the firmware a pull request is based on. Only blocking calls that are new compared with it fail; old ones are not held against the change. `-` skips the comparison: every existing blocking call is then listed as a warning and none fail (the example report is made this way). |
| `OUTDIR` | Output folder for results and report. |
| `REF_ELF CAND_ELF` | Optional reference and candidate firmware ELF files; enable the RAM and flash check. |

Environment: `REPLAY=path/to/regress.json` adds the old-PR table to the report; `SIZE_TOOL_PREFIX` sets the binutils prefix (default `arm-none-eabi-`, empty uses the host binutils, which read ARM ELF files); `SUBJECT` and `RUN_URL` label the report.

The script runs the G-code to blocks, G-code to steps and modules checkers, the size check when ELF files are given, and writes:

| File | Content |
| --- | --- |
| `report.html` | Toolpath, speed profile, steps per block, per-checker tables. Open in a browser. |
| `summary.md` | Short table in Markdown, for a job summary. |
| `comment.md` | Text suitable for a PR comment. |
| `*.result.json` | Machine-readable result of each checker. |

The exit status is non-zero if any checker failed. Warnings do not fail the run.

![Example report](../assets/report-example.png)

Example: check a PR branch against `edge`.

```sh
make -j"$(nproc)" SMOOTHIE_SRC=$PWD/fw BUILD=build/pr
./run_checks.sh build/pr/smoothie-sim $PWD/fw $PWD/base out/pr
```
