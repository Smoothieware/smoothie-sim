#!/usr/bin/env python3
"""Regression test for the wait checker: replay every old PR the maintainer rejected for blocking waits and fail if one is no longer flagged.

Usage: regress_prs.py OUT_DIR [--firmware CHECKOUT] [--trees DIR] [--prs 620 633 ...] [--no-run]
For each PR, replay_pr.sh builds a simulator from the PR tree and runs checkers/modules_check.py (result: OUT/PR/modules.result.json).
cases/pr-replay/expected.json says, per PR (runtime_modules = modules whose waits must show up), whether the static scan must flag it, whether the runtime check must flag it, and why a
PR is not runtime-capable (for example it cannot be built). --no-run only evaluates results already in OUT_DIR.
"""
import argparse, json, os, subprocess, sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def evaluate(pr, exp, out):
    path = os.path.join(out, pr, "modules.result.json")
    if not os.path.exists(path):
        return {"pr": pr, "static": None, "runtime": None, "problems": ["no result file (build failed?) see " + os.path.join(out, pr, "build.log")]}
    d = json.load(open(path))["data"]
    static = [h for h in d.get("new_static_hits", []) if h.get("severity") in ("fail", "warn")]
    # a runtime catch must come from the module the PR touched; the Panel LCD-init waits are in every run and prove nothing
    modules = exp.get("runtime_modules")
    runtime = [w for w in d.get("runtime_waits", []) if (w.get("module") in modules if modules else w.get("kind") != "long_handler")]
    if modules:   # handlers over the duration threshold that are not on the allow-list also count (a busy loop is not a wait call)
        runtime += [h for h in d.get("long_handlers", []) if not h.get("allowed") and h["name"].split("::")[0] in modules]
    problems = []
    if exp["static"] and not static: problems.append("static scan no longer flags it")
    if exp["runtime"] and not runtime: problems.append("runtime check no longer flags it")
    return {"pr": pr, "static": len(static), "runtime": len(runtime), "problems": problems}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out"); ap.add_argument("--firmware", help="Smoothieware checkout the PR trees are built from (needed unless --trees exists)"); ap.add_argument("--trees"); ap.add_argument("--prs", nargs="*"); ap.add_argument("--no-run", action="store_true")
    a = ap.parse_args()
    expected = json.load(open(os.path.join(HERE, "cases/pr-replay/expected.json")))
    prs = a.prs or list(expected)
    trees = a.trees or os.path.join(a.out, "trees")
    if not a.no_run:
        if not os.path.isdir(os.path.join(trees, "base")):
            if not a.firmware: sys.exit("regress_prs.py: --firmware CHECKOUT is required to build the PR trees")
            subprocess.run([os.path.join(HERE, "tools/make_pr_trees.sh"), a.out, a.firmware], check=True)
        for pr in prs:
            subprocess.run([os.path.join(HERE, "tools/replay_pr.sh"), pr, trees, a.out], check=False)
    bad = 0; rows = []
    for pr in prs:
        r = evaluate(pr, expected[pr], a.out); bad += bool(r["problems"])
        rows.append({**r, "expected": expected[pr]})
        print(json.dumps({"type": "result", **rows[-1]}))
    json.dump(rows, open(os.path.join(a.out, "regress.json"), "w"), indent=1)
    print(json.dumps({"type": "summary", "status": "fail" if bad else "pass", "prs": len(prs), "failing": bad}))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
