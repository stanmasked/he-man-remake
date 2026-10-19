"""Hostile source-only contracts for genuine post-victory B -> X -> X proof."""
from __future__ import annotations

import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from instrument_nexium_checkpoint_sword import (
    FRAMES as BASE_FRAMES, HID_EVENTS as BASE_HID_EVENTS,
)
from instrument_nexium_postvictory_b import (
    FRAMES, RETRY_FRAMES, RETRY_EVENTS, HID_EVENTS, instrument,
)
from verify_nexium_postvictory_b_pngs import verify
from test_nexium_checkpoint_sword import SyntheticRGB, FakeOpened, UPSTREAM


class PostVictoryGuestTests(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        self.root = Path(d.name)
        self.pixels = {f: SyntheticRGB(f) for f in FRAMES}
        for f in RETRY_FRAMES:
            p = self.pixels[f]
            if f <= 194:
                p.hp, p.enemy = 2, 0
            elif f == 195:
                p.hp, p.enemy = 3, 2
            elif f < 206:
                p.hp, p.enemy = 2, 2
            elif f < 223:
                p.hp, p.enemy = 2, 1
            else:
                p.hp, p.enemy = 2, 0
        for f in FRAMES:
            (self.root / f"raster-frame-{f:04}.png").write_bytes(
                b"mocked-image-decoder-only"
            )
        lines = (
            [f"HEMAN_GUEST_FRAME_PNG frame={f} original" for f in FRAMES]
            + [f"HEMAN_CHECKPOINT_SWORD_HID frame={f} {action}"
               for f, action in BASE_HID_EVENTS]
            + [f"HEMAN_POSTVICTORY_HID frame={f} {action}"
               for f, action in RETRY_EVENTS]
        )
        self.log = self.root / "raster-runner.log"
        self.log.write_text("\n".join(lines) + "\n")

    def evidence(self):
        pil = types.ModuleType("PIL")
        pil.Image = types.SimpleNamespace(
            open=lambda f: FakeOpened(
                self.pixels[int(Path(f).stem.split("-")[-1])]
            )
        )
        guest = types.ModuleType("verify_nexium_guest_pngs")
        guest.describe = lambda img: (img.markers, img.colors, img.x)
        with patch.dict(sys.modules, {
            "PIL": pil, "verify_nexium_guest_pngs": guest
        }):
            return verify(self.root)

    def replace_line(self, original, replacement):
        text = self.log.read_text()
        self.assertIn(original + "\n", text)
        self.log.write_text(text.replace(
            original + "\n", replacement + "\n"
        ))

    def test_dual_original_guest_receiver_instrumentation(self):
        source = instrument(UPSTREAM)
        self.assertEqual(source.count("HEMAN_POSTVICTORY_HID frame="), 2)
        self.assertEqual(source.count("HEMAN_CHECKPOINT_SWORD_HID frame="), 2)
        self.assertEqual(source.count("HEMAN_GUEST_FRAME_PNG frame="), 2)
        self.assertEqual(source.count(
            "if matches!(frames, 194 | 201 | 208 | 215 | 227 | 234)"
        ), 2)
        with self.assertRaisesRegex(ValueError, "already been instrumented"):
            instrument(source)

    def test_only_postvictory_B_and_two_new_X_presses(self):
        self.assertEqual(
            [x for x in RETRY_EVENTS if x[1] != "buttons="],
            [(194, "buttons=B"), (205, "buttons=X"), (221, "buttons=X")]
        )
        self.assertEqual(len(RETRY_EVENTS), 6)
        self.assertEqual(HID_EVENTS[:len(BASE_HID_EVENTS)], BASE_HID_EVENTS)
        self.assertEqual(FRAMES[:len(BASE_FRAMES)], BASE_FRAMES)
        self.assertGreater(205, 201)
        self.assertGreaterEqual(221 - 205, 15)

    def test_full_valid_guest_mock_contract(self):
        data = self.evidence()
        self.assertEqual(data["first_natural_death_frame"], 122)
        self.assertEqual(data["first_native_recovery_frame"], 123)
        self.assertEqual(data["postvictory_b_reset_observed_frame"], 195)
        self.assertEqual(data["postvictory_second_sword_victory"], [1, 0])
        self.assertEqual(data["hero_hp_after_second_victory"], 2)

    def test_B_still_pressed_instead_of_release_rejected(self):
        self.replace_line("HEMAN_POSTVICTORY_HID frame=201 buttons=",
                          "HEMAN_POSTVICTORY_HID frame=201 buttons=B")
        with self.assertRaisesRegex(ValueError, "Missing exact postvictory"):
            self.evidence()

    def test_false_postvictory_X_release_rejected(self):
        self.replace_line("HEMAN_POSTVICTORY_HID frame=228 buttons=",
                          "HEMAN_POSTVICTORY_HID frame=228 buttons=X")
        with self.assertRaisesRegex(ValueError, "Missing exact postvictory"):
            self.evidence()

    def test_log_prefix_does_not_count_as_B_event(self):
        self.replace_line("HEMAN_POSTVICTORY_HID frame=194 buttons=B",
                          "bogus HEMAN_POSTVICTORY_HID frame=194 buttons=B")
        with self.assertRaisesRegex(ValueError, "Missing exact postvictory"):
            self.evidence()

    def test_missing_real_frame_rejected(self):
        (self.root / "raster-frame-0195.png").unlink()
        with self.assertRaises(FileNotFoundError):
            self.evidence()

    def test_fake_capture_record_prefix_rejected(self):
        self.replace_line("HEMAN_GUEST_FRAME_PNG frame=220 original",
                          "bogus HEMAN_GUEST_FRAME_PNG frame=220 original")
        with self.assertRaisesRegex(ValueError, "Missing genuine retry frame"):
            self.evidence()

    def test_B_noop_cannot_claim_enemy_restoration(self):
        for f in range(195, 212):
            self.pixels[f].enemy = 0
        with self.assertRaisesRegex(ValueError, "did not restore"):
            self.evidence()

    def test_enemy_restored_before_B_is_rejected(self):
        self.pixels[193].enemy = 2
        with self.assertRaisesRegex(ValueError, "before real B"):
            self.evidence()

    def test_enemy_falsely_hit_before_postvictory_X_rejected(self):
        self.pixels[204].enemy = 1
        with self.assertRaisesRegex(ValueError, "before first post-B X"):
            self.evidence()

    def test_first_postvictory_X_missed_rejected(self):
        self.pixels[220].enemy = 2
        with self.assertRaisesRegex(ValueError, "wrong second-victory"):
            self.evidence()

    def test_second_postvictory_X_missed_rejected(self):
        self.pixels[242].enemy = 1
        with self.assertRaisesRegex(ValueError, "wrong second-victory"):
            self.evidence()

    def test_second_victory_hero_not_alive_rejected(self):
        self.pixels[270].hp = 0
        with self.assertRaisesRegex(ValueError, "wrong second-victory"):
            self.evidence()

    def test_one_world_unit_of_postvictory_drift_rejected(self):
        self.pixels[242].x = 207.5
        with self.assertRaisesRegex(ValueError, "world x=90 marker"):
            self.evidence()

    def test_missing_green_checkpoint_flag_rejected(self):
        self.pixels[195].flag = (0, 0, 0)
        with self.assertRaisesRegex(ValueError, "checkpoint unexpectedly"):
            self.evidence()


if __name__ == "__main__":
    unittest.main()
