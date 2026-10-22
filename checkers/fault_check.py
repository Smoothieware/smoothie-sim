#!/usr/bin/env python3
"""Fault injection: an over-temperature reading must halt the machine through the real TemperatureControl module.

  fault_check.py --sim SIM --config CONFIG --workdir DIR --out RESULT.json

Runs cases/faults/overtemp.gcode (heater target set, then the thermistor reads far above max_temp) and cases/faults/overtemp-control.gcode (same program, thermistor stays cool).
The fault run must print the firmware's MAXTEMP error and "HALT asserted", switch the heater target off and refuse the move after the halt; the control run must do none of that.
Needs the `modules` workload build (TemperatureControl compiled in); a config without a temperature_control section is reported as not checked.
"""
import argparse, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import Result, run_sim, write_result

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ERROR_TEXT = "MINTEMP or MAXTEMP triggered"


def judge(res, fault, control):
    """Add the checks for the serial outputs and block counts of the fault run and of the control run."""
    out, ctl = fault["serial_out"], control["serial_out"]
    res.expect("over-temperature prints the firmware MAXTEMP error", ERROR_TEXT in out, "error printed", "no %r in the console output" % ERROR_TEXT)
    res.expect("over-temperature asserts HALT", "HALT asserted" in out, "HALT asserted", "no 'HALT asserted' in the console output")
    res.expect("heater target is switched off by the halt", "/0.0 @0" in out.rsplit("M105", 1)[-1] or ERROR_TEXT in out and "T:" in out and "/0.0" in out.split(ERROR_TEXT, 1)[1],
               "target 0 after the fault", "the temperature report after the fault still shows a heater target")
    res.expect("a move sent after the halt is refused", out.rstrip().endswith("!!") and len(fault["blocks"]) < len(control["blocks"]),
               "%d block(s) planned against %d in the control run" % (len(fault["blocks"]), len(control["blocks"])),
               "the move after the halt was accepted (%d blocks against %d in the control run)" % (len(fault["blocks"]), len(control["blocks"])))
    res.expect("control run without the fault does not halt", ERROR_TEXT not in ctl and "HALT asserted" not in ctl, "no halt", "the control run halted too")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sim", required=True); ap.add_argument("--config", required=True); ap.add_argument("--workdir", required=True); ap.add_argument("--out", required=True)
    a = ap.parse_args()
    os.makedirs(a.workdir, exist_ok=True)
    res = Result("faults", "Fault injection")
    if "temperature_control" not in open(a.config).read():
        res.add("over-temperature halt", "info", "not checked: the config has no temperature_control section")
    else:
        runs = [run_sim(a.sim, a.config, os.path.join(a.workdir, name + ".json"), gcode=os.path.join(HERE, "cases/faults", name + ".gcode"), modules=True, extra=["--no-steps"])
                for name in ("overtemp", "overtemp-control")]
        judge(res, *runs)
    write_result(res, a.out)
    print(json.dumps({"type": "summary", "checker": "faults", "status": res.status, "counts": res.to_dict()["counts"]}))
    return 1 if res.status == "fail" else 0


if __name__ == "__main__":
    sys.exit(main())
