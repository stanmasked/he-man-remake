"""Read-only decoding of level object metadata from the user's local iOS archive.

The format's opaque per-object fields and post-object waypoint section are
intentionally NOT interpreted. No game logic is executed, copied or generated.
"""
from dataclasses import dataclass
import math
import struct

from .lvl import LevelFormatError, parse_level_header

_MAX_LEVEL_BYTES = 8_000_000
_MAX_TEXT_UNITS = 512
_MAX_AFFINE_SEARCH = 1024
_MAT_SIZE = 40  # 4 byte u32 element count followed by 9 float32 values


@dataclass(frozen=True)
class LevelProperty:
    name: str
    kind: str
    value: bool | int | float | str


@dataclass(frozen=True)
class LevelObject:
    index: int
    class_name: str
    group_name: str
    instance_name: str
    state: str
    x: float
    y: float
    matrix: tuple[float, ...]
    properties: tuple[LevelProperty, ...]
    offset: int
    end_offset: int
    opaque_before_state_bytes: int
    opaque_after_state_bytes: int


@dataclass(frozen=True)
class ParsedLevel:
    level_name: str
    objects: tuple[LevelObject, ...]
    trailer_offset: int
    trailer_bytes: int
    trailer_record_count_hint: int | None


def _need(data: bytes, cursor: int, size: int) -> None:
    if cursor < 0 or size < 0 or cursor + size > len(data):
        raise LevelFormatError(f"truncated level data at byte {cursor}")


def _string(data: bytes, cursor: int, *, allow_empty: bool = True) -> tuple[str, int]:
    _need(data, cursor, 2)
    units = struct.unpack_from("<H", data, cursor)[0]
    if units > _MAX_TEXT_UNITS or (not units and not allow_empty):
        raise LevelFormatError(f"invalid UTF-16 string length at byte {cursor}")
    end = cursor + 2 + 2 * units
    _need(data, cursor, 2 + 2 * units)
    try:
        value = data[cursor + 2:end].decode("utf-16le", errors="strict")
    except UnicodeDecodeError as exc:
        raise LevelFormatError(f"invalid UTF-16 text at byte {cursor}") from exc
    if any(ord(c) < 32 for c in value):
        raise LevelFormatError(f"control character in text at byte {cursor}")
    return value, end


def _find_affine(data: bytes, cursor: int) -> tuple[int, tuple[float, ...]]:
    """Find a 9-float affine matrix after the variable-length animation metadata.

    The decoded matrix has zeros in the perspective column and homogeneous
    coordinate 1. This proves the byte layout, not the in-game coordinate scale.
    """
    last = min(len(data) - (_MAT_SIZE + 1), cursor + _MAX_AFFINE_SEARCH)
    for at in range(cursor, last + 1):
        if data[at:at + 4] != b"\x09\x00\x00\x00":
            continue
        matrix = struct.unpack_from("<9f", data, at + 4)
        if (all(math.isfinite(v) for v in matrix)
                and abs(matrix[2]) < 1e-5
                and abs(matrix[5]) < 1e-5
                and abs(matrix[8] - 1.0) < 1e-5):
            return at, matrix
    raise LevelFormatError(f"3x3 affine matrix not found after byte {cursor}")


def parse_level_objects(data: bytes) -> ParsedLevel:
    """Parse all counted objects, with the trailing waypoint area left opaque.

    For an unsupported or truncated field, fail rather than guess boundaries.
    """
    if len(data) > _MAX_LEVEL_BYTES:
        raise LevelFormatError("level data exceed 8 MB size limit")
    header = parse_level_header(data)
    cursor = header.header_bytes
    rows: list[LevelObject] = []
    for index in range(header.record_count_hint):
        start = cursor
        class_name, cursor = _string(data, cursor, allow_empty=False)
        group_name, cursor = _string(data, cursor)
        instance_name, cursor = _string(data, cursor)
        # Unknown serialised fields occupy exactly 26 bytes in observed records.
        _need(data, cursor, 26)
        before_bytes = 26
        cursor += before_bytes
        state, cursor = _string(data, cursor)
        marker_at, matrix = _find_affine(data, cursor)
        after_bytes = marker_at - cursor
        cursor = marker_at + _MAT_SIZE
        _need(data, cursor, 1)
        nprops = data[cursor]
        cursor += 1
        props: list[LevelProperty] = []
        for _ in range(nprops):
            pname, cursor = _string(data, cursor, allow_empty=False)
            _need(data, cursor, 1)
            tag = data[cursor]
            cursor += 1
            if tag == 0:
                _need(data, cursor, 1)
                val = bool(data[cursor])
                cursor += 1
                kind = "bool"
            elif tag in (1, 2):
                _need(data, cursor, 4)
                val = struct.unpack_from("<i" if tag == 1 else "<f", data, cursor)[0]
                cursor += 4
                if tag == 2 and not math.isfinite(val):
                    raise LevelFormatError("non-finite float property")
                kind = "int" if tag == 1 else "float"
            elif tag == 3:
                val, cursor = _string(data, cursor)
                kind = "string"
            else:
                raise LevelFormatError(f"unsupported property tag {tag} at byte {cursor - 1}")
            props.append(LevelProperty(pname, kind, val))
        rows.append(LevelObject(
            index=index, class_name=class_name, group_name=group_name,
            instance_name=instance_name, state=state,
            x=matrix[6], y=matrix[7], matrix=matrix,
            properties=tuple(props), offset=start, end_offset=cursor,
            opaque_before_state_bytes=before_bytes,
            opaque_after_state_bytes=after_bytes,
        ))
    trailer_bytes = len(data) - cursor
    if trailer_bytes < 4:
        raise LevelFormatError("missing level trailer")
    trailer_count = struct.unpack_from("<I", data, cursor)[0]
    if trailer_count > 10000:
        raise LevelFormatError("implausible trailer record count")
    return ParsedLevel(header.embedded_name, tuple(rows), cursor,
                       trailer_bytes, trailer_count)
