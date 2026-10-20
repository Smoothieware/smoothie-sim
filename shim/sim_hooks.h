// Hooks inserted into the staged firmware by stage_patch.py.
#pragma once
#include "Module.h"
class Block;
void sim_event_begin(int event, Module *m);
void sim_event_end(int event, Module *m);
void sim_block_started(Block *b);
void sim_block_queued(void);   // a planned block was handed to the conveyor queue
// RAII marker: the enclosing firmware call blocks the caller until the machine catches up (wait_for_idle and similar)
struct SimWaitScope {
    const char *kind; unsigned long long start_us; int frame;
    explicit SimWaitScope(const char *k);
    ~SimWaitScope();
};
