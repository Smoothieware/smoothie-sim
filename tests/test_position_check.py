import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "checkers"))
from common import Result
import position_check as pc

CFG = "alpha_steps_per_mm 80\nbeta_steps_per_mm 80\ngamma_steps_per_mm 400\n"


def sim(pulses, counter=None, mp=(10, 0, 1)):
    return {"pulse_position": list(pulses), "final_steps": list(counter or pulses), "machine_position": list(mp), "steps_per_mm": [80, 80, 400]}


def run(s, gcode="G21\nG90\nG1 X10 F3000\nG1 Z1\n", cfg=CFG):
    r = Result("t", "t"); pc.check(r, s, gcode, cfg)
    return {c["check"]: c["status"] for c in r.to_dict()["checks"]}


class PositionCheck(unittest.TestCase):
    def test_destination_absolute_relative_arc(self):
        self.assertEqual(pc.destination("G90\nG1 X10 Y5\nG91\nG1 X-4\nG2 X1 Y1 I0 J1\n"), (7.0, 6.0, 0.0, None))

    def test_unsupported_commands_are_named(self):
        self.assertIn("G92", pc.destination("G92 X0\n")[3])
        self.assertIn("G20", pc.destination("G20\nG1 X1\n")[3])

    def test_comments_and_line_numbers(self):
        self.assertEqual(pc.destination("N10 G1 X3 ; go\n(note G92)\nG4 P1\n"), (3.0, 0.0, 0.0, None))

    def test_all_agree(self):
        self.assertEqual(set(run(sim([800, 0, 400])).values()), {"pass"})

    def test_lost_steps(self):
        st = run(sim([790, 0, 400], counter=[790, 0, 400]))
        self.assertEqual(st["emitted pulses equal destination x steps/mm from the config"], "fail")

    def test_wrong_steps_per_mm(self):
        st = run(sim([800, 0, 400]), cfg=CFG.replace("alpha_steps_per_mm 80", "alpha_steps_per_mm 160"))
        self.assertEqual(st["emitted pulses equal destination x steps/mm from the config"], "fail")

    def test_inverted_direction(self):
        st = run(sim([-800, 0, 400]))
        self.assertEqual(st["emitted pulses equal destination x steps/mm from the config"], "fail")
        self.assertEqual(st["pulse position equals the Robot machine position (within one step)"], "fail")

    def test_counter_disagrees_with_pins(self):
        st = run(sim([798, 0, 400], counter=[800, 0, 400]))
        self.assertEqual(st["pulses on the step and direction pins equal the motor step counter"], "fail")

    def test_robot_position_off(self):
        self.assertEqual(run(sim([800, 0, 400], mp=(9, 0, 1)))["Robot machine position equals the G-code destination"], "fail")

    def test_not_checked_cases_do_not_fail(self):
        self.assertEqual(list(run(sim([0, 0, 0]), gcode="G92 X0\n").values()), ["info"])
        self.assertEqual(list(run(sim([0, 0, 0]), cfg="arm_solution delta\n").values()), ["info"])
        self.assertEqual(list(run({"final_steps": [0]}).values()), ["info"])


if __name__ == "__main__":
    unittest.main()
