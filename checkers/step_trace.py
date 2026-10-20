#!/usr/bin/env python3
"""Step-trace recorder and comparer: a compact, reviewable reference for what the firmware emits for a G-code file.

  step_trace.py record  --result sim-result.json --out expected.trace
  step_trace.py compare --expected expected.trace --actual actual.trace [--out compare.json]

The trace is text, one line per planner block, so a changed reference reads as a diff in a pull request:

  # step-trace 1
  # actuators 3 steps_per_mm 80 80 400
  # final_steps 800 0 400
  B 0 line=3 steps=800,0,0 counts=800,0,0 dir=0 dirs=0,0,0 changes=0:+ start=38 ticks=21150 entry=0 exit=19.03

Exact (any difference fails): block count, per-axis planned steps, emitted step counts, direction bits, direction
changes inside a block, final step position of every motor. With tolerance (see TOLERANCES): block start tick,
block duration in ticks, entry/exit speed. The simulator's 10 us tick is an approximation of the real timer, so
timing is judged by closeness and counts by equality.
"""
import argparse, json, math, sys

VERSION = 1
# (relative, absolute): a timing value matches when |a-b| <= max(abs, rel * max(|a|,|b|))
TOLERANCES = {"start": (0.005, 4), "ticks": (0.005, 4), "entry": (0.005, 0.05), "exit": (0.005, 0.05)}


def _join(values):
    return ",".join(str(v) for v in values)


def _num(value):
    text = "%.4g" % value
    return "0" if text in ("-0", "0") else text


def record(result):
    """Build the trace text from a smoothie-sim result JSON (G-code or blocks mode)."""
    lines = ["# step-trace %d" % VERSION,
             "# actuators %d steps_per_mm %s" % (result["n_actuators"], " ".join(_num(v) for v in result["steps_per_mm"])),
             "# final_steps %s" % " ".join(str(int(v)) for v in result["final_steps"])]
    for block in result["blocks"]:
        changes = ";".join("%d:%s" % (axis, "".join("+" if sign > 0 else "-" for _, sign in axis_changes))
                           for axis, axis_changes in enumerate(block["dir_changes"]) if axis_changes)
        lines.append("B %d line=%d steps=%s counts=%s dir=%d dirs=%s changes=%s start=%d ticks=%d entry=%s exit=%s" % (
            block["index"], block["gcode_line"], _join(int(v) for v in block["steps"]), _join(block["step_counts"]),
            block["direction_bits"], _join(int(v) for v in block["step_dirs"]), changes or "-",
            block["start_tick"], block["ticks_run"], _num(block["entry_speed"]), _num(block["exit_speed"])))
    return "\n".join(lines) + "\n"


def parse(text):
    """Trace text -> {"header": {...}, "blocks": [dict, ...]}."""
    header, blocks = {}, []
    for raw in text.splitlines():
        if raw.startswith("# "):
            key, _, rest = raw[2:].partition(" ")
            header[key] = rest
        elif raw.startswith("B "):
            fields = raw.split()
            block = {"index": int(fields[1])}
            for field in fields[2:]:
                name, _, value = field.partition("=")
                block[name] = value
            blocks.append(block)
    return {"header": header, "blocks": blocks}


def _close(name, expected, actual):
    rel, absolute = TOLERANCES[name]
    a, b = float(expected), float(actual)
    return abs(a - b) <= max(absolute, rel * max(abs(a), abs(b)))


def compare(expected_text, actual_text):
    """Return {"status": "pass"|"fail", "exact": [...], "timing": [...]} (lists of human-readable differences)."""
    expected, actual = parse(expected_text), parse(actual_text)
    exact, timing = [], []
    for key in ("actuators", "final_steps"):
        if expected["header"].get(key) != actual["header"].get(key):
            exact.append("%s: expected %s, got %s" % (key, expected["header"].get(key), actual["header"].get(key)))
    if len(expected["blocks"]) != len(actual["blocks"]):
        exact.append("block count: expected %d, got %d" % (len(expected["blocks"]), len(actual["blocks"])))
    for e, a in zip(expected["blocks"], actual["blocks"]):
        where = "block %d (G-code line %s)" % (e["index"], e.get("line"))
        for field in ("steps", "counts", "dir", "dirs", "changes"):
            if e.get(field) != a.get(field):
                exact.append("%s %s: expected %s, got %s" % (where, field, e.get(field), a.get(field)))
        for field in ("start", "ticks", "entry", "exit"):
            if not _close(field, e[field], a[field]):
                timing.append("%s %s: expected %s, got %s" % (where, field, e[field], a[field]))
    return {"status": "fail" if exact or timing else "pass", "exact": exact, "timing": timing,
            "blocks_expected": len(expected["blocks"]), "blocks_actual": len(actual["blocks"])}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    rec = sub.add_parser("record")
    rec.add_argument("--result", required=True)
    rec.add_argument("--out", required=True)
    cmp_ = sub.add_parser("compare")
    cmp_.add_argument("--expected", required=True)
    cmp_.add_argument("--actual", required=True)
    cmp_.add_argument("--out")
    args = parser.parse_args()
    if args.command == "record":
        with open(args.result) as handle:
            text = record(json.load(handle))
        with open(args.out, "w") as handle:
            handle.write(text)
        return 0
    with open(args.expected) as e, open(args.actual) as a:
        outcome = compare(e.read(), a.read())
    if args.out:
        with open(args.out, "w") as handle:
            json.dump(outcome, handle, indent=1)
    print(json.dumps({"type": "result", **{k: outcome[k] for k in ("status", "blocks_expected", "blocks_actual")},
                      "exact_differences": len(outcome["exact"]), "timing_differences": len(outcome["timing"])}))
    for line in (outcome["exact"] + outcome["timing"])[:20]:
        print(json.dumps({"type": "warning", "message": line}))
    return 0 if outcome["status"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
