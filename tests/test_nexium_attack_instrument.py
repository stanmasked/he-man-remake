"""Asset-free pinned-NeXium attack-hook and channel-contract tests."""
from __future__ import annotations
import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from instrument_nexium_attack import instrument_attacks


PINNED_SOURCE = """
fn runner() {
    for frame in receiver.try_iter() {
            frames += 1;
            if frames <= 3 {
                println!("running");
            }
    }
    for frame in receiver.try_iter() {
        frames += 1;
        if frames <= 3 {
            println!("final");
        }
    }
}
"""


class NeXiumAttackHookTests(unittest.TestCase):
    def test_two_independent_frame_consumers(self):
        patched = instrument_attacks(PINNED_SOURCE)
        self.assertEqual(patched.count("HEMAN_ATTACK_HID frame="), 2)
        self.assertEqual(patched.count("HEMAN_GUEST_FRAME_PNG frame="), 2)
        self.assertEqual(patched.count("matches!(frames, 45 | 58 | 85 | 98)"), 2)
        self.assertEqual(patched.count("matches!(frames, 30 | 65 | 120)"), 2)
        self.assertEqual(patched.count('"buttons=X"'), 2)
        self.assertEqual(patched.count('"buttons="'), 2)

    def test_repeated_or_changed_instrumentation_is_rejected(self):
        once = instrument_attacks(PINNED_SOURCE)
        with self.assertRaises(ValueError):
            instrument_attacks(once)
        with self.assertRaises(ValueError):
            instrument_attacks(PINNED_SOURCE.replace("frames += 1;", "frames += 2;", 1))

    def test_enemy_hp_colors_are_actual_little_endian_rgba(self):
        self.assertEqual(struct.pack("<I", 0xffe1c86d), bytes((109,200,225,255)))
        self.assertEqual(struct.pack("<I", 0xff493b51), bytes((81,59,73,255)))
        self.assertEqual(struct.pack("<I", 0xffe77965), bytes((101,121,231,255)))

    def test_attack_is_a_button_mask_not_fake_state_change(self):
        self.assertIn('buttons=X', instrument_attacks(PINNED_SOURCE))
        self.assertNotIn("enemy_hp", instrument_attacks(PINNED_SOURCE))


if __name__ == "__main__":
    unittest.main()
