"""Validate the exact pinned NeXium kernel HID source behind stage-98 proof.

This checks the temporary upstream Rust source before building the emulator.
An unchanged repository SHA alone does not prove the Python reader still
understands every button bit and the format emitted by that kernel.
Never accept a parser pass as actual emulator execution or guest PNG proof.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from verify_nexium_hid_publication import BUTTON_BITS

BINDINGS = {
    "A": "NPAD_BUTTON_A",
    "B": "NPAD_BUTTON_B",
    "X": "NPAD_BUTTON_X",
    "Y": "NPAD_BUTTON_Y",
    "ZL": "NPAD_BUTTON_ZL",
    "ZR": "NPAD_BUTTON_ZR",
    "DLEFT": "NPAD_BUTTON_LEFT",
    "DRIGHT": "NPAD_BUTTON_RIGHT",
    "DUP": "NPAD_BUTTON_UP",
    "DDOWN": "NPAD_BUTTON_DOWN",
}
REQUIRED_TRACE_FIELDS = (
    "sample={}", "entry={}", "requested={:#x}", "injected={:?}",
    "npad={:x?}", "exclusive={}", "mapped={:#x}",
)


def validate_source(source: str) -> dict:
    if "pub struct ControllerInput" not in source or (
        "pub struct HidState" not in source
    ):
        raise ValueError("Not the pinned NeXium controller kernel source")

    layout = re.search(r"\bconst\s+LAYOUT_COUNT\s*:\s*usize\s*=\s*(\d+)\s*;", source)
    if not layout or int(layout.group(1)) != 7:
        raise ValueError("Pinned kernel NPAD layout width changed")

    for guest_name, rust_symbol in BINDINGS.items():
        mask = BUTTON_BITS[guest_name]
        if mask == 0 or mask & (mask - 1):
            raise ValueError("Invalid local one-bit guest controller mask")
        expected_shift = mask.bit_length() - 1
        declaration = re.search(
            rf"\bpub\s+const\s+{rust_symbol}\s*:\s*u64\s*=\s*1\s*<<\s*(\d+)\s*;",
            source,
        )
        if not declaration or int(declaration.group(1)) != expected_shift:
            raise ValueError(f"Upstream NPAD button bit drift: {guest_name}")
    # Runtime parser maps strings to upstream symbols, rather than an
    # independently copied table of button numbers.
    for packet in ("A", "B", "DRIGHT"):
        symbol = BINDINGS[packet]
        if not re.search(rf'"{packet}"\s*=>\s*{symbol}\b', source):
            raise ValueError(f"Kernel HID input text parser drift: {packet}")

    poll = re.search(
        r"cache\.checked\.elapsed\(\)\s*>=\s*"
        r"std::time::Duration::from_millis\((\d+)\)",
        source,
    )
    if not poll or int(poll.group(1)) != 25:
        raise ValueError("Pinned kernel HID input poll interval changed")

    for token in (
        'std::env::var_os("NEXIUM_HID_INJECT")',
        'std::env::var("NEXIUM_HID_INJECT_EXCLUSIVE")',
        'std::env::var("NEXIUM_HID_TRACE")',
        'log::info!(',
        'fn trace_published_input(',
        'self.trace_published_input(active_entry, requested, injected, exclusive);',
        'state_at(lifo, LIFO_STORAGE_ELEM_SIZE)',
        'self.mapped_host_ptr',
        'sample.npad_buttons',
    ):
        if token not in source:
            raise ValueError(f"Pinned NeXium HID trace implementation changed: {token}")

    trace = re.search(r'"(\[hid-publish\][^"\n]+)"', source)
    if not trace:
        raise ValueError("Pinned kernel HID trace format was removed")
    emitted_format = trace.group(1)
    for field in REQUIRED_TRACE_FIELDS:
        if field not in emitted_format:
            raise ValueError(f"Expected kernel HID receipt field missing: {field}")
    if emitted_format.count("npad=") != 1:
        raise ValueError("Ambiguous NPAD trace field")
    if "exclusive={}" not in emitted_format or "mapped={:#x}" not in emitted_format:
        raise ValueError("No exclusive and mapped shared-memory kernel evidence")

    return {
        "pinned_kernel_source_contract_valid": True,
        "npad_layouts": 7,
        "source_hid_poll_ms": 25,
        "controller_bit_declarations": len(BINDINGS),
        "required_trace_fields": list(REQUIRED_TRACE_FIELDS),
        "guest_kernel_actually_executed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("upstream_hid_state_rs", type=Path)
    args = parser.parse_args()
    result = validate_source(args.upstream_hid_state_rs.read_text(encoding="utf-8"))
    print(json.dumps(result, sort_keys=True, indent=2))
    print("PASS: actual pinned NeXium kernel HID layout, bit masks and trace "
          "format match the exact Python reader contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
