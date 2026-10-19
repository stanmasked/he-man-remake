"""Source contract and hostile evidence tests for checkpoint post-death X proof."""
from __future__ import annotations

import struct
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from instrument_nexium_checkpoint_sword import FRAMES, HID_EVENTS, instrument
from verify_nexium_checkpoint_sword_pngs import (
    ALIVE, EMPTY, ENEMY, FLAG_YELLOW, FLAG_GREEN,
    COUNTER_OFF, COUNTER_ON, verify,
)

UPSTREAM = """
fn runner() {
    for frame in primary.try_iter() {
            frames += 1;
            if frames <= 3 { println!("primary"); }
    }
    for frame in secondary.try_iter() {
        frames += 1;
        if frames <= 3 { println!("secondary"); }
    }
}
"""


class SyntheticRGB:
    def __init__(self, frame):
        self.frame = frame
        self.hp = 3 if frame in (30, 123) else (
            2 if frame in (80, 140, 160, 185) or 124 <= frame <= 130
            else 0 if frame == 122 else 1
        )
        self.enemy = 2 if frame <= 130 else (1 if frame == 140 else 0)
        self.x = 125.5 if frame == 30 else 205.5
        self.counter = COUNTER_OFF if frame <= 122 else COUNTER_ON
        self.flag = FLAG_YELLOW if frame == 30 else FLAG_GREEN
        self.markers = 192
        self.colors = 16

    def getpixel(self, point):
        x, y = point
        if y == 18 and x in (18, 36, 54):
            return ALIVE if (x - 18)//18 < self.hp else EMPTY
        if y == 18 and x in (226, 244):
            return ENEMY if (x - 226)//18 < self.enemy else EMPTY
        if point == (207, 250):
            return self.flag
        if point == (522, 62):
            return self.counter
        raise AssertionError(f"Unexpected sample {point}")


class FakeOpened:
    def __init__(self, pixels):
        self.format = "PNG"
        self.pixels = pixels

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def convert(self, mode):
        assert mode == "RGB"
        return self.pixels


class CheckpointSwordTests(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        self.path = Path(d.name)
        self.pixels = {frame: SyntheticRGB(frame) for frame in FRAMES}
        for frame in FRAMES:
            (self.path / f"raster-frame-{frame:04}.png").write_bytes(
                b"intentionally-not-a-real-png"
            )
        lines = (
            [f"HEMAN_GUEST_FRAME_PNG frame={n} original" for n in FRAMES]
            + [f"HEMAN_CHECKPOINT_SWORD_HID frame={n} {action}"
               for n, action in HID_EVENTS]
        )
        (self.path / "raster-runner.log").write_text("\n".join(lines) + "\n")

    def result(self):
        pil = types.ModuleType("PIL")
        pil.Image = types.SimpleNamespace(
            open=lambda file: FakeOpened(
                self.pixels[int(Path(file).stem.split("-")[-1])]
            )
        )
        renderer = types.ModuleType("verify_nexium_guest_pngs")
        renderer.describe = lambda img: (img.markers, img.colors, img.x)
        with patch.dict(sys.modules, {
            "PIL": pil, "verify_nexium_guest_pngs": renderer
        }):
            return verify(self.path)

    def test_dual_pinned_receiver_instrumentation(self):
        result = instrument(UPSTREAM)
        self.assertEqual(result.count("HEMAN_GUEST_FRAME_PNG frame="), 2)
        self.assertEqual(result.count("HEMAN_CHECKPOINT_SWORD_HID frame="), 2)
        self.assertEqual(result.count("matches!(frames, 45 | 66 | 129 | 136 | 148 | 155)"), 2)
        self.assertEqual(HID_EVENTS[-1], (155, "buttons="))
        with self.assertRaises(ValueError):
            instrument(result)

    def test_original_rgba_pixels_exact(self):
        for value, expected in (
            (0xffe77965, ALIVE), (0xff493b51, EMPTY),
            (0xffe1c86d, ENEMY), (0xffffcd77, FLAG_YELLOW),
            (0xff77e4a6, FLAG_GREEN), (0xff283d51, COUNTER_OFF),
            (0xff42d58a, COUNTER_ON),
        ):
            self.assertEqual(struct.pack("<I", value)[:3], bytes(expected))

    def test_full_mock_contract(self):
        data = self.result()
        self.assertEqual(data["natural_death_frame"], 122)
        self.assertEqual(data["native_recovery_frame"], 123)
        self.assertEqual(data["enemy_health_after_each_attack"], [1, 0])
        self.assertEqual(data["hero_health_after_victory"], 2)

    def test_genuine_21_step_checkpoint_approach(self):
        # Actual pinned NeXium runs vary by one D-pad tick before release.
        for frame in FRAMES:
            if frame != 30 and frame <= 122:
                self.pixels[frame].x = 209.5
        result = self.result()
        self.assertEqual(result["native_recovery_frame"], 123)
        self.assertEqual(result["enemy_health_after_each_attack"], [1, 0])

    def test_unexpected_predeath_input_drift_is_rejected(self):
        self.pixels[118].x = 209.5
        with self.assertRaisesRegex(ValueError, "moved before death"):
            self.result()

    def test_enemy_has_not_taken_first_sword_hit(self):
        self.pixels[140].enemy = 2
        with self.assertRaisesRegex(ValueError, "invalid combat/respawn HP"):
            self.result()

    def test_enemy_survives_second_sword_hit(self):
        self.pixels[160].enemy = 1
        with self.assertRaisesRegex(ValueError, "invalid combat/respawn HP"):
            self.result()

    def test_incorrect_respawn_x_rejected(self):
        self.pixels[123].x = 125.5
        with self.assertRaisesRegex(ValueError, "missed checkpoint recovery"):
            self.result()

    def test_missing_death_frame_rejected(self):
        self.pixels[122].hp = 1
        with self.assertRaisesRegex(ValueError, "Native death frame absent"):
            self.result()

    def test_player_takes_damage_after_enemy_dead(self):
        self.pixels[185].hp = 1
        with self.assertRaisesRegex(ValueError, "invalid combat/respawn HP"):
            self.result()

    def test_fake_x_release_still_held_rejected(self):
        log = self.path / "raster-runner.log"
        t = log.read_text()
        self.assertIn("HEMAN_CHECKPOINT_SWORD_HID frame=155 buttons=\n", t)
        log.write_text(t.replace(
            "HEMAN_CHECKPOINT_SWORD_HID frame=155 buttons=\n",
            "HEMAN_CHECKPOINT_SWORD_HID frame=155 buttons=X\n"
        ))
        with self.assertRaisesRegex(ValueError, "Missing exact real NeXium HID"):
            self.result()

    def test_missing_real_guest_frame_rejected(self):
        (self.path / "raster-frame-0160.png").unlink()
        with self.assertRaises(FileNotFoundError):
            self.result()


if __name__ == "__main__":
    unittest.main()
