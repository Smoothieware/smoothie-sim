# Limits

- Step timing is simulated at a 10 us tick and is approximate. Real interrupt latency is not modelled. The step and slow timers are served in time order, ties by NVIC priority (default); `--fixed-tick` (or `SMOOTHIE_SIM_ARGS=--fixed-tick` for the checkers) restores the old order of all step ticks of a millisecond first. Both gave identical results on every case and on the 8 replayed PRs (`tools/compare_dispatch.py`).
- Not simulated: SD card, USB, network, laser, panel and spindle hardware. Their modules are loaded with stubbed hardware (PWM, SPI, SD slot, LCD), so their handlers run but not their electrical behaviour.
- The module workload loads the event-registering modules (the coverage table in the report shows how much of each handler ran). The console `version` command is left out: it crashes the simulator.
- No golden case exists yet for delta or SCARA kinematics.
- `safe_delay_us` is recorded at runtime through a stage patch, so `safe_delay_ms` shows up as `ask-maintainer`.
- A wait the workload never reaches is only found by the static scan (PR 1227's delayed enable path was an example before the workload covered it).
- Blocking that is not a wait call (a blocking ADC read, a long `M109`) is only caught by the handler-duration check, and only if the workload runs it.
- Race mode is an interleaving explorer, not cycle-accurate timing.
- The size check parses `arm-none-eabi-size` output; it was validated on real ARM firmware ELF files, and on sample size files.
- The size check counts static RAM only. Heap use comes from the separate RAM model (`checkers/memory_check.py`), which needs a layout file made from a real ARM build; without one the report says "not measured".
- The RAM model is an estimate. Allocations are replayed on a first-fit model of the newlib heap and of Smoothieware's AHB0 pool, but the simulator allocates with host (64-bit) sizes. A size is converted to its ARM size only when the calling function names a class whose host size matches; every other allocation keeps its host size and the report counts them. Allocations that the simulator makes for its own recordings are recognised by their call stack and element types and left out. The stack depth is not measured: the report gives the room between the highest heap address and the stack limit, not the stack use. Heap shortages are therefore warnings, not failures.
- The feature checkers (`advance_check.py`, `backlash_check.py`) only apply to firmware trees that have the feature. They pass on the pressure-advance development branch of Smoothieware; they cannot run on plain `edge`.
