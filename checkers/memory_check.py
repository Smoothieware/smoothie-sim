#!/usr/bin/env python3
"""Checker: heap use of the firmware on the LPC1768, from the simulator's allocation trace.

The host simulator logs every allocation (--alloc-trace). Each one is mapped to the size it has on the ARM
(per-class sizes read from the ARM build's DWARF, see tools/lpc_memory_layout.py) and replayed on a model of the
main SRAM heap (newlib malloc: 8-byte header, 8-byte alignment, first fit, heap grows from __end__ towards the stack)
and of the AHB0 SRAM pool (the real MemoryPool: 4-byte header, sizes rounded to 4, first fit, coalescing).
Reports peak live bytes, fragmentation, the largest free block, failed allocations and the room left below the stack.
Without a layout file (no ARM build) it reports "not measured" and never fails. The idea and the heap model are adapted from
the Carvera Firmware Simulator (https://github.com/f355/carvera_firmware_simulator, include/sim/lpc_memory_accounting.hpp),
Copyright (c) 2026 Konstantin Tcepliaev <f355@f355.org>, GNU General Public License version 3 or (at your option) any later version.
"""
import argparse, json, os, re, shutil, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import Result, run_sim, write_result   # noqa: E402
from lpc_dwarf import elf_type_sizes                 # noqa: E402

HEADER_MAIN, ALIGN_MAIN, MIN_MAIN = 8, 8, 16
HEADER_AHB, ALIGN_AHB = 4, 4


class Heap:
    """First-fit heap over [start, limit). grows=True: the break rises on demand (newlib sbrk); False: fixed arena (MemoryPool)."""

    def __init__(self, start, limit, header, align, minimum, grows):
        self.start, self.limit, self.header, self.align, self.min, self.grows = start, limit, header, align, minimum, grows
        self.brk = start if grows else limit
        self.blocks = [] if grows else [[start, limit - start, False]]   # [address, size, used], sorted by address
        self.sizes, self.addr = {}, {}
        self.live = self.peak_live = self.failed = self.failed_bytes = self.max_brk = 0
        self.max_brk = start

    def block_size(self, n):
        b = max(self.min, n + self.header)
        return (b + self.align - 1) // self.align * self.align

    def alloc(self, ident, n):
        need = self.block_size(n)
        for b in self.blocks:
            if not b[2] and b[1] >= need:
                if b[1] - need >= max(self.min, self.align):
                    self.blocks.insert(self.blocks.index(b) + 1, [b[0] + need, b[1] - need, False])
                    b[1] = need
                b[2] = True
                return self._took(ident, b, n)
        if self.grows:
            last = self.blocks[-1] if self.blocks else None
            if last and not last[2]:   # extend the free block at the top
                extra = need - last[1]
                if self.brk + extra > self.limit:
                    return self._fail(n)
                self.brk += extra; last[1] = need; last[2] = True
                return self._took(ident, last, n)
            if self.brk + need > self.limit:
                return self._fail(n)
            b = [self.brk, need, True]; self.blocks.append(b); self.brk += need
            return self._took(ident, b, n)
        return self._fail(n)

    def _took(self, ident, b, n):
        self.addr[ident] = b; self.sizes[ident] = b[1]
        self.live += b[1]; self.peak_live = max(self.peak_live, self.live); self.max_brk = max(self.max_brk, self.brk)
        return True

    def _fail(self, n):
        self.failed += 1; self.failed_bytes += n
        return False

    def free(self, ident):
        b = self.addr.pop(ident, None)
        if b is None:
            return
        self.live -= self.sizes.pop(ident); b[2] = False
        i = self.blocks.index(b)
        if i + 1 < len(self.blocks) and not self.blocks[i + 1][2]:
            b[1] += self.blocks[i + 1][1]; del self.blocks[i + 1]
        if i > 0 and not self.blocks[i - 1][2]:
            self.blocks[i - 1][1] += b[1]; del self.blocks[i]; b = self.blocks[i - 1]
        if self.grows and self.blocks and self.blocks[-1] is b and not b[2]:   # trim the top free block
            self.brk -= b[1]; self.blocks.pop()

    def stats(self):
        free = [b[1] for b in self.blocks if not b[2]]
        if self.grows:   # the gap above the break counts as one free block
            free.append(self.limit - self.brk)
        return {"peak_live_bytes": self.peak_live, "live_bytes_at_end": self.live, "peak_extent_bytes": self.max_brk - self.start if self.grows else None,
                "free_bytes_at_end": sum(free) if self.grows else sum(f for f in free), "largest_free_block": max(free) if free else 0,
                "fragmented_free_bytes": sum(free) - (max(free) if free else 0), "failed_allocations": self.failed, "failed_bytes": self.failed_bytes}


def replay(events, layout):
    """events: ('a', id, arm_size, pool) / ('f', id). Returns the statistics of the main heap and the AHB pool."""
    m, a = layout["main_sram"], layout["ahb0"]
    main = Heap(m["heap_start"], m["stack_limit"], HEADER_MAIN, ALIGN_MAIN, MIN_MAIN, True)
    ahb = Heap(a["pool_start"], a["pool_end"], HEADER_AHB, ALIGN_AHB, HEADER_AHB + ALIGN_AHB, False)
    pool_of = {}
    for e in events:
        if e[0] == "a":
            _, ident, size, pool = e
            pool_of[ident] = ahb if pool else main
            pool_of[ident].alloc(ident, size)
        else:
            h = pool_of.pop(e[1], None)
            if h:
                h.free(e[1])
    ms, As = main.stats(), ahb.stats()
    ms["margin_to_stack_bytes"] = m["stack_limit"] - main.max_brk
    ms["stack_reserved_bytes"] = m["stack_top"] - m["stack_limit"]
    As["pool_bytes"] = a["pool_end"] - a["pool_start"]
    return {"main_sram": ms, "ahb0": As}


