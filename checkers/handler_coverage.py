"""Which event-handler functions of each module did the workload really run? Uses gcov counters from a simulator built with
COVERAGE=1 (the Makefile default). A handler that was merely registered, or that returned on its first line, does not count."""
import glob, json, os, re, subprocess


def clear_counters(obj_dir):
    for p in glob.glob(os.path.join(obj_dir, "**", "*.gcda"), recursive=True):
        os.remove(p)


def available(obj_dir):
    return bool(glob.glob(os.path.join(obj_dir, "modules", "**", "*.gcno"), recursive=True))


def collect(obj_dir, stage_src):
    """{relative source file: {function demangled name: (calls, lines_hit, lines_total, first line of the function)}} for every instrumented file with counters."""
    gcdas = sorted(glob.glob(os.path.join(obj_dir, "**", "*.gcda"), recursive=True))
    out = {}
    for i in range(0, len(gcdas), 40):
        p = subprocess.run(["gcov", "--json-format", "--stdout", "--demangled-names"] + gcdas[i:i + 40], capture_output=True, text=True, cwd=obj_dir)
        for line in p.stdout.splitlines():
            line = line.strip()
            if not line.startswith("{"):
                continue
            doc = json.loads(line)
            for f in doc.get("files", []):
                rel = os.path.relpath(f["file"], stage_src) if os.path.isabs(f["file"]) else f["file"]
                funcs = out.setdefault(rel, {})
                spans = [(fn["start_line"], fn["end_line"], fn.get("demangled_name") or fn["name"], fn["execution_count"]) for fn in f.get("functions", [])]
                for s, e, name, cnt in spans:
                    ls = [l for l in f.get("lines", []) if s <= l["line_number"] <= e]
                    total = len(ls); hit = sum(1 for l in ls if l["count"] > 0)
                    old = funcs.get(name, (0, 0, 0, s))
                    funcs[name] = (old[0] + cnt, max(old[1], hit), max(old[2], total), min(old[3], s))
    return out


def handler_rows(cov, rel):
    """Handler functions (on_*) of one module file with their counters."""
    rows = []
    for name, (calls, hit, total, line) in sorted(cov.get(rel, {}).items()):
        short = re.sub(r"\(.*", "", name).split("::")[-1]
        if short.startswith("on_"):
            rows.append({"function": name, "calls": calls, "lines_hit": hit, "lines_total": total, "line": line})
    return rows
