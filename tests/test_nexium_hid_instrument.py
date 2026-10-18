"""Pure-Python regression for deterministic guest HID instrumentation."""
from __future__ import annotations
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from instrument_nexium_hid import instrument_input


SOURCE = """
fn sample() {
    for frame in emulation.frame_rx.try_iter() {
            frames += 1;
            if frames <= 3 {
                println!("first");
            }
    }
    for frame in emulation.frame_rx.try_iter() {
        frames += 1;
        if frames <= 3 {
            println!("last");
        }
    }
}
"""


class PinnedNeXiumHidInjectionTests(unittest.TestCase):
    def test_both_guest_frame_receive_paths_have_events(self) -> None:
        code = instrument_input(SOURCE)
        self.assertEqual(code.count("HEMAN_HID_SCHEDULE frame="), 2)
        self.assertEqual(code.count("frames, 45 | 105"), 2)
        self.assertEqual(code.count('let text = if frames == 45'), 2)
        self.assertEqual(code.count('buttons=DRIGHT'), 2)
        self.assertEqual(code.count('"buttons="'), 2)
        self.assertEqual(code.count("HEMAN_GUEST_FRAME_PNG frame="), 2)
        self.assertEqual(code.count("raster-frame-{frames:04}.png"), 2)

    def test_instrumentation_fails_closed_if_repeated(self) -> None:
        code = instrument_input(SOURCE)
        with self.assertRaises(ValueError):
            instrument_input(code)

    def test_upstream_loop_change_does_not_silently_pass(self) -> None:
        with self.assertRaisesRegex(ValueError, "source changed"):
            instrument_input(SOURCE.replace("frames += 1;", "frames += 2;", 1))


if __name__ == "__main__":
    unittest.main()
