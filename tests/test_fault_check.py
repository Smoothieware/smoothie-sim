import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "checkers"))
import fault_check
from common import Result

HALT = "ok\nERROR: MINTEMP or MAXTEMP triggered on T. Check your temperature sensors!\nHALT asserted - reset or M999 required\nok T:439.1 /0.0 @0 \n!!\n"
CALM = "ok\nok T:25.0 /200.0 @0 \nok\n"


def run(fault, control, fb=1, cb=2):
    r = Result("faults", "t")
    fault_check.judge(r, {"serial_out": fault, "blocks": [0] * fb}, {"serial_out": control, "blocks": [0] * cb})
    return {c["check"]: c["status"] for c in r.to_dict()["checks"]}


class FaultCheck(unittest.TestCase):
    def test_halt_passes(self):
        self.assertEqual(set(run(HALT, CALM).values()), {"pass"})

    def test_no_halt_fails(self):
        s = run(CALM, CALM, 2, 2)
        self.assertEqual(s["over-temperature asserts HALT"], "fail")
        self.assertEqual(s["a move sent after the halt is refused"], "fail")

    def test_control_halting_fails(self):
        self.assertEqual(run(HALT, HALT)["control run without the fault does not halt"], "fail")


if __name__ == "__main__":
    unittest.main()
