"""Read-only preliminary decoder for He-Man's .lvl header structure.

This intentionally does NOT decode object records or execute source scripts.
"""
from dataclasses import asdict, dataclass
import math
import struct

class LevelFormatError(ValueError):
    """The observed format header cannot be parsed safely."""

_FIXED = struct.Struct("<I6fH")
_U16 = struct.Struct("<H")
_U32 = struct.Struct("<I")
_MAX_NAME_UNITS = 512
_MAX_RECORDS = 100_000

@dataclass(frozen=True)
class LevelHeader:
    format_version: int
    raw_floats: tuple[float, float, float, float, float, float]
    embedded_name: str
    record_count_hint: int
    first_record_label_hint: str | None
    header_bytes: int
    file_bytes: int

    def as_dict(self) -> dict:
        return asdict(self)

def _read_utf16(data: bytes, offset: int, *, optional: bool = False) -> tuple[str | None, int]:
    if len(data) - offset < 2:
        if optional:
            return None, offset
        raise LevelFormatError("truncated UTF-16LE length")
    length = _U16.unpack_from(data, offset)[0]
    if length == 0 or length > _MAX_NAME_UNITS:
        if optional:
            return None, offset
        raise LevelFormatError("invalid UTF-16LE length")
    after = offset + 2 + length * 2
    if after > len(data):
        if optional:
            return None, offset
        raise LevelFormatError("truncated UTF-16LE string")
    try:
        name = data[offset + 2:after].decode("utf-16le", errors="strict")
    except UnicodeDecodeError as exc:
        if optional:
            return None, offset
        raise LevelFormatError("invalid UTF-16LE name") from exc
    if not name.isprintable() or "\x00" in name:
        if optional:
            return None, offset
        raise LevelFormatError("invalid characters in name")
    return name, after

def parse_level_header(data: bytes) -> LevelHeader:
    if len(data) < _FIXED.size + _U32.size:
        raise LevelFormatError("input shorter than fixed header")
    version, *fields, _ = _FIXED.unpack_from(data)
    if version != 1:
        raise LevelFormatError(f"unsupported format version: {version}")
    floats = tuple(fields[:6])
    if not all(math.isfinite(f) for f in floats):
        raise LevelFormatError("non-finite numeric field")
    embedded_name, cursor = _read_utf16(data, _FIXED.size - _U16.size)
    assert embedded_name is not None
    if not embedded_name.lower().endswith(".lvl"):
        raise LevelFormatError("unexpected embedded level filename")
    if len(data) - cursor < 4:
        raise LevelFormatError("truncated record count")
    count = _U32.unpack_from(data, cursor)[0]
    if count > _MAX_RECORDS:
        raise LevelFormatError("record count exceeds safety bound")
    cursor += 4
    first_label, _ = _read_utf16(data, cursor, optional=True) if count else (None, cursor)
    return LevelHeader(
        format_version=version,
        raw_floats=floats,
        embedded_name=embedded_name,
        record_count_hint=count,
        first_record_label_hint=first_label,
        header_bytes=cursor,
        file_bytes=len(data),
    )
