#!/usr/bin/env python3
"""Extract the LPC1768 SRAM layout and the ARM size of every class from a real Smoothieware ARM build (linker map + ELF).
Output is the input of checkers/memory_check.py (--layout).
# Adapted from the Carvera Firmware Simulator (https://github.com/f355/carvera_firmware_simulator, scripts/lpc_memory_layout.py),
# Copyright (c) 2026 Konstantin Tcepliaev <f355@f355.org>, GNU General Public License version 3 or (at your option) any later version.
# Changes for smoothie-sim: upstream Smoothieware linker symbols and memory regions, type sizes of every class found in both builds.
"""
import argparse, json, os, re, shutil, subprocess, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "checkers"))
from lpc_dwarf import elf_type_sizes   # noqa: E402

_REGION = re.compile(r"^\s*(?P<name>RAM|USB_RAM|ETH_RAM)\s+(?P<origin>0x[0-9a-fA-F]+)\s+(?P<length>0x[0-9a-fA-F]+)\b", re.M)


def parse_symbol(map_text, symbol):
    for pat in (rf"^\s*(0x[0-9a-fA-F]+)\s+(?:PROVIDE\s*\(\s*)?{re.escape(symbol)}\b", rf"\b{re.escape(symbol)}\s*=\s*(0x[0-9a-fA-F]+)"):
        m = re.search(pat, map_text, re.M)
        if m:
            return int(m.group(1), 16)
    raise ValueError(f"linker map does not define {symbol}")


def build_layout(map_text, type_sizes, commit=""):
    regions = {m.group("name"): (int(m.group("origin"), 16), int(m.group("origin"), 16) + int(m.group("length"), 16)) for m in _REGION.finditer(map_text)}
    for need in ("RAM", "USB_RAM"):
        if need not in regions:
            raise ValueError(f"linker map is missing memory region {need}")
    heap_start, stack_limit, stack_top = parse_symbol(map_text, "__end__"), parse_symbol(map_text, "__StackLimit"), parse_symbol(map_text, "__StackTop")
    ahb_start, ahb_end = parse_symbol(map_text, "__AHB0_dyn_start"), parse_symbol(map_text, "__AHB0_end")
    ram = regions["RAM"]
    if not (ram[0] <= heap_start < stack_limit <= stack_top == ram[1]):
        raise ValueError("main SRAM linker symbols are inconsistent")
    if not (regions["USB_RAM"][0] <= ahb_start <= ahb_end == regions["USB_RAM"][1]):
        raise ValueError("AHB0 linker symbols are inconsistent")
    return {"schema_version": 1, "firmware_commit": commit,
            "main_sram": {"ram_start": ram[0], "ram_end": ram[1], "heap_start": heap_start, "stack_limit": stack_limit, "stack_top": stack_top},
            "ahb0": {"region_start": regions["USB_RAM"][0], "pool_start": ahb_start, "pool_end": ahb_end},
            "type_sizes": type_sizes}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--map", required=True, help="linker map of the ARM build (main.map)")
    ap.add_argument("--elf", required=True, help="ARM ELF with DWARF info (main.elf)")
    ap.add_argument("--host-elf", help="host simulator binary: only classes present in both builds are kept (smaller file)")
    ap.add_argument("--readelf", default=shutil.which("arm-none-eabi-readelf") or "arm-none-eabi-readelf")
    ap.add_argument("--commit", default="")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    wanted = None
    if a.host_elf:
        from lpc_dwarf import elf_type_sizes as host_sizes
        wanted = set(host_sizes(shutil.which("readelf") or "readelf", a.host_elf))
    layout = build_layout(open(a.map).read(), elf_type_sizes(a.readelf, a.elf, wanted), a.commit)
    json.dump(layout, open(a.out, "w"), indent=1, sort_keys=True)
    print(json.dumps({"type": "result", "layout": a.out, "types": len(layout["type_sizes"])}))


if __name__ == "__main__":
    main()
