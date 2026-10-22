# Acknowledgements

smoothie-sim takes ideas and some adapted code from the [Carvera Firmware Simulator](https://github.com/f355/carvera_firmware_simulator) by Konstantin Tcepliaev, licensed under the GNU General Public License version 3 or (at your option) any later version. Where their code is adapted, the file keeps their copyright header and says where it came from, and the combined work is distributed under GPL version 3 or later.

Taken or inspired by that project:
- RAM model (heap and AHB pool replay, per-class ARM sizes from DWARF, layout from the linker map): `checkers/memory_check.py` (heap model adapted from `include/sim/lpc_memory_accounting.hpp`), `checkers/lpc_dwarf.py` and `tools/lpc_memory_layout.py` (adapted from `scripts/lpc_memory_layout.py`), `sim/sim_alloc.cpp` (the idea of `src/firmware/firmware_allocation_hooks.cpp`), and the test cases of `tests/test_memory_model.py` (after `tests/lpc_memory_accounting_test.cpp`).
- End-of-job position check (pulse-integrated position against the Robot's machine position and the G-code destination): inspired by their `StepperAxis`, which integrates emitted step and direction pulses into a position; the implementation (`checkers/position_check.py`, the pin sampling in `sim/sim_main.cpp`) is our own.
- Over-temperature fault injection through the real TemperatureControl (`checkers/fault_check.py`, `cases/faults/`): the idea from their `tests/temperature_fault_runtime_test.cpp`; the implementation is our own.
- Event-ordered timer dispatch (next timer match, NVIC priority order): the design studied from their `timer_scheduler`, `interrupt_controller`, `event_engine` and `virtual_clock`; the implementation in `sim/sim_main.cpp` is our own, much smaller.
- `cases/cartesian/face-4x4-stock.gcode`: `tests/resources/Face 4x4 stock.cnc` from the Carvera_Controller repository (https://github.com/carvera-community/Carvera_Controller), a Fusion-generated facing program, copied unchanged.

Not taken: the GUI, the protobuf API, controller transports, Wi-Fi and Zigbee, the Makera protocol, tool changer, EEPROM, their build and packaging, Carvera configurations and board data, and the probe, spindle and laser models (possible future work).
