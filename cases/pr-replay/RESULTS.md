# Replay of historical PRs that the Smoothieware maintainer rejected for waits
Static = scan of the PR's changed files vs edge. Runtime = simulator built from the PR tree.

| PR | state | Maintainer's objection | offending code | static | runtime |
|----|-------|-----------------|----------------|--------|---------|
| 620 servo probe | closed | "delays are not allowed" | ZProbe `wait_ms(250)` | caught | not run (tree only partly applies) |
| 633 IR camera | closed | "remove the busy waits ... use a timer" | Iremitter `wait_us`, `us_ticker_read` loop | caught (27 hits) | not buildable: PR predates current Module API |
| 955 spindle refactor | merged | "you cannot use wait_us" | SoftSerial_tx.cpp:29 `wait_us` | caught (original commit 1a5819e) | not run |
| 1219 Max6675 | closed | "Waits are not allowed" | max6675.cpp:84 `wait_us(1)` | caught | caught (wait_us in TemperatureControl::ON_IDLE) |
| 1227 stepper enable delay | closed | "wait is not allowed ever" | StepperMotor.cpp:80 `wait` | caught | NOT caught: workload never triggers the delayed enable path |
| 1447 TMC2208/9 | open | "wait() is NOT valid" | MotorDriverControl `safe_delay_ms` | caught (the maintainer's view of safe_delay unconfirmed) | not run |
| 1488 software SPI | closed | "uses wait() ... not allowed" | mbed SWSPI.cpp `wait` | caught | not buildable: SWSPI lives outside src/ |
Not wait calls, so not detectable by this check: PR 564 (blocking ADC read), 1052 (M109 locks system), 746 (delays in on_idle skew zprobe).


## Update 2026-10-17 (regression test `tools/regress_prs.py`, all 8 cases pass)

| PR | What it does | Static scan | Runtime | Why |
|---|---|---|---|---|
| 564 (synthetic) | blocking ADC-style busy loop in TemperatureControl::on_second_tick | flagged (busy loop, handler) | flagged: handler ran 2 ms, not allow-listed | stands in for the maintainer's PR 564 complaint |
| 620 | servo on ZProbe | flagged | not runtime-capable | tree does not compile against edge (ZProbe.cpp servo_* undeclared) |
| 633 | Iremitter | flagged (27 hits) | flagged (384 wait_us in Iremitter) | builds with `cases/pr-replay/633/compat/port.patch` (old ON_GCODE_EXECUTE and append_gcode plumbing only) |
| 955 | spindle | flagged | not runtime-capable | SoftSerial.h:16 does not compile |
| 1219 | wait_us(1) in TemperatureControl | flagged | flagged (2694) | |
| 1227 | StepperMotor enable delay | flagged | flagged (13 waits in StepperMotor) | needed the simulator's GPIO ports to remember written pin levels |
| 1447 | motor driver | flagged | not runtime-capable | MotorDriverControl.cpp does not compile |
| 1488 | SWSPI.cpp in mbed/ | flagged | flagged (960, MotorDriverControl) | builds now: files outside src/ are staged (EXTRA_FILES) |
