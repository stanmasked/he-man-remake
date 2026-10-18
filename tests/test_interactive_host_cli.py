"""Synthetic desktop CLI mode regressions without a graphical display."""
from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
import json
import unittest

from heman_tools.host_demo import main


class InteractionCLITests(unittest.TestCase):
    def test_interaction_mode_headless(self):
        out = StringIO()
        with redirect_stdout(out):
            result = main(['--interactions', '--headless', '--ticks', '40'])
        data = json.loads(out.getvalue())
        self.assertEqual(result, 0)
        self.assertEqual(data['frames'], 40)
        self.assertIn('pickups', data)
        self.assertIn('hazards_hit', data)

    def test_base_host_mode_unchanged(self):
        out = StringIO()
        with redirect_stdout(out):
            result = main(['--headless', '--ticks', '10'])
        data = json.loads(out.getvalue())
        self.assertEqual(result, 0)
        self.assertEqual(data['frames'], 10)
        self.assertIn('grounded', data)
        self.assertNotIn('pickups', data)

    def test_private_ipa_cannot_combine_with_synthetic_events(self):
        with redirect_stderr(StringIO()):
            with self.assertRaises(SystemExit) as caught:
                main(['--headless', '--interactions', '--ipa', 'not-on-disk.ipa'])
        self.assertEqual(caught.exception.code, 2)

    def test_headless_event_mode_is_deterministic(self):
        def run():
            out = StringIO()
            with redirect_stdout(out):
                main(['--headless', '--interactions', '--ticks', '140'])
            return json.loads(out.getvalue())
        self.assertEqual(run(), run())


if __name__ == '__main__':
    unittest.main()
