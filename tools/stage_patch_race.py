#!/usr/bin/env python3
"""Race mode patches for the STAGED firmware: rebuild the Block flag bits from SimBit proxies (same byte sharing as the tree
under test: read from that tree's own Block.h, so old and fixed layouts are both simulated faithfully) and add a witness that
records when the step ISR really started a block, so a later re-plan of it can be detected."""
import sys, re, pathlib
root = pathlib.Path(sys.argv[1])

bh = root / "modules/robot/Block.h"
t = bh.read_text()
m = re.search(r"        struct \{\n(            (?:volatile )?bool recalculate_flag:1;.*?)        \};\n", t, re.S)
if not m: sys.exit("stage_patch_race: flag struct not found in Block.h")
body = m.group(1)
out, idx, s_value_line = [], 0, None
for line in body.splitlines():
    if "s_value" in line: s_value_line = line; continue
    mm = re.match(r"(\s+)(?:volatile )?bool (\w+):1;(.*)", line)
    if mm:
        out.append(f"{mm.group(1)}SimBit<{idx}> {mm.group(2)};{mm.group(3)}"); idx += 1
    else:
        out.append(line)   # comments
new = "        union {\n            uint8_t sim_raw;\n" + "\n".join(out) + "\n        };\n"
if s_value_line: new += s_value_line.replace("            ", "        ", 1) + "\n"
t = t.replace(m.group(0), new)
t = t.replace("        static uint8_t n_actuators;", "        bool sim_started= false;   // simulator witness: the step ISR started this block\n        static uint8_t n_actuators;", 1)
t = t.replace("#include <bitset>", "#include <bitset>\n#include \"sim_race.h\"", 1)
if t.count("sim_started") != 1 or "SimBit<5>" not in t: sys.exit("stage_patch_race: Block.h patch failed")
bh.write_text(t)

def sub(rel, old, new, count=1):
    p = root / rel; s = p.read_text()
    if s.count(old) != count: sys.exit(f"stage_patch_race: {rel}: {old[:50]!r} count={s.count(old)} expected {count}")
    p.write_text(s.replace(old, new))
sub("modules/robot/Conveyor.cpp", "b->is_ticking= true;", "b->is_ticking= true; b->sim_started= true;", 2)
sub("modules/robot/Block.cpp", "void Block::clear()\n{\n", "void Block::clear()\n{\n    sim_started = false;\n")
sub("modules/robot/Block.cpp", "    // if block is currently executing, don't touch anything!\n    if (is_ticking) return;",
    "    // if block is currently executing, don't touch anything!\n    if (sim_started && !is_ticking) sim_race_replan_of_started(this);\n    if (is_ticking) return;")
print("stage_patch_race: applied")
