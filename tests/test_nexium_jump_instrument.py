"""Source-only jump HID instrumentation regression, no original IPA."""
from __future__ import annotations
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from instrument_nexium_jump import instrument_jump

PINNED_LOOPS = """
fn test() {
    for frame in recv.try_iter() {
            frames += 1;
            if frames <= 3 {
                println!("live");
            }
    }
    for frame in recv.try_iter() {
        frames += 1;
        if frames <= 3 {
            println!("drain");
        }
    }
}
"""

class JumpSourceTests(unittest.TestCase):
    def test_source_instruments_both_paths_and_exact_frames(self):
        data=instrument_jump(PINNED_LOOPS)
        self.assertEqual(data.count("HEMAN_JUMP_HID frame="),2)
        self.assertEqual(data.count("HEMAN_GUEST_FRAME_PNG frame="),2)
        self.assertEqual(data.count("matches!(frames, 30 | 65 | 120)"),2)
        self.assertEqual(data.count("matches!(frames, 45 | 58)"),2)
        self.assertEqual(data.count('"buttons=A"'),2)
        self.assertEqual(data.count('"buttons="'),2)
    def test_no_duplicate_instrumentation(self):
        with self.assertRaises(ValueError):
            instrument_jump(instrument_jump(PINNED_LOOPS))
    def test_invalid_upstream_source_rejected(self):
        with self.assertRaises(ValueError):
            instrument_jump(PINNED_LOOPS.replace("frames += 1;","frames += 2;",1))

if __name__=="__main__":
    unittest.main()
