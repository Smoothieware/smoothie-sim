// Simulator replacement: pools are plain heap allocations on the host. With --alloc-trace each one is logged as an AHB SRAM
// allocation (the real pool lives in the AHB0 bank), and checkers/memory_check.py replays it on a model of that pool.
#ifndef _MEMORYPOOL_H
#define _MEMORYPOOL_H
#include <cstdint>
#include <cstdlib>
#include "sim_alloc.h"
class StreamOutput;
class MemoryPool {
public:
    MemoryPool() {}
    void *alloc(size_t n) { void *p = malloc(n); sim_alloc_note_pool(p, 1); return p; }
    void dealloc(void *p) { ::free(p); }
    void debug(StreamOutput *) {}
    bool has(void *) { return false; }
    uint32_t free(void) { return 65535; }
};
inline void *operator new(size_t n, MemoryPool &pool) { return pool.alloc(n); }
inline void operator delete(void *p, MemoryPool &pool) { pool.dealloc(p); }
#endif
