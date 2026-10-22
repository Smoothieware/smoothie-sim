// Shared state of the simulator: fake clock, machine ticking, captured blocks, steps, handler timings.
#pragma once
#include <stdint.h>
#include <string>
#include <vector>
#include <map>
#include <utility>

struct BlockRec {
    int index = 0;
    int gcode_line = 0;            // 1-based line of the G-code that was being parsed when the block started
    uint64_t start_tick = 0;       // machine tick (step ticker period) when the block started
    uint64_t start_us = 0;
    std::vector<uint32_t> steps;
    uint32_t steps_event_count = 0;
    float nominal_rate = 0, nominal_speed = 0, millimeters = 0, entry_speed = 0, exit_speed = 0;
    float acceleration = 0, initial_rate = 0, maximum_rate = 0, max_entry_speed = 0;
    uint32_t accelerate_until = 0, decelerate_after = 0, total_move_ticks = 0;
    uint32_t direction_bits = 0;
    bool is_g123 = false, primary_axis = false;
    std::vector<double> steps_per_tick, acceleration_change, deceleration_change, plateau_rate; // real values (fixed point /2^62)
    std::vector<uint32_t> steps_to_move;
    std::vector<std::vector<uint32_t>> step_ticks;   // per actuator: tick offsets (from block start) of every step
    std::vector<int> step_dirs;                      // per actuator: direction bit seen (1 = negative)
    uint32_t ticks_run = 0;
    // Per actuator: (index of the step, sign) for the first step and for every step whose direction differs from the step
    // before it (+1 = current_step went up, -1 = it went down). A motor that never reverses has exactly one entry.
    std::vector<std::vector<std::pair<uint32_t, int>>> dir_changes;
    std::vector<int> sign_now;                       // per actuator: sign of the last step seen in this block, 0 = none yet
    // Filament advance data of the block (only filled when the firmware has the feature, see sim_block_started)
    bool has_filament_advance = false;
    std::vector<int32_t> advance_lead;               // per actuator: lead (steps ahead of nominal) at the end of this block
    std::vector<uint32_t> flip_tick;                 // per actuator: tick at which the motor reverses, 0 = never
    std::vector<double> decel_start_adjust;          // per actuator: rate offset applied when the deceleration begins
    std::vector<uint32_t> advance_motors;            // actuators the planner marked as shaped for this block
};

struct WaitRec {
    std::string kind, module, event;
    uint64_t microseconds = 0;
    int gcode_line = 0;
};

struct HandlerStat {
    uint64_t calls = 0, self_us = 0, max_self_us = 0;
};

struct SimState {
    std::vector<int> queued_lines;   // G-code line that produced each queued block, in queue order
    int adc_value = 3900;           // 12-bit raw ADC value fed to every channel (default is about 25 C on a 100k thermistor)
    uint64_t now_us = 0;
    double next_step_tick_us = 0, next_slow_tick_us = 0;
    bool event_dispatch = true;    // timers are served in time order, ties by interrupt priority; --fixed-tick restores all step ticks of a millisecond first
    double step_period_us = 10.0;
    bool machine_enabled = false;
    bool in_isr = false;
    uint64_t tick_counter = 0;
    int current_line = 0;
    bool capture_steps = true;
    std::vector<BlockRec> blocks;
    int active_block = -1;
    std::vector<int32_t> last_steps;                // last observed current_step per actuator
    std::vector<int64_t> pulse_position;            // position integrated from the step and direction pin levels at every emitted pulse
    std::vector<WaitRec> waits;
    std::map<std::string, HandlerStat> handlers;    // "Module::EVENT"
    std::map<std::string, std::vector<std::string>> hooks; // module -> events it was called for
    std::string serial_out;
    // call stack bookkeeping
    struct Frame { int event; std::string module; uint64_t start_us; uint64_t nested_us; uint64_t machine_us_start; };
    std::vector<Frame> stack;
    uint64_t machine_advance_us = 0;                // time advanced only because the machine ticks (idle passes)
    double idle_us = 50;                            // time that passes per idle pass of the main loop
    double blocking_threshold_us = 1000;            // handler self time above this is reported as blocking
};
extern SimState SIM;

void sim_advance(uint64_t us, bool idle_time = false);   // move the fake clock; runs the step/slow tickers that are due
void sim_machine_start();                                // call once after the kernel is set up
const char *sim_event_name(int event);
