"""Adversarial source-only tests for the REAL NeXium HM_EXIT guest proof.

All mocked PNGs are test fixtures, never considered emulator evidence.
"""
from __future__ import annotations

import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from instrument_nexium_exit_clear import FRAMES, INPUT_EVENTS, instrument
from verify_nexium_exit_clear_pngs import (
    CLEAR_BORDER, CLEAR_LETTER, verify,
)
from test_nexium_hid_instrument import SOURCE


class FakeRGB:
    size = (640, 360)

    def __init__(self, x, clear):
        self.x = x
        self.clear = clear
        self.border = CLEAR_BORDER if clear else (1, 2, 3)
        self.letter = CLEAR_LETTER if clear else (1, 2, 3)
        self.markers = 192
        self.colors = 16

    def getpixel(self, point):
        if point == (547, 47):
            return self.border
        if point == (553, 53):
            return self.letter
        raise AssertionError(f"Unknown guest HUD position {point}")


class FakeOpened:
    format = "PNG"

    def __init__(self, rgb):
        self.rgb = rgb

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def convert(self, mode):
        assert mode == "RGB"
        return self.rgb


class GenuineExitContractTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.folder = Path(temp.name)
        x = (125.5, 185.5, 265.5, 365.5, 365.5)
        self.pixels = {
            frame: FakeRGB(pos, frame >= 80)
            for frame, pos in zip(FRAMES, x)
        }
        for frame in FRAMES:
            (self.folder / f"raster-frame-{frame:04}.png").write_bytes(b"mock-image")
        records = [
            f"HEMAN_GUEST_FRAME_PNG frame={f} dimensions=640x360 path=guest.png"
            for f in FRAMES
        ] + [
            f"HEMAN_HID_SCHEDULE frame={frame} {buttons}"
            for frame, buttons in INPUT_EVENTS
        ]
        self.log = self.folder / "raster-runner.log"
        self.log.write_text("\n".join(records) + "\n")

    def check(self):
        pil = types.ModuleType("PIL")
        pil.Image = types.SimpleNamespace(
            open=lambda file: FakeOpened(
                self.pixels[int(Path(file).stem.split("-")[-1])]
            )
        )
        guest = types.ModuleType("verify_nexium_guest_pngs")
        guest.describe = lambda rgb: (rgb.markers, rgb.colors, rgb.x)
        with patch.dict(sys.modules, {
            "PIL": pil, "verify_nexium_guest_pngs": guest
        }):
            return verify(self.folder)

    def change_log(self, old, new):
        current = self.log.read_text()
        self.assertIn(old + "\n", current)
        self.log.write_text(current.replace(old + "\n", new + "\n"))

    def test_both_pinned_guest_frame_rx_receivers(self):
        coded = instrument(SOURCE)
        self.assertEqual(coded.count(
            "if matches!(frames, 30 | 60 | 80 | 120 | 300) {"
        ), 2)
        self.assertEqual(coded.count("HEMAN_HID_SCHEDULE frame="), 2)
        self.assertEqual(coded.count("HEMAN_GUEST_FRAME_PNG frame="), 2)
        with self.assertRaisesRegex(ValueError, "already been instrumented"):
            instrument(coded)

    def test_real_right_schedule_not_fake_B(self):
        self.assertEqual(INPUT_EVENTS, (
            (45, "buttons=DRIGHT"), (105, "buttons=")
        ))
        self.assertEqual(FRAMES, (30, 60, 80, 120, 300))

    def test_valid_source_only_fixture(self):
        v = self.check()
        self.assertTrue(v["exit_hidden_before_input"])
        self.assertEqual(v["exit_visible"], [80, 120, 300])
        self.assertEqual(v["player_world_x_markers"][-2:], [365.5, 365.5])

    def test_clear_before_controller_press_rejected(self):
        self.pixels[30].border = CLEAR_BORDER
        self.pixels[30].letter = CLEAR_LETTER
        with self.assertRaisesRegex(ValueError, "before any right-input"):
            self.check()

    def test_absent_clear_after_exit_contact_rejected(self):
        self.pixels[80].border = (1, 2, 3)
        self.pixels[80].letter = (1, 2, 3)
        with self.assertRaisesRegex(ValueError, "not visible"):
            self.check()

    def test_partial_badge_rejected(self):
        self.pixels[80].letter = (1, 2, 3)
        with self.assertRaisesRegex(ValueError, "partial or forged"):
            self.check()

    def test_no_player_movement_rejected(self):
        self.pixels[80].x = 125.5
        with self.assertRaisesRegex(ValueError, "did not move"):
            self.check()

    def test_still_moving_after_release_rejected(self):
        self.pixels[300].x = 377.5
        with self.assertRaisesRegex(ValueError, "after releasing"):
            self.check()

    def test_forged_hid_release_rejected(self):
        self.change_log(
            "HEMAN_HID_SCHEDULE frame=105 buttons=",
            "HEMAN_HID_SCHEDULE frame=105 buttons=DRIGHT"
        )
        with self.assertRaisesRegex(ValueError, "Missing exact"):
            self.check()

    def test_prefixed_fake_hid_rejected(self):
        self.change_log(
            "HEMAN_HID_SCHEDULE frame=45 buttons=DRIGHT",
            "false HEMAN_HID_SCHEDULE frame=45 buttons=DRIGHT"
        )
        with self.assertRaisesRegex(ValueError, "Missing exact"):
            self.check()

    def test_forged_png_record_rejected(self):
        self.change_log(
            "HEMAN_GUEST_FRAME_PNG frame=80 dimensions=640x360 path=guest.png",
            "false HEMAN_GUEST_FRAME_PNG frame=80 dimensions=640x360 path=guest.png"
        )
        with self.assertRaisesRegex(ValueError, "Missing genuine guest"):
            self.check()

    def test_deleted_captured_frame_rejected(self):
        (self.folder / "raster-frame-0080.png").unlink()
        with self.assertRaises(FileNotFoundError):
            self.check()

    def test_lost_native_position_marker_rejected(self):
        self.pixels[120].markers = 0
        with self.assertRaisesRegex(ValueError, "position marker missing"):
            self.check()

    def test_wrong_guest_resolution_rejected(self):
        self.pixels[120].size = (320, 240)
        with self.assertRaisesRegex(ValueError, "resolution mismatch"):
            self.check()


if __name__ == "__main__":
    unittest.main()
