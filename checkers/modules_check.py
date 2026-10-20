#!/usr/bin/env python3
"""Checker 3: modules - forbidden waits, interference and handler timing.

Three independent parts:
 A. static scan  - finds calls that block (wait, wait_ms, safe_delay*, us_ticker_read busy loops) in the dirs of rules.json scan_dirs
                   plus any file the PR changed (wait_for_idle is allowed: rules.json allowed_calls). With --base-src it only reports
                   violations that are new compared with the base tree (line numbers ignored), so old debt does not fail a PR.
 B. runtime      - runs a workload G-code with all modules loaded; the simulator records each time a handler blocked
                   (wait* inside an event) and handlers that ran longer than the threshold.
 C. interference - runs the same motion G-code with core only and with all modules; the planner blocks must be identical,
                   otherwise a module changed motion. Also compares final positions.
"""
import argparse, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ROOT, Result, run_sim, write_result
import handler_coverage


# SpindleMaker only builds the spindle; the event handlers live in the class it creates
HANDLER_CLASS = {"SpindleMaker": "PWMSpindleControl"}


def changed_files(src_root, base_root):
    """Source files (.c/.cpp/.h) that differ between the two trees, anywhere in the repository."""
    out = set()
    for d, _, files in os.walk(src_root):
        for fn in files:
            if not fn.endswith((".cpp", ".h", ".c")):
                continue
            rel = os.path.relpath(os.path.join(d, fn), src_root)
            other = os.path.join(base_root, rel)
            if not os.path.exists(other) or open(os.path.join(d, fn), "rb").read() != open(other, "rb").read():
                out.add(rel)
    return out


def merge_run(main, extra):
    """Fold the result of another simulator run into the main workload's result: waits are appended, handler stats added up."""
    main.setdefault("waits", []).extend(extra.get("waits", []))
    for name, h in extra.get("handlers", {}).items():
        m = main.setdefault("handlers", {}).setdefault(name, {"calls": 0, "self_us": 0, "max_self_us": 0})
        m["calls"] += h.get("calls", 0); m["self_us"] += h.get("self_us", 0); m["max_self_us"] = max(m["max_self_us"], h.get("max_self_us", 0))


def rule_for(rules, call, text=""):
    """(status, reason) the rules table gives a call; a wait_us with a tiny literal argument is the short-wait rule."""
    sw = rules.get("short_wait")
    if sw and call == sw["call"]:
        m = re.search(r"\(\s*(\d+)\s*\)", text)
        if m and int(m.group(1)) <= sw["max_us"]:
            return sw["status"], sw["reason"]
    r = rules["calls"].get(call)
    return (r["status"], r["reason"]) if r else ("forbidden", "blocking call")


FUNC_DEF = re.compile(r"^[A-Za-z_][\w:<>\*&\s,~]*?\b(?:(\w+)::)?(~?\w+)\s*\([^;{}]*\)\s*(?:const)?\s*(?:\{.*)?$")
STARTUP = {"on_module_loaded", "on_config_reload", "UpdateConfig", "load_tools", "initDisplay", "init"}


def functions(path):
    """Functions of a source file: [(name, first_line, last_line, called_names, is_constructor)]. Definitions start at
    column 0, which is how the firmware is formatted; anything else falls into context 'unknown'."""
    lines = open(path, errors="replace").read().splitlines()
    starts = []
    for i, line in enumerate(lines):
        if line and not line[0].isspace() and not line.startswith(("#", "//", "/*", "*", "}", "{")):
            m = FUNC_DEF.match(line.rstrip())
            if m and m.group(2) not in ("if", "for", "while", "switch", "return", "else"):
                starts.append((i + 1, m.group(2), m.group(1)))
    spans = []
    for k, (ln, name, cls) in enumerate(starts):
        end = starts[k + 1][0] - 1 if k + 1 < len(starts) else len(lines)
        spans.append((name, ln, end, name.lstrip("~") == cls))
    names = {n for n, _, _, _ in spans}
    res = []
    for name, ln, end, ctor in spans:
        body = "\n".join(lines[ln - 1:end])
        calls = {n for n in names if n != name and re.search(r"(?<![\w.])" + re.escape(n) + r"\s*\(", body)}
        res.append((name, ln, end, calls, ctor))
    return res


