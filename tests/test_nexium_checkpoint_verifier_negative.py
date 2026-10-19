"""Fail-closed tests for the genuine NeXium checkpoint controller verifier.

These are source-only synthetic pixel fixtures, NOT emulator screenshots.
Only the image decoder and marker descriptor are mocked.
"""
from __future__ import annotations

import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from verify_nexium_checkpoint_pngs import (
    COUNTER_OFF, COUNTER_ON, ENEMY_HP, FLAG_OFF, FLAG_ON,
    FRAMES, HID_EVENTS, PLAYER_HP, verify,
)


class SyntheticPixels:
    def __init__(self, frame: int, center: float, index: int):
        self.frame = frame
        self.center = center
        self.index = index
        self.marker_pixels = 192
        self.colors = 16
        self.overrides = {}

    def getpixel(self, xy):
        if xy in self.overrides:
            return self.overrides[xy]
        if xy in ((18, 18), (36, 18), (54, 18)):
            return PLAYER_HP
        if xy in ((226, 18), (244, 18)):
            return ENEMY_HP
        if xy == (190, 250):
            return FLAG_OFF if self.index == 0 else FLAG_ON
        if xy == (522, 62):
            return COUNTER_OFF if self.index < 2 else COUNTER_ON
        raise AssertionError(f"Verifier accessed unexpected pixel {xy}")


class FakeOpen:
    def __init__(self, rgb, fmt):
        self.rgb = rgb
        self.format = fmt

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def convert(self, kind):
        if kind != "RGB":
            raise AssertionError("Only RGB images expected")
        return self.rgb


class CheckpointGuestVerifierTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.folder = Path(tmp.name)
        self.pixels = {
            n: SyntheticPixels(n, x, i)
            for i, (n, x) in enumerate(zip(
                FRAMES, (125.5, 255.5, 205.5, 235.5, 235.5)
            ))
        }
        self.bad_format = None
        for n in FRAMES:
            (self.folder / f"raster-frame-{n:04}.png").write_bytes(b"not-a-png")
        self.log = self.folder / "raster-runner.log"
        self.log.write_text(
            "".join(
                f"HEMAN_GUEST_FRAME_PNG frame={n} dimensions=640x360 "
                f"path=raster-frame-{n:04}.png\n"
                for n in FRAMES
            ) + "".join(
                f"HEMAN_CHECKPOINT_HID frame={n} {action}\n"
                for n, action in HID_EVENTS
            )
        )

    def evaluate(self):
        fake_pil = types.ModuleType("PIL")

        def open_image(path):
            frame = int(Path(path).stem.split("-")[-1])
            fmt = "JPEG" if self.bad_format == frame else "PNG"
            return FakeOpen(self.pixels[frame], fmt)

        fake_pil.Image = types.SimpleNamespace(open=open_image)
        fake_markers = types.ModuleType("verify_nexium_guest_pngs")
        fake_markers.describe = lambda rgb: (
            rgb.marker_pixels, rgb.colors, rgb.center
        )
        with patch.dict(sys.modules, {
            "PIL": fake_pil, "verify_nexium_guest_pngs": fake_markers
        }):
            return verify(self.folder)

    def log_remove(self, line):
        text = self.log.read_text()
        self.assertIn(line, text)
        self.log.write_text(text.replace(line, "REMOVED"))

    def test_valid_checkpoint_b_and_post_reset_controller(self):
        report = self.evaluate()
        self.assertTrue(report["checkpoint_activation_by_right"])
        self.assertTrue(report["b_reset_to_activated_checkpoint"])
        self.assertTrue(report["control_resumed_after_respawn"])
        self.assertTrue(report["release_stops_movement"])

    def test_missing_checkpoint_activation_flag(self):
        self.pixels[95].overrides[(190, 250)] = FLAG_OFF
        with self.assertRaisesRegex(ValueError, "checkpoint flag activation mismatch"):
            self.evaluate()

    def test_false_positive_initial_flag(self):
        self.pixels[30].overrides[(190, 250)] = FLAG_ON
        with self.assertRaisesRegex(ValueError, "checkpoint flag activation mismatch"):
            self.evaluate()

    def test_missing_native_respawn_counter(self):
        self.pixels[145].overrides[(522, 62)] = COUNTER_OFF
        with self.assertRaisesRegex(ValueError, "native respawn counter mismatch"):
            self.evaluate()

    def test_false_native_counter_before_reset(self):
        self.pixels[95].overrides[(522, 62)] = COUNTER_ON
        with self.assertRaisesRegex(ValueError, "native respawn counter mismatch"):
            self.evaluate()

    def test_missing_player_hp_tick(self):
        self.pixels[145].overrides[(36, 18)] = (0, 0, 0)
        with self.assertRaisesRegex(ValueError, "hero HP changed unexpectedly"):
            self.evaluate()

    def test_enemy_hp_must_be_untouched(self):
        self.pixels[195].overrides[(244, 18)] = (0, 0, 0)
        with self.assertRaisesRegex(ValueError, "enemy HP changed unexpectedly"):
            self.evaluate()

    def test_initial_world_position_protected(self):
        self.pixels[30].center = 180.0
        with self.assertRaisesRegex(ValueError, "did not start"):
            self.evaluate()

    def test_right_must_reach_checkpoint(self):
        self.pixels[95].center = 150.0
        with self.assertRaisesRegex(ValueError, "did not activate distant checkpoint"):
            self.evaluate()

    def test_b_must_reset_to_checkpoint_not_spawn(self):
        self.pixels[145].center = 125.5
        with self.assertRaisesRegex(ValueError, "did not respawn at checkpoint"):
            self.evaluate()

    def test_player_must_move_after_b(self):
        self.pixels[195].center = 210.0
        with self.assertRaisesRegex(ValueError, "cannot move after"):
            self.evaluate()

    def test_player_must_stop_after_release(self):
        self.pixels[230].center = 268.0
        with self.assertRaisesRegex(ValueError, "kept moving"):
            self.evaluate()

    def test_missing_world_marker_rejected(self):
        self.pixels[95].marker_pixels = 0
        with self.assertRaisesRegex(ValueError, "missing source-authored x marker"):
            self.evaluate()

    def test_low_color_diversity_rejected(self):
        self.pixels[95].colors = 2
        with self.assertRaisesRegex(ValueError, "missing source-authored x marker"):
            self.evaluate()

    def test_missing_guest_png_fails_closed(self):
        (self.folder / "raster-frame-0145.png").unlink()
        with self.assertRaises(FileNotFoundError):
            self.evaluate()

    def test_wrong_png_format_fails_closed(self):
        self.bad_format = 195
        with self.assertRaisesRegex(ValueError, "is not a PNG"):
            self.evaluate()

    def test_missing_capture_log_fails_closed(self):
        self.log_remove("HEMAN_GUEST_FRAME_PNG frame=145 ")
        with self.assertRaisesRegex(ValueError, "Missing true guest framebuffer"):
            self.evaluate()

    def test_missing_b_hid_event_fails_closed(self):
        self.log_remove("HEMAN_CHECKPOINT_HID frame=107 buttons=B")
        with self.assertRaisesRegex(ValueError, "Missing real NeXium checkpoint HID"):
            self.evaluate()

    def test_missing_second_right_release_fails_closed(self):
        self.log_remove("HEMAN_CHECKPOINT_HID frame=174 buttons=")
        with self.assertRaisesRegex(ValueError, "Missing real NeXium checkpoint HID"):
            self.evaluate()

    def test_false_release_right_still_held_is_rejected(self):
        # A prefix search for "buttons=" would incorrectly accept this.
        log = self.log.read_text()
        old = "HEMAN_CHECKPOINT_HID frame=78 buttons=\n"
        self.assertIn(old, log)
        self.log.write_text(log.replace(old,
            "HEMAN_CHECKPOINT_HID frame=78 buttons=DRIGHT\n"))
        with self.assertRaisesRegex(ValueError, "Missing real NeXium checkpoint HID"):
            self.evaluate()

    def test_false_b_release_still_held_is_rejected(self):
        log = self.log.read_text()
        old = "HEMAN_CHECKPOINT_HID frame=117 buttons=\n"
        self.assertIn(old, log)
        self.log.write_text(log.replace(old,
            "HEMAN_CHECKPOINT_HID frame=117 buttons=B\n"))
        with self.assertRaisesRegex(ValueError, "Missing real NeXium checkpoint HID"):
            self.evaluate()

    def test_extra_unrelated_log_text_does_not_mask_release(self):
        log = self.log.read_text()
        old = "HEMAN_CHECKPOINT_HID frame=174 buttons=\n"
        self.assertIn(old, log)
        self.log.write_text(log.replace(old,
            "prefix HEMAN_CHECKPOINT_HID frame=174 buttons=\n"))
        with self.assertRaisesRegex(ValueError, "Missing real NeXium checkpoint HID"):
            self.evaluate()

    def test_missing_runner_log_fails_closed(self):
        self.log.unlink()
        with self.assertRaises(FileNotFoundError):
            self.evaluate()


if __name__ == "__main__":
    unittest.main()
