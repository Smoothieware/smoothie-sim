#!/usr/bin/env python3
"""Compare the fixed-tick dispatcher with the event-driven one (--event-dispatch) on every case: the simulator JSON must be identical.
Usage: compare_dispatch.py SIM OUT_DIR [RACE_SIM]   (RACE_SIM is a RACE=1 build, needed for the race cases; prints one JSONL line per case, then a summary with both run times)
"""
import json, os, re, subprocess, sys, time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
C = os.path.join(HERE, "cases")
CASES = [  # name, config, gcode, extra options
    ("cartesian/square", "cartesian/config.txt", "cartesian/square.gcode", ["--full-steps"]),
    ("cartesian/mixed", "cartesian/config.txt", "cartesian/mixed.gcode", ["--full-steps"]),
    ("modules/workload", "modules/config.txt", "modules/workload.gcode", ["--modules"]),
    ("modules/panel", "modules/panel-config.txt", "modules/panel-workload.gcode", ["--modules"]),
    ("filament-advance/chain", "filament-advance/config.txt", "filament-advance/chain.gcode", ["--full-steps"]),
    ("race/raster", "cartesian/config.txt", "race/raster.gcode", ["--race-force-every", "7"]),
    ("race/fine_raster", "cartesian/config.txt", "race/fine_raster.gcode", ["--race-window-us", "2"]),
]


def run(sim, cfg, gcode, extra, out, dispatch):
    cmd = [sim, "--config", os.path.join(C, cfg), "--gcode", os.path.join(C, gcode), "--out", out] + extra + (["--event-dispatch"] if dispatch else ["--fixed-tick"])
    t = time.time()
    p = subprocess.run(cmd, capture_output=True, text=True)
    return time.time() - t, p.returncode, p.stdout + p.stderr


def normalize(text):
    return re.sub(r"Used Heap Size: \d+", "Used Heap Size: N", text)   # the M-command heap report prints an uninitialised value that differs between any two runs


def main():
    sim, out = sys.argv[1], sys.argv[2]
    race_sim = sys.argv[3] if len(sys.argv) > 3 else None
    os.makedirs(out, exist_ok=True)
    tot = [0.0, 0.0]; diff = 0
    for name, cfg, gcode, extra in CASES:
        r = []
        if name.startswith("race/") and not race_sim:
            print(json.dumps({"type": "warning", "case": name, "message": "skipped: no RACE=1 simulator given"}))
            continue
        for i, d in enumerate((False, True)):
            o = os.path.join(out, name.replace("/", "_") + (".event" if d else ".fixed") + ".json")
            t, rc, text = run(race_sim if name.startswith("race/") else sim, cfg, gcode, extra, o, d)
            tot[i] += t
            r.append((o, rc, text))
        same = r[0][1] == r[1][1] and normalize(json.dumps(json.load(open(r[0][0])), sort_keys=True)) == normalize(json.dumps(json.load(open(r[1][0])), sort_keys=True))   # console text is not compared: it echoes the differing --out path
        diff += 0 if same else 1
        print(json.dumps({"type": "result", "case": name, "identical": same, "rc": [r[0][1], r[1][1]]}))
    print(json.dumps({"type": "summary", "cases": len(CASES), "different": diff, "seconds_fixed": round(tot[0], 2), "seconds_event": round(tot[1], 2)}))
    return 1 if diff else 0


if __name__ == "__main__":
    sys.exit(main())