def context_of(funcs, line):
    """handler = inside, or called from, an on_* event handler of the same file; startup = only reachable from
    constructors / on_module_loaded / config code; helper = reachable from nothing recognised in this file (a caller in
    another file may be a handler); unknown = not inside a recognised function."""
    here = next((f for f in funcs if f[1] <= line <= f[2]), None)
    if not here:
        return "unknown", ""
    callers = {f[0]: set() for f in funcs}
    is_ctor = {f[0]: f[4] for f in funcs}
    for n, _, _, cs, _ in funcs:
        for c in cs:
            callers[c].add(n)
    seen, stack, roots = set(), [here[0]], set()
    while stack:
        n = stack.pop()
        if n in seen:
            continue
        seen.add(n)
        if not callers.get(n):
            roots.add(n)
        stack.extend(callers.get(n, ()))
    if any(n.startswith("on_") or n == "main_loop" for n in seen):
        return "handler", here[0]
    if roots and all(r in STARTUP or is_ctor.get(r) for r in roots):
        return "startup", here[0]
    return "helper", here[0]


def severity(status, context):
    """fail for a forbidden call on a handler path or an unclassified path; warn for ask-maintainer calls and for waits
    that only run at start-up."""
    if status == "allowed":
        return "ok"
    if status == "ask-maintainer":
        return "warn"
    return "warn" if context == "startup" else "fail"


def scan(src_root, rules, extra=frozenset()):
    """Scan rules["scan_dirs"] plus the files in `extra` (the files a PR changed, wherever they live)."""
    pats = {n: re.compile(r"(?<![\w.])" + re.escape(n) + r"\s*\(") for n, r in rules["calls"].items() if r["status"] != "allowed"}
    busy = re.compile(rules["busy_loop_pattern"])
    hits = []
    rels = set(extra)
    for sd in rules.get("scan_dirs", ["src/modules"]):
        for d, _, files in os.walk(os.path.join(src_root, sd)):
            for fn in files:
                if fn.endswith((".cpp", ".h", ".c")):
                    rels.add(os.path.relpath(os.path.join(d, fn), src_root))
    for rel in sorted(rels):
        p = os.path.join(src_root, rel)
        if not os.path.exists(p) or any(rel.startswith(x) for x in rules["allow"]):
            continue
        funcs = None
        for ln, line in enumerate(open(p, errors="replace"), 1):
            code = re.sub(r"//.*", "", line)
            found = [(n, "") for n, rx in pats.items() if rx.search(code) and not re.match(r"\s*(void|int|bool)\s", code)]
            if busy.search(code):
                found.append(("us_ticker_read", "possible busy-wait on the microsecond timer"))
            for n, why in found:
                if funcs is None:
                    funcs = functions(p)
                ctx, fn_name = context_of(funcs, ln)
                if n == "us_ticker_read":
                    status, reason = "forbidden", why
                else:
                    status, reason = rule_for(rules, n, code)
                hits.append({"file": rel, "line": ln, "call": n, "why": reason, "rule": status, "context": ctx, "function": fn_name,
                             "severity": severity(status, ctx), "text": line.strip()[:120]})
    return hits


def key(h):
    return (h["file"], h["call"], h["text"])


def hooks(src_root):
    """Which events each module registers for, a map to see who can interfere."""
    inv = {}
    rx = re.compile(r"register_for_event\s*\(\s*(ON_\w+)")
    for d, _, files in os.walk(os.path.join(src_root, "src", "modules")):
        for fn in files:
            if fn.endswith(".cpp"):
                t = open(os.path.join(d, fn), errors="replace").read()
                ev = sorted(set(rx.findall(t)))
                if ev:
                    inv[os.path.relpath(os.path.join(d, fn), src_root)] = ev
    return inv


