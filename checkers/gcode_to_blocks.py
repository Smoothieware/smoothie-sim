#!/usr/bin/env python3
"""Checker 1: G-code -> planner blocks (everything before step generation).

Runs the real Smoothieware serial/G-code/Robot/Planner code in the simulator and checks the blocks it queues:
  * independent invariants (need no reference): end position, step conservation, distance, speed limits,
    acceleration limit between entry and exit speed, junction continuity, trapezoid sanity;
  * optional comparison with a stored reference run (golden blocks or a base-branch run) within a tolerance.
"""
import argparse, json, math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import Result, run_sim, write_result, parse_gcode_endpoints

REL = 1e-4          # relative tolerance for float fields compared with a reference
ABS = 1e-3


def close(a, b, rel=REL, ab=ABS):
    return abs(a - b) <= max(ab, rel * max(abs(a), abs(b)))


def check_invariants(res, sim, gcode, cartesian):
    blocks, spm = sim["blocks"], sim["steps_per_mm"]
    n = len(spm)
    res.expect("blocks produced", len(blocks) > 0, f"{len(blocks)} blocks", "no blocks were queued")
    # step conservation: simulator's final step counters == signed sum of block steps
    net = [0] * n
    for b in blocks:
        for i in range(n):
            s = b["steps"][i] if i < len(b["steps"]) else 0
            net[i] += -s if (b["direction_bits"] >> i) & 1 else s
    res.expect("signed block steps add up to the final actuator position", net == [int(x) for x in sim["final_steps"]],
               f"net steps {net}", f"blocks give {net} but machine ended at {sim['final_steps']}")
    # independent end-point model of the G-code
    if gcode:
        pos, moves = parse_gcode_endpoints(gcode)
        if cartesian:
            exp = [round(pos[a] * spm[i]) for i, a in enumerate("XYZE"[:n])]
            tol = max(2, len(blocks))   # each planned block rounds its target to whole steps
            ok = all(abs(exp[i] - net[i]) <= tol for i in range(len(exp)))
            res.expect("end position matches the G-code (independent parser)", ok, f"expected steps {exp}, got {net}", f"expected steps {exp}, got {net} (tolerance {tol})")
    bad = []
    for i, b in enumerate(blocks):
        sec = f"block {i} (line {b['gcode_line']})"
        if b["steps_event_count"] != max(b["steps"]): bad.append(f"{sec}: steps_event_count {b['steps_event_count']} != max(steps)")
        if b["nominal_speed"] > 0 and not close(b["nominal_rate"], b["steps_event_count"] * b["nominal_speed"] / b["millimeters"], 1e-3, 0.5):
            bad.append(f"{sec}: nominal_rate {b['nominal_rate']:.2f} inconsistent with speed/distance")
        if b["entry_speed"] > b["nominal_speed"] * 1.0001 + 1e-3 or b["exit_speed"] > b["nominal_speed"] * 1.0001 + 1e-3:
            bad.append(f"{sec}: entry {b['entry_speed']:.3f}/exit {b['exit_speed']:.3f} above nominal {b['nominal_speed']:.3f}")
        reach = abs(b["exit_speed"] ** 2 - b["entry_speed"] ** 2) / (2 * b["acceleration"]) if b["acceleration"] > 0 else 0
        if reach > b["millimeters"] * 1.001 + 1e-3:
            bad.append(f"{sec}: speed change {b['entry_speed']:.2f}->{b['exit_speed']:.2f} needs {reach:.3f} mm at {b['acceleration']} mm/s2, block is {b['millimeters']:.3f} mm")
        if not (b["accelerate_until"] <= b["decelerate_after"] <= max(b["total_move_ticks"], b["decelerate_after"])):
            bad.append(f"{sec}: trapezoid ticks out of order ({b['accelerate_until']}, {b['decelerate_after']}, {b['total_move_ticks']})")
        if b["max_entry_speed"] + 1e-3 < b["entry_speed"]:
            bad.append(f"{sec}: entry speed {b['entry_speed']:.3f} above junction limit {b['max_entry_speed']:.3f}")
        if cartesian and b["is_g123"] and b["millimeters"] > 0:
            d = math.sqrt(sum((b["steps"][k] / spm[k]) ** 2 for k in range(min(3, n))))
            if b["steps_event_count"] > 3 and not close(d, b["millimeters"], 2e-3, 2.0 / min(spm[:3])):
                bad.append(f"{sec}: length {b['millimeters']:.4f} mm but steps imply {d:.4f} mm")
    res.expect("per-block planner invariants (rates, limits, trapezoid)", not bad, f"{len(blocks)} blocks checked", "; ".join(bad[:8]) + (f" (+{len(bad)-8} more)" if len(bad) > 8 else ""))
    # junction continuity: exit of one block == entry of the next (the planner may only lower the exit via look-ahead before the next arrives)
    jb = []
    for i in range(len(blocks) - 1):
        a, b = blocks[i], blocks[i + 1]
        if not close(a["exit_speed"], b["entry_speed"], 1e-3, 0.05): jb.append(f"{i}->{i+1}: exit {a['exit_speed']:.3f} vs entry {b['entry_speed']:.3f}")
    res.expect("junction speeds continuous between blocks", not jb, "all junctions continuous", "; ".join(jb[:6]))
    if blocks:
        res.expect("machine starts and ends at rest", blocks[0]["entry_speed"] < 1e-3 and blocks[-1]["exit_speed"] < 1e-3,
                   "entry of first and exit of last block are 0", f"first entry {blocks[0]['entry_speed']}, last exit {blocks[-1]['exit_speed']}")


