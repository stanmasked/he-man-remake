"""Mock-only Stage112 NeXium HID/PNG oracle tests; NOT guest execution."""
from __future__ import annotations

import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from instrument_nexium_lore_lab import FRAMES, HID_EVENTS, instrument
from verify_nexium_lore_lab_hid import LAB_BITS, expected_masks, verify as hid_verify
from verify_nexium_lore_lab_pngs import (
    STATES, HERO, BG, GREY, GREEN, BIO, ART, SAVE,
    verify as png_verify, inspect,
)
from test_nexium_hid_instrument import SOURCE


def trace(masks=None) -> str:
    masks = [0] + list(expected_masks() if masks is None else masks)
    lines = []
    for sample, mask in enumerate(masks, start=1):
        injection = (
            "None" if mask == 0 else
            "Some(ControllerInput { buttons: " + str(mask) +
            ", stick_l_x: 0, stick_l_y: 0, stick_r_x: 0, stick_r_y: 0 })"
        )
        layouts = ", ".join(format(value, "x") for value in
                            (mask, mask, 0, 0, 0, 0, 0))
        lines.append(
            f"[hid-publish] sample={sample} entry=0 requested=0x0 "
            f"injected={injection} npad=[{layouts}] "
            f"mouse=0x0 keyboard=[] exclusive=true mapped=0x1000"
        )
    return "\n".join(lines) + "\n"


class FakeFrame:
    size = (640, 360)

    def __init__(self, state, payload):
        self.state = state
        self.payload = payload

    def getpixel(self, point):
        flags = self.state[:5]
        colors = (GREEN, GREEN, BIO, ART, SAVE)
        for idx, p in enumerate(((30,30),(84,30),(138,30),
                                 (192,30),(246,30))):
            if point == p:
                return colors[idx] if flags[idx] else GREY
        if point == (600,20):
            return BG
        if point == (360,30):
            return GREEN if self.state[5] >= 1 else BG
        if point == (372,30):
            return GREEN if self.state[5] == 2 else BG
        x,y = point
        if y == 188:
            left = 64 + self.state[6] - 5
            return HERO if left <= x < left+10 else BG
        raise AssertionError(f"unexpected fake pixel {point}")

    def tobytes(self):
        return self.payload


class FakePNG:
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


class Stage112HIDRegression(unittest.TestCase):
    def test_instrumenting_both_original_frame_rx_paths(self):
        code = instrument(SOURCE)
        self.assertEqual(code.count("HEMAN_LORE_HID frame="), 2)
        self.assertEqual(code.count("HEMAN_GUEST_FRAME_PNG frame="), 2)
        for token in ('145 => "buttons=L"', '230 => "buttons=R"',
                      '275 => "buttons=Y"', '355 => "buttons=X"'):
            self.assertIn(token, code)
        with self.assertRaises(ValueError):
            instrument(code)

    def test_pinned_button_bits(self):
        self.assertEqual(LAB_BITS["L"], 64)
        self.assertEqual(LAB_BITS["R"], 128)
        self.assertEqual(LAB_BITS["X"], 4)
        self.assertEqual(LAB_BITS["Y"], 8)
        self.assertEqual(len(HID_EVENTS), 20)
        self.assertEqual(len(FRAMES), 12)

    def test_simulated_complete_trace_not_a_guest_attestation(self):
        result = hid_verify(trace())
        self.assertEqual(result["verified_guest_button_edges"], len(HID_EVENTS))
        self.assertFalse(result["real_guest_pngs_verified_here"])
        self.assertFalse(result["original_ios_gameplay_fidelity_verified"])

    def test_real_kernel_receipt_not_only_runner_write(self):
        with self.assertRaisesRegex(ValueError, "No real pinned kernel"):
            hid_verify("HEMAN_LORE_HID frame=45 buttons=DRIGHT")

    def test_missing_l_r_x_y_button_edges_fail_closed(self):
        masks = list(expected_masks())
        for name in ("L", "R", "X", "Y"):
            with self.subTest(name=name):
                idx = next(i for i, value in enumerate(masks)
                           if value == LAB_BITS[name])
                without = masks[:idx] + masks[idx+1:]
                with self.assertRaisesRegex(ValueError, "missed or added"):
                    hid_verify(trace(without))

    def test_injected_button_must_reach_npad_layout(self):
        with self.assertRaisesRegex(ValueError, "never reached"):
            hid_verify(trace().replace("npad=[40, 40,", "npad=[0, 0,", 1))

    def test_unmapped_active_and_nonexclusive_rejected(self):
        with self.assertRaisesRegex(ValueError, "not exclusive"):
            hid_verify(trace().replace("exclusive=true", "exclusive=false", 1))
        lines = trace().splitlines()
        lines[1] = lines[1].replace("mapped=0x1000", "mapped=0x0")
        with self.assertRaisesRegex(ValueError, "not mapped"):
            hid_verify("\n".join(lines)+"\n")


