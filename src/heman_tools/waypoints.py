"""Read-only decoder for named point groups in the final .lvl section.

Two flags and link indices are preserved without inventing gameplay semantics.
No executable content from the source game is loaded.
"""
from dataclasses import dataclass
import math
import struct

from .lvl import LevelFormatError
from .objects import _string, _need, parse_level_objects

_POINT = struct.Struct("<IfffHI")
_U32 = struct.Struct("<I")
_MAX_GROUPS = 10_000
_MAX_POINTS_PER_GROUP = 10_000
_MAX_TOTAL_POINTS = 100_000
_MAX_LINKS_PER_POINT = 10_000


@dataclass(frozen=True)
class PathPoint:
    x: float
    y: float
    z: float
    marker: int
    short_field: int
    link_indices: tuple[int, ...]


@dataclass(frozen=True)
class NamedPointGroup:
    name: str
    points: tuple[PathPoint, ...]


@dataclass(frozen=True)
class LevelPointGroups:
    level_name: str
    groups: tuple[NamedPointGroup, ...]
    total_points: int
    total_links: int
    trailing_unparsed_bytes: int


def parse_waypoints(data: bytes) -> LevelPointGroups:
    """Consume all named point groups, rejecting malformed counts and boundaries."""
    parsed = parse_level_objects(data)
    cursor = parsed.trailer_offset
    _need(data, cursor, _U32.size)
    n_groups = _U32.unpack_from(data, cursor)[0]
    if n_groups > _MAX_GROUPS:
        raise LevelFormatError("too many named point groups")
    cursor += _U32.size
    groups = []
    total_points = 0
    total_links = 0
    for group_i in range(n_groups):
        name, cursor = _string(data, cursor, allow_empty=False)
        _need(data, cursor, _U32.size)
        count = _U32.unpack_from(data, cursor)[0]
        cursor += _U32.size
        if count > _MAX_POINTS_PER_GROUP or count > _MAX_TOTAL_POINTS - total_points:
            raise LevelFormatError("too many points in group")
        points = []
        for point_i in range(count):
            _need(data, cursor, _POINT.size)
            marker, x, y, z, short_field, n_links = _POINT.unpack_from(data, cursor)
            cursor += _POINT.size
            if not all(math.isfinite(v) for v in (x, y, z)):
                raise LevelFormatError(f"non-finite coordinate in group {group_i}, point {point_i}")
            if n_links > _MAX_LINKS_PER_POINT or n_links > (len(data) - cursor) // 4:
                raise LevelFormatError("invalid count of point links")
            links = tuple(_U32.unpack_from(data, cursor + k * 4)[0] for k in range(n_links))
            if any(index >= count for index in links):
                raise LevelFormatError(f"point link outside group {group_i}")
            cursor += n_links * 4
            total_links += n_links
            points.append(PathPoint(x, y, z, marker, short_field, links))
        total_points += count
        groups.append(NamedPointGroup(name, tuple(points)))
    if cursor != len(data):
        raise LevelFormatError(f"point-group block has {len(data) - cursor} unexpected bytes")
    return LevelPointGroups(parsed.level_name, tuple(groups), total_points, total_links, 0)
