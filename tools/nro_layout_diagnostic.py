"""Inspect native libnx .nro segments and the current NeXium loader bound check.

Original files are read only. This diagnoses an emulator incompatibility,
never patches/rewrites the .nro or mistakes valid cross-compilation for boot.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import struct


@dataclass(frozen=True)
class NroLayout:
    file_bytes: int
    magic_offset: int
    declared_size: int
    text_end: int
    ro_end: int
    data_end: int
    emulator_slice_bytes: int
    original_bounds_ok: bool
    nexium_bounds_ok: bool

    @property
    def loader_shortfall(self) -> int:
        return max(0, max(self.text_end, self.ro_end, self.data_end)
                   - self.emulator_slice_bytes)


def inspect_nro(image: bytes) -> NroLayout:
    if len(image) < 128:
        raise ValueError("file too short for a NRO0 header")
    if image[:4] == b"NRO0":
        pos = 0
    elif image[16:20] == b"NRO0":
        pos = 16
    else:
        raise ValueError("missing NRO0 magic at offset 0 or 16")
    if len(image) < pos + 128:
        raise ValueError("truncated NRO0 header")

    declared_size = struct.unpack_from("<I", image, pos + 8)[0]
    pairs = [
        struct.unpack_from("<II", image, pos + off)
        for off in (0x10, 0x18, 0x20)
    ]
    original_ends = [offset + size for offset, size in pairs]
    # This 128-byte adjustment is the current NeXium implementation,
    # NOT the normative devkitPro NRO segment interpretation.
    ends = [
        (offset + 128 if offset < 128 else offset) + size
        for offset, size in pairs
    ]
    text_end, ro_end, data_end = ends
    available = len(image) - pos
    return NroLayout(
        file_bytes=len(image),
        magic_offset=pos,
        declared_size=declared_size,
        text_end=text_end,
        ro_end=ro_end,
        data_end=data_end,
        emulator_slice_bytes=available,
        original_bounds_ok=(declared_size <= len(image)
                            and all(end <= len(image) for end in original_ends)),
        nexium_bounds_ok=all(end <= available for end in ends),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("nro", type=Path)
    args = parser.parse_args()
    try:
        result = inspect_nro(args.nro.read_bytes())
    except (OSError, ValueError) as exc:
        print(json.dumps({"file": str(args.nro), "error": str(exc)}))
        return 2
    print(json.dumps({"file": str(args.nro), **asdict(result),
                      "loader_shortfall": result.loader_shortfall},
                     indent=2, sort_keys=True))
    if not result.original_bounds_ok:
        print("ERROR: segment bounds invalid even for the original file.")
        return 2
    if not result.nexium_bounds_ok:
        print("INCOMPATIBLE: current NeXium loader subtracts the "
              "16-byte NRO wrapper when checking segments. "
              "This does not mean the devkitPro NRO is invalid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
