"""Read-only multilayer tilemap parser. No rendering or gameplay collision claim."""
from dataclasses import dataclass
import math
import struct


class TileMapFormatError(ValueError):
    """Malformed or unsupported iOS multilayer .map."""


MAX_FILE = 16_000_000
MAX_CELLS = 100_000
MAX_ATLASES = 256
MAX_UTF16_UNITS = 512


@dataclass(frozen=True)
class TileCell:
    tile_id: int
    atlas_id: int

    @property
    def empty(self) -> bool:
        return self.tile_id == 0xffff


@dataclass(frozen=True)
class TileLayer:
    name: str
    identity: int
    visible: bool
    opacity: float
    tile_width: int
    tile_height: int
    atlas_tile_width: int
    atlas_tile_height: int
    columns: int
    rows: int
    atlases: tuple[str, ...]
    tile_ids: tuple[int, ...]
    atlas_ids: bytes

    def cell(self, x: int, y: int) -> TileCell:
        if not isinstance(x, int) or not isinstance(y, int) or not (0 <= x < self.columns and 0 <= y < self.rows):
            raise IndexError('tile coordinate out of range')
        p = y * self.columns + x
        return TileCell(self.tile_ids[p], self.atlas_ids[p])

    @property
    def occupied_count(self) -> int:
        return sum(t != 0xffff for t in self.tile_ids)


@dataclass(frozen=True)
class TileMap:
    layers: tuple[TileLayer, ...]

    def layer(self, name: str) -> TileLayer:
        found = [l for l in self.layers if l.name == name]
        if len(found) != 1:
            raise KeyError(f'expected one named layer: {name!r}')
        return found[0]


class _Reader:
    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0

    def read(self, n: int) -> bytes:
        if n < 0 or n > len(self.data) - self.pos:
            raise TileMapFormatError(f'truncated map at offset {self.pos}')
        result = self.data[self.pos:self.pos+n]
        self.pos += n
        return result

    def u32(self) -> int:
        return struct.unpack('<I', self.read(4))[0]

    def u16(self) -> int:
        return struct.unpack('<H', self.read(2))[0]

    def f32(self) -> float:
        return struct.unpack('<f', self.read(4))[0]

    def utf16(self, *, allow_empty: bool = False) -> str:
        units = self.u16()
        if units > MAX_UTF16_UNITS or (not allow_empty and not units):
            raise TileMapFormatError('invalid UTF-16 string length')
        try:
            text = self.read(units*2).decode('utf-16le', errors='strict')
        except UnicodeDecodeError as exc:
            raise TileMapFormatError('invalid UTF-16 string') from exc
        if any(ord(char) < 32 for char in text):
            raise TileMapFormatError('control character in name')
        return text


def parse_tilemap(data: bytes) -> TileMap:
    if len(data) < 4 or len(data) > MAX_FILE:
        raise TileMapFormatError('invalid map byte length')
    reader = _Reader(data)
    count = reader.u32()
    if not 1 <= count <= 3:
        raise TileMapFormatError(f'unsupported multilayer map count {count}')
    layers = []
    for _ in range(count):
        identity = reader.u32()
        if identity != 0:
            raise TileMapFormatError('unsupported layer identity')
        visible_raw = reader.read(1)[0]
        if visible_raw not in (0,1):
            raise TileMapFormatError('invalid visibility flag')
        opacity = reader.f32()
        if not math.isfinite(opacity) or not 0 <= opacity <= 1:
            raise TileMapFormatError('invalid opacity')
        name = reader.utf16()
        tile_width, tile_height, atlas_tile_width, atlas_tile_height = (reader.u32() for _ in range(4))
        if not all(1 <= n <= 4096 for n in (tile_width, tile_height, atlas_tile_width, atlas_tile_height)):
            raise TileMapFormatError('invalid tile dimensions')
        columns, rows, atlas_count = reader.u32(), reader.u32(), reader.u32()
        if not columns or not rows or columns > MAX_CELLS or rows > MAX_CELLS // columns:
            raise TileMapFormatError('invalid map dimensions')
        if atlas_count > MAX_ATLASES:
            raise TileMapFormatError('too many atlas references')
        atlases = tuple(reader.utf16() for _ in range(atlas_count))
        cells = columns * rows
        tile_ids = struct.unpack('<' + str(cells) + 'H', reader.read(cells*2))
        atlas_ids = reader.read(cells)
        # Empty tile IDs may retain arbitrary/stale atlas IDs in the original.
        if any(t != 0xffff and a >= atlas_count for t, a in zip(tile_ids, atlas_ids)):
            raise TileMapFormatError('occupied tile references non-existent atlas')
        layers.append(TileLayer(name, identity, bool(visible_raw), opacity,
                                tile_width, tile_height, atlas_tile_width,
                                atlas_tile_height, columns, rows, atlases,
                                tile_ids, atlas_ids))
    if reader.pos != len(data):
        raise TileMapFormatError('trailing bytes after final layer')
    return TileMap(tuple(layers))
