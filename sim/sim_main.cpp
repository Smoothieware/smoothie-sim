// Smoothieware x86 simulator driver.
//   smoothie-sim --config cfg.txt --gcode in.gcode --out result.json [options]
// Runs the real firmware (planner, conveyor, step ticker, modules) against a fake clock and fake serial port.
#define private public
#define protected public
#include "Kernel.h"
#include "Adc.h"
#include "Module.h"
#include "Config.h"
#include "Robot.h"
#include "Planner.h"
#include "Conveyor.h"
#include "Block.h"
#include "StepTicker.h"
#include "StepperMotor.h"
#include "SlowTicker.h"
#include "SerialConsole.h"
#include "GcodeDispatch.h"
#include "platform_memory.h"
#include "StreamOutputPool.h"
#include "ConfigValue.h"
#include "checksumm.h"
#undef private
#undef protected
#include "sim_hooks.h"
#include "sim_hw.h"
#include "sim_runtime.h"
#include "sim_modules.h"
#include "sim_alloc.h"
#include <cstdio>
#include <cstring>
#include <cxxabi.h>
#include <typeinfo>
#include <fstream>
#include <sstream>
#include <algorithm>

SimState SIM;
extern "C" char sim_config_buf[1 << 18];
extern "C" void TIMER2_IRQHandler(void);

const char *sim_event_name(int e) {
    static const char *n[] = {"ON_MAIN_LOOP", "ON_CONSOLE_LINE_RECEIVED", "ON_GCODE_RECEIVED", "ON_IDLE", "ON_SECOND_TICK",
        "ON_GET_PUBLIC_DATA", "ON_SET_PUBLIC_DATA", "ON_HALT", "ON_ENABLE", "ON_GCODE_EXECUTE", "ON_SPEED_CHANGE", "ON_FILE_RESUME",
        "ON_PLAY", "ON_PAUSE", "ON_BLOCK_BEGIN", "ON_BLOCK_END", "ON_STATE_CHANGE", "ON_SET_PUBLIC_DATA2", "ON_MOVE_COMPLETED"};
    return (e >= 0 && e < (int)(sizeof(n) / sizeof(n[0]))) ? n[e] : "ON_UNKNOWN";
}

static std::string module_name(Module *m) {
    int st = 0; char *d = abi::__cxa_demangle(typeid(*m).name(), nullptr, nullptr, &st);
    std::string r = (st == 0 && d) ? d : typeid(*m).name(); free(d); return r;
}

void sim_event_begin(int event, Module *m) {
    SimState::Frame f{event, module_name(m), SIM.now_us, 0, SIM.machine_advance_us};
    SIM.stack.push_back(f);
}
void sim_event_end(int event, Module *m) {
    if (SIM.stack.empty()) return;
    auto f = SIM.stack.back(); SIM.stack.pop_back();
    uint64_t total = SIM.now_us - f.start_us;
    uint64_t machine = SIM.machine_advance_us - f.machine_us_start;
    uint64_t self = total - std::min(total, f.nested_us + machine);
    if (!SIM.stack.empty()) SIM.stack.back().nested_us += total;
    auto &h = SIM.handlers[f.module + "::" + sim_event_name(event)];
    h.calls++; h.self_us += self; h.max_self_us = std::max<uint64_t>(h.max_self_us, self);
    bool is_conveyor_idle = (event == 3 && f.module == "Conveyor");
    if (self > SIM.blocking_threshold_us && event != 3 /*ON_IDLE*/) {
        WaitRec w; w.kind = "long_handler"; w.module = f.module; w.event = sim_event_name(event);
        w.microseconds = self; w.gcode_line = SIM.current_line; SIM.waits.push_back(w);
    }
    // one pass of the firmware's idle loop takes idle_us of machine time (the step ticker runs meanwhile)
    if (is_conveyor_idle) sim_advance((uint64_t)SIM.idle_us, true);
}

