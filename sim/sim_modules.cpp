// Module loading (mirrors init() in the firmware's main.cpp) and the blocks->steps injector.
#define private public
#define protected public
#include "Kernel.h"
#include "Robot.h"
#include "Planner.h"
#include "Conveyor.h"
#include "Block.h"
#include "Player.h"
#include "CurrentControl.h"
#include "KillButton.h"
#include "SwitchPool.h"
#include "ExtruderMaker.h"
#include "TemperatureControlPool.h"
#include "Endstops.h"
#include "ZProbe.h"
#include "ToolManager.h"
#include "SCARAcal.h"
#include "RotaryDeltaCalibration.h"
#include "TemperatureSwitch.h"
#include "Drillingcycles.h"
#include "FilamentDetector.h"
#include "Laser.h"
#include "SpindleMaker.h"
#include "MotorDriverControl.h"
#include "Panel.h"
#if __has_include("Iremitter.h")   // module that only exists in the replay of PR 633
#include "Iremitter.h"
#define SIM_HAS_IREMITTER 1
#endif
#include "platform_memory.h"
#undef private
#undef protected
#include "sim_modules.h"
#include "sim_runtime.h"
#include <cstdio>
#include <fstream>
#include <sstream>

void sim_load_modules(Kernel *kernel, bool all_modules) {
    if (!all_modules) return;   // baseline: only the modules the Kernel constructor creates
    kernel->add_module(new (AHB0) ToolManager());
    kernel->add_module(new (AHB0) Player());
    kernel->add_module(new (AHB0) CurrentControl());
    kernel->add_module(new (AHB0) KillButton());
    { SwitchPool *sp = new SwitchPool(); sp->load_tools(); delete sp; }
    { ExtruderMaker *em = new ExtruderMaker(); em->load_tools(); delete em; }
    { TemperatureControlPool *tp = new TemperatureControlPool(); tp->load_tools(); delete tp; }
    kernel->add_module(new (AHB0) Endstops());
    kernel->add_module(new (AHB0) ZProbe());
    kernel->add_module(new (AHB0) SCARAcal());
    kernel->add_module(new (AHB0) RotaryDeltaCalibration());
    kernel->add_module(new (AHB0) TemperatureSwitch());
    kernel->add_module(new (AHB0) Drillingcycles());
    kernel->add_module(new (AHB0) FilamentDetector());
    kernel->add_module(new Laser());
    { SpindleMaker *sm = new SpindleMaker(); sm->load_spindle(); delete sm; }
    kernel->add_module(new MotorDriverControl(0));
    kernel->add_module(new (AHB0) Panel());
#ifdef SIM_HAS_IREMITTER
    kernel->add_module(new Iremitter());
#endif
}

// Text format, one block per line (written by checkers/blocks_to_steps.py):
//   n_axes steps[0..n-1] direction_bits nominal_speed nominal_rate acceleration millimeters entry_speed exit_speed
// The block is handed to the real Block::calculate_trapezoid()/prepare() path exactly as the Planner does it,
// but with the speeds taken from the input instead of from the planner's look-ahead.
void sim_inject_blocks(const std::string &path) {
    std::ifstream in(path);
    if (!in) { fprintf(stderr, "cannot read %s\n", path.c_str()); exit(2); }
    std::string line; int n = 0;
    while (std::getline(in, line)) {
        n++;
        if (line.empty() || line[0] == '#') continue;
        std::istringstream ls(line); int axes; ls >> axes;
        Block *b = THECONVEYOR->queue.head_ref();
        b->clear();
        uint32_t maxsteps = 0;
        for (int i = 0; i < axes; i++) { uint32_t s; ls >> s; if (i < Block::n_actuators) { b->steps[i] = s; if (s > maxsteps) maxsteps = s; } }
        unsigned dir; float nspeed, nrate, acc, mm, entry, exit_; ls >> dir >> nspeed >> nrate >> acc >> mm >> entry >> exit_;
        for (int i = 0; i < axes && i < Block::n_actuators; i++) b->direction_bits[i] = (dir >> i) & 1;
        b->steps_event_count = maxsteps; b->nominal_speed = nspeed; b->nominal_rate = nrate; b->acceleration = acc;
        b->millimeters = mm; b->entry_speed = entry; b->primary_axis = true; b->is_g123 = true;
        // Planner::append_block gives every moving motor its axis record (and the extension record) before the trapezoid;
        // this injector has no backlash correction, so it passes an all-zero correction (set_active reads every entry)
#ifdef SIM_SPARSE_BLOCKS
        static const int32_t no_correction[8] = {0}; // 8 >= the largest motor count (Block::n_actuators is set at run time)
        b->set_active(no_correction);
#endif
        b->calculate_trapezoid(entry, exit_);
        b->ready();
        SIM.current_line = n;
        THECONVEYOR->queue_head_block();
    }
}
