# Limits

- Step timing is simulated at a 10 us tick and is approximate. Real interrupt latency is not modelled.
- Not simulated: SD card, USB, network, laser, panel and spindle hardware. Their modules are loaded with stubbed hardware (PWM, SPI, SD slot, LCD), so their handlers run but not their electrical behaviour.
- The module workload loads the event-registering modules (the coverage table in the report shows how much of each handler ran). The console `version` command is left out: it crashes the simulator.
- No golden case exists yet for delta or SCARA kinematics.
- `safe_delay_us` is recorded at runtime through a stage patch, so `safe_delay_ms` shows up as `ask-maintainer`.
- A wait the workload never reaches is only found by the static scan (PR 1227's delayed enable path was an example before the workload covered it).
- Blocking that is not a wait call (a blocking ADC read, a long `M109`) is only caught by the handler-duration check, and only if the workload runs it.
- Race mode is an interleaving explorer, not cycle-accurate timing.
- The size check parses `arm-none-eabi-size` output; it was validated on real ARM firmware ELF files, and on sample size files.
- Heap and stack use are not static and are not part of the size check.
- The feature checkers (`advance_check.py`, `backlash_check.py`) only apply to firmware trees that have the feature. They pass on the pressure-advance development branch of Smoothieware; they cannot run on plain `edge`.
