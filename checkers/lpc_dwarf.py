"""Sizes of named classes, structs and unions read from a readelf DWARF dump (ARM firmware ELF or the host simulator).
# Adapted from the Carvera Firmware Simulator (https://github.com/f355/carvera_firmware_simulator, scripts/lpc_memory_layout.py),
# Copyright (c) 2026 Konstantin Tcepliaev <f355@f355.org>, GNU General Public License version 3 or (at your option) any later version.
# Changes for smoothie-sim: upstream Smoothieware linker symbols and memory regions, type sizes of every class found in both builds.
"""
import re, subprocess

_DIE = re.compile(r"^\s*<\d+><[0-9a-fA-F]+>:\s+Abbrev Number:.*\(DW_TAG_(?:class_type|structure_type|union_type)\)")
_ANY_DIE = re.compile(r"^\s*<\d+><[0-9a-fA-F]+>:")
_ATTR = re.compile(r"DW_AT_(?P<name>name|byte_size)\s*:\s*(?P<value>.+?)\s*$")


def _attr_text(raw):
    return raw.rsplit("): ", 1)[1].strip() if "): " in raw else raw.strip()


def parse_type_sizes(readelf_lines, wanted=None):
    """{type name: byte size}; wanted limits the names kept. Raises when one name has two different sizes in the same ELF."""
    sizes, name, size, in_type = {}, None, None, False

    def finish():
        if name is None or size is None or (wanted is not None and name not in wanted):
            return
        if sizes.get(name, size) != size:
            sizes[name] = max(sizes[name], size)   # same name in different scopes: keep the larger, the checker reports sizes as an upper bound
        else:
            sizes[name] = size

    for line in readelf_lines:
        if _ANY_DIE.match(line):
            finish(); name = size = None; in_type = _DIE.match(line) is not None
            continue
        if not in_type:
            continue
        m = _ATTR.search(line)
        if m is None:
            continue
        value = _attr_text(m.group("value"))
        if m.group("name") == "name":
            name = value
        else:
            size = int(value, 0)
    finish()
    return dict(sorted(sizes.items()))


def elf_type_sizes(readelf, elf, wanted=None):
    """Run readelf on an ELF and parse its type sizes line by line (the dump of a firmware is large)."""
    p = subprocess.Popen([readelf, "--debug-dump=info", elf], stdout=subprocess.PIPE, text=True, errors="replace")
    sizes = parse_type_sizes(p.stdout, wanted)
    p.wait()
    return sizes
