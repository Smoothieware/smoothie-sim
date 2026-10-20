# How it works

## Staging

The firmware is never edited. `make` copies `SMOOTHIE_SRC/src` to `BUILD/stage/src`, then:

1. lays `overlay/` over the copy (simulator replacements of firmware files that only make sense on the MCU: `MemoryPool`, `MRI_Hooks.h`, `SDFAT.h`, the file config source, `sLPC17xx.h`);
2. copies `EXTRA_FILES` to `src/extra/`;
3. runs `tools/stage_patch.py` on the copy, and `tools/stage_patch_race.py` when `RACE=1`.

Every stage patch is an exact-text replacement that must match **exactly once**. If upstream code moved, staging fails with the pattern and its count
instead of silently running an un-instrumented firmware.

## Host shims

`shim/` provides the headers the firmware includes for the LPC17xx and mbed (`mbed.h`, `LPC17xx.h`, `cmsis.h`, `PinNames.h`, the `lpc17xx_*.h` drivers, ...).
They map GPIO, timers, UART, SPI, I2C and PWM onto a software model in `sim/sim_hw.cpp`, so the unmodified firmware code compiles with `g++` on x86.
`shim/sim_hooks.h` declares the hooks the stage patches insert; `shim/sim_force.h` is force-included in every translation unit.

## What is compiled

All of `src/` except directories that need hardware or are replaced (USB, networking, ChaNFS, ADC driver, watchdog, `main.cpp`, play LED, the 3D-printer panel screens, test framework).
The real Kernel, Robot, Planner, Conveyor, StepTicker, G-code dispatch and modules run unchanged.

## Simulator runtime (`sim/`)

| File | Role |
| --- | --- |
| `sim_main.cpp` | Entry point. Fake clock, machine ticking (step ticker at a 10 us period), serial G-code input, capture of planner blocks and step pulses, handler timing, JSON output. |
| `sim_hw.cpp` | Software model of GPIO ports, timers and the other peripherals the shims expose. |
| `sim_modules.cpp` | Loads the modules for the module workload and implements the block injector used by `blocks_to_steps.py`. |
| `sim_runtime.h` | Shared state (`BlockRec`, `SimState`). |
| `sim_stubs.cpp` | Link stubs for symbols the excluded code would have provided. |

The simulator's command line is internal: the checkers in `checkers/` are the supported interface. They start the simulator with a config file and G-code, read its JSON (blocks, steps, waits, handler timings, coverage) and judge it.

## Check pipeline

```
G-code ──► smoothie-sim ──► blocks JSON ──► gcode_to_blocks.py   (planner invariants)
                │                │
                │                └────────► blocks_to_steps.py   (inject blocks into the real StepTicker)
                └──► waits, handler times ─► modules_check.py    (+ static scan of the source)
firmware ELFs ───────────────────────────► size_check.py
all result JSON ─────────────────────────► report.py ──► report.html, summary.md, comment.md
```
