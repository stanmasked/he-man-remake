"""Simulated kernel log regression checks; NEVER standalone emulator proof."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from verify_nexium_hid_publication import expected_masks, verify, read_publications


def make_trace(masks=None, *, neutral_prefix=True):
    masks = list(expected_masks() if masks is None else masks)
    if neutral_prefix:
        masks.insert(0, 0)
    lines = []
    for i, mask in enumerate(masks, start=1):
        injected = (
            "None" if mask == 0
            else "Some(ControllerInput { buttons: "
            + str(mask)
            + ", stick_l_x: 0, stick_l_y: 0, stick_r_x: 0, stick_r_y: 0 })"
        )
        layouts = [mask, mask, 0, 0, 0, 0, 0]
        # Rust {:x?} uses lower-case hexadecimal without 0x.
        layout_str = ", ".join(format(v, "x") for v in layouts)
        lines.append(
            f"[2026-10-21T00:00:00Z INFO  nexium_kernel::hid_state] "
            f"[hid-publish] sample={i} entry=0 requested=0x0 "
            f"injected={injected} npad=[{layout_str}] "
            f"mouse=0x0 mouse_x=0 mouse_y=0 wheel_x=0 wheel_y=0 "
            f"keyboard_mods=0x0 keyboard=[] touches=0 "
            f"exclusive=true mapped=0x101000"
        )
    return "\n".join(lines) + "\n"


class HostOnlyHidPublicationTests(unittest.TestCase):
    def test_expected_real_input_masks_include_both_A_transitions(self):
        self.assertEqual(expected_masks(), (
            16384, 0, 1, 0, 16384, 16385, 16384, 0,
            1, 0, 16384, 16385, 16384, 0, 2, 0,
        ))

    def test_positive_mock_trace_is_not_emulator_evidence(self):
        got = verify(make_trace())
        self.assertEqual(got["real_kernel_button_transitions"], 16)
        self.assertTrue(got["npad_shared_memory_confirmed"])
        self.assertFalse(got["native_guest_frame_rx_png_proven_here"])
        self.assertFalse(got["original_ios_fidelity_verified"])

    def test_kernel_trace_required_not_runner_write_only(self):
        with self.assertRaisesRegex(ValueError, "No authentic NeXium"):
            verify("HEMAN_THREE_HID frame=45 buttons=DRIGHT\n")

    def test_first_A_was_not_sampled(self):
        masks = list(expected_masks())
        masks.pop(2)
        with self.assertRaisesRegex(ValueError, "did not consume"):
            verify(make_trace(masks))

    def test_third_room_A_was_not_sampled(self):
        masks = list(expected_masks())
        masks.pop(11)
        with self.assertRaisesRegex(ValueError, "did not consume"):
            verify(make_trace(masks))

    def test_B_was_not_sampled(self):
        masks = list(expected_masks())
        masks.pop(14)
        with self.assertRaisesRegex(ValueError, "did not consume"):
            verify(make_trace(masks))

    def test_release_between_A_presses_must_be_observed(self):
        masks = list(expected_masks())
        masks.pop(3)
        with self.assertRaisesRegex(ValueError, "did not consume"):
            verify(make_trace(masks))

    def test_unexpected_button_press_rejected(self):
        masks = list(expected_masks())
        masks.insert(7, 8)
        with self.assertRaisesRegex(ValueError, "did not consume"):
            verify(make_trace(masks))

    def test_nonexclusive_kernel_input_rejected(self):
        with self.assertRaisesRegex(ValueError, "not exclusive"):
            verify(make_trace().replace("exclusive=true", "exclusive=false", 1))

    def test_malformed_kernel_receipt_rejected(self):
        with self.assertRaisesRegex(ValueError, "Malformed pinned NeXium"):
            verify(make_trace().replace("npad=[", "memory=[", 1))

    def test_missing_shared_memory_mapping_rejected(self):
        with self.assertRaisesRegex(ValueError, "not mapped"):
            verify(make_trace().replace("mapped=0x101000", "mapped=0x0", 1))

    def test_injected_buttons_not_written_to_npad_rejected(self):
        text = make_trace()
        # This substitution targets the first active DRIGHT event only.
        with self.assertRaisesRegex(ValueError, "never reached"):
            verify(text.replace("npad=[4000, 4000,", "npad=[0, 0,", 1))

    def test_missing_repeated_NPAD_sample_rejected(self):
        with self.assertRaisesRegex(ValueError, "must report"):
            verify(make_trace().replace(
                "npad=[0, 0, 0, 0, 0, 0, 0]",
                "npad=[0, 0, 0]", 1,
            ))

    def test_sampling_numbers_must_increase(self):
        text = make_trace()
        text = text.replace("sample=2", "sample=1", 1)
        with self.assertRaisesRegex(ValueError, "did not increase"):
            verify(text)

    def test_no_openai_or_synthetic_success_claim(self):
        result = verify(make_trace())
        self.assertFalse(result["native_guest_frame_rx_png_proven_here"])


if __name__ == "__main__":
    unittest.main()
