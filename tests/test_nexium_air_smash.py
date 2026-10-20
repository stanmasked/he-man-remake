"""Mock RGB objects to reject forged/incomplete guest evidence (not emulation)."""
from __future__ import annotations

import sys
import tempfile
import types
from pathlib import Path
from unittest import TestCase, main
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from instrument_nexium_air_smash import instrument, FRAMES, HID_EVENTS
from verify_nexium_air_smash_pngs import (
    verify, READY, ACTIVE, IMPACT, COOLDOWN, BORDER,
    STAGE_ONE, STAGE_TWO, FIRST_CLEAR_BORDER, FIRST_CLEAR_TEXT, CYAN_Y_MARK,
)
from test_nexium_hid_instrument import SOURCE

REV = {"ready": READY, "active": ACTIVE, "impact": IMPACT,
       "cooldown": COOLDOWN}


class FakeRGB:
    size = (640, 360)
    def __init__(self, stage, status, clear, y, x, data):
        self.stage, self.status, self.clear = stage, status, clear
        self.y, self.x, self.data = y, x, data

    def getpixel(self, xy):
        if xy == (404, 9):
            return STAGE_ONE if self.stage == 1 else STAGE_TWO
        if xy == (408, 9):
            return STAGE_TWO
        if xy == (547, 47):
            return FIRST_CLEAR_BORDER if self.clear else (0, 0, 0)
        if xy == (553, 53):
            return FIRST_CLEAR_TEXT if self.clear else (0, 0, 0)
        if xy == (575, 79):
            return BORDER
        if xy == (588, 88):
            return REV.get(self.status, (1, 2, 3))
        if xy[0] == 476 and 80 <= xy[1] < 340:
            return CYAN_Y_MARK if self.y <= xy[1] < self.y + 9 else (0, 0, 0)
        raise ValueError(f"Unexpected pixel {xy}")

    def tobytes(self):
        return self.data


class FakeImage:
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


