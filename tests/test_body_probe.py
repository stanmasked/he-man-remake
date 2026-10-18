"""Synthetic-only script driver tests; no IPA or artwork needed."""
import unittest

from heman_tools.body_probe import run_body_script, local_ipa_body_probe
from test_body_physics import world


class BodyProbeTests(unittest.TestCase):
    def test_stationary_landing(self):
        report = run_body_script(world(), x=20, feet_y=0, ticks=120)
        self.assertTrue(report['grounded'])
        self.assertAlmostEqual(report['final_feet_y'], 64, delta=0.01)
        self.assertGreater(report['grounded_ticks'], 1)

    def test_horizontal_blocked_and_counted(self):
        report = run_body_script(world(), x=20, feet_y=64, ticks=120, axis=1)
        self.assertGreater(report['wall_contact_ticks'], 0)
        self.assertLessEqual(report['final_x'], 43.01)

    def test_repeatability(self):
        def simulate():
            return run_body_script(world(), x=20, feet_y=64, ticks=120, jump_tick=2)
        self.assertEqual(simulate(), simulate())

    def test_invalid_ticks_and_jump(self):
        with self.assertRaises(ValueError): run_body_script(world(), x=20, feet_y=64, ticks=0)
        with self.assertRaises(ValueError): run_body_script(world(), x=20, feet_y=64, ticks=4, jump_tick=5)

    def test_ipa_path_traversal_rejected_before_read(self):
        with self.assertRaises(ValueError):
            local_ipa_body_probe(None, map_name='../secret.map')


if __name__=='__main__':
    unittest.main()