def classify_runtime(raw, rules):
    """Apply the rules table to the waits the simulator recorded. Returns (waits to report, waits accepted by rule)."""
    out, acc = [], []
    for x in raw:
        if x["kind"] == "long_handler":   # a duration record, judged by the long-handler check
            continue
        r = rules["calls"].get(x["kind"])
        if r and r["status"] == "allowed":
            continue
        x = dict(x)
        if any(x["module"] == q["module"] and x["us"] <= q["max_us"] for q in rules.get("accepted_runtime_waits", [])):
            x["rule"] = "accepted"; acc.append(x); continue
        status, reason = (r["status"], r["reason"]) if r else ("forbidden", "blocking call")
        sw = rules.get("short_wait")
        if sw and x["kind"] == sw["call"] and x["us"] <= sw["max_us"]:
            status, reason = sw["status"], sw["reason"]
        if status == "forbidden" and any(x["module"] == q["module"] and x["event"] == q["event"] for q in rules.get("known_debt_runtime_waits", [])):
            status, reason = "known-debt", next(q["reason"] for q in rules["known_debt_runtime_waits"] if x["module"] == q["module"])
        x["rule"], x["reason"] = status, reason
        x["severity"] = "fail" if status == "forbidden" else "warn"
        out.append(x)
    return out, acc


