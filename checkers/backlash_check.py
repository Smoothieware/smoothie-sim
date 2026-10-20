#!/usr/bin/env python3
"""Checker 5: backlash compensation (M425), run on the REAL Robot, planner and step ticker.

Pattern X10, X0, X10 at 80 steps/mm with 0.5 mm slack = 40 steps per reversal:
  A. M425 X0.5: block 1 has 800 steps, blocks 2 and 3 have 840 (two reversals); the run without M425 has 800 each.
  B. M425 X0.5 then M425 P0: identical to the run without compensation (P0 keeps the value but switches it off).
  C. M425 X0.5, M425 P0, M425 P1: slack is back (840 on the reversal).
  D. G92 X0 between moves does not move a motor, so the tracked direction stays valid: the reversal still gets 40 steps.
  E. A negative or > 100 mm value is ignored (800 each).
  F. Take-up profile: the 40 slack steps of the reversal block are issued early (default backlash_takeup_rate = the motor's
     maximum), well before the point where the spread-over-the-block profile (backlash_takeup_rate 0) would have issued them,
     and the block still has 840 steps, ending at the same position.
"""
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import Result, run_sim, write_result

BODY = ["G90", "G1 X10 F6000", "G1 X0", "G1 X10"]


def x_steps(sim, cfg, work, name, lines):
    path = f"{work}/{name}.gcode"
    open(path, "w").write("\n".join(lines) + "\n")
    blocks = run_sim(sim, cfg, f"{work}/{name}.json", gcode=path, modules=True)["blocks"]
    return [b["step_counts"][0] for b in blocks if b["step_counts"][0]]


def reversal_block(sim, cfg, work, name, lines):
    """The second X block (the reversal): its step count and the tick of its 40th step."""
    path = f"{work}/{name}.gcode"
    open(path, "w").write("\n".join(lines) + "\n")
    blocks = [b for b in run_sim(sim, cfg, f"{work}/{name}.json", gcode=path, modules=True)["blocks"] if b["step_counts"][0]]
    b = blocks[1]
    return b["step_counts"][0], len(b["step_ticks"][0]), b["step_ticks"][0][39]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sim", required=True); ap.add_argument("--config", required=True)
    ap.add_argument("--workdir", required=True); ap.add_argument("--out", required=True)
    a = ap.parse_args(); os.makedirs(a.workdir, exist_ok=True)
    res = Result("backlash", "Backlash compensation (M425)")
    run = lambda n, pre, body=BODY: x_steps(a.sim, a.config, a.workdir, n, pre + body)
    off = run("off", [])
    cases = [
        ("A: M425 X0.5 adds 40 steps per reversal", run("a", ["M425 X0.5"]), [800, 840, 840]),
        ("B: M425 P0 switches it off", run("b", ["M425 X0.5", "M425 P0"]), off),
        ("C: M425 P1 switches it back on", run("c", ["M425 X0.5", "M425 P0", "M425 P1"]), [800, 840, 840]),
        ("D: G92 does not forget the direction", run("d", ["M425 X0.5"], ["G90", "G1 X10 F6000", "G92 X0", "G1 X-10", "G1 X0"]), [800, 840, 840]),
        ("E: values over 100 mm are ignored", run("e", ["M425 X500"]), off),
    ]
    res.expect("baseline without M425 is 800 steps per move", off == [800, 800, 800], "800,800,800", str(off))
    for name, got, want in cases:
        res.expect(name, got == want, str(want), str(got))
    # F: same moves with the take-up phase on (default) and switched off through the config key
    cfg_off = f"{a.workdir}/config-takeup-off.txt"
    open(cfg_off, "w").write(open(a.config).read() + "\nbacklash_takeup_rate 0\n")
    on_steps, on_n, on_40 = reversal_block(a.sim, a.config, a.workdir, "f_on", ["M425 X0.5"] + BODY)
    off_steps, off_n, off_40 = reversal_block(a.sim, cfg_off, a.workdir, "f_off", ["M425 X0.5"] + BODY)
    res.expect("F: take-up on and off both issue 840 steps in the reversal block", on_steps == off_steps == 840 and on_n == off_n == 840,
               "840 / 840", f"on {on_steps} ({on_n} pulses), off {off_steps} ({off_n} pulses)")
    res.expect("F: the 40 slack steps are issued at least twice as early with take-up", on_40 * 2 <= off_40,
               "on_tick*2 <= off_tick", f"40th step at tick {on_40} with take-up, {off_40} without")
    write_result(res, a.out)
    print(res.status)
    sys.exit(0 if res.status == "pass" else 1)


if __name__ == "__main__":
    main()
