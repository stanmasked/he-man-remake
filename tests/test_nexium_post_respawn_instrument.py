"""Pinned Rust runner and RGBA contract for post-respawn NeXium input."""
from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from instrument_nexium_post_respawn import instrument, FRAMES as CAPTURE
from verify_nexium_post_respawn_pngs import (
    FRAMES, EXPECTED_HP, PLAYER_ALIVE, PLAYER_EMPTY,
    ENEMY_ALIVE, RESPAWN_GREEN,
)

TEMPLATE = """
fn runner() {
    for frame in first_receiver.try_iter() {
            frames += 1;
            if frames <= 3 {
                print!("start");
            }
    }
    for frame in second_receiver.try_iter() {
        frames += 1;
        if frames <= 3 {
            print!("drain");
        }
    }
}
"""


class PostRespawnRunnerTests(unittest.TestCase):
    def test_exact_frame_capture_and_real_hid_events_in_both_paths(self):
        rust = instrument(TEMPLATE)
        self.assertEqual(tuple(CAPTURE), tuple(FRAMES))
        self.assertEqual(tuple(EXPECTED_HP), (3, 2, 2, 2))
        self.assertEqual(rust.count("HEMAN_GUEST_FRAME_PNG frame="), 2)
        self.assertEqual(rust.count("HEMAN_RESPAWN_HID frame="), 2)
        self.assertEqual(rust.count(
            "matches!(frames, 62 | 90 | 160 | 220)"), 2)
        self.assertEqual(rust.count("matches!(frames, 80 | 120)"), 2)
        self.assertEqual(rust.count("buttons=DRIGHT"), 2)
        self.assertEqual(rust.count("buttons="), 4)

    def test_reinstrumentation_fails_closed(self):
        with self.assertRaises(ValueError):
            instrument(instrument(TEMPLATE))

    def test_changed_pinned_receiver_fails_closed(self):
        with self.assertRaises(ValueError):
            instrument(TEMPLATE.replace("frames += 1;", "frames += 2;", 1))

    def test_rgba8888_pixels_match_real_renderer(self):
        self.assertEqual(struct.pack("<I", 0xffe77965)[:3], bytes(PLAYER_ALIVE))
        self.assertEqual(struct.pack("<I", 0xff493b51)[:3], bytes(PLAYER_EMPTY))
        self.assertEqual(struct.pack("<I", 0xffe1c86d)[:3], bytes(ENEMY_ALIVE))
        self.assertEqual(struct.pack("<I", 0xff42d58a)[:3], bytes(RESPAWN_GREEN))


if __name__ == "__main__":
    unittest.main()
