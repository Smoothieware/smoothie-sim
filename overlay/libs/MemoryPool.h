// Simulator replacement: pools are plain heap allocations on the host.
#ifndef _MEMORYPOOL_H
#define _MEMORYPOOL_H
#include <cstdint>
#include <cstdlib>
class StreamOutput;
class MemoryPool {
public:
    MemoryPool() {}
    void *alloc(size_t n) { return malloc(n); }
    void dealloc(void *p) { ::free(p); }
    void debug(StreamOutput *) {}
    bool has(void *) { return false; }
    uint32_t free(void) { return 65535; }
};
inline void *operator new(size_t n, MemoryPool &pool) { return pool.alloc(n); }
inline void operator delete(void *p, MemoryPool &pool) { pool.dealloc(p); }
#endif
