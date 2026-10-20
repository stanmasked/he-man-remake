"""Synthetic contract tests for guest-only ZR proof (never real evidence)."""
from __future__ import annotations

import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from instrument_nexium_dash import FRAMES, HID_EVENTS, instrument
from verify_nexium_dash_pngs import (
    READY, ACTIVE, COOLING, STAGE_ONE, STAGE_TWO, verify,
)
from test_nexium_hid_instrument import SOURCE


class FakeFrame:
    size = (640, 360)
    def __init__(self, stage, world_x, gauge, seed):
        self.stage = stage
        self.world_x = world_x
        self.gauge = gauge
        self.seed = seed
        self.colors = 16
        self.markers = 192

    def getpixel(self, xy):
        if xy == (404, 9):
            return STAGE_ONE if self.stage == 1 else STAGE_TWO
        if xy == (408, 9):
            return STAGE_TWO
        if xy == (437, 16):
            return self.gauge
        raise AssertionError(f"unexpected pixel {xy}")

    def tobytes(self):
        return bytes([self.seed])


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


class DashGuestContractTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        xs = (245.5, 121.5, 157.5, 225.5, 290.5, 390.5, 390.5)
        gauges = (READY, READY, READY, ACTIVE, COOLING, COOLING, READY)
        self.frames = {
            f: FakeFrame(1 if f == 75 else 2, x, g, i+1)
            for i, (f,x,g) in enumerate(zip(FRAMES, xs, gauges))
        }
        for frame in FRAMES:
            (self.root / f"raster-frame-{frame:04}.png").write_bytes(
                b"test-only-not-a-real-neXium-png")
        self.log = self.root / "raster-runner.log"
        self.log.write_text("\n".join([
            f"HEMAN_GUEST_FRAME_PNG frame={f} dimensions=640x360 path=fake"
            for f in FRAMES
        ] + [f"HEMAN_DASH_HID frame={f} {state}"
             for f,state in HID_EVENTS])+"\n")

    def run_verifier(self):
        pil = types.ModuleType("PIL")
        pil.Image = types.SimpleNamespace(
            open=lambda path: FakeOpen(
                self.frames[int(Path(path).stem.split("-")[-1])]))
        marker = types.ModuleType("verify_nexium_guest_pngs")
        marker.describe = lambda frame: (
            frame.markers, frame.colors, frame.world_x)
        with patch.dict(sys.modules, {
            "PIL": pil, "verify_nexium_guest_pngs": marker,
        }):
            return verify(self.root)

    def test_instrument_both_authentic_frame_receivers(self):
        source = instrument(SOURCE)
        self.assertEqual(source.count("HEMAN_DASH_HID frame="), 2)
        self.assertEqual(source.count("HEMAN_GUEST_FRAME_PNG frame="), 2)
        with self.assertRaises(ValueError):
            instrument(source)

    def test_event_combination_uses_neXium_comma_button_syntax(self):
        self.assertIn((120, "buttons=DRIGHT,ZR"), HID_EVENTS)
        self.assertIn((128, "buttons=DRIGHT"), HID_EVENTS)

    def test_good_source_contract(self):
        data = self.run_verifier()
        self.assertTrue(data["dash_real_guest_confirmed"])
        self.assertEqual(data["stage_ids"], [1,2,2,2,2,2,2])
        self.assertEqual(data["dash_hud"]["125"], "active")
        self.assertFalse(data["commercial_ios_fidelity_verified"])

    def test_missing_zr_edge_rejected(self):
        self.log.write_text(self.log.read_text().replace(
            "HEMAN_DASH_HID frame=120 buttons=DRIGHT,ZR",
            "HEMAN_DASH_HID frame=120 buttons=DRIGHT"))
        with self.assertRaisesRegex(ValueError, "Missing real ZR"):
            self.run_verifier()

    def test_quoted_log_marker_rejected(self):
        self.log.write_text(self.log.read_text().replace(
            "HEMAN_DASH_HID frame=128 buttons=DRIGHT",
            "untrusted HEMAN_DASH_HID frame=128 buttons=DRIGHT"))
        with self.assertRaisesRegex(ValueError, "Missing real ZR"):
            self.run_verifier()

    def test_missing_real_png_rejected(self):
        (self.root / "raster-frame-0125.png").unlink()
        with self.assertRaises(FileNotFoundError):
            self.run_verifier()

    def test_bad_stage_rejected(self):
        self.frames[125].stage = 1
        with self.assertRaisesRegex(ValueError, "Stage 1 CLEAR"):
            self.run_verifier()

    def test_zr_must_activate_guest_hud(self):
        self.frames[125].gauge = READY
        with self.assertRaisesRegex(ValueError, "HUD sequence"):
            self.run_verifier()

    def test_cooldown_cannot_be_skipped(self):
        self.frames[140].gauge = READY
        with self.assertRaisesRegex(ValueError, "HUD sequence"):
            self.run_verifier()

    def test_dash_must_actually_accelerate(self):
        self.frames[125].world_x = 200.5
        with self.assertRaisesRegex(ValueError, "speed burst"):
            self.run_verifier()

    def test_release_must_stop_actual_world_x(self):
        self.frames[240].world_x += 20.0
        with self.assertRaisesRegex(ValueError, "release"):
            self.run_verifier()

    def test_pixel_mode_must_remain_original_640x360(self):
        self.frames[105].size = (320, 180)
        with self.assertRaisesRegex(ValueError, "framebuffer size"):
            self.run_verifier()


if __name__ == "__main__":
    unittest.main()