SimWaitScope::SimWaitScope(const char *k) : kind(k), start_us(SIM.now_us), frame((int)SIM.stack.size()) {}
SimWaitScope::~SimWaitScope() {
    if (frame == 0) return;   // called from the driver itself, not from a firmware handler
    auto &f = SIM.stack[frame - 1];
    WaitRec w; w.kind = kind; w.module = f.module; w.event = sim_event_name(f.event);
    w.microseconds = SIM.now_us - start_us; w.gcode_line = SIM.current_line; SIM.waits.push_back(w);
}

void sim_block_queued() { SIM.queued_lines.push_back(SIM.current_line); }

static const double FP = 4611686018427387904.0; // 2^62
void sim_block_started(Block *b) {
    BlockRec r; r.index = (int)SIM.blocks.size(); r.gcode_line = r.index < (int)SIM.queued_lines.size() ? SIM.queued_lines[r.index] : 0;
    r.start_tick = SIM.tick_counter; r.start_us = SIM.now_us;
    int n = Block::n_actuators;
    for (int i = 0; i < n; i++) r.steps.push_back(b->steps[i]);
    r.steps_event_count = b->steps_event_count; r.nominal_rate = b->nominal_rate; r.nominal_speed = b->nominal_speed;
    r.millimeters = b->millimeters; r.entry_speed = b->entry_speed; r.exit_speed = b->exit_speed;
    r.acceleration = b->acceleration; r.initial_rate = b->initial_rate; r.maximum_rate = b->maximum_rate;
    r.max_entry_speed = b->max_entry_speed; r.accelerate_until = b->accelerate_until; r.decelerate_after = b->decelerate_after;
    r.total_move_ticks = b->total_move_ticks; r.direction_bits = (uint32_t)b->direction_bits.to_ulong();
    r.is_g123 = b->is_g123; r.primary_axis = b->primary_axis;
    for (int i = 0; i < n; i++) {
        static const Block::tickinfo_t none = {}; // motor without an axis record
#ifdef SIM_SPARSE_BLOCKS   // firmware whose Block keeps axis records only for the motors that move
        const Block::tickinfo_t &t = b->is_active(i) ? *b->axis(i) : none;
#else                      // upstream edge: one record per actuator
        const Block::tickinfo_t &t = b->tick_info ? b->tick_info[i] : none;
#endif
        r.steps_per_tick.push_back(t.steps_per_tick / FP); r.acceleration_change.push_back(t.acceleration_change / FP);
        r.deceleration_change.push_back(t.deceleration_change / FP); r.plateau_rate.push_back(t.plateau_rate / FP);
        r.steps_to_move.push_back(t.steps_to_move);
    }
    r.step_ticks.assign(n, {}); r.step_dirs.assign(n, 0);
    r.dir_changes.assign(n, {}); r.sign_now.assign(n, 0);
#ifdef FILAMENT_ADVANCE   // defined by FilamentAdvance.h, only in firmware trees that have the feature (not in CNC builds)
    r.has_filament_advance = true;
    for (int i = 0; i < n; i++) {
        r.advance_lead.push_back(b->shaper_state[i]); r.flip_tick.push_back(b->ext_of(i).reversal_tick);
        r.decel_start_adjust.push_back(b->ext_of(i).decel_start_rate_delta / FP);
        if (b->shaped_motors[i]) r.advance_motors.push_back(i);
    }
#endif
    SIM.blocks.push_back(std::move(r)); SIM.active_block = (int)SIM.blocks.size() - 1;
}

