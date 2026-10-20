"""Synthetic verification tests; real guest PNG proof requires NeXium CI."""
from __future__ import annotations
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from instrument_nexium_pause import FRAMES, HID_EVENTS, instrument
from verify_nexium_pause_pngs import PAUSE_BORDER, PAUSE_TEXT, verify
from test_nexium_hid_instrument import SOURCE


class FakeRGB:
    size = (640, 360)

    def __init__(self, position: float, paused: bool, image_state: bytes):
        self.x = position
        self.paused = paused
        self.image_state = image_state
        self.markers = 192
        self.colors = 16

    def getpixel(self, xy):
        if xy == (224, 131):
            return PAUSE_BORDER if self.paused else (1, 2, 3)
        if xy == (270, 162):
            return PAUSE_TEXT if self.paused else (1, 2, 3)
        raise AssertionError(f"unexpected screenshot sample at {xy}")

    def tobytes(self):
        return self.image_state


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


class PauseProofContractTests(unittest.TestCase):
    def setUp(self):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.folder = Path(td.name)
        xs = (125.5, 205.5, 245.5, 245.5, 315.5, 365.5, 365.5)
        self.images = {
            f: FakeRGB(x, f in (110, 135),
                       b"frozen" if f in (110, 135) else bytes([i]))
            for i, (f, x) in enumerate(zip(FRAMES, xs))
        }
        for frame in FRAMES:
            (self.folder / f"raster-frame-{frame:04}.png").write_bytes(b"fixture-not-real")
        lines = [
            f"HEMAN_GUEST_FRAME_PNG frame={f} dimensions=640x360 path=somewhere"
            for f in FRAMES
        ] + [
            f"HEMAN_PAUSE_HID frame={f} {a}" for f, a in HID_EVENTS
        ]
        self.log = self.folder / "raster-runner.log"
        self.log.write_text("\n".join(lines) + "\n")

    def inspect(self):
        pil = types.ModuleType("PIL")
        pil.Image = types.SimpleNamespace(open=lambda file: FakeOpened(
            self.images[int(Path(file).stem.split("-")[-1])]))
        guest = types.ModuleType("verify_nexium_guest_pngs")
        guest.describe = lambda im: (im.markers, im.colors, im.x)
        with patch.dict(sys.modules, {
            "PIL": pil, "verify_nexium_guest_pngs": guest,
        }):
            return verify(self.folder)

    def test_both_guest_frame_rx_paths_are_instrumented(self):
        code = instrument(SOURCE)
        self.assertEqual(code.count("HEMAN_PAUSE_HID frame="), 2)
        self.assertEqual(code.count("HEMAN_GUEST_FRAME_PNG frame="), 2)
        self.assertEqual(code.count("frames, 45 | 85 | 90 | 145 | 150 | 205"), 2)
        with self.assertRaises(ValueError):
            instrument(code)

    def test_real_minus_schedule_includes_release_and_resume(self):
        self.assertEqual(HID_EVENTS, (
            (45, "buttons=DRIGHT"), (85, "buttons=MINUS"),
            (90, "buttons=DRIGHT"), (145, "buttons=MINUS"),
            (150, "buttons=DRIGHT"), (205, "buttons="),
        ))

    def test_expected_synthetic_contract(self):
        out = self.inspect()
        self.assertEqual(out["pause_visible_at_frames"], [110, 135])
        self.assertTrue(out["paused_guest_frames_identical"])
        self.assertTrue(out["right_motion_after_resume"])

    def test_missing_minus_hid_log_rejected(self):
        s = self.log.read_text()
        self.log.write_text(s.replace(
            "HEMAN_PAUSE_HID frame=85 buttons=MINUS",
            "HEMAN_PAUSE_HID frame=85 buttons="))
        with self.assertRaisesRegex(ValueError, "Missing exact NeXium"):
            self.inspect()

    def test_prefixed_forged_log_rejected(self):
        s = self.log.read_text()
        self.log.write_text(s.replace(
            "HEMAN_PAUSE_HID frame=145 buttons=MINUS",
            "forged HEMAN_PAUSE_HID frame=145 buttons=MINUS"))
        with self.assertRaisesRegex(ValueError, "Missing exact NeXium"):
            self.inspect()

    def test_missing_guest_png_log_rejected(self):
        s = self.log.read_text()
        self.log.write_text(s.replace(
            "HEMAN_GUEST_FRAME_PNG frame=110 dimensions=640x360",
            "fake HEMAN_GUEST_FRAME_PNG frame=110 dimensions=640x360"))
        with self.assertRaisesRegex(ValueError, "Missing real guest"):
            self.inspect()

    def test_missing_guest_image_rejected(self):
        (self.folder / "raster-frame-0135.png").unlink()
        with self.assertRaises(FileNotFoundError):
            self.inspect()

    def test_paused_badge_absent_rejected(self):
        self.images[110].paused = False
        with self.assertRaisesRegex(ValueError, "PAUSED visibility"):
            self.inspect()

    def test_false_paused_badge_after_resume_rejected(self):
        self.images[175].paused = True
        with self.assertRaisesRegex(ValueError, "PAUSED visibility"):
            self.inspect()

    def test_player_drift_while_paused_rejected(self):
        self.images[135].x += 20
        with self.assertRaisesRegex(ValueError, "moved while Minus pause"):
            self.inspect()

    def test_enemy_or_world_changed_while_frozen_rejected(self):
        self.images[135].image_state = b"enemy-moved"
        with self.assertRaisesRegex(ValueError, "framebuffer changed"):
            self.inspect()

    def test_player_did_not_resume_rejected(self):
        self.images[175].x = self.images[135].x
        with self.assertRaisesRegex(ValueError, "did not resume"):
            self.inspect()

    def test_right_movement_before_pause_required(self):
        self.images[70].x = self.images[30].x
        with self.assertRaisesRegex(ValueError, "before pause"):
            self.inspect()

    def test_release_drift_rejected(self):
        self.images[300].x += 40
        with self.assertRaisesRegex(ValueError, "after final Right release"):
            self.inspect()

    def test_genuine_resolution_required(self):
        self.images[135].size = (320, 240)
        with self.assertRaisesRegex(ValueError, "framebuffer"):
            self.inspect()

    def test_actual_player_marker_required(self):
        self.images[110].markers = 0
        with self.assertRaisesRegex(ValueError, "marker missing"):
            self.inspect()


if __name__ == "__main__":
    unittest.main()
