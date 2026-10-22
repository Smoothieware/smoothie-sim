// Allocation trace: every new / new[] / delete and every malloc / calloc / realloc / free called from the firmware objects
// is logged with its host size and the call stack, so checkers/memory_check.py can replay it on a model of the LPC1768 SRAM.
//   - operator new / delete are replaced here (they are link-time replaceable);
//   - direct malloc / free calls are caught with the linker option -Wl,--wrap=malloc,... (see the Makefile), which only
//     rewrites references in the simulator and firmware objects, never the ones inside libc and libstdc++.
// Trace format, one text line per event (the load base lets the checker turn a return address into a symbol):
//   B <load base hex>
//   a <id> <host bytes> <pool 0|1> <return address offsets hex ...>
//   f <id>
#include "sim_alloc.h"
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <new>
#include <unordered_map>
#include <vector>
#include <execinfo.h>
#include <link.h>

namespace {
struct Event { char op; uint32_t id, size; uint8_t pool, depth; uint64_t frames[10]; };
bool tracing = false;
thread_local bool in_hook = false;   // our own bookkeeping allocates too: never trace that
uint32_t next_id = 1;
uintptr_t load_base = 0;
std::vector<Event> *events = nullptr;
std::unordered_map<void *, uint32_t> *live = nullptr;

int base_cb(struct dl_phdr_info *info, size_t, void *) { load_base = info->dlpi_addr; return 1; }   // the first entry is the executable

void record_alloc(void *p, size_t size) {
    if (!tracing || in_hook || !p) return;
    in_hook = true;
    Event e{}; e.op = 'a'; e.id = next_id++; e.size = (uint32_t)size;
    void *bt[12]; int n = backtrace(bt, 12);
    for (int i = 2; i < n && e.depth < 10; i++) e.frames[e.depth++] = (uint64_t)((uintptr_t)bt[i] - load_base);   // skip the hook and backtrace()
    events->push_back(e); (*live)[p] = e.id;
    in_hook = false;
}
void record_free(void *p) {
    if (!tracing || in_hook || !p) return;
    in_hook = true;
    auto it = live->find(p);
    if (it != live->end()) { Event e{}; e.op = 'f'; e.id = it->second; events->push_back(e); live->erase(it); }
    in_hook = false;
}
}

void sim_alloc_note_pool(void *p, int pool) {
    if (!tracing || in_hook || !p) return;
    in_hook = true;
    auto it = live->find(p);
    if (it != live->end()) for (auto i = events->size(); i-- > 0;) if ((*events)[i].op == 'a' && (*events)[i].id == it->second) { (*events)[i].pool = (uint8_t)pool; break; }
    in_hook = false;
}

void sim_alloc_start() {
    in_hook = true;
    dl_iterate_phdr(base_cb, nullptr);
    events = new std::vector<Event>(); live = new std::unordered_map<void *, uint32_t>();
    events->reserve(1 << 16);
    void *warm[2]; backtrace(warm, 2);   // the first call loads libgcc, which allocates
    in_hook = false; tracing = true;
}

void sim_alloc_write(const char *path) {
    tracing = false;
    FILE *f = fopen(path, "w"); if (!f) { perror(path); return; }
    fprintf(f, "B %llx\n", (unsigned long long)load_base);
    for (auto &e : *events) {
        if (e.op == 'f') { fprintf(f, "f %u\n", e.id); continue; }
        fprintf(f, "a %u %u %d", e.id, e.size, e.pool);
        for (int i = 0; i < e.depth; i++) fprintf(f, " %llx", (unsigned long long)e.frames[i]);
        fputc('\n', f);
    }
    fclose(f);
}

extern "C" void *__real_malloc(size_t); extern "C" void __real_free(void *);   // plain libc: the wrappers below must not record twice
void *operator new(size_t n) { void *p = __real_malloc(n ? n : 1); if (!p) throw std::bad_alloc(); record_alloc(p, n); return p; }
void *operator new[](size_t n) { void *p = __real_malloc(n ? n : 1); if (!p) throw std::bad_alloc(); record_alloc(p, n); return p; }
void *operator new(size_t n, const std::nothrow_t &) noexcept { void *p = __real_malloc(n ? n : 1); record_alloc(p, n); return p; }
void *operator new[](size_t n, const std::nothrow_t &) noexcept { void *p = __real_malloc(n ? n : 1); record_alloc(p, n); return p; }
void operator delete(void *p) noexcept { record_free(p); __real_free(p); }
void operator delete[](void *p) noexcept { record_free(p); __real_free(p); }
void operator delete(void *p, size_t) noexcept { record_free(p); __real_free(p); }
void operator delete[](void *p, size_t) noexcept { record_free(p); __real_free(p); }

extern "C" {
void *__real_malloc(size_t); void *__real_calloc(size_t, size_t); void *__real_realloc(void *, size_t); void __real_free(void *);
void *__wrap_malloc(size_t n) { void *p = __real_malloc(n); record_alloc(p, n); return p; }
void *__wrap_calloc(size_t a, size_t b) { void *p = __real_calloc(a, b); record_alloc(p, a * b); return p; }
void *__wrap_realloc(void *old, size_t n) {
    if (old) record_free(old);
    void *p = __real_realloc(old, n); record_alloc(p, n); return p;
}
void __wrap_free(void *p) { record_free(p); __real_free(p); }
}
