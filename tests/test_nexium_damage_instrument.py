"""Source-only NRO damage/respawn capture and RGBA contract regression."""
from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from instrument_nexium_damage import instrument, TIMELINE
from verify_nexium_damage_pngs import (
    FRAMES, EXPECTED_HEALTH, EXPECTED_RESPAWNS,
    ALIVE, EMPTY, COUNTER_EMPTY, COUNTER_ACTIVE
)

TEMPLATE="""
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


class DamageRunnerTests(unittest.TestCase):
    def test_both_original_receiver_paths_capture_same_frames(self):
        out=instrument(TEMPLATE)
        self.assertEqual(out.count("HEMAN_GUEST_FRAME_PNG frame="),2)
        self.assertEqual(out.count(
            "matches!(frames, 10 | 25 | 40 | 61 | 62)"
        ),2)
        self.assertEqual(tuple(TIMELINE),FRAMES)
        self.assertEqual(EXPECTED_HEALTH,(2,2,1,0,3))
        self.assertEqual(EXPECTED_RESPAWNS,(0,0,0,0,1))

    def test_reject_duplicate_or_changed_source(self):
        with self.assertRaises(ValueError):
            instrument(instrument(TEMPLATE))
        with self.assertRaises(ValueError):
            instrument(TEMPLATE.replace("frames += 1;","frames += 2;",1))

    def test_real_raster_little_endian_rgba_colors(self):
        self.assertEqual(struct.pack("<I",0xffe77965)[:3],bytes(ALIVE))
        self.assertEqual(struct.pack("<I",0xff493b51)[:3],bytes(EMPTY))
        self.assertEqual(struct.pack("<I",0xff283d51)[:3],bytes(COUNTER_EMPTY))
        self.assertEqual(struct.pack("<I",0xff42d58a)[:3],bytes(COUNTER_ACTIVE))


if __name__=="__main__":
    unittest.main()