def read_trace(path):
    base, events = 0, []
    for line in open(path):
        p = line.split()
        if p[0] == "B":
            base = int(p[1], 16)
        elif p[0] == "a":
            events.append(("a", int(p[1]), int(p[2]), int(p[3]), [int(x, 16) for x in p[4:]]))
        elif p[0] == "f":
            events.append(("f", int(p[1])))
    return events


def resolve_frames(binary, offsets, base_is_pie=True):
    """{offset: (function, file)} via addr2line on the host simulator."""
    uniq = sorted(set(offsets))
    if not uniq or not shutil.which("addr2line"):
        return {}
    out = subprocess.run(["addr2line", "-f", "-C", "-e", binary] + [hex(o) for o in uniq], capture_output=True, text=True).stdout.splitlines()
    return {o: (out[2 * i], out[2 * i + 1].split(":")[0]) for i, o in enumerate(uniq) if 2 * i + 1 < len(out)}


# Containers the simulator keeps for its own recordings (sim/sim_runtime.h) are filled from patched firmware code, so the call stack alone
# cannot tell them from firmware allocations. They hold these element types; the real firmware does not allocate them this way.
SIM_ELEMENT = re.compile(r"__new_allocator<(?:SimState::\w+|BlockRec|WaitRec|(?:unsigned )?int|double|std::vector<|std::pair<unsigned int, int>|std::_Rb_tree_node<)")


def simulator_owned(funcs, files):
    """True when an allocation belongs to the simulator's own bookkeeping, not to the simulated firmware."""
    own = next((f for f in files if "/c++/" not in f and "/bits/" not in f), "")   # innermost frame outside the C++ library
    if "/sim/" in own or "/shim/" in own:
        return True
    return any(SIM_ELEMENT.search(fn) for fn in funcs[:2])


def arm_size_for(host_size, funcs, host_sizes, arm_sizes):
    """Map a host allocation size to the ARM size. Exact when a class named by the calling function has this host size."""
    for fn in funcs:
        for cls in re.findall(r"([A-Za-z_]\w*)(?:::|>|\b)", fn):
            if cls in arm_sizes and host_sizes.get(cls) == host_size:
                return arm_sizes[cls], True
    return host_size, False


def not_measured(res, why):
    res.add("RAM model", "info", f"not measured: {why}")
    res.data = {"measured": False, "reason": why}
    return res


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sim", required=True); ap.add_argument("--config", required=True); ap.add_argument("--gcode", required=True)
    ap.add_argument("--layout", help="memory layout JSON from tools/lpc_memory_layout.py (needs a real ARM build); without it nothing is measured")
    ap.add_argument("--workdir", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--min-margin", type=int, default=2048, help="warn when less than this many bytes lie between the heap and the stack")
    a = ap.parse_args()
    os.makedirs(a.workdir, exist_ok=True)
    res = Result("memory", "RAM model (heap and AHB pool)")
    if not a.layout or not os.path.exists(a.layout):
        write_result(not_measured(res, "no ARM build layout given (--layout), so the heap cannot be sized for the LPC1768"), a.out)
        return 0
    layout = json.load(open(a.layout))
    trace, js = os.path.join(a.workdir, "alloc.trace"), os.path.join(a.workdir, "run.json")
    run_sim(a.sim, a.config, js, gcode=a.gcode, extra=("--alloc-trace", trace))
    raw = read_trace(trace)
    frames = resolve_frames(a.sim, [o for e in raw if e[0] == "a" for o in e[4]])
    host_sizes = elf_type_sizes(shutil.which("readelf") or "readelf", a.sim, set(layout["type_sizes"]))
    arm = layout["type_sizes"]
    events, inexact, dropped = [], 0, 0
    for e in raw:
        if e[0] == "f":
            events.append(e); continue
        _, ident, hsize, pool, offs = e
        funcs = [frames[o][0] for o in offs if o in frames]
        files = [frames[o][1] for o in offs if o in frames]
        if simulator_owned(funcs, files) or (pool == 0 and not any("/stage/src/" in f for f in files)):
            dropped += 1; continue
        size, exact = arm_size_for(hsize, funcs, host_sizes, arm)
        inexact += 0 if exact else 1
        events.append(("a", ident, size, pool))
    st = replay(events, layout)
    m, h = st["main_sram"], st["ahb0"]
    res.data = {"measured": True, "firmware_commit": layout.get("firmware_commit", ""), "allocations": sum(1 for e in events if e[0] == "a"),
                "size_inexact": inexact, "simulator_allocations_ignored": dropped, **st}
    res.add("RAM model", "info", f"{res.data['allocations']} allocations replayed; {inexact} could not be mapped to an ARM class size and keep their host size")
    estimate = inexact > 0   # host sizes (64-bit pointers, libstdc++ strings) overstate the ARM ones, so a shortage is a warning, not a proof
    res.expect("main heap", m["failed_allocations"] == 0, f"peak live {m['peak_live_bytes']} B, largest free block {m['largest_free_block']} B", f"{m['failed_allocations']} allocations failed ({m['failed_bytes']} B)", warn_only=estimate)
    res.expect("margin to stack", m["margin_to_stack_bytes"] >= a.min_margin, f"{m['margin_to_stack_bytes']} B between the highest heap address and the stack limit", f"only {m['margin_to_stack_bytes']} B left below the stack limit (minimum {a.min_margin} B)", warn_only=True)
    res.expect("AHB0 pool", h["failed_allocations"] == 0, f"peak live {h['peak_live_bytes']} of {h['pool_bytes']} B", f"{h['failed_allocations']} allocations failed in the AHB0 pool", warn_only=estimate)
    write_result(res, a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