static void step_tick_once() {
    auto &acts = THEROBOT->actuators;
    SIM.in_isr = true;
    int owner = SIM.active_block;   // a block that finishes and a new one that starts can share one tick: charge steps to the block that was running before the tick
    if (SIM.pulse_position.size() != acts.size()) SIM.pulse_position.assign(acts.size(), 0);
    std::vector<bool> dir_before(acts.size());
    for (size_t i = 0; i < acts.size(); i++) dir_before[i] = acts[i]->dir_pin.get();
    StepTicker::getInstance()->step_tick();
    for (size_t i = 0; i < acts.size(); i++)   // a pulse is a high step pin; the direction pin says which way the driver moves (low = forward)
        if (acts[i]->step_pin.get()) SIM.pulse_position[i] += dir_before[i] ? -1 : 1;
    StepTicker::getInstance()->unstep_tick();
    SIM.in_isr = false;
    if (SIM.last_steps.size() != acts.size()) { SIM.last_steps.resize(acts.size()); for (size_t i = 0; i < acts.size(); i++) SIM.last_steps[i] = acts[i]->get_current_step(); }
    for (size_t i = 0; i < acts.size(); i++) {
        int32_t cur = acts[i]->get_current_step();
        if (cur != SIM.last_steps[i]) {
            if (owner >= 0) {
                auto &b = SIM.blocks[owner];
                if (SIM.capture_steps) b.step_ticks[i].push_back((uint32_t)(SIM.tick_counter - b.start_tick));
                b.step_dirs[i] = acts[i]->which_direction();
                int sign = (cur > SIM.last_steps[i]) ? 1 : -1;   // each tick makes at most one step per motor
                if (sign != b.sign_now[i]) { b.dir_changes[i].push_back({(uint32_t)b.step_ticks[i].size() - (SIM.capture_steps ? 1 : 0), sign}); b.sign_now[i] = sign; }
                b.ticks_run = (uint32_t)(SIM.tick_counter - b.start_tick) + 1;
            }
            SIM.last_steps[i] = cur;
        }
    }
    SIM.tick_counter++;
}

// ---- race mode: the step ISR preempts the firmware inside a flag read-modify-write ----
#ifdef SIM_RACE
#include "sim_race.h"
static struct { double window_us = 0; uint64_t force_every = 0; bool busy = false; uint64_t points = 0, fired = 0, lost_stores = 0, lost_ticking = 0, replans = 0; uint64_t lost_by_bit[8] = {0}; } RACE;
void sim_race_set_window(double us) { RACE.window_us = us; }
void sim_race_set_force_every(uint64_t n) { RACE.force_every = n; }
void sim_race_preempt(void) {
    if ((RACE.window_us <= 0 && !RACE.force_every) || !SIM.machine_enabled || SIM.in_isr || RACE.busy) return;
    RACE.points++;
    // Systematic exploration: fire a tick at every Nth flag write whether or not one is due (an ISR landing at an arbitrary point).
    // The machine then runs ahead of the planner, which is the starved-queue case where the race matters.
    if (RACE.force_every && RACE.points % RACE.force_every == 0) {
        RACE.busy = true; step_tick_once(); RACE.fired++; RACE.busy = false; return;
    }
    // A tick that is due within the window would, on the MCU, interrupt this very instruction sequence: run it now.
    if (SIM.next_step_tick_us <= SIM.now_us + RACE.window_us) {
        RACE.busy = true; step_tick_once(); SIM.next_step_tick_us += SIM.step_period_us; RACE.fired++; RACE.busy = false;
    }
}
void sim_race_note_store(uint8_t lost) { RACE.lost_stores++; for (int i = 0; i < 8; i++) if (lost & (1u << i)) RACE.lost_by_bit[i]++; }
void sim_race_replan_of_started(const void *) { RACE.replans++; }
static void sim_race_report() {
    fprintf(stderr, "SIM_RACE window_us=%g preempt_points=%llu isr_fired_inside_rmw=%llu overwritten_stores=%llu (by flag bit 0..7: %llu %llu %llu %llu %llu %llu %llu %llu) replans_of_running_block=%llu\n",
        RACE.window_us, (unsigned long long)RACE.points, (unsigned long long)RACE.fired, (unsigned long long)RACE.lost_stores,
        (unsigned long long)RACE.lost_by_bit[0], (unsigned long long)RACE.lost_by_bit[1], (unsigned long long)RACE.lost_by_bit[2], (unsigned long long)RACE.lost_by_bit[3],
        (unsigned long long)RACE.lost_by_bit[4], (unsigned long long)RACE.lost_by_bit[5], (unsigned long long)RACE.lost_by_bit[6], (unsigned long long)RACE.lost_by_bit[7],
        (unsigned long long)RACE.replans);
}
#endif