class Stage112PNGMockRegression(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.folder = Path(temp.name)
        self.fake = {}
        payload = {}
        payload[165] = b"original-saved-guest-scene"
        payload[265] = payload[165]
        payload[485] = b"completed-saved-guest-scene"
        payload[530] = payload[485]
        for frame in FRAMES:
            state = STATES[frame]
            midpoint = (state[6] + state[7]) // 2
            row = state[:6] + (midpoint, midpoint)
            raw = payload.get(frame, f"guest-image-{frame}".encode())
            self.fake[frame] = FakeFrame(row, raw)
            (self.folder / f"raster-frame-{frame:04}.png").write_bytes(b"fake")
        log_lines = [
            "Production runner complete: frames=540",
            "cycles=50000 svcs=2000 frames=530",
            *(f"HEMAN_LORE_HID frame={frame} {command}"
              for frame, command in HID_EVENTS),
            *(f"HEMAN_GUEST_FRAME_PNG frame={frame} dimensions=640x360 "
              f"path={self.folder / f'raster-frame-{frame:04}.png'}"
              for frame in FRAMES),
        ]
        (self.folder / "raster-runner.log").write_text(
            "\n".join(log_lines) + "\n"
        )

    def check(self):
        pil = types.ModuleType("PIL")
        pil.Image = types.SimpleNamespace(
            open=lambda path: FakePNG(self.fake[int(
                Path(path).stem.split("-")[-1]
            )])
        )
        with patch.dict(sys.modules, {"PIL": pil}):
            return png_verify(self.folder)

    def test_mock_positive_is_never_original_ios_evidence(self):
        result = self.check()
        self.assertEqual(
            result["authentic_pinned_nexium_frame_rx_pngs_validated"], 12
        )
        self.assertFalse(result["original_ios_source_fidelity_verified"])
        self.assertFalse(result["hardware_nintendo_switch_execution_verified"])

    def test_missing_guest_log_rejected(self):
        (self.folder / "raster-runner.log").write_text("CI passed\n")
        with self.assertRaisesRegex(ValueError, "did not complete"):
            self.check()

    def test_runner_hid_write_mismatch_rejected(self):
        log = self.folder / "raster-runner.log"
        log.write_text(log.read_text().replace("buttons=Y", "buttons=A", 1))
        with self.assertRaisesRegex(ValueError, "transcript"):
            self.check()

    def test_corrupted_guest_bio_reward_marker_rejected(self):
        old = self.fake[445]
        bad = list(old.state)
        bad[2] = 0
        self.fake[445] = FakeFrame(tuple(bad), old.payload)
        with self.assertRaisesRegex(ValueError, "HUD"):
            self.check()

    def test_collected_count_cannot_be_faked_by_hud_only(self):
        old = self.fake[445]
        bad = list(old.state)
        bad[5] = 1
        self.fake[445] = FakeFrame(tuple(bad), old.payload)
        with self.assertRaisesRegex(ValueError, "counter"):
            self.check()

    def test_save_state_must_match_restored_visuals(self):
        old = self.fake[265]
        self.fake[265] = FakeFrame(old.state, b"wrong restored bytes")
        with self.assertRaisesRegex(ValueError, "reproduce saved"):
            self.check()

    def test_final_save_load_must_be_stable(self):
        old = self.fake[530]
        self.fake[530] = FakeFrame(old.state, b"changed completed pixels")
        with self.assertRaisesRegex(ValueError, "pixel-stable"):
            self.check()

    def test_position_cannot_be_teleported(self):
        old = self.fake[345]
        wrong = list(old.state)
        wrong[6] = 175
        self.fake[345] = FakeFrame(tuple(wrong), old.payload)
        with self.assertRaisesRegex(ValueError, "location failed"):
            self.check()


if __name__ == "__main__":
    unittest.main()
