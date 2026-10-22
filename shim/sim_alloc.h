// Allocation trace of the simulated firmware (see sim/sim_alloc.cpp). Off unless the simulator runs with --alloc-trace.
#pragma once
#include <stddef.h>
// The pool the firmware allocates from: the main heap (malloc / new) or the AHB SRAM pool (MemoryPool, new(AHB0) T).
void sim_alloc_note_pool(void *p, int pool);   // pool 1 = AHB pool; relabels an allocation already recorded as main heap
void sim_alloc_start();                    // begin recording (--alloc-trace)
void sim_alloc_write(const char *path);     // stop recording and write the trace file
