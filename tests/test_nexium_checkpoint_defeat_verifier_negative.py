"""Adversarial source-only verifier tests for true checkpoint auto-respawn.

Only substitute the image decoder and marker descriptor; call the unmodified
guest verifier. These fake fixtures are NOT evidence of NeXium execution.
"""
from __future__ import annotations

import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from verify_nexium_checkpoint_defeat_pngs import (
    ALIVE, EMPTY, ENEMY, FLAG_OFF, FLAG_ON, FRAMES, HID_EVENTS,
    RESPAWN_OFF, RESPAWN_ON, verify,
)


class FakePixels:
    def __init__(self, frame: int):
        self.frame = frame
        self.hp = 3 if frame == 30 else (
            2 if frame in (80, 145) or 122 <= frame <= 130
            else 0 if frame == 120
            else 3 if frame == 121
            else 1
        )
        self.counter = RESPAWN_OFF if frame <= 120 else RESPAWN_ON
        self.flag = FLAG_OFF if frame == 30 else FLAG_ON
        self.center = 125.5 if frame == 30 else (
            209.5 if frame <= 120 else 205.5
        )
        self.markers = 192
        self.colors = 18
        self.enemy = [ENEMY, ENEMY]

    def getpixel(self, pixel):
        x, y = pixel
        if y == 18 and x in (18, 36, 54):
            return ALIVE if (x - 18) // 18 < self.hp else EMPTY
        if y == 18 and x in (226, 244):
            return self.enemy[(x - 226) // 18]
        if pixel == (207, 250):
            return self.flag
        if pixel == (522, 62):
            return self.counter
        raise AssertionError(f"Unexpected guest pixel access: {pixel!r}")


class OpenedImage:
    def __init__(self, rgb, fmt):
        self.rgb = rgb
        self.format = fmt

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def convert(self, fmt):
        if fmt != "RGB":
            raise AssertionError("RGB expected")
        return self.rgb


class CheckpointNaturalDeathEvidenceTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.dir = Path(temp.name)
        self.images = {frame: FakePixels(frame) for frame in FRAMES}
        for frame in FRAMES:
            (self.dir / f"raster-frame-{frame:04}.png").write_bytes(
                b"not-a-real-png-verifier-decoder-mocked"
            )
        self.bad_fmt = None
        log = "".join(
            f"HEMAN_GUEST_FRAME_PNG frame={frame} x\n"
            for frame in FRAMES
        )
        log += "".join(
            f"HEMAN_CHECKPOINT_DEFEAT_HID frame={t} {action}\n"
            for t, action in HID_EVENTS
        )
        (self.dir / "raster-runner.log").write_text(log)

    def evaluate(self):
        pil = types.ModuleType("PIL")

        def read(path):
            frame = int(Path(path).stem.split("-")[-1])
            return OpenedImage(
                self.images[frame],
                "JPEG" if frame == self.bad_fmt else "PNG",
            )

        pil.Image = types.SimpleNamespace(open=read)
        markers = types.ModuleType("verify_nexium_guest_pngs")
        markers.describe = lambda frame: (
            frame.markers, frame.colors, frame.center
        )
        with patch.dict(sys.modules, {
            "PIL": pil, "verify_nexium_guest_pngs": markers,
        }):
            return verify(self.dir)

    def corrupt_log(self, marker):
        log = self.dir / "raster-runner.log"
        s = log.read_text()
        self.assertIn(marker, s)
        log.write_text(s.replace(marker, "CORRUPTED"))

    def test_valid_precise_death_and_checkpoint_recovery(self):
        result = self.evaluate()
        self.assertEqual(result["native_death_frame"], 120)
        self.assertEqual(result["native_recovery_frame"], 121)
        self.assertEqual(result["respawn_world_x"], 205.5)
        self.assertEqual(result["health_before_death"], [3, 2, 1])
        self.assertEqual(result["final_hp_at_frame_145"], 2)

    def test_no_visible_zero_hp_frame_rejected(self):
        self.images[120].hp = 1
        with self.assertRaisesRegex(ValueError, "exactly one visible natural death"):
            self.evaluate()

    def test_multiple_zero_hp_frames_rejected(self):
        self.images[121].hp = 0
        with self.assertRaisesRegex(ValueError, "exactly one visible natural death"):
            self.evaluate()

    def test_no_time_for_recovery_rejected(self):
        self.images[120].hp = 1
        self.images[130].hp = 0
        with self.assertRaisesRegex(ValueError, "space left"):
            self.evaluate()

    def test_incomplete_next_frame_recovery_rejected(self):
        self.images[121].hp = 2
        with self.assertRaisesRegex(ValueError, "next-frame"):
            self.evaluate()

    def test_premature_respawn_counter_rejected(self):
        self.images[120].counter = RESPAWN_ON
        with self.assertRaisesRegex(ValueError, "before actual defeat"):
            self.evaluate()

    def test_lost_respawn_counter_rejected(self):
        self.images[124].counter = RESPAWN_OFF
        with self.assertRaisesRegex(ValueError, "did not persist"):
            self.evaluate()

    def test_predeath_damage_cooldown_regression_rejected(self):
        self.images[118].hp = 2
        with self.assertRaisesRegex(ValueError, "cooldown/defeat"):
            self.evaluate()

    def test_spawn_instead_of_checkpoint_rejected(self):
        self.images[121].center = 125.5
        with self.assertRaisesRegex(ValueError, "not checkpoint"):
            self.evaluate()

    def test_wrong_final_hp_rejected(self):
        self.images[145].hp = 3
        with self.assertRaisesRegex(ValueError, "unexpected HP/respawn"):
            self.evaluate()

    def test_checkpoint_never_activated_rejected(self):
        self.images[80].flag = FLAG_OFF
        with self.assertRaisesRegex(ValueError, "checkpoint flag"):
            self.evaluate()

    def test_missing_world_x_marker_rejected(self):
        self.images[120].markers = 0
        with self.assertRaisesRegex(ValueError, "missing original HUD"):
            self.evaluate()

    def test_enemy_hp_mutation_rejected(self):
        self.images[145].enemy = [ENEMY, EMPTY]
        with self.assertRaisesRegex(ValueError, "enemy HP changed"):
            self.evaluate()

    def test_missing_guest_png_rejected(self):
        (self.dir / "raster-frame-0120.png").unlink()
        with self.assertRaises(FileNotFoundError):
            self.evaluate()

    def test_wrong_image_format_rejected(self):
        self.bad_fmt = 120
        with self.assertRaisesRegex(ValueError, "is not PNG"):
            self.evaluate()

    def test_missing_capture_record_rejected(self):
        self.corrupt_log("HEMAN_GUEST_FRAME_PNG frame=121 ")
        with self.assertRaisesRegex(ValueError, "Missing actual guest capture"):
            self.evaluate()

    def test_missing_real_dpad_press_rejected(self):
        self.corrupt_log("HEMAN_CHECKPOINT_DEFEAT_HID frame=45 buttons=DRIGHT")
        with self.assertRaisesRegex(ValueError, "Missing real D-pad"):
            self.evaluate()

    def test_missing_dpad_release_rejected(self):
        self.corrupt_log("HEMAN_CHECKPOINT_DEFEAT_HID frame=66 buttons=")
        with self.assertRaisesRegex(ValueError, "Missing real D-pad"):
            self.evaluate()

    def test_false_release_right_still_held_is_rejected(self):
        log_path = self.dir / "raster-runner.log"
        log = log_path.read_text()
        old = "HEMAN_CHECKPOINT_DEFEAT_HID frame=66 buttons=\n"
        self.assertIn(old, log)
        log_path.write_text(log.replace(old,
            "HEMAN_CHECKPOINT_DEFEAT_HID frame=66 buttons=DRIGHT\n"))
        with self.assertRaisesRegex(ValueError, "Missing real D-pad"):
            self.evaluate()

    def test_release_with_suffix_in_log_line_is_rejected(self):
        log_path = self.dir / "raster-runner.log"
        log = log_path.read_text()
        old = "HEMAN_CHECKPOINT_DEFEAT_HID frame=66 buttons=\n"
        self.assertIn(old, log)
        log_path.write_text(log.replace(old,
            "HEMAN_CHECKPOINT_DEFEAT_HID frame=66 buttons= extra\n"))
        with self.assertRaisesRegex(ValueError, "Missing real D-pad"):
            self.evaluate()

    def test_missing_runner_log_rejected(self):
        (self.dir / "raster-runner.log").unlink()
        with self.assertRaises(FileNotFoundError):
            self.evaluate()


if __name__ == "__main__":
    unittest.main()
