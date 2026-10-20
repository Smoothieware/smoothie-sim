#!/usr/bin/env python3
"""Insert the simulator's observation hooks into the STAGED copy of the firmware (never the real tree).
Each patch must match exactly once; if upstream code moved, staging fails loudly instead of silently
running an un-instrumented firmware."""
import sys, pathlib

root = pathlib.Path(sys.argv[1])  # staged src/ directory
PATCHES = [
    # Upstream StreamOutput::printf passes the same va_list to vsnprintf twice. That works on ARM, where va_list is a plain pointer
    # restored by the callee, but on x86-64 the first call consumes it, so any message of 64 characters or more (M115) read garbage and crashed.
    ("libs/StreamOutput.cpp",
     "    int size = vsnprintf(b, 64, format, args) + 1;",
     "    va_list args_again;\n    va_copy(args_again, args);\n    int size = vsnprintf(b, 64, format, args) + 1;"),
    ("libs/StreamOutput.cpp",
     "vsnprintf(buffer, size, format, args);",
     "vsnprintf(buffer, size, format, args_again);"),
    ("libs/Kernel.cpp",
     "        (m->*kernel_callback_functions[id_event])(argument);",
     "        sim_event_begin(id_event, m);\n        (m->*kernel_callback_functions[id_event])(argument);\n        sim_event_end(id_event, m);"),
    ("libs/Kernel.cpp",
     "#include <malloc.h>",
     "#include <malloc.h>\n#include \"sim_hooks.h\""),
    ("libs/StepTicker.cpp",
     "    current_tick= 0;\n\n    if(ok) {",
     "    current_tick= 0;\n    if(ok) sim_block_started(current_block);\n\n    if(ok) {"),
    ("libs/StepTicker.cpp",
     "#include <mri.h>\n",
     "#include <mri.h>\n#include \"sim_hooks.h\"\n"),
    ("modules/robot/Conveyor.cpp",
     "    queue.produce_head();\n\n    // not sure", "    queue.produce_head();\n    sim_block_queued();\n\n    // not sure"),
    ("modules/robot/Conveyor.cpp",
     "#include \"Kernel.h\"\n", "#include \"Kernel.h\"\n#include \"sim_hooks.h\"\n"),
    ("modules/robot/Conveyor.cpp",
     "void Conveyor::wait_for_idle(bool wait_for_motors)\n{\n", "void Conveyor::wait_for_idle(bool wait_for_motors)\n{\n    SimWaitScope sim_wait_scope(\"wait_for_idle\");\n"),
    ("libs/Pin.h",
     '            if ( this->inverting ^ value )\n                this->port->FIOSET = 1 << this->pin;\n            else\n                this->port->FIOCLR = 1 << this->pin;\n', '            if ( this->inverting ^ value ) {\n                this->port->FIOSET = 1 << this->pin;\n                this->port->FIOPIN |= 1 << this->pin;   // sim: a GPIO port remembers what was written, like the MCU does\n            } else {\n                this->port->FIOCLR = 1 << this->pin;\n                this->port->FIOPIN &= ~(1u << this->pin);\n            }\n'),
    ("libs/utils.cpp",
     "void safe_delay_us(uint32_t dus)\n{\n", "void safe_delay_us(uint32_t dus)\n{\n    SimWaitScope sim_wait_scope(\"safe_delay\");   // record the delay like a wait: it blocks the caller\n"),
    ("libs/utils.cpp",
     "#include \"utils.h\"\n", "#include \"utils.h\"\n#include \"sim_hooks.h\"\n"),
    ("libs/utils.cpp",
     "    fclose(lp);\n    return exists;", "    if(lp) fclose(lp);  // host libc crashes on fclose(NULL); the MCU's does not\n    return exists;"),
    ("modules/utils/simpleshell/SimpleShell.cpp",
     "std::max(sps, 1UL)", "std::max<uint32_t>(sps, 1UL)"),
    ("modules/tools/laser/Laser.cpp",
     "1000 / std::min(1000UL, (uint32_t)pwm_frequency)", "1000 / std::min<uint32_t>(1000UL, (uint32_t)pwm_frequency)"),
    ("modules/tools/laser/Laser.cpp",
     "attach(std::min(1000UL, 1000000 / period)", "attach(std::min<uint32_t>(1000UL, 1000000 / period)"),
]
for rel, old, new in PATCHES:
    p = root / rel
    text = p.read_text()
    if text.count(old) != 1:
        sys.exit(f"stage_patch: pattern not found exactly once in {rel}: {old[:60]!r} (count={text.count(old)})")
    p.write_text(text.replace(old, new))
print("stage_patch: applied", len(PATCHES), "patches")
