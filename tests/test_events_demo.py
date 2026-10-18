"""Display-free event CLI regressions using a made-up game course."""
import json
import unittest

from heman_tools.events_demo import replay


class EventDemoTests(unittest.TestCase):
    def test_headless_determinism(self):
        self.assertEqual(replay(240), replay(240))

    def test_small_step(self):
        result = replay(1)
        self.assertEqual(result["frames"], 1)
        self.assertEqual(result["respawns"], 0)

    def test_result_serializable(self):
        result = replay(120)
        self.assertEqual(json.loads(json.dumps(result))["frames"], 120)

    def test_tick_bounds(self):
        for ticks in (-5, 0, 3601):
            with self.assertRaises(ValueError):
                replay(ticks)


if __name__ == "__main__":
    unittest.main()