void sim_advance(uint64_t us, bool idle_time) {
    SIM.now_us += us;
    if (idle_time) SIM.machine_advance_us += us;
    if (!SIM.machine_enabled || SIM.in_isr) return;
    bool outer_frames = !SIM.stack.empty();
    uint64_t before = SIM.now_us;
    auto slow_tick = [] {
        sim_tim[2].IR |= 1; TIMER2_IRQHandler(); SIM.next_slow_tick_us += 1000.0;
        if (Adc::instance) for (int c = 0; c < 8; c++) Adc::instance->new_sample(c, (uint32_t)SIM.adc_value << 4);   // fake thermistor reading (~25 C)
    };
    if (SIM.event_dispatch) {
        // Event-driven: the earliest timer match runs first; a tie goes to the step ticker, which has the higher NVIC priority (TIMER0 is 2, TIMER2 is 4 in Kernel.cpp).
        for (;;) {
            bool step_due = SIM.next_step_tick_us <= SIM.now_us, slow_due = SIM.next_slow_tick_us <= SIM.now_us;
            if (!step_due && !slow_due) break;
            if (step_due && (!slow_due || SIM.next_step_tick_us <= SIM.next_slow_tick_us)) { step_tick_once(); SIM.next_step_tick_us += SIM.step_period_us; }
            else slow_tick();
        }
    } else {
        while (SIM.next_step_tick_us <= SIM.now_us) { step_tick_once(); SIM.next_step_tick_us += SIM.step_period_us; }
        while (SIM.next_slow_tick_us <= SIM.now_us) slow_tick();
    }
    (void)outer_frames; (void)before;
}

void sim_machine_start() {
    SIM.step_period_us = 1e6 / THEKERNEL->base_stepping_frequency;
    SIM.next_step_tick_us = SIM.now_us + SIM.step_period_us;
    SIM.next_slow_tick_us = SIM.now_us + 1000.0;
    THEKERNEL->step_ticker->start();
    SIM.machine_enabled = true;
}


// ---- workload stimulus lines -------------------------------------------------------------------------------------------
// A workload comment of the form ";@sim <verb> ..." is not sent to the firmware; it drives something no G-code can:
//   pin <port.pin> <0|1>       set the level the firmware reads on an input pin (buttons, switches)
//   pulses <port.pin> <count>  rising edges on an interrupt input pin (what the GPIO interrupt would deliver)
//   adc <raw>                  12-bit raw value every thermistor channel reads from now on (lower = hotter)
//   wait <ms>                  let simulated time pass with the main loop and idle running (second ticks, button polling)
static bool sim_pin_number(const std::string &text, int &port, int &bit) {
    return sscanf(text.c_str(), "%d.%d", &port, &bit) == 2 && port >= 0 && port < 5 && bit >= 0 && bit < 32;
}
static void sim_directive(Kernel *kernel, const std::string &line) {
    std::istringstream ls(line.substr(5)); std::string verb, a; long b = 0;
    ls >> verb >> a >> b;
    int port = 0, bit = 0;
    if (verb == "pin" && sim_pin_number(a, port, bit)) {
        if (b) sim_gpio[port].FIOPIN |= 1u << bit; else sim_gpio[port].FIOPIN &= ~(1u << bit);
    } else if (verb == "pulses" && sim_pin_number(a, port, bit)) {
        for (long n = 0; n < b; n++)
            for (auto *pin : mbed::sim_interrupt_pins())
                if ((int)pin->pin_ == port * 32 + bit && pin->rise_cb_) { SIM.in_isr = true; pin->rise_cb_(); SIM.in_isr = false; }
    } else if (verb == "adc") {
        SIM.adc_value = atoi(a.c_str());
    } else if (verb == "wait") {
        long ms = atol(a.c_str());
        for (long t = 0; t < ms; t++) {
            sim_advance(1000, true);
            if (t % 20 == 19) { kernel->call_event(ON_MAIN_LOOP); kernel->call_event(ON_IDLE); }   // 50 Hz, the panel's button poll rate
        }
    } else {
        fprintf(stderr, "unknown workload stimulus: %s\n", line.c_str()); exit(2);
    }
}

