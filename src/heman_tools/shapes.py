"""Conservative, read-only decoder of iOS .shape collision candidates.

Shape interpretation and association with level instances are separate tasks.
Only plain polygon and circle primitives are decoded here. Never execute source.
"""
from dataclasses import dataclass
import math
import struct

from .lvl import LevelFormatError

_MAX_FILE = 1024 * 1024
_MAX_REF_UNITS = 512
_MAX_VERTICES = 4096
_HEADER = struct.Struct('<IIH')
_U32 = struct.Struct('<I')
_CIRCLE = struct.Struct('<fff')

@dataclass(frozen=True)
class Shape:
    kind: str
    flags: int
    reference: str | None
    vertices: tuple[tuple[float, float], ...]
    radius: float | None
    center: tuple[float, float] | None

    def bounds(self) -> tuple[float, float, float, float]:
        """Local-space AABB; does not imply level placement or physical use."""
        if self.kind == 'circle':
            assert self.center is not None and self.radius is not None
            x, y = self.center
            return x - self.radius, y - self.radius, x + self.radius, y + self.radius
        xs = [p[0] for p in self.vertices]
        ys = [p[1] for p in self.vertices]
        return min(xs), min(ys), max(xs), max(ys)


def parse_shape(data: bytes) -> Shape:
    if len(data) < _HEADER.size or len(data) > _MAX_FILE:
        raise LevelFormatError('invalid .shape length')
    kind, flags, name_units = _HEADER.unpack_from(data)
    if name_units > _MAX_REF_UNITS:
        raise LevelFormatError('oversized reference name')
    cursor = _HEADER.size + 2 * name_units
    if cursor > len(data):
        raise LevelFormatError('truncated reference name')
    ref = None
    if name_units:
        try:
            ref = data[_HEADER.size:cursor].decode('utf-16le', errors='strict')
        except UnicodeDecodeError as exc:
            raise LevelFormatError('invalid reference string') from exc
        if any(ord(c) < 32 for c in ref):
            raise LevelFormatError('control character in reference')
    if kind == 0:
        if cursor + 4 > len(data):
            raise LevelFormatError('missing polygon point count')
        count = _U32.unpack_from(data, cursor)[0]
        cursor += 4
        if not 3 <= count <= _MAX_VERTICES or cursor + count * 8 != len(data):
            raise LevelFormatError('invalid polygon points or trailing bytes')
        values = struct.unpack_from('<' + 'f' * (count * 2), data, cursor)
        if not all(math.isfinite(v) for v in values):
            raise LevelFormatError('non-finite polygon vertex')
        vertices = tuple((values[i], values[i+1]) for i in range(0, len(values), 2))
        return Shape('polygon', flags, ref, vertices, None, None)
    if kind == 1:
        if cursor + _CIRCLE.size != len(data):
            raise LevelFormatError('invalid circle size')
        radius, x, y = _CIRCLE.unpack_from(data, cursor)
        if not all(math.isfinite(v) for v in (radius, x, y)) or radius <= 0:
            raise LevelFormatError('invalid circle values')
        return Shape('circle', flags, ref, (), radius, (x, y))
    raise LevelFormatError(f'unsupported shape kind {kind}')


def affine_point(point: tuple[float, float], matrix: tuple[float, ...]) -> tuple[float, float]:
    """Apply the observed level 3x3 transform, without assuming pixel units."""
    if len(matrix) != 9 or not all(math.isfinite(x) for x in (*point, *matrix)):
        raise ValueError('invalid affine point/matrix')
    if abs(matrix[2]) > 1e-5 or abs(matrix[5]) > 1e-5 or abs(matrix[8]-1.0) > 1e-5:
        raise ValueError('unsupported projective transform')
    x, y = point
    return matrix[0]*x + matrix[3]*y + matrix[6], matrix[1]*x + matrix[4]*y + matrix[7]
