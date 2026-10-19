"""Adversarial contract tests for NeXium's damage/respawn PNG verifier.

These tests intentionally substitute in-memory frame readers so source-only
Python CI needs neither Pillow nor original game resources. They do NOT stand
in for the separate real NeXium guest-frame integration workflow.
"""
from __future__ import annotations

import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from verify_nexium_damage_pngs import (
    ALIVE, COUNTER_ACTIVE, COUNTER_EMPTY, EMPTY, ENEMY_ALIVE,
    EXPECTED_HEALTH, FRAMES, HP_X, verify,
)


class SyntheticRGB:
    def __init__(self, hp: int, respawn: bool):
        self.hp = hp
        self.respawn = respawn
        self.world_x = 125.5
        self.marker_count = 192
        self.colors = 16
        self.enemy_hp = 2
        self.player_hp_override = {}

    def getpixel(self, xy):
        x, y = xy
        if y == 18 and x in HP_X:
            return self.player_hp_override.get(x, ALIVE if HP_X.index(x) < self.hp else EMPTY)
        if y == 18 and x in (226, 244):
            return ENEMY_ALIVE if self.enemy_hp == 2 else EMPTY
        if (x, y) == (522, 62):
            return COUNTER_ACTIVE if self.respawn else COUNTER_EMPTY
        raise AssertionError(f"Unexpected inspected pixel {xy!r}")


class FakeOpenedFrame:
    def __init__(self, image: SyntheticRGB, fmt: str = "PNG"):
        self.image = image
        self.format = fmt

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def convert(self, mode):
        assert mode == "RGB"
        return self.image


class FailClosedDamagePNGTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        self.rgb = {}
        for i, frame in enumerate(FRAMES):
            (self.folder / f"raster-frame-{frame:04}.png").write_bytes(b"fake image: never decoded")
            self.rgb[frame] = SyntheticRGB(EXPECTED_HEALTH[i], i == len(FRAMES) - 1)
        self.log_path = self.folder / "raster-runner.log"
        self.log_path.write_text("".join(
            f"HEMAN_GUEST_FRAME_PNG frame={frame} path=raster-frame-{frame:04}.png\n"
            for frame in FRAMES
        ))
        self.bad_format_frame = None

    def run_verifier(self):
        fake_pil = types.ModuleType("PIL")

        def open_frame(path):
            frame = int(Path(path).stem.split("-")[-1])
            fmt = "JPEG" if frame == self.bad_format_frame else "PNG"
            return FakeOpenedFrame(self.rgb[frame], fmt)

        fake_pil.Image = types.SimpleNamespace(open=open_frame)
        fake_guest = types.ModuleType("verify_nexium_guest_pngs")
        fake_guest.describe = lambda img: (img.marker_count, img.colors, img.world_x)
        with patch.dict(sys.modules, {"PIL": fake_pil,
                                      "verify_nexium_guest_pngs": fake_guest}):
            return verify(self.folder)

    def test_valid_timeline_passes_and_retains_native_respawn(self):
        outcome = self.run_verifier()
        self.assertEqual([s["player_hp"] for s in outcome["states"]], list(EXPECTED_HEALTH))
        self.assertEqual([s["respawns"] for s in outcome["states"]], [0, 0, 0, 0, 1])
        self.assertTrue(outcome["invulnerability_preserved_hp"])
        self.assertTrue(outcome["native_defeat_and_recovery_visible"])

    def test_fails_if_immunity_frame_loses_health(self):
        self.rgb[25].hp = 1
        with self.assertRaisesRegex(ValueError, "player HP mismatch"):
            self.run_verifier()

    def test_fails_if_defeat_never_reaches_zero_health(self):
        self.rgb[61].hp = 1
        with self.assertRaisesRegex(ValueError, "player HP mismatch"):
            self.run_verifier()

    def test_fails_if_one_health_tick_has_wrong_pixel_color(self):
        self.rgb[40].player_hp_override[18] = (1, 2, 3)
        with self.assertRaisesRegex(ValueError, "player HP mismatch"):
            self.run_verifier()

    def test_fails_if_enemy_is_also_damaged(self):
        self.rgb[40].enemy_hp = 1
        with self.assertRaisesRegex(ValueError, "Enemy reset/state corruption"):
            self.run_verifier()

    def test_fails_if_native_respawn_marker_is_absent(self):
        self.rgb[62].respawn = False
        with self.assertRaisesRegex(ValueError, "expected native respawn indicator"):
            self.run_verifier()

    def test_fails_if_native_respawn_marker_appears_too_early(self):
        self.rgb[61].respawn = True
        with self.assertRaisesRegex(ValueError, "expected native respawn indicator"):
            self.run_verifier()

    def test_fails_if_player_moves_instead_of_staying_in_contact(self):
        self.rgb[25].world_x = 150.0
        with self.assertRaisesRegex(ValueError, "Unexpected player world-x movement"):
            self.run_verifier()

    def test_fails_if_guest_world_marker_disappears(self):
        self.rgb[10].marker_count = 0
        with self.assertRaisesRegex(ValueError, "Guest character/world marker missing"):
            self.run_verifier()

    def test_fails_if_guest_frame_has_too_few_colors(self):
        self.rgb[25].colors = 2
        with self.assertRaisesRegex(ValueError, "Guest character/world marker missing"):
            self.run_verifier()

    def test_fails_if_any_expected_png_is_absent(self):
        (self.folder / "raster-frame-0040.png").unlink()
        with self.assertRaises(FileNotFoundError):
            self.run_verifier()

    def test_fails_if_image_format_is_not_png(self):
        self.bad_format_frame = 40
        with self.assertRaisesRegex(ValueError, "is not PNG"):
            self.run_verifier()

    def test_fails_if_runner_did_not_log_final_guest_capture(self):
        self.log_path.write_text("".join(
            f"HEMAN_GUEST_FRAME_PNG frame={frame} path=frame.png\n"
            for frame in FRAMES[:-1]
        ))
        with self.assertRaisesRegex(ValueError, "No evidence for captured guest frame 62"):
            self.run_verifier()

    def test_fails_if_guest_runner_log_is_missing(self):
        self.log_path.unlink()
        with self.assertRaises(FileNotFoundError):
            self.run_verifier()


if __name__ == "__main__":
    unittest.main()