// ---------------- JSON output ----------------
static std::string esc(const std::string &s) {
    std::string o; for (unsigned char c : s) { if (c == '"' || c == '\\') { o += '\\'; o += c; } else if (c == '\n') o += "\\n"; else if (c == '\r') o += "\\r"; else if (c < 32 || c >= 127) o += '?'; else o += c; } return o;
}
static void put_num(FILE *f, double v) { if (v != v || v > 1e300 || v < -1e300) fputs("null", f); else fprintf(f, "%.9g", v); }
template <typename T> static void put_arr(FILE *f, const std::vector<T> &v) { fputc('[', f); for (size_t i = 0; i < v.size(); i++) { if (i) fputc(',', f); put_num(f, (double)v[i]); } fputc(']', f); }

static void write_result(const char *path, const std::string &mode, bool full_steps) {
    FILE *f = fopen(path, "w"); if (!f) { perror(path); return; }
    fprintf(f, "{\"schema\":1,\"mode\":\"%s\",\"step_period_us\":%.6f,\"n_actuators\":%d,\n", mode.c_str(), SIM.step_period_us, (int)THEROBOT->actuators.size());
    fputs("\"steps_per_mm\":", f); { std::vector<double> v; for (auto *a : THEROBOT->actuators) v.push_back(a->get_steps_per_mm()); put_arr(f, v); }
    fputs(",\n\"pulse_position\":", f); { std::vector<double> v; for (size_t i = 0; i < THEROBOT->actuators.size(); i++) v.push_back(i < SIM.pulse_position.size() ? (double)SIM.pulse_position[i] : 0.0); put_arr(f, v); }
    fputs(",\n\"machine_position\":", f); { std::vector<double> v; for (size_t i = 0; i < THEROBOT->actuators.size(); i++) v.push_back(THEROBOT->machine_position[i]); put_arr(f, v); }
    fputs(",\n\"final_steps\":", f); { std::vector<double> v; for (auto *a : THEROBOT->actuators) v.push_back(a->get_current_step()); put_arr(f, v); }
    fputs(",\n\"blocks\":[\n", f);
    for (size_t bi = 0; bi < SIM.blocks.size(); bi++) {
        auto &b = SIM.blocks[bi];
        if (bi) fputs(",\n", f);
        fprintf(f, "{\"index\":%d,\"gcode_line\":%d,\"start_tick\":%llu,\"steps\":", b.index, b.gcode_line, (unsigned long long)b.start_tick); put_arr(f, b.steps);
        fprintf(f, ",\"steps_event_count\":%u,\"nominal_rate\":", b.steps_event_count); put_num(f, b.nominal_rate);
        fputs(",\"nominal_speed\":", f); put_num(f, b.nominal_speed); fputs(",\"millimeters\":", f); put_num(f, b.millimeters);
        fputs(",\"entry_speed\":", f); put_num(f, b.entry_speed); fputs(",\"exit_speed\":", f); put_num(f, b.exit_speed);
        fputs(",\"acceleration\":", f); put_num(f, b.acceleration); fputs(",\"initial_rate\":", f); put_num(f, b.initial_rate);
        fputs(",\"maximum_rate\":", f); put_num(f, b.maximum_rate); fputs(",\"max_entry_speed\":", f); put_num(f, b.max_entry_speed);
        fprintf(f, ",\"accelerate_until\":%u,\"decelerate_after\":%u,\"total_move_ticks\":%u,\"direction_bits\":%u,\"is_g123\":%s,\"primary_axis\":%s",
                b.accelerate_until, b.decelerate_after, b.total_move_ticks, b.direction_bits, b.is_g123 ? "true" : "false", b.primary_axis ? "true" : "false");
        fputs(",\"steps_per_tick\":", f); put_arr(f, b.steps_per_tick); fputs(",\"acceleration_change\":", f); put_arr(f, b.acceleration_change);
        fputs(",\"deceleration_change\":", f); put_arr(f, b.deceleration_change); fputs(",\"plateau_rate\":", f); put_arr(f, b.plateau_rate);
        fputs(",\"steps_to_move\":", f); put_arr(f, b.steps_to_move);
        fprintf(f, ",\"ticks_run\":%u,\"step_dirs\":", b.ticks_run); put_arr(f, b.step_dirs);
        fputs(",\"step_counts\":[", f); for (size_t m = 0; m < b.step_ticks.size(); m++) fprintf(f, "%s%zu", m ? "," : "", b.step_ticks[m].size()); fputc(']', f);
        fputs(",\"dir_changes\":[", f);
        for (size_t m = 0; m < b.dir_changes.size(); m++) { fputs(m ? ",[" : "[", f); for (size_t k = 0; k < b.dir_changes[m].size(); k++) fprintf(f, "%s[%u,%d]", k ? "," : "", b.dir_changes[m][k].first, b.dir_changes[m][k].second); fputc(']', f); }
        fputc(']', f);
        if (b.has_filament_advance) {
            fputs(",\"advance_lead\":", f); put_arr(f, b.advance_lead); fputs(",\"flip_tick\":", f); put_arr(f, b.flip_tick);
            fputs(",\"decel_start_adjust\":", f); put_arr(f, b.decel_start_adjust); fputs(",\"advance_motors\":", f); put_arr(f, b.advance_motors);
        }
        fputs(",\"step_ticks\":[", f);
        for (size_t m = 0; m < b.step_ticks.size(); m++) { if (m) fputc(',', f); if (full_steps || b.step_ticks[m].size() <= 4000) put_arr(f, b.step_ticks[m]); else { // thin out long lists to every Nth step
            std::vector<uint32_t> t; size_t stride = b.step_ticks[m].size() / 2000 + 1; for (size_t i = 0; i < b.step_ticks[m].size(); i += stride) t.push_back(b.step_ticks[m][i]); put_arr(f, t); } }
        fprintf(f, "],\"step_tick_stride\":[");
        for (size_t m = 0; m < b.step_ticks.size(); m++) fprintf(f, "%s%zu", m ? "," : "", (full_steps || b.step_ticks[m].size() <= 4000) ? (size_t)1 : b.step_ticks[m].size() / 2000 + 1);
        fputs("]}", f);
    }
    fputs("\n],\n\"waits\":[", f);
    for (size_t i = 0; i < SIM.waits.size(); i++) { auto &w = SIM.waits[i]; fprintf(f, "%s{\"kind\":\"%s\",\"module\":\"%s\",\"event\":\"%s\",\"us\":%llu,\"gcode_line\":%d}", i ? "," : "", w.kind.c_str(), esc(w.module).c_str(), w.event.c_str(), (unsigned long long)w.microseconds, w.gcode_line); }
    fputs("],\n\"handlers\":{", f);
    { bool first = true; for (auto &kv : SIM.handlers) { fprintf(f, "%s\"%s\":{\"calls\":%llu,\"self_us\":%llu,\"max_self_us\":%llu}", first ? "" : ",", esc(kv.first).c_str(), (unsigned long long)kv.second.calls, (unsigned long long)kv.second.self_us, (unsigned long long)kv.second.max_self_us); first = false; } }
    fprintf(f, "},\n\"serial_out\":\"%s\",\n\"end_us\":%llu,\"ticks\":%llu}\n", esc(SIM.serial_out).c_str(), (unsigned long long)SIM.now_us, (unsigned long long)SIM.tick_counter);
    fclose(f);
}

