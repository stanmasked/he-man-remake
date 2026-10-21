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
    STATES, HERO, BG, GREY, GREEN, BIO, ART, SAVE, SD_FAILURE,
    verify as png_verify, inspect, main as png_cli,
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

    def __init__(self, state, payload, sd_status=0):
        self.state = state
        self.payload = payload
        self.sd_status = sd_status

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
        if point == (430,30):
            return {0: GREY, 1: GREEN, 2: SD_FAILURE}[self.sd_status]
        x,y = point
        if y == 188:
            left = 64 + self.state[6] - 5
            return HERO if left <= x < left+10 else BG
        raise AssertionError(f"unexpected fake pixel {point}")

    def tobytes(self):
        # Keep mock frames byte-stable while satisfying the real RGB buffer size.
        return self.payload.ljust(640 * 360 * 3, b"\0")


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
        for token in ('145 => "buttons=L"',
                      '230 => "buttons=R"',
                      '470 => "buttons=ZL,L"',
                      '530 => "buttons=ZL,R"',
                      '275 => "buttons=Y"', '365 => "buttons=X"'):
            self.assertIn(token, code)
        with self.assertRaises(ValueError):
            instrument(code)

    def test_fresh_attack_only_after_verified_gate_approach(self):
        # Actual *second* Stage112 NeXium guest archive (run 39600185389):
        # frame 345: synthetic actor x=110, frame 395: actor x=94.
        # Gate centre=104 and native AABB+circle contact requires 95<=x<=113.
        # This was a TRUE block despite all real NPAD keys being published.
        # Releasing DLEFT 2 receiver frames EARLIER makes the model
        # expected x=98 (two fewer native steps at 2 px/step). The real
        # NeXium rerun must verify the result; this test is not that proof.
        schedule = dict(HID_EVENTS)
        self.assertEqual(schedule[310], "buttons=DLEFT")
        self.assertEqual(schedule[350], "buttons=")
        self.assertEqual(schedule[365], "buttons=X")
        self.assertEqual(schedule[380], "buttons=")
        actual_prior_guest_x = 94
        corrected_x = actual_prior_guest_x + (352 - 350) * 2
        self.assertTrue(95 <= corrected_x <= 113)
        self.assertGreaterEqual(365 - 350, 4)
        self.assertLess(380, 395)

    def test_pinned_button_bits(self):
        self.assertEqual(LAB_BITS["L"], 64)
        self.assertEqual(LAB_BITS["R"], 128)
        self.assertEqual(LAB_BITS["X"], 4)
        self.assertEqual(LAB_BITS["Y"], 8)
        self.assertEqual(len(HID_EVENTS), 26)
        self.assertEqual(len(FRAMES), 13)
        schedule = dict(HID_EVENTS)
        self.assertEqual(schedule[460], "buttons=ZL")
        self.assertEqual(schedule[470], "buttons=ZL,L")
        self.assertEqual(schedule[520], "buttons=ZL")
        self.assertEqual(schedule[530], "buttons=ZL,R")

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
        payload[215] = b"reset-scene"
        payload[518] = payload[215]
        payload[485] = b"completed-saved-guest-scene"
        payload[540] = payload[485]
        sd_statuses = {485: 1, 518: 1, 540: 1}
        for frame in FRAMES:
            state = STATES[frame]
            midpoint = (state[6] + state[7]) // 2
            row = state[:6] + (midpoint, midpoint)
            raw = payload.get(frame, f"guest-image-{frame}".encode())
            self.fake[frame] = FakeFrame(row, raw, sd_statuses.get(frame, 0))
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
            result["authentic_pinned_nexium_frame_rx_pngs_validated"], len(FRAMES)
        )
        self.assertTrue(result["guest_sd_save_succeeded"])
        self.assertTrue(result["guest_sd_load_succeeded"])
        self.assertTrue(result["guest_sd_round_trip_verified"])
        self.assertFalse(result["original_ios_source_fidelity_verified"])
        self.assertFalse(result["hardware_nintendo_switch_execution_verified"])

    def test_cli_stdout_contains_one_strict_json_document(self):
        import contextlib
        import io
        import json
        output, diagnostics = io.StringIO(), io.StringIO()
        pil = types.ModuleType("PIL")
        pil.Image = types.SimpleNamespace(
            open=lambda path: FakePNG(self.fake[int(
                Path(path).stem.split("-")[-1]
            )])
        )
        with patch.dict(sys.modules, {"PIL": pil}):
            with patch.object(sys, "argv", ["guest-oracle", str(self.folder)]):
                with contextlib.redirect_stdout(output):
                    with contextlib.redirect_stderr(diagnostics):
                        self.assertEqual(png_cli(), 0)
        report = json.loads(output.getvalue())
        self.assertTrue(report["guest_sd_round_trip_verified"])
        self.assertIn("PASS: genuine pinned NeXium guest", diagnostics.getvalue())
        self.assertNotIn("PASS:", output.getvalue())

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

    def test_final_ram_save_load_must_be_stable(self):
        old = self.fake[540]
        self.fake[540] = FakeFrame(old.state, b"changed completed pixels", old.sd_status)
        with self.assertRaisesRegex(ValueError, "SD save/load did not reproduce"):
            self.check()

    def test_sd_unavailable_is_reported_and_reset_session_is_preserved(self):
        for frame in (485, 518, 540):
            old = self.fake[frame]
            state = old.state
            if frame == 540:
                reset = STATES[518]
                midpoint = (reset[6] + reset[7]) // 2
                state = reset[:6] + (midpoint, midpoint)
                payload = b"reset-scene"
            elif frame == 518:
                payload = b"reset-scene"
            else:
                payload = old.payload
            self.fake[frame] = FakeFrame(state, payload, 2)
        result = self.check()
        self.assertFalse(result["guest_sd_save_succeeded"])
        self.assertFalse(result["guest_sd_load_succeeded"])
        self.assertFalse(result["guest_sd_round_trip_verified"])
        self.assertTrue(result["guest_sd_failure_preserved_reset_session"])

    def test_green_sd_restore_requires_a_successful_sd_save(self):
        old = self.fake[485]
        self.fake[485] = FakeFrame(old.state, old.payload, 2)
        prior = self.fake[518]
        self.fake[518] = FakeFrame(prior.state, prior.payload, 2)
        with self.assertRaisesRegex(ValueError, "although this run's SD save failed"):
            self.check()

    def test_sd_load_failure_after_successful_save_preserves_reset_session(self):
        old = self.fake[540]
        reset = STATES[518]
        midpoint = (reset[6] + reset[7]) // 2
        reset_row = reset[:6] + (midpoint, midpoint)
        self.fake[540] = FakeFrame(reset_row, b"reset-scene", 2)
        result = self.check()
        self.assertTrue(result["guest_sd_save_succeeded"])
        self.assertFalse(result["guest_sd_load_succeeded"])
        self.assertFalse(result["guest_sd_round_trip_verified"])
        self.assertTrue(result["guest_sd_failure_preserved_reset_session"])

    def test_sd_attempt_must_change_the_result_indicator(self):
        old = self.fake[485]
        self.fake[485] = FakeFrame(old.state, old.payload, 0)
        with self.assertRaisesRegex(ValueError, "ZL\+L did not reach"):
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