class AirSmashGuestContractTests(TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.fake = {}
        for index, f in enumerate(FRAMES):
            status = (
                None if f == 75 else
                "active" if f in (145, 146) else
                "impact" if f in (147, 148, 150, 152) else
                "cooldown" if f in (158, 183, 193, 211) else
                "ready")
            self.fake[f] = FakeRGB(
                1 if f == 75 else 2, status, f == 75,
                260 if f == 143 else 310,
                125.5 if f == 75 else
                160.0 if f in (183, 193, 211, 231) else
                50.0 if f == 245 else 120.0,
                b"paused-raster" if f in (183, 193) else
                bytes((index+1,)))
            (self.root / f"raster-frame-{f:04}.png").write_bytes(
                b"not-real-guest-png")
        lines = [
            f"HEMAN_SMASH_HID frame={f} {action}"
            for f, action in HID_EVENTS
        ]
        lines += [
            f"HEMAN_GUEST_FRAME_PNG frame={f} dimensions=640x360 "
            f"path={self.root / f'raster-frame-{f:04}.png'}"
            for f in FRAMES
        ]
        self.log = self.root / "raster-runner.log"
        self.log.write_text("\n".join(lines) + "\n")

    def run_check(self):
        pil = types.ModuleType("PIL")
        pil.Image = types.SimpleNamespace(
            open=lambda file: FakeImage(
                self.fake[int(Path(file).stem.split("-")[-1])]))
        guest = types.ModuleType("verify_nexium_guest_pngs")
        guest.describe = lambda rgb: (192, 16, rgb.x)
        # Imported verifier captures describe at module import; patch there.
        with patch.dict(sys.modules, {"PIL": pil}), patch(
                "verify_nexium_air_smash_pngs.describe",
                side_effect=guest.describe):
            return verify(self.root)

    def test_pinned_guest_injection_reaches_both_frame_receivers(self):
        modified = instrument(SOURCE)
        self.assertEqual(modified.count("HEMAN_SMASH_HID frame="), 2)
        self.assertEqual(modified.count("HEMAN_GUEST_FRAME_PNG frame="), 2)
        self.assertIn('144 | 150 => "buttons=DRIGHT,ZL"', modified)
        self.assertIn('175 => "buttons=MINUS"', modified)
        with self.assertRaises(ValueError):
            instrument(modified)

    def test_positive_fake_contract_is_not_real_emulator_evidence(self):
        report = self.run_check()
        self.assertTrue(report["real_guest_jump_and_zl_activation"])
        self.assertTrue(report["pause_retained_identical_guest_pixels"])
        self.assertFalse(report["original_ios_ability_parity_verified"])

    def test_missing_zl_edge_rejected(self):
        self.log.write_text(self.log.read_text().replace(
            "HEMAN_SMASH_HID frame=144 buttons=DRIGHT,ZL",
            "HEMAN_SMASH_HID frame=144 buttons=DRIGHT"))
        with self.assertRaisesRegex(ValueError, "controller"):
            self.run_check()

    def test_duplicate_zl_edge_rejected(self):
        self.log.write_text(self.log.read_text() +
                            "HEMAN_SMASH_HID frame=144 buttons=DRIGHT,ZL\n")
        with self.assertRaisesRegex(ValueError, "controller"):
            self.run_check()

    def test_absent_frame_rejected(self):
        (self.root / "raster-frame-0145.png").unlink()
        with self.assertRaisesRegex(ValueError, "guest PNG"):
            self.run_check()

    def test_duplicate_png_attestation_rejected(self):
        extra = (f"HEMAN_GUEST_FRAME_PNG frame=145 dimensions=640x360 "
                 f"path={self.root / 'raster-frame-0145.png'}\n")
        self.log.write_text(self.log.read_text() + extra)
        with self.assertRaisesRegex(ValueError, "attestation"):
            self.run_check()

    def test_stale_other_session_png_path_rejected(self):
        original = str(self.root / "raster-frame-0145.png")
        self.log.write_text(self.log.read_text().replace(
            original, "/tmp/previous-run/raster-frame-0145.png"))
        with self.assertRaisesRegex(ValueError, "wrong-run"):
            self.run_check()

    def test_no_staged_native_jump_rejected(self):
        self.fake[143].y = 308
        with self.assertRaisesRegex(ValueError, "A-button jump"):
            self.run_check()

    def test_missing_active_status_rejected(self):
        for f in (145, 146, 147, 148):
            self.fake[f].status = "ready"
        with self.assertRaisesRegex(ValueError, "active ZL"):
            self.run_check()

    def test_missing_landing_impact_rejected(self):
        for f in (147, 148, 150, 152):
            self.fake[f].status = "cooldown"
        with self.assertRaisesRegex(ValueError, "impact"):
            self.run_check()

    def test_repeated_zl_cooldown_bypass_rejected(self):
        self.fake[158].status = "active"
        with self.assertRaisesRegex(ValueError, "second ZL"):
            self.run_check()

    def test_pause_frame_changed_rejected(self):
        self.fake[193].data = b"unexpected-new-frame"
        with self.assertRaisesRegex(ValueError, "pause"):
            self.run_check()

    def test_native_b_respawn_missing_rejected(self):
        self.fake[245].x = 158.0
        with self.assertRaisesRegex(ValueError, "B edge"):
            self.run_check()

    def test_wrong_stage_rejected(self):
        self.fake[145].stage = 1
        with self.assertRaisesRegex(ValueError, "transition"):
            self.run_check()

    def test_premature_final_clear_rejected(self):
        self.fake[148].clear = True
        with self.assertRaisesRegex(ValueError, "FINISH"):
            self.run_check()

    def test_bad_hud_color_rejected(self):
        self.fake[145].status = "invalid"
        with self.assertRaisesRegex(ValueError, "indicator"):
            self.run_check()

    def test_lingering_cooldown_after_restart_rejected(self):
        self.fake[245].status = "cooldown"
        with self.assertRaisesRegex(ValueError, "respawn"):
            self.run_check()


if __name__ == "__main__":
    main()
