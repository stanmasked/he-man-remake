"""Source-only pinned NeXium checkpoint defeat/recovery instrumentation tests."""
from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from instrument_nexium_checkpoint_defeat import (
    FRAMES, HID_EVENTS, instrument,
)
from verify_nexium_checkpoint_defeat_pngs import (
    ALIVE, EMPTY, ENEMY, FLAG_OFF, FLAG_ON,
    RESPAWN_OFF, RESPAWN_ON, DENSE,
)

PINNED = """
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


class CheckpointNativeDefeatProofContract(unittest.TestCase):
    def test_dual_pinned_guest_receivers_and_capture_schedule(self):
        rust = instrument(PINNED)
        expected = "matches!(frames, " + " | ".join(map(str, FRAMES)) + ")"
        self.assertEqual(rust.count(expected), 2)
        self.assertEqual(rust.count("HEMAN_GUEST_FRAME_PNG frame="), 2)
        self.assertEqual(rust.count("HEMAN_CHECKPOINT_DEFEAT_HID frame="), 2)
        self.assertEqual(rust.count("matches!(frames, 45 | 66)"), 2)
        self.assertEqual(HID_EVENTS, ((45, "buttons=DRIGHT"), (66, "buttons=")))
        self.assertEqual(tuple(range(116, 131)), DENSE)
        self.assertEqual(FRAMES[0:3], (30, 80, 105))
        self.assertEqual(FRAMES[-1], 145)

    def test_changed_receiver_rejected(self):
        with self.assertRaises(ValueError):
            instrument(PINNED.replace("frames += 1;", "frames += 2;", 1))

    def test_second_instrumentation_rejected(self):
        with self.assertRaises(ValueError):
            instrument(instrument(PINNED))

    def test_little_endian_native_renderer_colors(self):
        pairs = (
            (0xffe77965, ALIVE), (0xff493b51, EMPTY),
            (0xffe1c86d, ENEMY), (0xffffcd77, FLAG_OFF),
            (0xff77e4a6, FLAG_ON), (0xff283d51, RESPAWN_OFF),
            (0xff42d58a, RESPAWN_ON),
        )
        for packed, rgb in pairs:
            self.assertEqual(struct.pack("<I", packed)[:3], bytes(rgb))


if __name__ == "__main__":
    unittest.main()
