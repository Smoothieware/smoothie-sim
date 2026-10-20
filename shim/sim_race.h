// Race mode (-DSIM_RACE): the shared Block flag byte is rebuilt from SimBit proxies. Every write is a read-modify-write
// like the Cortex-M3 does (ldrb / orr or bic / strb), and the step interrupt may run between the read and the write.
#pragma once
#include <stdint.h>
void sim_race_preempt(void);                 // may run a due step-tick ISR right here (sim_main.cpp)
void sim_race_note_store(uint8_t lost_bits); // bits another context changed between our read and our write, now overwritten
void sim_race_replan_of_started(const void *block);
template <int N> struct SimBit {
    uint8_t b;                               // all SimBit of one flag byte live in a union, so they share this byte
    operator bool() const { return (b >> N) & 1; }
    SimBit &operator=(bool v) {
        uint8_t r = b;                       // load
        sim_race_preempt();                  // the step ISR can fire here
        uint8_t lost = (uint8_t)((b ^ r) & ~(1u << N));
        if (lost) sim_race_note_store(lost);
        b = v ? (uint8_t)(r | (1u << N)) : (uint8_t)(r & ~(1u << N));   // store
        return *this;
    }
};