FIELDS = ["steps", "nominal_rate", "nominal_speed", "millimeters", "entry_speed", "exit_speed", "acceleration", "initial_rate",
          "maximum_rate", "accelerate_until", "decelerate_after", "total_move_ticks", "direction_bits"]


def compare(res, sim, ref, label):
    a, b = sim["blocks"], ref["blocks"]
    res.expect(f"block count equals {label}", len(a) == len(b), f"{len(a)} blocks", f"{len(a)} blocks vs {len(b)} in {label}")
    diffs = []
    for i, (x, y) in enumerate(zip(a, b)):
        for f in FIELDS:
            xv, yv = x[f], y[f]
            if isinstance(xv, list):
                if len(xv) != len(yv) or any(not close(p, q) for p, q in zip(xv, yv)): diffs.append({"block": i, "field": f, "got": xv, "ref": yv})
            elif f in ("accelerate_until", "decelerate_after", "total_move_ticks"):
                if abs(xv - yv) > max(2, 1e-4 * abs(yv)): diffs.append({"block": i, "field": f, "got": xv, "ref": yv})
            elif not close(xv, yv): diffs.append({"block": i, "field": f, "got": xv, "ref": yv})
    res.expect(f"every block field equals {label} (rel {REL})", not diffs, "no differences",
               f"{len(diffs)} differing fields, first: " + "; ".join(f"block {d['block']} {d['field']} {d['got']} vs {d['ref']}" for d in diffs[:4]))
    res.data["diffs_vs_" + label.replace(" ", "_")] = diffs[:200]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sim", required=True, help="smoothie-sim binary under test")
    ap.add_argument("--config", required=True); ap.add_argument("--gcode", required=True)
    ap.add_argument("--workdir", required=True, help="scratch folder for simulator output")
    ap.add_argument("--reference", help="blocks JSON of a reference run (simulator output) to compare with")
    ap.add_argument("--cartesian", action="store_true", help="enable geometry checks valid for Cartesian kinematics")
    ap.add_argument("--modules", action="store_true"); ap.add_argument("--out", required=True)
    a = ap.parse_args()
    os.makedirs(a.workdir, exist_ok=True)
    sim = run_sim(a.sim, a.config, os.path.join(a.workdir, "gcode_to_blocks.json"), gcode=a.gcode, modules=a.modules, extra=["--no-steps"])
    res = Result("gcode_to_blocks", "G-code to blocks")
    check_invariants(res, sim, a.gcode, a.cartesian)
    if a.reference:
        compare(res, sim, json.load(open(a.reference)), "reference")
    res.data.update({"sim_output": os.path.join(a.workdir, "gcode_to_blocks.json"), "blocks": len(sim["blocks"])})
    write_result(res, a.out)
    print(json.dumps({"type": "summary", "checker": res.name, "status": res.status, "counts": res.to_dict()["counts"]}))
    return 1 if res.status == "fail" else 0


if __name__ == "__main__":
    sys.exit(main())
