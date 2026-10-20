"""Entirely fake images for source-contract tests; not NeXium evidence."""
from __future__ import annotations

import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from instrument_nexium_stage_chain import FRAMES, HID_EVENTS, instrument
from verify_nexium_stage_chain_pngs import (
    STAGE_FACE, STAGE_TEXT, CLEAR_BORDER, CLEAR_LETTER, verify,
)
from test_nexium_hid_instrument import SOURCE


class FakeRGB:
    size = (640, 360)

    def __init__(self, world_x, stage, clear, seed):
        self.world_x = world_x
        self.stage = stage
        self.clear = clear
        self.seed = seed
        self.markers = 192
        self.colors = 16

    def getpixel(self, xy):
        if xy == (404, 9):
            return STAGE_FACE if self.stage == 1 else STAGE_TEXT
        if xy == (408, 9):
            return STAGE_TEXT
        if xy == (547, 47):
            return CLEAR_BORDER if self.clear else (1, 2, 3)
        if xy == (553, 53):
            return CLEAR_LETTER if self.clear else (1, 2, 3)
        raise AssertionError(f"unexpected pixel {xy}")

    def tobytes(self):
        return bytes([self.seed])


class FakeOpened:
    format = "PNG"

    def __init__(self, image):
        self.image = image

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def convert(self, mode):
        assert mode == "RGB"
        return self.image


class StageGuestContractTests(unittest.TestCase):
    def setUp(self):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.root = Path(td.name)
        xs = (125.5, 265.5, 121.5, 201.5, 261.5, 261.5)
        self.images = {
            frame: FakeRGB(x, 1 if i < 2 else 2, i == 1, i + 1)
            for i, (frame, x) in enumerate(zip(FRAMES, xs))
        }
        for frame in FRAMES:
            (self.root / f"raster-frame-{frame:04}.png").write_bytes(b"fake-not-png")
        self.log = self.root / "raster-runner.log"
        self.log.write_text("\n".join([
            f"HEMAN_GUEST_FRAME_PNG frame={f} dimensions=640x360 path=fake"
            for f in FRAMES
        ] + [f"HEMAN_CHAIN_HID frame={f} {action}"
             for f, action in HID_EVENTS]) + "\n")

    def evaluate(self):
        pil = types.ModuleType("PIL")
        pil.Image = types.SimpleNamespace(open=lambda path: FakeOpened(
            self.images[int(Path(path).stem.split("-")[-1])]))
        guest = types.ModuleType("verify_nexium_guest_pngs")
        guest.describe = lambda im: (im.markers, im.colors, im.world_x)
        with patch.dict(sys.modules, {
            "PIL": pil, "verify_nexium_guest_pngs": guest
        }):
            return verify(self.root)

    def test_original_two_guest_receivers_instrumented(self):
        result = instrument(SOURCE)
        self.assertEqual(result.count("HEMAN_CHAIN_HID frame="), 2)
        self.assertEqual(result.count("HEMAN_GUEST_FRAME_PNG frame="), 2)
        with self.assertRaises(ValueError):
            instrument(result)

    def test_exact_hid_schedule(self):
        self.assertEqual(HID_EVENTS, (
            (45, "buttons=DRIGHT"), (78, "buttons="),
            (90, "buttons=A"), (95, "buttons="),
            (110, "buttons=DRIGHT"), (165, "buttons="),
        ))

    def test_valid_source_contract(self):
        result = self.evaluate()
        self.assertEqual(result["stages"], [1, 1, 2, 2, 2, 2])
        self.assertEqual(result["clear_visible"], [75])
        self.assertTrue(result["stage_2_movement_and_release_confirmed"])
        self.assertFalse(result["original_ios_content_verified"])

    def test_missing_real_a_press_rejected(self):
        self.log.write_text(self.log.read_text().replace(
            "HEMAN_CHAIN_HID frame=90 buttons=A",
            "HEMAN_CHAIN_HID frame=90 buttons="))
        with self.assertRaisesRegex(ValueError, "Missing exact"):
            self.evaluate()

    def test_fake_prefixed_hid_rejected(self):
        self.log.write_text(self.log.read_text().replace(
            "HEMAN_CHAIN_HID frame=110 buttons=DRIGHT",
            "fake HEMAN_CHAIN_HID frame=110 buttons=DRIGHT"))
        with self.assertRaisesRegex(ValueError, "Missing exact"):
            self.evaluate()

    def test_missing_png_capture_log_rejected(self):
        self.log.write_text(self.log.read_text().replace(
            "HEMAN_GUEST_FRAME_PNG frame=105 dimensions=640x360",
            "fake HEMAN_GUEST_FRAME_PNG frame=105 dimensions=640x360"))
        with self.assertRaisesRegex(ValueError, "Missing original"):
            self.evaluate()

    def test_missing_png_file_rejected(self):
        (self.root / "raster-frame-0105.png").unlink()
        with self.assertRaises(FileNotFoundError):
            self.evaluate()

    def test_stage_stuck_on_first_rejected(self):
        self.images[105].stage = 1
        with self.assertRaisesRegex(ValueError, "did not transition"):
            self.evaluate()

    def test_stage_badge_missing_rejected(self):
        self.images[140].getpixel = lambda xy: (0, 0, 0)
        with self.assertRaisesRegex(ValueError, "stage badge"):
            self.evaluate()

    def test_first_clear_not_earned_rejected(self):
        self.images[75].clear = False
        with self.assertRaisesRegex(ValueError, "CLEAR"):
            self.evaluate()

    def test_clear_leaks_to_second_stage_rejected(self):
        self.images[140].clear = True
        with self.assertRaisesRegex(ValueError, "completion leaked"):
            self.evaluate()

    def test_no_second_room_reset_rejected(self):
        self.images[105].world_x = 260
        with self.assertRaisesRegex(ValueError, "did not reset"):
            self.evaluate()

    def test_no_second_room_motion_rejected(self):
        self.images[140].world_x = self.images[105].world_x
        with self.assertRaisesRegex(ValueError, "did not move"):
            self.evaluate()

    def test_no_release_stop_rejected(self):
        self.images[240].world_x += 40
        with self.assertRaisesRegex(ValueError, "persisted after release"):
            self.evaluate()


if __name__ == "__main__":
    unittest.main()
