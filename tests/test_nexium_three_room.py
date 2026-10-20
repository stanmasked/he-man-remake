"""Mock-only fail-closed verifier regression tests; NOT NeXium execution."""
from __future__ import annotations

import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from instrument_nexium_three_room import FRAMES, HID_EVENTS, instrument
from verify_nexium_three_room_pngs import (
    verify, DIGITS, WHITE, FACE, GOLD, CLEAR_BORDER, CLEAR_LETTER,
    RETRY_GREEN, CYAN_HEIGHT, PROGRESS_COLOR,
)
from test_nexium_hid_instrument import SOURCE


class FakeRGB:
    size = (640, 360)

    def __init__(self, stage, clear, finish, respawn, y, x, payload):
        self.stage, self.clear, self.finish = stage, clear, finish
        self.respawn, self.y, self.x, self.payload = respawn, y, x, payload
        self.progress = None

    def getpixel(self, xy):
        if xy == (393, 4):
            return GOLD
        if xy == (398, 8):
            return FACE
        x, y = xy
        if y in (10, 14, 18, 22, 26) and x in (405, 409, 413):
            n = ((y - 10) // 4) * 3 + (x - 405) // 4
            return WHITE if DIGITS[self.stage][n] == "1" else FACE
        if xy == (547, 47):
            return CLEAR_BORDER if self.clear else (0, 0, 0)
        if xy == (553, 53):
            return CLEAR_LETTER if self.clear else (0, 0, 0)
        if xy == (208, 120):
            return GOLD if self.finish else (0, 0, 0)
        if xy in ((258, 155), (315, 213), (322, 218)):
            return WHITE if self.finish else (0, 0, 0)
        if xy in ((254, 201), (311, 210)):
            return RETRY_GREEN if self.finish else (0, 0, 0)
        if xy == (522, 62):
            return RETRY_GREEN if self.respawn else (0, 0, 0)
        if 70 <= x < 530 and 330 <= y < 340:
            left = 70 + int(self.progress / 2 + 0.5) if self.progress is not None else -1
            return PROGRESS_COLOR if left <= x < left + 4 else (0, 0, 0)
        if x == 476 and 80 <= y < 340:
            return CYAN_HEIGHT if self.y <= y < self.y + 9 else (0, 0, 0)
        raise AssertionError(f"unhandled pixel {xy}")

    def tobytes(self):
        return self.payload


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


class ThirdRoomMockContractTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.folder = Path(tmp.name)
        self.frames = {}
        for idx, f in enumerate(FRAMES):
            stage = 1 if f == 75 else 2 if f <= 505 else 3
            clear = f in (75, 465, 505, 1045, 1080, 1120)
            finish = f in (1045, 1080, 1120)
            respawn = 850 <= f <= 1120
            y = 250 if f == 970 else 314 if stage == 3 else 310
            x = 245 if f == 75 else 121 if f in (105, 535, 1170, 1190) else 445
            payload = b"stage-3-frozen" if f in (1080, 1120) else bytes([idx + 1])
            self.frames[f] = FakeRGB(stage, clear, finish, respawn, y, x, payload)
            if stage == 3:
                self.frames[f].progress = {
                    535: 60, 650: 290, 820: 630, 850: 460,
                    930: 620, 945: 650, 970: 700,
                    1045: 828, 1080: 828, 1120: 828,
                    1170: 48, 1190: 48,
                }[f]
            (self.folder / f"raster-frame-{f:04}.png").write_bytes(b"fake")
        self.log = self.folder / "raster-runner.log"
        self.log.write_text("\n".join([
            "Production runner complete: frames=1205",
            *(
                f"HEMAN_THREE_HID frame={f} {action}"
                for f, action in HID_EVENTS
            ),
            *(
                f"HEMAN_GUEST_FRAME_PNG frame={f} dimensions=640x360 "
                f"path={self.folder / f'raster-frame-{f:04}.png'}"
                for f in FRAMES
            ),
        ]) + "\n")

    def run_check(self):
        pil = types.ModuleType("PIL")
        pil.Image = types.SimpleNamespace(open=lambda p: FakeOpen(
            self.frames[int(Path(p).stem.split("-")[-1])]))
        guest = types.ModuleType("verify_nexium_guest_pngs")
        guest.describe = lambda frame: (192, 16, frame.x)
        with patch.dict(sys.modules, {"PIL": pil, "verify_nexium_guest_pngs": guest}):
            return verify(self.folder)

    def test_instruments_both_pinned_receivers_and_exact_edges(self):
        source = instrument(SOURCE)
        self.assertEqual(source.count("HEMAN_THREE_HID frame="), 2)
        self.assertEqual(source.count("HEMAN_GUEST_FRAME_PNG frame="), 2)
        self.assertIn('952 => "buttons=DRIGHT,A"', source)
        self.assertIn('1140 => "buttons=B"', source)
        with self.assertRaises(ValueError):
            instrument(source)

    def test_positive_fake_contract_is_not_guest_proof(self):
        output = self.run_check()
        self.assertEqual(output["stage_sequence"], [
            1, 2, 2, 2, 2, 2, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3])
        self.assertTrue(output["genuine_stage3_jump_seen"])
        self.assertFalse(output["original_ios_physics_fidelity_verified"])

    def test_stage_three_must_appear(self):
        # Mutate the whole fake frame consistently: if stage 3 is absent,
        # its optional full world-X HUD must also be absent. A mismatched
        # stage2 badge + stage3 cursor is covered by the separate
        # test_world_x_hud_must_not_appear_on_earlier_stages regression.
        self.frames[535].stage = 2
        self.frames[535].progress = None
        with self.assertRaisesRegex(ValueError, "three-stage"):
            self.run_check()

    def test_corrupted_unclamped_world_x_rejected(self):
        self.frames[820].progress = 290
        with self.assertRaisesRegex(ValueError, "world-X"):
            self.run_check()

    def test_forged_progress_cursor_missing_rejected(self):
        self.frames[1045].progress = None
        with self.assertRaisesRegex(ValueError, "world-X"):
            self.run_check()

    def test_world_x_hud_must_not_appear_on_earlier_stages(self):
        self.frames[365].progress = 560
        with self.assertRaisesRegex(ValueError, "leaked"):
            self.run_check()

    def test_corrupt_third_stage_glyph_rejected(self):
        old = self.frames[535].getpixel
        self.frames[535].getpixel = lambda p: (
            (4, 5, 6) if p == (413, 22) else old(p))
        with self.assertRaisesRegex(ValueError, "HUD color"):
            self.run_check()

    def test_stage_two_FINISH_must_not_appear(self):
        self.frames[465].finish = True
        with self.assertRaisesRegex(ValueError, "FINISH"):
            self.run_check()

    def test_third_clear_cannot_be_faked_with_finish(self):
        self.frames[1045].clear = False
        with self.assertRaisesRegex(ValueError, "earned CLEAR"):
            self.run_check()

    def test_pre_exit_third_clear_rejected(self):
        self.frames[970].clear = True
        with self.assertRaisesRegex(ValueError, "earned CLEAR"):
            self.run_check()

    def test_missing_hazard_respawn_rejected(self):
        self.frames[850].respawn = False
        with self.assertRaisesRegex(ValueError, "hazard/respawn"):
            self.run_check()

    def test_no_jump_rejected(self):
        self.frames[970].y = 314
        with self.assertRaisesRegex(ValueError, "A jump"):
            self.run_check()

    def test_final_must_freeze(self):
        self.frames[1120].payload = b"still-updating"
        with self.assertRaisesRegex(ValueError, "advanced"):
            self.run_check()

    def test_B_must_clear_finish(self):
        self.frames[1170].finish = True
        with self.assertRaisesRegex(ValueError, "FINISH"):
            self.run_check()

    def test_B_must_reset_respawn_flag(self):
        self.frames[1170].respawn = True
        with self.assertRaisesRegex(ValueError, "hazard state"):
            self.run_check()

    def test_missing_controller_B_rejected(self):
        self.log.write_text(self.log.read_text().replace(
            "HEMAN_THREE_HID frame=1140 buttons=B",
            "HEMAN_THREE_HID frame=1140 buttons="))
        with self.assertRaisesRegex(ValueError, "HID"):
            self.run_check()

    def test_duplicate_png_receipt_rejected(self):
        line = (f"HEMAN_GUEST_FRAME_PNG frame=1045 dimensions=640x360 "
                f"path={self.folder / 'raster-frame-1045.png'}\n")
        self.log.write_text(self.log.read_text() + line)
        with self.assertRaisesRegex(ValueError, "duplicated"):
            self.run_check()

    def test_previous_session_png_rejected(self):
        line = str(self.folder / "raster-frame-1045.png")
        self.log.write_text(self.log.read_text().replace(
            line, "/tmp/stale/raster-frame-1045.png"))
        with self.assertRaisesRegex(ValueError, "Cross-session"):
            self.run_check()

    def test_truncated_guest_file_rejected(self):
        (self.folder / "raster-frame-1045.png").unlink()
        with self.assertRaises(FileNotFoundError):
            self.run_check()

    def test_unexpected_old_guest_png_record_rejected(self):
        self.log.write_text(self.log.read_text() +
            "HEMAN_GUEST_FRAME_PNG frame=1300 dimensions=640x360 "
            "path=/tmp/previous-run/raster-frame-1300.png\n")
        with self.assertRaisesRegex(ValueError, "unexpected guest PNG"):
            self.run_check()

    def test_extra_unscheduled_hid_edge_rejected(self):
        self.log.write_text(self.log.read_text() +
                            "HEMAN_THREE_HID frame=1200 buttons=A\n")
        with self.assertRaisesRegex(ValueError, "guest HID"):
            self.run_check()

    def test_leftward_drift_after_B_rejected(self):
        self.frames[1190].x = self.frames[1170].x - 25
        with self.assertRaisesRegex(ValueError, "drifted"):
            self.run_check()

    def test_missing_real_runner_completion_rejected(self):
        self.log.write_text(self.log.read_text().replace(
            "Production runner complete: frames=1205", "guest interrupted"))
        with self.assertRaisesRegex(ValueError, "never completed"):
            self.run_check()


if __name__ == "__main__":
    unittest.main()
