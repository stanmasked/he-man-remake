"""Fail-closed adversarial tests of the post-respawn guest HUD verifier.

All frames here are in-memory fakes. This unit suite verifies rejection
logic, not emulator execution or original iOS game fidelity.
"""
from __future__ import annotations

import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from verify_nexium_post_respawn_pngs import (
    ENEMY_ALIVE, EXPECTED_HP, FRAMES, PLAYER_ALIVE, PLAYER_EMPTY,
    RESPAWN_GREEN, verify,
)

DARK = (81, 61, 40)


class FakeRGB:
    def __init__(self, frame, health, world_x):
        self.frame = frame
        self.health = health
        self.world_x = world_x
        self.count = 192
        self.colors = 16
        self.enemy_hp = 2
        self.respawn = True
        self.tick_override = {}

    def getpixel(self, coordinate):
        x, y = coordinate
        if y == 18 and x in (18, 36, 54):
            index = (x - 18) // 18
            return self.tick_override.get(
                x, PLAYER_ALIVE if index < self.health else PLAYER_EMPTY
            )
        if y == 18 and x in (226, 244):
            return ENEMY_ALIVE if self.enemy_hp == 2 else PLAYER_EMPTY
        if (x, y) == (522, 62):
            return RESPAWN_GREEN if self.respawn else DARK
        raise AssertionError(f"Unexpected pixel request {coordinate!r}")


class OpenedImage:
    def __init__(self, pixels, format_name="PNG"):
        self.pixels = pixels
        self.format = format_name

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def convert(self, target_format):
        if target_format != "RGB":
            raise AssertionError("Verifier must read RGB")
        return self.pixels


class PostRespawnVerifierFailClosed(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.folder = Path(temp.name)
        self.frames = {
            frame: FakeRGB(frame, hp, position)
            for frame, hp, position in zip(
                FRAMES, EXPECTED_HP, (125.5, 145.5, 205.5, 205.5)
            )
        }
        for frame in FRAMES:
            # Bytes are intentionally invalid: the decoder is mocked;
            # no generated image may be mistaken for real guest evidence.
            (self.folder / f"raster-frame-{frame:04}.png").write_bytes(b"fixture")
        self.log = self.folder / "raster-runner.log"
        self.log.write_text(
            "".join(
                f"HEMAN_GUEST_FRAME_PNG frame={frame} dimensions=640x360 "
                f"path=raster-frame-{frame:04}.png\n"
                for frame in FRAMES
            )
            + "HEMAN_RESPAWN_HID frame=80 buttons=DRIGHT\n"
            + "HEMAN_RESPAWN_HID frame=120 buttons=\n"
        )
        self.bad_image_frame = None

    def evaluate(self):
        fake_pil = types.ModuleType("PIL")

        def open_image(path):
            frame = int(Path(path).stem.split("-")[-1])
            fmt = "JPEG" if frame == self.bad_image_frame else "PNG"
            return OpenedImage(self.frames[frame], fmt)

        fake_pil.Image = types.SimpleNamespace(open=open_image)
        fake_guest = types.ModuleType("verify_nexium_guest_pngs")
        fake_guest.describe = lambda image: (
            image.count, image.colors, image.world_x
        )
        with patch.dict(
            sys.modules, {"PIL": fake_pil, "verify_nexium_guest_pngs": fake_guest}
        ):
            return verify(self.folder)

    def test_good_contract_passes_without_pillow_dependency(self):
        outcome = self.evaluate()
        self.assertEqual(
            [item["player_hp"] for item in outcome["frames"]], list(EXPECTED_HP)
        )
        self.assertTrue(outcome["real_hid_right_after_respawn"])
        self.assertTrue(outcome["right_release_stops_movement"])

    def test_defeat_recovery_must_restore_full_health(self):
        self.frames[62].health = 2
        with self.assertRaisesRegex(ValueError, "player HP differs"):
            self.evaluate()

    def test_post_recovery_contact_damage_must_be_visible(self):
        self.frames[90].health = 3
        with self.assertRaisesRegex(ValueError, "player HP differs"):
            self.evaluate()

    def test_health_pickup_cannot_mask_damage_regression(self):
        self.frames[160].health = 3
        with self.assertRaisesRegex(ValueError, "player HP differs"):
            self.evaluate()

    def test_enemy_hp_must_remain_untouched(self):
        self.frames[160].enemy_hp = 1
        with self.assertRaisesRegex(ValueError, "enemy HP changed"):
            self.evaluate()

    def test_respawn_indicator_must_be_present_in_all_frames(self):
        self.frames[62].respawn = False
        with self.assertRaisesRegex(ValueError, "missing native respawn"):
            self.evaluate()

    def test_world_marker_must_have_right_pixel_count(self):
        self.frames[90].count = 20
        with self.assertRaisesRegex(ValueError, "no genuine source HUD"):
            self.evaluate()

    def test_world_marker_must_have_scene_diversity(self):
        self.frames[90].colors = 2
        with self.assertRaisesRegex(ValueError, "no genuine source HUD"):
            self.evaluate()

    def test_respawn_world_x_must_be_spawn_coordinate(self):
        self.frames[62].world_x = 160.0
        with self.assertRaisesRegex(ValueError, "did not naturally respawn"):
            self.evaluate()

    def test_right_input_must_move_before_frame_90(self):
        self.frames[90].world_x = 130.0
        with self.assertRaisesRegex(ValueError, "did not move player"):
            self.evaluate()

    def test_sustained_right_movement_must_continue(self):
        self.frames[160].world_x = 170.0
        with self.assertRaisesRegex(ValueError, "failed to continue"):
            self.evaluate()

    def test_player_must_stop_after_right_release(self):
        self.frames[220].world_x = 235.0
        with self.assertRaisesRegex(ValueError, "kept moving"):
            self.evaluate()

    def test_missing_png_fails_closed(self):
        (self.folder / "raster-frame-0160.png").unlink()
        with self.assertRaises(FileNotFoundError):
            self.evaluate()

    def test_wrong_image_type_fails_closed(self):
        self.bad_image_frame = 160
        with self.assertRaisesRegex(ValueError, "is not PNG"):
            self.evaluate()

    def test_missing_actual_capture_log_fails_closed(self):
        self.log.write_text(
            self.log.read_text().replace(
                "HEMAN_GUEST_FRAME_PNG frame=220 ", "MISSING_CAPTURE frame=220 "
            )
        )
        with self.assertRaisesRegex(ValueError, "Missing genuine guest frame capture"):
            self.evaluate()

    def test_missing_real_right_press_event_fails_closed(self):
        self.log.write_text(
            self.log.read_text().replace(
                "HEMAN_RESPAWN_HID frame=80 buttons=DRIGHT", "unknown input"
            )
        )
        with self.assertRaisesRegex(ValueError, "Missing genuine NeXium HID"):
            self.evaluate()

    def test_missing_release_event_fails_closed(self):
        self.log.write_text(
            self.log.read_text().replace(
                "HEMAN_RESPAWN_HID frame=120 buttons=", "unknown release"
            )
        )
        with self.assertRaisesRegex(ValueError, "Missing genuine NeXium HID"):
            self.evaluate()

    def test_missing_runner_log_fails_closed(self):
        self.log.unlink()
        with self.assertRaises(FileNotFoundError):
            self.evaluate()


if __name__ == "__main__":
    unittest.main()
