"""Adversarial tests for genuine guest X-sword evidence after native respawn.

Only fake the image opener and marker descriptor, leaving the exact production
verifier untouched. Source-only Python CI needs no Pillow or proprietary IPA.
Passing these tests is not a substitute for actual NeXium guest PNG proof.
"""
from __future__ import annotations

import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from verify_nexium_post_respawn_sword_pngs import (
    ALIVE_ENEMY, ALIVE_PLAYER, EMPTY, EXPECTED_ENEMY_HP,
    EXPECTED_PLAYER_HP, FRAMES, HID_EVENTS, RESPAWN_GREEN, verify,
)

DARK_COUNTER = (81, 61, 40)


class FakeGuestRGB:
    def __init__(self, frame: int, player_hp: int, enemy_hp: int):
        self.frame = frame
        self.player_hp = player_hp
        self.enemy_hp = enemy_hp
        self.native_respawn = True
        self.world_x = 125.5
        self.magenta_pixels = 192
        self.colors = 16
        self.overrides = {}

    def getpixel(self, point):
        if point in self.overrides:
            return self.overrides[point]
        x, y = point
        if y == 18 and x in (18, 36, 54):
            return ALIVE_PLAYER if (x - 18) // 18 < self.player_hp else EMPTY
        if y == 18 and x in (226, 244):
            return ALIVE_ENEMY if (x - 226) // 18 < self.enemy_hp else EMPTY
        if point == (522, 62):
            return RESPAWN_GREEN if self.native_respawn else DARK_COUNTER
        raise AssertionError(f"Unexpected pixel queried: {point}")


class FakeOpenedPNG:
    def __init__(self, rgb: FakeGuestRGB, fmt: str):
        self.rgb = rgb
        self.format = fmt

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def convert(self, fmt: str):
        if fmt != "RGB":
            raise AssertionError("Verifier must inspect RGB")
        return self.rgb


