"""Check pinned dual Rust receivers and true renderer RGBA checkpoint colors."""
from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from instrument_nexium_checkpoint import (
    FRAMES as CAPTURE_FRAMES, HID_EVENTS as CONTROLLER_EVENTS, instrument,
)
from verify_nexium_checkpoint_pngs import (
    FRAMES, HID_EVENTS, FLAG_OFF, FLAG_ON, COUNTER_OFF, COUNTER_ON,
    PLAYER_HP, ENEMY_HP,
)

PINNED_RECEIVERS = """
fn runner() {
    for frame in primary.try_iter() {
            frames += 1;
            if frames <= 3 {
                println!("primary");
            }
    }
    for frame in drain.try_iter() {
        frames += 1;
        if frames <= 3 {
            println!("drain");
        }
    }
}
"""


class GenuineCheckpointRunnerContract(unittest.TestCase):
    def test_dual_guest_frame_receivers_and_real_hid_schedule(self):
        result = instrument(PINNED_RECEIVERS)
        self.assertEqual(tuple(CAPTURE_FRAMES), tuple(FRAMES))
        self.assertEqual(tuple(CONTROLLER_EVENTS), tuple(HID_EVENTS))
        self.assertEqual(result.count("HEMAN_GUEST_FRAME_PNG frame="), 2)
        self.assertEqual(result.count("HEMAN_CHECKPOINT_HID frame="), 2)
        self.assertEqual(result.count(
            "matches!(frames, 30 | 95 | 145 | 195 | 230)"), 2)
        self.assertEqual(result.count(
            "matches!(frames, 45 | 78 | 107 | 117 | 160 | 174)"), 2)
        self.assertEqual(result.count('107 => "buttons=B"'), 2)
        self.assertEqual(result.count('45 | 160 => "buttons=DRIGHT"'), 2)

    def test_double_instrumentation_rejected(self):
        with self.assertRaises(ValueError):
            instrument(instrument(PINNED_RECEIVERS))

    def test_unpinned_frame_receiver_rejected(self):
        with self.assertRaises(ValueError):
            instrument(PINNED_RECEIVERS.replace("frames += 1;", "frames += 2;", 1))

    def test_exact_little_endian_renderer_flag_and_hud_colors(self):
        samples = (
            (0xffffcd77, FLAG_OFF), (0xff77e4a6, FLAG_ON),
            (0xff283d51, COUNTER_OFF), (0xff42d58a, COUNTER_ON),
            (0xffe77965, PLAYER_HP), (0xffe1c86d, ENEMY_HP),
        )
        for packed, rgb in samples:
            self.assertEqual(struct.pack("<I", packed)[:3], bytes(rgb))


if __name__ == "__main__":
    unittest.main()
