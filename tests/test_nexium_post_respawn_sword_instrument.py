"""Source-only contract tests for genuine post-respawn X-button evidence.

Pinned upstream Rust guest capture and real RGBA8888 HUD colors are checked
without Pillow, Nintendo SDK, or original iOS game data.
"""
from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from instrument_nexium_post_respawn_sword import (
    FRAMES as CAPTURE_FRAMES, HID_EVENTS as INPUT_EVENTS, instrument,
)
from verify_nexium_post_respawn_sword_pngs import (
    ALIVE_ENEMY, ALIVE_PLAYER, EMPTY, EXPECTED_ENEMY_HP,
    EXPECTED_PLAYER_HP, FRAMES, RESPAWN_GREEN, HID_EVENTS,
)

PINNED = """
fn runner() {
    for frame in primary.try_iter() {
            frames += 1;
            if frames <= 3 {
                print!("primary");
            }
    }
    for frame in drain.try_iter() {
        frames += 1;
        if frames <= 3 {
            print!("drain");
        }
    }
}
"""


class NeXiumPostRespawnSwordContract(unittest.TestCase):
    def test_exact_dual_receiver_hooks(self):
        rust = instrument(PINNED)
        self.assertEqual(FRAMES, CAPTURE_FRAMES)
        self.assertEqual(HID_EVENTS, INPUT_EVENTS)
        self.assertEqual(EXPECTED_PLAYER_HP, (3, 2, 2, 2))
        self.assertEqual(EXPECTED_ENEMY_HP, (2, 1, 0, 0))
        self.assertEqual(rust.count("HEMAN_GUEST_FRAME_PNG frame="), 2)
        self.assertEqual(rust.count("HEMAN_RESPAWN_SWORD_HID frame="), 2)
        self.assertEqual(
            rust.count("matches!(frames, 62 | 79 | 115 | 170)"), 2
        )
        self.assertEqual(
            rust.count("matches!(frames, 65 | 74 | 84 | 93)"), 2
        )
        self.assertEqual(
            rust.count("matches!(frames, 65 | 84)"), 2
        )

    def test_double_instrumentation_is_rejected(self):
        with self.assertRaises(ValueError):
            instrument(instrument(PINNED))

    def test_changed_pinned_frame_receiver_is_rejected(self):
        with self.assertRaises(ValueError):
            instrument(PINNED.replace("frames += 1;", "frames += 2;", 1))

    def test_original_renderer_pixel_contract(self):
        self.assertEqual(struct.pack("<I", 0xffe77965)[:3], bytes(ALIVE_PLAYER))
        self.assertEqual(struct.pack("<I", 0xffe1c86d)[:3], bytes(ALIVE_ENEMY))
        self.assertEqual(struct.pack("<I", 0xff493b51)[:3], bytes(EMPTY))
        self.assertEqual(struct.pack("<I", 0xff42d58a)[:3], bytes(RESPAWN_GREEN))


if __name__ == "__main__":
    unittest.main()
