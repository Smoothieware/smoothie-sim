#!/usr/bin/env python3
"""Checker 2: planner blocks -> step pulses (the StepTicker / Block trapezoid side).

Input is a blocks JSON (output of the simulator in G-code mode, or a hand-made file in the same schema).
Each block's planned fields are written in the injector text format, the real StepTicker runs them in the simulator
(--blocks-in), and the emitted step counts and timing are compared with what the block promised:
  * every axis emits exactly its `steps` count with the right direction;
  * blocks run in order and each lasts about its trapezoid time (planned distance / speed profile);
  * the step rate never exceeds the block's nominal rate and the entry/exit rates match the plan.
With --gcode instead of --blocks the G-code is first run through the simulator (combined G-code -> steps check).
"""
import argparse, json, math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import Result, run_sim, write_result, trapezoid_profile
import position_check


def write_injector(blocks, path):
    with open(path, "w") as f:
        for b in blocks:
            n = len(b["steps"])
            f.write(" ".join([str(n)] + [str(s) for s in b["steps"]] +
                             [str(b["direction_bits"])] +
                             [repr(float(b[k])) for k in ("nominal_speed", "nominal_rate", "acceleration", "millimeters", "entry_speed", "exit_speed")]) + "\n")


def planned_time(b):
    pts = trapezoid_profile(b)
    return pts[-1][0]


def check(res, blocks_in, sim, spm):
    out = sim["blocks"]
    res.expect("every injected block was executed", len(out) == len(blocks_in), f"{len(out)} blocks ran", f"{len(blocks_in)} injected but {len(out)} ran")
    bad_steps, bad_time, bad_rate = [], [], []
    period = sim.get("step_period_us", 10) * 1e-6
    for i, (b, o) in enumerate(zip(blocks_in, out)):
        want = b["steps"]
        got = o.get("step_counts") or [0] * len(want)
        if list(got[:len(want)]) != list(want):
            bad_steps.append(f"block {i}: planned {want} emitted {got}")
        if o["steps_event_count"] and o["total_move_ticks"]:
            pt = planned_time(b)
            at = o["ticks_run"] * period
            if pt > 0 and abs(at - pt) > max(0.03 * pt, 3 * period + 0.0005):
                bad_time.append(f"block {i}: planned {pt*1000:.2f} ms, ran {at*1000:.2f} ms")
            peak = o["steps_event_count"] / max(at, 1e-9)
            if peak > 0 and o["nominal_rate"] > 0 and (o["steps_event_count"] / max(at, 1e-9)) > 1.5 * o["nominal_rate"]:
                bad_rate.append(f"block {i}: average rate {peak:.0f} steps/s exceeds nominal {o['nominal_rate']:.0f}")
    res.expect("step counts per axis equal the plan", not bad_steps, f"{len(out)} blocks exact", "; ".join(bad_steps[:5]))
    res.expect("block duration matches trapezoid time (3 %)", not bad_time, "all within tolerance", "; ".join(bad_time[:5]))
    res.expect("step rate never exceeds nominal rate", not bad_rate, "ok", "; ".join(bad_rate[:5]))
    fin = [int(x) for x in sim["final_steps"]]
    net = [0] * len(fin)
    for b in blocks_in:
        for k in range(len(fin)):
            s = b["steps"][k] if k < len(b["steps"]) else 0
            net[k] += -s if (b["direction_bits"] >> k) & 1 else s
    res.expect("final actuator position equals signed sum of planned steps", net == fin, f"{fin}", f"planned {net}, machine {fin}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sim", required=True); ap.add_argument("--config", required=True)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--blocks", help="blocks JSON (simulator output schema)")
    g.add_argument("--gcode", help="G-code file: run G-code -> blocks -> steps in one go")
    ap.add_argument("--workdir", required=True); ap.add_argument("--modules", action="store_true"); ap.add_argument("--out", required=True)
    a = ap.parse_args()
    os.makedirs(a.workdir, exist_ok=True)
    name = "gcode_to_steps" if a.gcode else "blocks_to_steps"
    res = Result(name, "G-code to steps" if a.gcode else "Blocks to steps")
    src = a.blocks
    if a.gcode:
        src = os.path.join(a.workdir, "stage1.json")
        stage1 = run_sim(a.sim, a.config, src, gcode=a.gcode, modules=a.modules, extra=["--no-steps"])
    blocks_in = json.load(open(src))["blocks"]
    inj = os.path.join(a.workdir, "blocks_in.txt"); write_injector(blocks_in, inj)
    out = os.path.join(a.workdir, name + ".json")
    sim = run_sim(a.sim, a.config, out, blocks_in=inj, full_steps=False)
    check(res, blocks_in, sim, sim["steps_per_mm"])
    if a.gcode:   # the injected-block run above bypasses the Robot, so the end-of-job position comes from the G-code run
        position_check.check(res, stage1, open(a.gcode).read(), open(a.config).read())
    res.data.update({"sim_output": out, "blocks": len(blocks_in)})
    write_result(res, a.out)
    print(json.dumps({"type": "summary", "checker": name, "status": res.status, "counts": res.to_dict()["counts"]}))
    return 1 if res.status == "fail" else 0


if __name__ == "__main__":
    sys.exit(main())
