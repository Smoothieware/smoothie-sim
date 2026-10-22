"""End-to-end tests that run a real smoothie-sim binary: SMOOTHIE_SIM=build/smoothie-sim python3 -I tests/test_integration.py
Skipped when SMOOTHIE_SIM is not set (the unit tests in the other files need no binary)."""
import json, os, re, subprocess, sys, tempfile, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "checkers"))
SIM = os.environ.get("SMOOTHIE_SIM", "")
CART = os.path.join(ROOT, "cases/cartesian")


def read(path):
    with open(path) as f:
        return f.read()


def run_cli(*args):
    return subprocess.run([sys.executable, "-I", *args], capture_output=True, text=True, timeout=900)


def results(path):
    return {c["check"]: c["status"] for c in json.loads(read(path))["checks"]}


def sim_json(out, gcode, config, *extra):
    subprocess.run([SIM, "--config", config, "--gcode", gcode, "--out", out, *extra], capture_output=True, timeout=900, check=True)
    text = read(out)
    return re.sub(r"Used Heap Size: \d+", "H", text.replace(out, "OUT"))


@unittest.skipUnless(SIM and os.path.exists(SIM), "set SMOOTHIE_SIM to a built smoothie-sim")
class Integration(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def path(self, name):
        return os.path.join(self.tmp.name, name)

    def steps_check(self, gcode, config):
        out = self.path("r.json")
        run_cli(os.path.join(ROOT, "checkers/blocks_to_steps.py"), "--sim", SIM, "--config", config, "--gcode", gcode, "--workdir", self.path("w"), "--out", out)
        return results(out)

    def test_position_check_passes_on_square_and_mixed(self):
        for name in ("square.gcode", "mixed.gcode"):
            st = self.steps_check(os.path.join(CART, name), os.path.join(CART, "config.txt"))
            self.assertEqual(st["Robot machine position equals the G-code destination"], "pass", name)
            self.assertNotIn("fail", st.values(), name)

    def test_position_check_catches_a_wrong_steps_per_mm_claim(self):
        # the simulator runs with the real config; the checker is told another steps/mm, so the pulses cannot match
        import position_check
        from common import Result
        cfg = read(os.path.join(CART, "config.txt"))
        gcode = read(os.path.join(CART, "square.gcode"))
        sim = json.loads(sim_json(self.path("s.json"), os.path.join(CART, "square.gcode"), os.path.join(CART, "config.txt")))
        good, bad = Result("t", "t"), Result("t", "t")
        position_check.check(good, sim, gcode, cfg)
        position_check.check(bad, sim, gcode, re.sub(r"alpha_steps_per_mm\s+\S+", "alpha_steps_per_mm 1", cfg))
        self.assertNotIn("fail", [c["status"] for c in good.to_dict()["checks"]])
        self.assertIn("fail", [c["status"] for c in bad.to_dict()["checks"]])

    def test_facing_program_runs_through_steps_checker(self):
        st = self.steps_check(os.path.join(CART, "face-4x4-stock.gcode"), os.path.join(CART, "config.txt"))
        self.assertNotIn("fail", st.values())

    def test_fault_check_halts_and_control_does_not(self):
        out = self.path("f.json")
        r = run_cli(os.path.join(ROOT, "checkers/fault_check.py"), "--sim", SIM, "--config", os.path.join(ROOT, "cases/modules/config.txt"), "--workdir", self.path("f"), "--out", out)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(set(results(out).values()), {"pass"})

    def test_event_dispatch_and_fixed_tick_give_identical_output(self):
        cfg, gc = os.path.join(CART, "config.txt"), os.path.join(CART, "mixed.gcode")
        self.assertEqual(sim_json(self.path("a.json"), gc, cfg, "--fixed-tick"), sim_json(self.path("a.json"), gc, cfg, "--event-dispatch"))

    def test_same_binary_is_deterministic(self):
        cfg, gc = os.path.join(CART, "config.txt"), os.path.join(CART, "square.gcode")
        self.assertEqual(sim_json(self.path("d.json"), gc, cfg), sim_json(self.path("d.json"), gc, cfg))

    def test_pulse_position_is_reported(self):
        d = json.loads(sim_json(self.path("p.json"), os.path.join(CART, "square.gcode"), os.path.join(CART, "config.txt")))
        self.assertEqual(len(d["pulse_position"]), len(d["final_steps"]))
        self.assertIn("machine_position", d)


if __name__ == "__main__":
    unittest.main()
