# Race mode (`RACE=1`)

```sh
make RACE=1 -j"$(nproc)" SMOOTHIE_SRC=/path/to/Smoothieware BUILD=build/race
```

Builds a simulator in which the step interrupt can preempt the firmware inside a flag write. `tools/stage_patch_race.py` rebuilds the `Block` flag byte of the tree under test
(old or fixed layout, read from that tree's own `Block.h`) from `SimBit` proxies (`shim/sim_race.h`). Each write is load, preempt point, store, as on the Cortex-M3.
At a preempt point the real `StepTicker::step_tick` runs (real Conveyor fetch, real Block code).

Options:

- `--race-window-us W`: run a tick that is due within W us of the write.
- `--race-force-every N`: fire a tick at every Nth flag write (the machine runs ahead of the planner: the starved-queue worst case).

At exit the simulator prints `SIM_RACE ...`: stores that overwrote another context's flag change (per bit; bit 5 is `is_ticking` in the old layout) and
`replans_of_running_block` (`calculate_trapezoid` entered for a block the ISR started but whose `is_ticking` reads false).

Workloads: `cases/race/raster.gcode`, `cases/race/fine_raster.gcode` (2000 tiny moves).
Limit: firing is an interleaving explorer, not cycle-accurate timing.
