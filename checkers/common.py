"""Shared helpers for the simulator checkers: running the simulator, result records, G-code end-point parsing."""
import json, math, os, re, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


class Result:
    """One checker's outcome: a list of named checks, each pass / fail / warn / info."""

    def __init__(self, name, title):
        self.name, self.title, self.checks, self.data = name, title, [], {}

    def add(self, check, status, detail="", **extra):
        self.checks.append({"check": check, "status": status, "detail": detail, **extra})

    def expect(self, check, ok, detail_ok="", detail_bad="", warn_only=False):
        self.add(check, "pass" if ok else ("warn" if warn_only else "fail"), detail_ok if ok else detail_bad)

    @property
    def status(self):
        s = [c["status"] for c in self.checks]
        return "fail" if "fail" in s else ("warn" if "warn" in s else "pass")

    def to_dict(self):
        n = {k: sum(1 for c in self.checks if c["status"] == k) for k in ("pass", "fail", "warn", "info")}
        return {"checker": self.name, "title": self.title, "status": self.status, "counts": n,
                "checks": self.checks, "data": self.data}


def run_sim(binary, config, out, gcode=None, blocks_in=None, modules=False, full_steps=False, extra=(), timeout=600):
    cmd = [binary, "--config", config, "--out", out]
    if gcode:
        cmd += ["--gcode", gcode]
    if blocks_in:
        cmd += ["--blocks-in", blocks_in]
    if modules:
        cmd += ["--modules"]
    if full_steps:
        cmd += ["--full-steps"]
    cmd += list(extra) + os.environ.get("SMOOTHIE_SIM_ARGS", "").split()   # for example --event-dispatch, to run a whole checker set in another timer mode
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if p.returncode != 0:
        raise RuntimeError(f"simulator failed ({p.returncode}): {' '.join(cmd)}\n{p.stderr[-2000:]}")
    return json.load(open(out))


def write_result(res, path):
    json.dump(res.to_dict(), open(path, "w"), indent=1)


def parse_gcode_endpoints(path, axes="XYZE"):
    """Independent end-point model: absolute/relative moves of G0-G3 (arcs end on their target), G92 offsets.
    Returns the final position per axis in mm and the number of motion lines."""
    pos = {a: 0.0 for a in axes}
    absolute, e_absolute, moves = True, True, 0
    for raw in open(path):
        line = re.sub(r"[;(].*", "", raw).strip().upper()
        if not line:
            continue
        words = dict(re.findall(r"([A-Z])\s*(-?\d+\.?\d*|-?\.\d+)", line))
        g = words.get("G")
        if g in ("90", "91"):
            absolute = g == "90"; e_absolute = absolute
        elif g == "92":
            for a in axes:
                if a in words: pos[a] = float(words[a])
        elif g in ("0", "1", "2", "3"):
            moved = False
            for a in axes:
                if a in words:
                    v = float(words[a])
                    ab = e_absolute if a == "E" else absolute
                    pos[a] = v if ab else pos[a] + v
                    moved = True
            moves += moved
    return pos, moves


def block_positions(blocks, steps_per_mm):
    """Cumulative machine position (mm per actuator) after each block, from signed step counts."""
    n = len(steps_per_mm)
    cur = [0.0] * n
    out = [list(cur)]
    for b in blocks:
        for i in range(n):
            s = b["steps"][i] if i < len(b["steps"]) else 0
            cur[i] += (-s if (b["direction_bits"] >> i) & 1 else s) / steps_per_mm[i]
        out.append(list(cur))
    return out


def trapezoid_profile(b, samples=40):
    """(time_s, speed_mm_s) polyline of a block from its planned entry/nominal/exit speeds and acceleration."""
    mm, a, ve, vx, vn = b["millimeters"], b["acceleration"], b["entry_speed"], b["exit_speed"], b["nominal_speed"]
    if mm <= 0 or a <= 0:
        return [(0, ve), (0, vx)]
    vpeak = min(vn, math.sqrt(max(a * mm + (ve * ve + vx * vx) / 2, 0)))
    d_acc = max((vpeak ** 2 - ve ** 2) / (2 * a), 0); d_dec = max((vpeak ** 2 - vx ** 2) / (2 * a), 0)
    d_plat = max(mm - d_acc - d_dec, 0)
    t_acc = (vpeak - ve) / a; t_dec = (vpeak - vx) / a; t_plat = d_plat / vpeak if vpeak > 0 else 0
    pts = [(0.0, ve), (t_acc, vpeak), (t_acc + t_plat, vpeak), (t_acc + t_plat + t_dec, vx)]
    return pts
