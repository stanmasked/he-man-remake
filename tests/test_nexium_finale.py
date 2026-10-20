"""Fabricated guest PNG proxies. These tests DO NOT execute NeXium."""
from __future__ import annotations

import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from instrument_nexium_finale import FRAMES, HID_EVENTS, instrument
from verify_nexium_finale_pngs import (
    STAGE_ONE, STAGE_TWO, CLEAR_BORDER, CLEAR_LETTER,
    FINISH_BORDER, FINISH_GLYPH, FINISH_UNDERLINE, CYAN_HEIGHT, verify,
)
from test_nexium_hid_instrument import SOURCE


class FakeRGB:
    size = (640, 360)
    def __init__(self, stage, clear, finish, height, world_x, blob):
        self.stage = stage
        self.clear = clear
        self.finish = finish
        self.height = height
        self.world_x = world_x
        self.blob = blob

    def getpixel(self, xy):
        if xy == (404, 9):
            return STAGE_ONE if self.stage == 1 else STAGE_TWO
        if xy == (408, 9):
            return STAGE_TWO
        if xy == (547, 47):
            return CLEAR_BORDER if self.clear else (0, 0, 0)
        if xy == (553, 53):
            return CLEAR_LETTER if self.clear else (0, 0, 0)
        if xy == (208, 120):
            return FINISH_BORDER if self.finish else (0, 0, 0)
        if xy == (258, 155):
            return FINISH_GLYPH if self.finish else (0, 0, 0)
        if xy == (254, 201):
            return FINISH_UNDERLINE if self.finish else (0, 0, 0)
        if xy[0] == 476:
            return CYAN_HEIGHT if self.height <= xy[1] < self.height + 9 else (0, 0, 0)
        raise AssertionError(f"unexpected pixel {xy}")

    def tobytes(self):
        return self.blob


class FakeOpen:
    format = "PNG"
    def __init__(self, frame):
        self.frame = frame
    def __enter__(self):
        return self
    def __exit__(self, *_):
        return False
    def convert(self, mode):
        assert mode == "RGB"
        return self.frame


class FinaleGuestSyntheticContractTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = Path(folder.name)
        self.frames = {}
        for idx, frame in enumerate(FRAMES):
            is_frozen = frame in (490, 515)
            self.frames[frame] = FakeRGB(
                1 if frame == 75 else 2,
                frame == 75,
                frame in (465, 490, 515),
                240 if frame == 365 else 310,
                (245.5 if frame == 75 else
                 121.5 if frame == 105 else
                 445.5 if frame < 540 else 121.5),
                b"frozen-still-frame" if is_frozen else bytes([idx + 1]))
            (self.folder / f"raster-frame-{frame:04}.png").write_bytes(
                b"this-is-fake-not-an-actual-png")
        self.log = self.folder / "raster-runner.log"
        self.log.write_text("\n".join([
            f"HEMAN_GUEST_FRAME_PNG frame={f} dimensions=640x360 "
            f"path={self.folder / f'raster-frame-{f:04}.png'}"
            for f in FRAMES
        ] + [
            f"HEMAN_FINALE_HID frame={frame} {buttons}"
            for frame, buttons in HID_EVENTS
        ]) + "\n")

    def run_checker(self):
        fake_pil = types.ModuleType("PIL")
        fake_pil.Image = types.SimpleNamespace(open=lambda path: FakeOpen(
            self.frames[int(Path(path).stem.split("-")[-1])]))
        guest = types.ModuleType("verify_nexium_guest_pngs")
        guest.describe = lambda frame: (192, 16, frame.world_x)
        with patch.dict(sys.modules, {
            "PIL": fake_pil, "verify_nexium_guest_pngs": guest}):
            return verify(self.folder)

    def test_inject_both_genuine_upstream_frame_receivers(self):
        output = instrument(SOURCE)
        self.assertEqual(output.count("HEMAN_FINALE_HID frame="), 2)
        self.assertEqual(output.count("HEMAN_GUEST_FRAME_PNG frame="), 2)
        self.assertIn('350 => "buttons=DRIGHT,A"', output)
        self.assertIn('540 => "buttons=B"', output)
        with self.assertRaises(ValueError):
            instrument(output)

    def test_input_script_captures_real_jump_and_fresh_B(self):
        self.assertIn((350, "buttons=DRIGHT,A"), HID_EVENTS)
        self.assertIn((353, "buttons=DRIGHT"), HID_EVENTS)
        self.assertIn((540, "buttons=B"), HID_EVENTS)
        self.assertIn((543, "buttons="), HID_EVENTS)

    def test_good_fake_contract_never_claims_original_ios(self):
        data = self.run_checker()
        self.assertTrue(data["native_jump_visible"])
        self.assertTrue(data["native_B_restart_confirmed"])
        self.assertTrue(data["final_two_guest_frames_byte_identical"])
        self.assertEqual(data["terminal_finish_frames"], [465, 490, 515])
        self.assertFalse(data["original_ios_gameplay_fidelity_verified"])

    def test_missing_B_edge_rejected(self):
        self.log.write_text(self.log.read_text().replace(
            "HEMAN_FINALE_HID frame=540 buttons=B",
            "HEMAN_FINALE_HID frame=540 buttons="))
        with self.assertRaisesRegex(ValueError, "guest HID"):
            self.run_checker()

    def test_duplicate_guest_hid_rejected(self):
        self.log.write_text(self.log.read_text() +
            "HEMAN_FINALE_HID frame=540 buttons=B\n")
        with self.assertRaisesRegex(ValueError, "guest HID"):
            self.run_checker()

    def test_missing_or_duplicate_png_capture_attestation_rejected(self):
        line = (f"HEMAN_GUEST_FRAME_PNG frame=465 dimensions=640x360 "
                f"path={self.folder / 'raster-frame-0465.png'}\n")
        self.log.write_text(self.log.read_text() + line)
        with self.assertRaisesRegex(ValueError, "attestation"):
            self.run_checker()

    def test_stale_guest_png_from_other_run_rejected(self):
        target = str(self.folder / "raster-frame-0465.png")
        self.log.write_text(self.log.read_text().replace(
            f"path={target}", "path=/tmp/previous-run/raster-frame-0465.png"))
        with self.assertRaisesRegex(ValueError, "path disagrees"):
            self.run_checker()

    def test_no_real_native_second_exit_rejected(self):
        self.frames[465].finish = False
        with self.assertRaisesRegex(ValueError, "FINISH/B restart"):
            self.run_checker()

    def test_early_fake_finish_rejected(self):
        self.frames[330].finish = True
        with self.assertRaisesRegex(ValueError, "FINISH/B restart"):
            self.run_checker()

    def test_partial_overlay_is_rejected(self):
        old = self.frames[465].getpixel
        self.frames[465].getpixel = lambda p: (
            (0, 0, 0) if p == (254, 201) else old(p))
        with self.assertRaisesRegex(ValueError, "Partially drawn FINISH"):
            self.run_checker()

    def test_finishing_does_not_hide_emulator_motion(self):
        self.frames[515].blob = b"unexpected-player-motion"
        with self.assertRaisesRegex(ValueError, "advanced"):
            self.run_checker()

    def test_B_must_reset_world_x_and_hide_finish(self):
        self.frames[565].world_x = 440
        with self.assertRaisesRegex(ValueError, "native stage-2 player"):
            self.run_checker()

    def test_B_must_clear_FINISH_panel(self):
        self.frames[565].finish = True
        with self.assertRaisesRegex(ValueError, "FINISH/B restart"):
            self.run_checker()

    def test_jump_requires_world_height_marker(self):
        self.frames[365].height = 305
        with self.assertRaisesRegex(ValueError, "native A jump"):
            self.run_checker()

    def test_first_room_CLEAR_never_substitutes_for_finale(self):
        self.frames[75].clear = False
        with self.assertRaisesRegex(ValueError, "first-room CLEAR"):
            self.run_checker()

    def test_stage_label_must_stay_two_during_retry(self):
        self.frames[565].stage = 1
        with self.assertRaisesRegex(ValueError, "transition"):
            self.run_checker()

    def test_missing_png_file_rejected(self):
        (self.folder / "raster-frame-0490.png").unlink()
        with self.assertRaises(FileNotFoundError):
            self.run_checker()

    def test_bad_dimensions_rejected(self):
        self.frames[490].size = (320, 180)
        with self.assertRaisesRegex(ValueError, "dimensions"):
            self.run_checker()


if __name__ == "__main__":
    unittest.main()
