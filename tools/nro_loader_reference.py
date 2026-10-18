"""Independent reference parser for normal devkitPro/libnx .nro layout.

The NroStart at offset 0 is part of the image, while NRO0 metadata starts
at offset 16. Segment offsets remain absolute file/code-image offsets.
No emulation, binary rewriting, original iOS data, or private files.
"""
from __future__ import annotations
from dataclasses import dataclass
import struct


@dataclass(frozen=True)
class Segment:
    offset: int
    size: int
    end: int


@dataclass(frozen=True)
class NroImage:
    size: int
    mod0_offset: int
    bss_size: int
    text: Segment
    ro: Segment
    data: Segment

    def bytes_for(self, blob: bytes, name: str) -> bytes:
        if name not in ("text", "ro", "data"):
            raise ValueError("unknown NRO segment")
        seg = getattr(self, name)
        return blob[seg.offset:seg.end]


def parse_standard_nro(blob: bytes) -> NroImage:
    """Validate canonical libnx NroStart+NroHeader+3 segment offsets."""
    if len(blob) < 0x80:
        raise ValueError("truncated NRO start/header")
    if blob[0x10:0x14] != b"NRO0":
        raise ValueError("missing canonical NRO0 signature at +0x10")
    mod0_offset, = struct.unpack_from("<I", blob, 4)
    declared_size, = struct.unpack_from("<I", blob, 0x18)
    if declared_size < 0x80 or declared_size > len(blob):
        raise ValueError("invalid NRO image size")
    bss_size, = struct.unpack_from("<I", blob, 0x38)
    segs = []
    for offset in (0x20, 0x28, 0x30):
        start, length = struct.unpack_from("<II", blob, offset)
        # Python integers do not overflow. Bounds are checked against the
        # declared NRO code image, not optional ASET trailing assets.
        end = start + length
        if start > declared_size or end > declared_size:
            raise ValueError("segment exceeds declared NRO image")
        segs.append(Segment(start, length, end))
    text, ro, data = segs
    if text.offset != 0:
        raise ValueError("NRO text must begin at image offset zero")
    if text.end > ro.offset or ro.end > data.offset:
        raise ValueError("overlapping or unordered NRO code segments")
    return NroImage(declared_size, mod0_offset, bss_size,
                    text, ro, data)