def coverage(src_root, sim_handlers, makefile, gcov=None):
    """Every module source file that registers events: exercised by the workload, partly exercised, never run, or excluded from
    the build (and why). With gcov counters (`gcov` = handler_coverage.collect output) a module counts as exercised only when
    every on_* handler function in it was entered at least once; without counters the old rule (any handler of the class ran)
    is used."""
    excl = re.search(r"EXCLUDE_DIRS\s*:=(.*?)\n\n", open(makefile).read(), re.S)
    excl = [x for x in re.split(r"[\s\\]+", excl.group(1)) if x] if excl else []
    ran = {k.split("::")[0] for k in sim_handlers}
    rows = []
    for rel, ev in sorted(hooks(src_root).items()):
        stem = os.path.splitext(os.path.basename(rel))[0]
        stem = HANDLER_CLASS.get(stem, stem)
        sub = rel.split("src/", 1)[-1]
        ex = [x for x in excl if sub.startswith(x)]
        hrows = handler_coverage.handler_rows(gcov, sub) if gcov else []
        miss = []
        if ex: state, why = "excluded", "build excludes " + ex[0] + " (needs hardware the simulator does not fake)"
        elif hrows:
            miss = [h["function"] for h in hrows if h["calls"] == 0]
            n_in = len(hrows) - len(miss)
            state = "exercised" if not miss else ("partial" if n_in else "loaded-not-run")
            why = f"{n_in} of {len(hrows)} handler functions entered" + (": never entered " + ", ".join(m.split("::")[-1].split("(")[0] for m in miss) if miss else "")
        elif stem in ran or any(r.lower() == stem.lower() for r in ran): state, why = "exercised", "handlers ran in the workload (no line counters)"
        else: state, why = "loaded-not-run", "compiled in but no handler ran (module not loaded or no matching G-code in the workload)"
        rows.append({"file": rel, "events": ev, "state": state, "why": why, "handlers": hrows})
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sim", default="-", help="simulator binary; with --static-only it is not used")
    ap.add_argument("--static-only", action="store_true", help="only the source scan (for a PR tree that does not build)")
    ap.add_argument("--_unused", help=argparse.SUPPRESS); ap.add_argument("--src", required=True, help="firmware tree under test")
    ap.add_argument("--base-src", help="base firmware tree: only new static violations fail")
    ap.add_argument("--base-sim", help="simulator built from the base tree: runtime waits and long handlers it also shows are reported as existing, not new")
    ap.add_argument("--config", default="-"); ap.add_argument("--workload", default="-", help="G-code with module commands")
    ap.add_argument("--extra-run", default=[], nargs=2, action="append", metavar=("CONFIG", "WORKLOAD"),
                    help="another workload with its own config (for hardware variants one config cannot hold, such as a second panel type); counters and handler timings are merged into the main run")
    ap.add_argument("--motion", default=[], nargs="+", help="motion-only G-code files for the interference test")
    ap.add_argument("--makefile", default=os.path.join(ROOT, "Makefile"))
    ap.add_argument("--rules", default=os.path.join(ROOT, "rules.json")); ap.add_argument("--workdir", required=True); ap.add_argument("--out", required=True)
    a = ap.parse_args()
    os.makedirs(a.workdir, exist_ok=True)
    rules = json.load(open(a.rules)); res = Result("modules", "Modules")
    # A
    extra = changed_files(a.src, a.base_src) if a.base_src else frozenset()
    hits = scan(a.src, rules, extra); res.data["static_hits"] = hits
    def describe(h):
        return f"{h['file']}:{h['line']} {h['call']} in {h['function'] or '?'} ({h['context']}; rule {h['rule']})"
    if a.base_src:
        old = {key(h) for h in scan(a.base_src, rules, extra)}
        new = [h for h in hits if key(h) not in old and h["severity"] != "ok"]
        res.data["new_static_hits"] = new
        res.data["existing_static_hits"] = [h for h in hits if key(h) in old and h["severity"] != "ok"]
        bad = [h for h in new if h["severity"] == "fail"]
        status = "fail" if bad else ("warn" if new else "pass")
        res.add("no new blocking calls versus base", status, f"{len(hits)} existing, 0 new" if not new else
                f"{len(bad)} to fix, {len(new) - len(bad)} for the maintainers to judge: " + "; ".join(describe(h) for h in (bad + new)[:6]))
    else:
        res.add("static blocking calls found in modules", "warn" if hits else "pass", f"{len(hits)} blocking calls in the firmware tree. No reference tree was given, so none count as new and none fail; give one (BASE_SRC) to fail only on calls a change adds")
    res.data["hooks"] = hooks(a.src)
    if a.static_only:
        write_result(res, a.out)
        print(json.dumps({"type": "summary", "checker": "modules", "status": res.status, "counts": res.to_dict()["counts"]}))
        return 1 if res.status == "fail" else 0
    # B
    obj_dir = os.path.join(os.path.dirname(os.path.abspath(a.sim)), "obj")
    stage_src = os.path.join(os.path.dirname(os.path.abspath(a.sim)), "stage", "src")
    counters = handler_coverage.available(obj_dir)
    if counters:
        handler_coverage.clear_counters(obj_dir)
    w = run_sim(a.sim, a.config, os.path.join(a.workdir, "modules_workload.json"), gcode=a.workload, modules=True, extra=["--no-steps"])
    for n, (xcfg, xload) in enumerate(a.extra_run):
        merge_run(w, run_sim(a.sim, xcfg, os.path.join(a.workdir, f"modules_workload_extra{n}.json"), gcode=xload, modules=True, extra=["--no-steps"]))
    gcov = handler_coverage.collect(obj_dir, stage_src) if counters else None
    waits, accepted = classify_runtime(w.get("waits", []), rules)
    old_waits, old_long = set(), set()
    if a.base_sim:
        # Same workload on the base simulator: what it also shows is not caused by this change.
        bw = run_sim(a.base_sim, a.config, os.path.join(a.workdir, "modules_workload_base.json"), gcode=a.workload, modules=True, extra=["--no-steps"])
        for n, (xcfg, xload) in enumerate(a.extra_run):
            merge_run(bw, run_sim(a.base_sim, xcfg, os.path.join(a.workdir, f"modules_workload_base_extra{n}.json"), gcode=xload, modules=True, extra=["--no-steps"]))
        old_waits = {(x["module"], x["event"], x["kind"]) for x in classify_runtime(bw.get("waits", []), rules)[0]}
        old_long = {n for n, h in bw.get("handlers", {}).items() if h.get("max_self_us", 0) > rules["runtime_long_handler_us"]}
        res.data["existing_runtime_waits"] = [x for x in waits if (x["module"], x["event"], x["kind"]) in old_waits]
        waits = [x for x in waits if (x["module"], x["event"], x["kind"]) not in old_waits]
    res.data["runtime_waits"] = waits; res.data["accepted_runtime_waits"] = accepted; res.data["handlers"] = w.get("handlers", {})
    n_old_w = len(res.data.get("existing_runtime_waits", []))
    bad = [x for x in waits if x["severity"] == "fail"]
    status_w = "fail" if bad else ("warn" if waits else "pass")
    def wdesc(x):
        return f"{x['kind']} in {x['module']}::{x['event']} (G-code line {x['gcode_line']}) {x['us']/1000:.1f} ms [{x['rule']}]"
    res.add("handlers did not block while running the workload", status_w,
            ("no new waits" if a.base_sim else "no waits") if not waits else "; ".join(wdesc(x) for x in (bad + [x for x in waits if x not in bad])[:6]) +
            (f" (+{len(waits) - 6} more)" if len(waits) > 6 else "") + (f"; {len(accepted)} accepted by rule" if accepted else "") + (f"; {n_old_w} more also happen in the reference firmware (collapsed in the report)" if n_old_w else ""))
    longh = []
    for n, h in w.get("handlers", {}).items():
        if h.get("max_self_us", 0) > rules["runtime_long_handler_us"]:
            longh.append(dict(name=n, allowed=rules["long_handler_allow"].get(n), **{k: v for k, v in h.items() if k != "name"}))
    res.data["long_handlers"] = longh
    res.data["existing_long_handlers"] = [h for h in longh if h["name"] in old_long]
    longh = [h for h in longh if h["name"] not in old_long]; res.data["long_handlers"] = longh
    badh = [h for h in longh if not h["allowed"]]
    res.add("no handler ran longer than threshold", "fail" if badh else "pass",
            ("ok" if not longh else "; ".join(f"{h['name']} max {h.get('max_self_us', 0)} us" + (" (allowed: " + h["allowed"][:60] + ")" if h["allowed"] else " (NOT allowed)") for h in longh[:8])))
    cov = coverage(a.src, w.get("handlers", {}), a.makefile, gcov); res.data["coverage"] = cov
    n_ex = sum(c["state"] == "exercised" for c in cov); n_x = sum(c["state"] == "excluded" for c in cov)
    n_pa = sum(c["state"] == "partial" for c in cov); n_nr = len(cov) - n_ex - n_x - n_pa
    res.add("module coverage", "warn" if (n_x or n_nr or n_pa) else "pass",
            f"{n_ex} of {len(cov)} event-registering module files fully exercised, {n_pa} partly, {n_nr} never run, {n_x} excluded from the simulator build"
            + ("" if counters else " (no line counters in this simulator build)"))
    # C
    f = ["steps", "nominal_rate", "entry_speed", "exit_speed", "acceleration", "millimeters"]
    for m in a.motion:
        nm = os.path.basename(m)
        base = run_sim(a.sim, a.config, os.path.join(a.workdir, "core_" + nm + ".json"), gcode=m, extra=["--no-steps"])
        full = run_sim(a.sim, a.config, os.path.join(a.workdir, "mods_" + nm + ".json"), gcode=m, modules=True, extra=["--no-steps"])
        diffs = []
        if len(base["blocks"]) != len(full["blocks"]):
            diffs.append(f"block count {len(base['blocks'])} vs {len(full['blocks'])}")
        for i, (x, y) in enumerate(zip(base["blocks"], full["blocks"])):
            for k in f:
                if k == "steps":
                    n = max(len(x[k]), len(y[k]))
                    if list(x[k]) + [0] * (n - len(x[k])) != list(y[k]) + [0] * (n - len(y[k])): diffs.append(f"block {i} steps: {x[k]} vs {y[k]}")
                    continue
                if x[k] != y[k] and abs(x[k] - y[k]) > 1e-4 * max(1, abs(x[k])):
                    diffs.append(f"block {i} {k}: {x[k]} vs {y[k]}")
        n = max(len(base["final_steps"]), len(full["final_steps"]))
        pad = lambda v: [int(q) for q in v] + [0] * (n - len(v))
        same = pad(base["final_steps"]) == pad(full["final_steps"])
        res.expect(f"interference: {nm} identical with all modules loaded", not diffs and same, f"{len(base['blocks'])} blocks and final position identical", "; ".join(diffs[:4]) or "final position differs")
        res.data.setdefault("interference", []).append({"file": nm, "blocks": len(base["blocks"]), "ok": not diffs and same})
    write_result(res, a.out)
    print(json.dumps({"type": "summary", "checker": "modules", "status": res.status, "counts": res.to_dict()["counts"]}))
    return 1 if res.status == "fail" else 0


if __name__ == "__main__":
    sys.exit(main())