static std::string read_file(const std::string &p) { std::ifstream in(p); if (!in) { fprintf(stderr, "cannot read %s\n", p.c_str()); exit(2); } std::stringstream ss; ss << in.rdbuf(); return ss.str(); }

int main(int argc, char **argv) {
    std::string cfg, gcode, out = "sim-result.json", mode = "gcode", blocks_in, alloc_trace;
    bool full_steps = false, with_modules = false;
    for (int i = 1; i < argc; i++) {
        std::string a = argv[i];
        auto next = [&]() -> std::string { if (i + 1 >= argc) { fprintf(stderr, "missing value for %s\n", a.c_str()); exit(2); } return argv[++i]; };
        if (a == "--config") cfg = next(); else if (a == "--gcode") gcode = next(); else if (a == "--out") out = next();
        else if (a == "--blocks-in") blocks_in = next(); else if (a == "--alloc-trace") alloc_trace = next(); else if (a == "--event-dispatch") SIM.event_dispatch = true; else if (a == "--fixed-tick") SIM.event_dispatch = false; else if (a == "--full-steps") full_steps = true; else if (a == "--no-steps") SIM.capture_steps = false;
        #ifdef SIM_RACE
        else if (a == "--race-force-every") { sim_race_set_force_every(strtoull(next().c_str(), nullptr, 10)); atexit(sim_race_report); }
        else if (a == "--race-window-us") { sim_race_set_window(atof(next().c_str())); atexit(sim_race_report); }
#endif
        else if (a == "--modules") with_modules = true; else if (a == "--adc-value") SIM.adc_value = atoi(next().c_str()); else if (a == "--idle-us") SIM.idle_us = atof(next().c_str());
        else if (a == "--blocking-threshold-us") SIM.blocking_threshold_us = atof(next().c_str());
        else { fprintf(stderr, "unknown option %s\n", a.c_str()); return 2; }
    }
    if (cfg.empty()) { fprintf(stderr, "usage: smoothie-sim --config cfg --gcode file|--blocks-in blocks.json --out result.json [--modules] [--full-steps]\n"); return 2; }
    std::string ctext = read_file(cfg);
    if (ctext.size() > sizeof(sim_config_buf) - 2) { fprintf(stderr, "config too large\n"); return 2; }
    memset(sim_config_buf, '\n', sizeof(sim_config_buf));
    memcpy(sim_config_buf, ctext.data(), ctext.size());

    if (!alloc_trace.empty()) sim_alloc_start();
    static char pool_mem[1]; (void)pool_mem;
    _AHB0 = new MemoryPool(); _AHB1 = new MemoryPool();
    Kernel *kernel = new Kernel();
    sim_load_modules(kernel, with_modules);
    kernel->config->config_cache_clear();
    kernel->conveyor->start(THEROBOT->get_number_registered_motors());
    kernel->slow_ticker->start();
    THEROBOT->after_config();
    sim_machine_start();

    if (!blocks_in.empty()) { mode = "blocks"; sim_inject_blocks(blocks_in); }
    else if (!gcode.empty()) {
        std::istringstream in(read_file(gcode)); std::string line; int n = 0;
        while (std::getline(in, line)) {
            n++; SIM.current_line = n;
            while (!line.empty() && (line.back() == '\r')) line.pop_back();
            if (line.compare(0, 5, ";@sim") == 0) { sim_directive(kernel, line); continue; }
            for (char c : line) kernel->serial->on_serial_char_received(c);
            kernel->serial->on_serial_char_received('\n');
            // one pass of the firmware main loop per line, with enough passes to consume the received line
            for (int guard = 0; guard < 100000 && kernel->serial->lf_count > 0; guard++) {
                kernel->call_event(ON_MAIN_LOOP); kernel->call_event(ON_IDLE);
            }
        }
    }
    SIM.current_line = 0;
    kernel->conveyor->wait_for_idle();   // drain: everything queued gets executed by the step ticker
    sim_advance(1000, true);
    write_result(out.c_str(), mode, full_steps);
    if (!alloc_trace.empty()) sim_alloc_write(alloc_trace.c_str());
    fprintf(stderr, "smoothie-sim: %zu blocks, %llu ticks, %zu waits recorded -> %s\n", SIM.blocks.size(), (unsigned long long)SIM.tick_counter, SIM.waits.size(), out.c_str());
    return 0;
}
