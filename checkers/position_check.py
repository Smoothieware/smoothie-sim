#!/usr/bin/env python3
"""End-of-job position check: pulses emitted on the step and direction pins, the Robot's machine position and the G-code destination must agree.

The simulator integrates the position from the real pin levels at every emitted step pulse (`pulse_position`, steps) and reports the Robot's last requested
position (`machine_position`, mm). For a cartesian machine and a G-code file this module can follow (absolute or relative G0/G1/G2/G3 end points in mm), it checks:
  * the pulse-integrated position equals the motor step counter (a step the counter counted but the pin never pulsed, or the reverse);
  * pulse position / steps_per_mm equals the Robot's machine position within one step;
  * the Robot's machine position equals the G-code destination;
  * the pulse count equals destination * steps_per_mm from the config (wrong steps/mm, inverted direction and lost steps all show up here).
Anything it cannot follow (G20, G92, G28, work offsets, non-cartesian arm solution) makes the check report "not checked" instead of guessing.
"""
import re

AXES = "XYZ"
SPM_KEYS = ("alpha_steps_per_mm", "beta_steps_per_mm", "gamma_steps_per_mm")
MOTION = {0, 1, 2, 3}
IGNORED = {4, 17, 18, 19, 21, 94}   # dwell, plane selection, millimetres, feed per minute: no effect on the destination


def config_value(text, key):
    m = re.search(r"^\s*%s\s+(\S+)" % re.escape(key), text, re.M)
    return m.group(1) if m else None


def is_cartesian(config_text):
    return (config_value(config_text, "arm_solution") or "cartesian") == "cartesian"


def destination(gcode_text):
    """Return (x, y, z, None) in mm after the last move, or (None, None, None, reason) when the file uses something this parser does not follow."""
    pos = [0.0, 0.0, 0.0]
    absolute = True
    for raw in gcode_text.splitlines():
        line = re.sub(r"\(.*?\)|;.*", "", raw).strip().upper()
        line = re.sub(r"^N\d+\s*", "", line)
        if not line or line.startswith("%"):
            continue
        words = re.findall(r"([A-Z])\s*(-?\d+\.?\d*|-?\.\d+)", line)
        gs = [float(v) for c, v in words if c == "G"]
        for g in gs:
            if g in (90, 91):
                absolute = g == 90
            elif g not in MOTION and g not in IGNORED:
                return None, None, None, "G%g is not followed" % g
        if not any(g in MOTION for g in gs):
            continue
        for c, v in words:
            if c in AXES:
                i, v = AXES.index(c), float(v)
                pos[i] = pos[i] + v if not absolute else v
    return pos[0], pos[1], pos[2], None


def check(res, sim, gcode_text, config_text):
    """Add the position checks to `res` from the simulator result `sim` of a full G-code run."""
    if "pulse_position" not in sim or "machine_position" not in sim:
        res.add("pulse position vs machine position vs G-code destination", "info", "not checked: this simulator build does not report the positions")
        return
    if not is_cartesian(config_text):
        res.add("pulse position vs machine position vs G-code destination", "info", "not checked: arm solution is not cartesian")
        return
    x, y, z, why = destination(gcode_text)
    if why:
        res.add("pulse position vs machine position vs G-code destination", "info", "not checked: " + why)
        return
    dest = [x, y, z]
    spm = [float(config_value(config_text, k) or sim["steps_per_mm"][i]) for i, k in enumerate(SPM_KEYS)]
    pulses, counter, mp = sim["pulse_position"], sim["final_steps"], sim["machine_position"]
    n = min(3, len(pulses))
    bad = [(AXES[i], pulses[i], counter[i]) for i in range(n) if pulses[i] != counter[i]]
    res.expect("pulses on the step and direction pins equal the motor step counter", not bad, "equal on every axis", "; ".join("%s: pulses %d, counter %d" % b for b in bad))
    bad = [(AXES[i], pulses[i] / spm[i], mp[i]) for i in range(n) if abs(pulses[i] / spm[i] - mp[i]) > 1.0 / spm[i] + 1e-3]
    res.expect("pulse position equals the Robot machine position (within one step)", not bad, "equal on every axis",
               "; ".join("%s: pulses give %.4f mm, Robot says %.4f mm" % b for b in bad))
    bad = [(AXES[i], mp[i], dest[i]) for i in range(n) if abs(mp[i] - dest[i]) > 1e-3]
    res.expect("Robot machine position equals the G-code destination", not bad, "[%s] mm" % ", ".join("%g" % d for d in dest[:n]),
               "; ".join("%s: Robot %.4f mm, G-code %.4f mm" % b for b in bad))
    bad = [(AXES[i], pulses[i], round(dest[i] * spm[i])) for i in range(n) if abs(pulses[i] - dest[i] * spm[i]) > 1.0]
    res.expect("emitted pulses equal destination x steps/mm from the config", not bad, "[%s] steps" % ", ".join("%d" % round(dest[i] * spm[i]) for i in range(n)),
               "; ".join("%s: %d pulses, expected %d" % b for b in bad))
