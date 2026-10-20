"""Synthetic Rust fragments test fail-closed source-contract matching only.

A real pinned upstream hid_state.rs is checked separately, immediately
after GitHub Actions clones the exact NeXium SHA. These are NOT guest traces.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from check_pinned_nexium_hid_source import BINDINGS, REQUIRED_TRACE_FIELDS, validate_source
from verify_nexium_hid_publication import BUTTON_BITS


def fixture():
    blocks = [
        "pub struct ControllerInput {}",
        "pub struct HidState {}",
        "const LAYOUT_COUNT: usize = 7;",
    ]
    for symbol, rust_constant in BINDINGS.items():
        blocks.append(
            f"pub const {rust_constant}: u64 = 1 << "
            f"{BUTTON_BITS[symbol].bit_length() - 1};"
        )
    blocks.extend([
        '"A" => NPAD_BUTTON_A,',
        '"B" => NPAD_BUTTON_B,',
        '"DRIGHT" => NPAD_BUTTON_RIGHT,',
        'cache.checked.elapsed() >= std::time::Duration::from_millis(25)',
        'std::env::var_os("NEXIUM_HID_INJECT")',
        'std::env::var("NEXIUM_HID_INJECT_EXCLUSIVE")',
        'std::env::var("NEXIUM_HID_TRACE")',
        'fn trace_published_input(',
        'self.trace_published_input(active_entry, requested, injected, exclusive);',
        'state_at(lifo, LIFO_STORAGE_ELEM_SIZE)',
        'self.mapped_host_ptr',
        'sample.npad_buttons',
        'log::info!("[hid-publish] sample={} entry={} requested={:#x} '
        'injected={:?} npad={:x?} mouse={:#x} exclusive={} mapped={:#x}",);',
    ])
    return "\n".join(blocks)


class PinnedKernelSourceContractUnitTests(unittest.TestCase):
    def test_fixture_validity_does_not_claim_guest(self):
        out = validate_source(fixture())
        self.assertTrue(out["pinned_kernel_source_contract_valid"])
        self.assertEqual(out["npad_layouts"], 7)
        self.assertEqual(out["source_hid_poll_ms"], 25)
        self.assertFalse(out["guest_kernel_actually_executed"])

    def test_reject_wrong_layout_count(self):
        with self.assertRaisesRegex(ValueError, "layout width"):
            validate_source(fixture().replace("LAYOUT_COUNT: usize = 7", "LAYOUT_COUNT: usize = 6"))

    def test_reject_wrong_A_bit(self):
        with self.assertRaisesRegex(ValueError, "bit drift"):
            validate_source(fixture().replace("NPAD_BUTTON_A: u64 = 1 << 0",
                                              "NPAD_BUTTON_A: u64 = 1 << 2"))

    def test_reject_wrong_B_bit(self):
        with self.assertRaisesRegex(ValueError, "bit drift"):
            validate_source(fixture().replace("NPAD_BUTTON_B: u64 = 1 << 1",
                                              "NPAD_BUTTON_B: u64 = 1 << 3"))

    def test_reject_wrong_right_bit(self):
        with self.assertRaisesRegex(ValueError, "bit drift"):
            validate_source(fixture().replace("NPAD_BUTTON_RIGHT: u64 = 1 << 14",
                                              "NPAD_BUTTON_RIGHT: u64 = 1 << 15"))

    def test_reject_changed_controller_text(self):
        with self.assertRaisesRegex(ValueError, "text parser drift"):
            validate_source(fixture().replace('"DRIGHT" => NPAD_BUTTON_RIGHT',
                                              '"RIGHT" => NPAD_BUTTON_RIGHT'))

    def test_reject_renamed_HID_file_variable(self):
        with self.assertRaisesRegex(ValueError, "trace implementation changed"):
            validate_source(fixture().replace('var_os("NEXIUM_HID_INJECT")',
                                              'var_os("NEW_HID_PATH")'))

    def test_reject_changed_poll_interval(self):
        with self.assertRaisesRegex(ValueError, "poll interval"):
            validate_source(fixture().replace("from_millis(25)", "from_millis(10)"))

    def test_reject_missing_actual_NPAD_trace(self):
        with self.assertRaisesRegex(ValueError, "field missing"):
            validate_source(fixture().replace("npad={:x?}", "memory={:x?}"))

    def test_reject_unmapped_or_nonexclusive_trace_contract(self):
        with self.assertRaisesRegex(ValueError, "field missing"):
            validate_source(fixture().replace("exclusive={} mapped={:#x}", "exclusive={}"))

    def test_reject_missing_kernel_publication_call(self):
        with self.assertRaisesRegex(ValueError, "trace implementation changed"):
            validate_source(fixture().replace(
                "self.trace_published_input(active_entry, requested, injected, exclusive);",
                "/* kernel publish disabled */"
            ))

    def test_trace_fields_are_unique(self):
        self.assertEqual(len(REQUIRED_TRACE_FIELDS), len(set(REQUIRED_TRACE_FIELDS)))


if __name__ == "__main__":
    unittest.main()
