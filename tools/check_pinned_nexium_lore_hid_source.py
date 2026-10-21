"""Verify the pinned upstream kernel implements ALL lore lab HID buttons.

Base Stage099 HID checks cover its original A/B/DRIGHT scheme, but this
new real-guest route adds physical L/R shoulder buttons, X, Y, DLEFT.
Matching source syntax does not constitute actual guest execution.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from check_pinned_nexium_hid_source import validate_source
from verify_nexium_lore_lab_hid import LAB_BITS

LAB_BINDINGS = {
    "DLEFT": "NPAD_BUTTON_LEFT",
    "X": "NPAD_BUTTON_X",
    "Y": "NPAD_BUTTON_Y",
    "L": "NPAD_BUTTON_L",
    "R": "NPAD_BUTTON_R",
}


def validate_extra(source: str) -> dict:
    for name, symbol in LAB_BINDINGS.items():
        mask = LAB_BITS[name]
        if mask == 0 or (mask & (mask-1)):
            raise ValueError(f"Non-single-bit lab controller mapping: {name}")
        bit = mask.bit_length()-1
        if not re.search(
            rf"\bpub\s+const\s+{symbol}\s*:\s*u64\s*=\s*1\s*<<\s*{bit}\s*;",
            source,
        ):
            raise ValueError(f"Pinned kernel {name} NPAD mask declaration drifted")
        if not re.search(rf'"{name}"\s*=>\s*{symbol}\b', source):
            raise ValueError(f"Pinned kernel {name} textual injector drifted")
    return {
        "extra_pinned_lore_hid_source_contract_valid": True,
        "mapped_source_buttons": sorted(LAB_BINDINGS),
        "guest_kernel_actually_executed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("upstream_hid_state_rs", type=Path)
    args = parser.parse_args()
    source = args.upstream_hid_state_rs.read_text()
    validate_source(source)
    result = validate_extra(source)
    print(json.dumps(result, indent=2, sort_keys=True))
    print("PASS: pinned original NeXium HID kernel maps L/R/X/Y/DLEFT")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
