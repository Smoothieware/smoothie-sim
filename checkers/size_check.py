#!/usr/bin/env python3
"""Checker 4: flash and RAM use of a firmware build compared with a reference build.

Inputs are two ELF files (reference = e.g. the PR's base branch, candidate = the PR) built with the
same toolchain and make options. Sizes come from `arm-none-eabi-size -A`; per-symbol growth from
`arm-none-eabi-nm --size-sort -S`. For tests, pre-captured text can be given instead of ELFs
(--ref-size-file / --cand-size-file, optional --ref-nm-file / --cand-nm-file).

Memory classes (LPC1769 map): flash 0x00000000-0x0007FFFF, main RAM 0x10000000-0x10007FFF,
AHB RAM 0x2007C000-0x2008FFFF. Flash used = sections placed in flash (.text, .ARM.*, .data load image);
RAM used = .data + .bss + other sections placed in RAM. Heap and stack are not static, so they are
not counted here; the free-heap figure on a real board still has to be read with `M[...]` / `mem`.
"""
import argparse, json, subprocess, sys

FLASH = (0x0, 0x80000)
RAMS = {"ram": (0x10000000, 0x10008000), "ahb_ram": (0x2007C000, 0x20090000)}


def run(cmd):
    return subprocess.run(cmd, check=True, capture_output=True, text=True).stdout


def parse_size_a(text):
    """Return list of (section, size, address) from `size -A` output."""
    out = []
    for line in text.splitlines():
        p = line.split()
        if len(p) == 3 and p[1].isdigit() and p[2].isdigit() and not line.startswith("Total"):
            out.append((p[0], int(p[1]), int(p[2])))
    return out


def classify(sections, data_load_size=0):
    use = {"flash": 0, "ram": 0, "ahb_ram": 0}
    by_section = {}
    for name, size, addr in sections:
        if size == 0 or addr == 0 and name not in (".text", ".isr_vector"):
            if not (name == ".text" or name == ".isr_vector"):
                continue
        if FLASH[0] <= addr < FLASH[1]:
            use["flash"] += size
            by_section[name] = ("flash", size)
            continue
        for k, (lo, hi) in RAMS.items():
            if lo <= addr < hi:
                use[k] += size
                by_section[name] = (k, size)
                # initialised data also occupies flash as the load image
                if name == ".data" or name.startswith(".data"):
                    use["flash"] += size
    return use, by_section


def parse_nm(text):
    syms = {}
    for line in text.splitlines():
        p = line.split(None, 3)
        if len(p) == 4 and p[2].lower() in "tdbrwv":
            try:
                size = int(p[1], 16)
            except ValueError:
                continue
            if size > 0x1000000:   # linker markers (for example __end_bss_RAM5) are addresses, not sizes: larger than any MCU memory
                continue
            syms[p[3]] = (size, p[2])
    return syms


def load(elf, size_file, nm_file, tool_prefix):
    size_txt = open(size_file).read() if size_file else run([tool_prefix + "size", "-A", elf])
    if nm_file:
        nm_txt = open(nm_file).read()
    elif elf:
        nm_txt = run([tool_prefix + "nm", "--size-sort", "-S", "-C", elf])
    else:
        nm_txt = ""
    use, secs = classify(parse_size_a(size_txt))
    return use, secs, parse_nm(nm_txt)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ref-elf"); ap.add_argument("--cand-elf")
    ap.add_argument("--ref-size-file"); ap.add_argument("--cand-size-file")
    ap.add_argument("--ref-nm-file"); ap.add_argument("--cand-nm-file")
    ap.add_argument("--tool-prefix", default="arm-none-eabi-")
    ap.add_argument("--max-flash-increase", type=int, default=None, help="bytes; fail above this")
    ap.add_argument("--max-ram-increase", type=int, default=None, help="bytes (RAM + AHB RAM); fail above this")
    ap.add_argument("--top", type=int, default=15)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    if not ((a.ref_elf or a.ref_size_file) and (a.cand_elf or a.cand_size_file)):
        ap.error("need a reference and a candidate (ELF or size file)")
    ru, rs, rsym = load(a.ref_elf, a.ref_size_file, a.ref_nm_file, a.tool_prefix)
    cu, cs, csym = load(a.cand_elf, a.cand_size_file, a.cand_nm_file, a.tool_prefix)
    rows = []
    for k, label in (("flash", "Flash"), ("ram", "RAM"), ("ahb_ram", "AHB RAM")):
        rows.append({"memory": label, "reference": ru[k], "candidate": cu[k], "delta": cu[k] - ru[k],
                     "percent": round(100.0 * (cu[k] - ru[k]) / ru[k], 3) if ru[k] else None})
    changes = []
    for n in set(rsym) | set(csym):
        r = rsym.get(n, (0, "-")); c = csym.get(n, (0, "-"))
        if r[0] != c[0]:
            changes.append({"symbol": n, "reference": r[0], "candidate": c[0], "delta": c[0] - r[0], "kind": c[1] if c[0] else r[1]})
    changes.sort(key=lambda x: -abs(x["delta"]))
    ram_delta = rows[1]["delta"] + rows[2]["delta"]
    problems = []
    if a.max_flash_increase is not None and rows[0]["delta"] > a.max_flash_increase:
        problems.append(f"flash grew by {rows[0]['delta']} bytes (limit {a.max_flash_increase})")
    if a.max_ram_increase is not None and ram_delta > a.max_ram_increase:
        problems.append(f"RAM grew by {ram_delta} bytes (limit {a.max_ram_increase})")
    result = {"checker": "size", "status": "fail" if problems else "pass", "problems": problems,
              "summary": ", ".join(f"{r['memory']} {r['delta']:+d} B" for r in rows),
              "rows": rows, "top_symbol_changes": changes[:a.top], "limits": {"flash": a.max_flash_increase, "ram": a.max_ram_increase}}
    json.dump(result, open(a.out, "w"), indent=1)
    print(result["summary"], "->", result["status"])
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
