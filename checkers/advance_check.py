#!/usr/bin/env python3
"""Checker 4: filament advance (pressure advance for the extruder), run on the REAL planner and step ticker.

Needs a simulator built from a firmware tree that has FilamentAdvance (a 3D printer build, not CNC). Two checks:

  A. chain.gcode: a mixed print (squares with extrusion, a retract, a travel, a prime, K changed mid-file) is run
     twice, once with the shaping on and once with `M900 K0` first. For every block the extruder emits:
       * net steps (forward minus backward, from the direction changes) == nominal steps + lead_out - lead_in;
       * blocks that are not shaped (retract, prime, travel) are untouched;
       * a flip tick, if any, has no step pulse in it, and a block has a backward step iff it has a flip;
       * block durations stay within 0.1% (+100 ticks) of the unshaped run: the head does not slow down;
     and the whole chain ends with lead 0 and identical final extruder position in both runs.
  B. one 100 mm move at three accelerations and three K values: the extruder gets ahead of the nominal position by
     K x cruise rate (within 2 steps) at the end of the acceleration, and ends exactly where the unshaped run ends.
     (Regression test for ramps shorter than K: at 3000 mm/s^2 the ramp lasts 17 ms, K is 50 ms.)
"""
import argparse, bisect, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import Result, run_sim, write_result

E = 3                      # actuator index of the first extruder (alpha, beta, gamma, then the extruder)
NO_FLIP = 4e9              # the simulator reports "never reverses" as 0xFFFFFFFF


def positions(block):
    """Signed extruder position after each of its steps, rebuilt from the recorded direction changes."""
    ticks, changes = block["step_ticks"][E], block["dir_changes"][E]
    pos, p, j = [], 0, 0
    for i in range(len(ticks)):
        while j + 1 < len(changes) and changes[j + 1][0] <= i:
            j += 1
        p += changes[j][1]
        pos.append(p)
    return ticks, pos


def at(ticks, pos, t):
    k = bisect.bisect_right(ticks, t)
    return pos[k - 1] if k else 0


def check_chain(res, sim, work, cfg, gcode):
    text = open(gcode).read()
    with open(work + "/chain_off.gcode", "w") as f:
        f.write("M900 K0\n" + re.sub(r"(?m)^M900.*\n", "", text))
    on = run_sim(sim, cfg, work + "/chain_on.json", gcode=gcode, modules=True)["blocks"]
    off_run = run_sim(sim, cfg, work + "/chain_off.json", gcode=work + "/chain_off.gcode", modules=True)
    off = off_run["blocks"]
    res.expect("chain: same number of blocks with and without shaping", len(on) == len(off), f"{len(on)} blocks", f"{len(on)} vs {len(off)}")
    lead, bad, shaped_n, flips = 0, [], 0, 0
    nom_total = net_total = 0
    for i, (b, n) in enumerate(zip(on, off)):
        steps = b["step_counts"][E]
        _, pos = positions(b) if b["step_ticks"][E] else ([], [0])
        net = pos[-1] if b["step_ticks"][E] else 0
        nominal = n["step_counts"][E] * (-1 if n["direction_bits"] & (1 << E) else 1)
        nom_total, net_total = nom_total + nominal, net_total + net
        flip = b["flip_tick"][E]; flip = None if flip >= NO_FLIP else int(flip)
        if E in b.get("advance_motors", []):
            shaped_n += 1
            if net != nominal + b["advance_lead"][E] - lead:
                bad.append(f"block {i}: net {net} != nominal {nominal} + lead_out {b['advance_lead'][E]} - lead_in {lead}")
            lead = b["advance_lead"][E]
            backward = any(sg < 0 for _, sg in b["dir_changes"][E])
            if flip is not None:
                flips += 1
                if flip in b["step_ticks"][E]: bad.append(f"block {i}: a step pulse in the flip tick {flip}")
            if backward != (flip is not None): bad.append(f"block {i}: backward step {backward} but flip tick {flip}")
        elif b["primary_axis"] and net != nominal:
            bad.append(f"block {i}: unshaped block moved {net} steps, nominal {nominal}")
        if abs(b["ticks_run"] - n["ticks_run"]) > 100 + n["ticks_run"] // 1000:
            bad.append(f"block {i}: lasted {b['ticks_run']} ticks, unshaped {n['ticks_run']}")
    res.expect("chain: every block makes the planned net steps, unshaped blocks untouched, flips clean, durations kept",
               not bad, f"{len(on)} blocks, {shaped_n} shaped, {flips} reversals", "; ".join(bad))
    res.expect("chain: lead returns to 0 and nominal total equals net total", lead == 0 and nom_total == net_total,
               f"net {net_total} == nominal {nom_total}", f"end lead {lead}, net {net_total} vs nominal {nom_total}")
    res.expect("chain: final positions identical with and without shaping",
               run_sim(sim, cfg, work + "/chain_on2.json", gcode=gcode, modules=True)["final_steps"] == off_run["final_steps"],
               "same final_steps", "final_steps differ")
    res.expect("chain: the file exercises reversals and K changes", flips >= 2 and shaped_n >= 8, f"{flips} reversals", f"only {flips} reversals, {shaped_n} shaped blocks")


def check_sweep(res, sim, work, cfg):
    base, bad, rows = open(cfg).read(), [], []
    for accel in (500, 1000, 3000):
        conf = work + f"/sweep_{accel}.txt"
        open(conf, "w").write(re.sub(r"(?m)^acceleration \d+", f"acceleration {accel}", base))
        off = run_sim(sim, conf, work + "/s_off.json", gcode=write(work, "s_off.gcode", "M900 K0\nG1 X100 E5 F3000\n"), modules=True)["blocks"][0]
        so, po = positions(off)
        cruise = 5 * 140 / (100 / 50.0)            # extruder steps/s at 50 mm/s: 5 mm of filament over 100 mm
        for k in (0.02, 0.05, 0.10):
            on = run_sim(sim, conf, work + "/s_on.json", gcode=write(work, "s_on.gcode", f"M900 K{k}\nG1 X100 E5 F3000\n"), modules=True)["blocks"][0]
            sa, pa = positions(on)
            peak = max(at(sa, pa, t) - at(so, po, t) for t in range(0, on["ticks_run"], 50))
            want = k * cruise
            rows.append(f"{accel}/{k}: lead {peak} (want {want:.1f})")
            if abs(peak - want) > 2: bad.append(f"accel {accel} K {k}: peak lead {peak}, expected {want:.1f}")
            if pa[-1] != po[-1]: bad.append(f"accel {accel} K {k}: ends at {pa[-1]}, unshaped {po[-1]}")
    res.expect("sweep: lead = K x cruise rate and exact end position at 500, 1000 and 3000 mm/s^2", not bad, "; ".join(rows), "; ".join(bad))


def write(work, name, text):
    path = os.path.join(work, name)
    open(path, "w").write(text)
    return path


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sim", required=True); ap.add_argument("--config", required=True)
    ap.add_argument("--gcode", required=True); ap.add_argument("--workdir", required=True); ap.add_argument("--out", required=True)
    a = ap.parse_args()
    os.makedirs(a.workdir, exist_ok=True)
    res = Result("advance", "Filament advance (real planner and step ticker)")
    check_chain(res, a.sim, a.workdir, a.config, a.gcode)
    check_sweep(res, a.sim, a.workdir, a.config)
    write_result(res, a.out)
    for c in res.checks: print(f"[{c['status']}] {c['check']}: {c['detail']}")
    sys.exit(1 if res.status == "fail" else 0)


if __name__ == "__main__":
    main()