class PostRespawnSwordVerifierNegativeTests(unittest.TestCase):
    def setUp(self):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.folder = Path(td.name)
        self.images = {
            frame: FakeGuestRGB(frame, hp, enemy_hp)
            for frame, hp, enemy_hp in zip(
                FRAMES, EXPECTED_PLAYER_HP, EXPECTED_ENEMY_HP
            )
        }
        for frame in FRAMES:
            # Deliberately not decodable PNGs: only the decoder is mocked.
            # These fixtures can never be confused with real guest evidence.
            (self.folder / f"raster-frame-{frame:04}.png").write_bytes(
                b"synthetic-rejected-by-real-image-decoder"
            )
        self.log = self.folder / "raster-runner.log"
        lines = [
            f"HEMAN_GUEST_FRAME_PNG frame={frame} dimensions=640x360 "
            f"path=raster-frame-{frame:04}.png\n"
            for frame in FRAMES
        ]
        lines.extend(
            f"HEMAN_RESPAWN_SWORD_HID frame={frame} {action}\n"
            for frame, action in HID_EVENTS
        )
        self.log.write_text("".join(lines))
        self.invalid_format_frame = None

    def evaluate(self):
        pil = types.ModuleType("PIL")

        def open_fixture(path):
            frame = int(Path(path).stem.split("-")[-1])
            fmt = "JPEG" if frame == self.invalid_format_frame else "PNG"
            return FakeOpenedPNG(self.images[frame], fmt)

        pil.Image = types.SimpleNamespace(open=open_fixture)
        guest = types.ModuleType("verify_nexium_guest_pngs")
        guest.describe = lambda rgb: (
            rgb.magenta_pixels, rgb.colors, rgb.world_x
        )
        with patch.dict(
            sys.modules,
            {"PIL": pil, "verify_nexium_guest_pngs": guest},
        ):
            return verify(self.folder)

    def replace_log(self, old: str, new: str = "MISSING"):
        src = self.log.read_text()
        self.assertIn(old, src)
        self.log.write_text(src.replace(old, new))

    def test_valid_four_guest_frame_contract(self):
        data = self.evaluate()
        self.assertTrue(data["genuine_native_respawn"])
        self.assertEqual(data["real_x_attack_hp_progression"], [2, 1, 0, 0])
        self.assertEqual(
            [f["player_hp"] for f in data["guest_frames"]],
            list(EXPECTED_PLAYER_HP),
        )
        self.assertEqual(
            [f["enemy_hp"] for f in data["guest_frames"]],
            list(EXPECTED_ENEMY_HP),
        )
        self.assertEqual(tuple(map(tuple, data["x_press_release_events"])),
                         HID_EVENTS)

    def test_death_recovery_requires_full_hp(self):
        self.images[62].player_hp = 2
        with self.assertRaisesRegex(ValueError, "hero HP mismatch"):
            self.evaluate()

    def test_first_contact_after_recovery_is_visible(self):
        self.images[79].player_hp = 3
        with self.assertRaisesRegex(ValueError, "hero HP mismatch"):
            self.evaluate()

    def test_player_hp_after_second_sword_is_stable(self):
        self.images[115].player_hp = 1
        with self.assertRaisesRegex(ValueError, "hero HP mismatch"):
            self.evaluate()

    def test_no_delayed_hero_damage_after_enemy_defeat(self):
        self.images[170].player_hp = 1
        with self.assertRaisesRegex(ValueError, "hero HP mismatch"):
            self.evaluate()

    def test_enemy_begins_with_two_hp(self):
        self.images[62].enemy_hp = 1
        with self.assertRaisesRegex(ValueError, "enemy HP mismatch"):
            self.evaluate()

    def test_first_x_must_inflict_one_hit(self):
        self.images[79].enemy_hp = 2
        with self.assertRaisesRegex(ValueError, "enemy HP mismatch"):
            self.evaluate()

    def test_second_x_must_defeat_enemy(self):
        self.images[115].enemy_hp = 1
        with self.assertRaisesRegex(ValueError, "enemy HP mismatch"):
            self.evaluate()

    def test_enemy_cannot_reappear_after_defeat(self):
        self.images[170].enemy_hp = 2
        with self.assertRaisesRegex(ValueError, "enemy HP mismatch"):
            self.evaluate()

    def test_native_respawn_marker_must_be_present(self):
        self.images[115].native_respawn = False
        with self.assertRaisesRegex(ValueError, "no native player respawn signal"):
            self.evaluate()

    def test_player_cannot_move_during_sword_only_input(self):
        self.images[115].world_x = 148.0
        with self.assertRaisesRegex(ValueError, "moved without D-pad input"):
            self.evaluate()

    def test_world_marker_must_have_192_pixels(self):
        self.images[79].magenta_pixels = 0
        with self.assertRaisesRegex(ValueError, "missing native renderer HUD"):
            self.evaluate()

    def test_scene_must_have_diverse_colors(self):
        self.images[79].colors = 1
        with self.assertRaisesRegex(ValueError, "missing native renderer HUD"):
            self.evaluate()

    def test_wrong_player_hud_tick_color_is_rejected(self):
        self.images[62].overrides[(36, 18)] = (0, 0, 0)
        with self.assertRaisesRegex(ValueError, "hero HP mismatch"):
            self.evaluate()

    def test_wrong_enemy_hud_tick_color_is_rejected(self):
        self.images[79].overrides[(226, 18)] = (0, 0, 0)
        with self.assertRaisesRegex(ValueError, "enemy HP mismatch"):
            self.evaluate()

    def test_missing_guest_frame_fails_closed(self):
        (self.folder / "raster-frame-0115.png").unlink()
        with self.assertRaises(FileNotFoundError):
            self.evaluate()

    def test_wrong_image_format_fails_closed(self):
        self.invalid_format_frame = 79
        with self.assertRaisesRegex(ValueError, "not a real PNG"):
            self.evaluate()

    def test_missing_capture_log_fails_closed(self):
        self.replace_log("HEMAN_GUEST_FRAME_PNG frame=170 ")
        with self.assertRaisesRegex(ValueError, "no actual guest capture"):
            self.evaluate()

    def test_first_x_press_must_be_logged(self):
        self.replace_log("HEMAN_RESPAWN_SWORD_HID frame=65 buttons=X")
        with self.assertRaisesRegex(ValueError, "Missing real NeXium X action"):
            self.evaluate()

    def test_first_x_release_must_be_logged(self):
        self.replace_log("HEMAN_RESPAWN_SWORD_HID frame=74 buttons=")
        with self.assertRaisesRegex(ValueError, "Missing real NeXium X action"):
            self.evaluate()

    def test_second_x_press_must_be_logged(self):
        self.replace_log("HEMAN_RESPAWN_SWORD_HID frame=84 buttons=X")
        with self.assertRaisesRegex(ValueError, "Missing real NeXium X action"):
            self.evaluate()

    def test_second_x_release_must_be_logged(self):
        self.replace_log("HEMAN_RESPAWN_SWORD_HID frame=93 buttons=")
        with self.assertRaisesRegex(ValueError, "Missing real NeXium X action"):
            self.evaluate()

    def test_missing_runner_log_is_not_silent_success(self):
        self.log.unlink()
        with self.assertRaises(FileNotFoundError):
            self.evaluate()


if __name__ == "__main__":
    unittest.main()
