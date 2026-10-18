"""Prototype vertical character physics over a pixel-mask collision tilemap.

This is a host-side experiment, NOT the original game's physics or a Switch
build. Coordinates have +Y pointing down. Only feet contacts are handled;
head hits, side walls, moving platforms and combat are out of scope.
"""
from dataclasses import dataclass
import math

EMPTY = 0xffff


@dataclass(frozen=True)
class CollisionMask:
    """Per-row bitsets, bit x represents solid local pixel x."""
    size: int
    rows: tuple[int, ...]

    def __post_init__(self):
        if not 1 <= self.size <= 64 or len(self.rows) != self.size:
            raise ValueError('invalid collision mask size')
        if any(not isinstance(v, int) or v < 0 or v >= (1 << self.size) for v in self.rows):
            raise ValueError('invalid collision row bits')

    @classmethod
    def from_alpha(cls, alpha_rows, *, threshold=128):
        rows = tuple(tuple(row) for row in alpha_rows)
        size = len(rows)
        if not 1 <= size <= 64 or any(len(row) != size for row in rows):
            raise ValueError('alpha mask must be square and between 1 and 64 pixels')
        if not 1 <= threshold <= 255:
            raise ValueError('invalid alpha threshold')
        if any(not isinstance(a, int) or not 0 <= a <= 255 for row in rows for a in row):
            raise ValueError('alpha is not a byte')
        return cls(size, tuple(sum((1 << x) for x, a in enumerate(row) if a >= threshold)
                               for row in rows))

    def solid(self, x: int, y: int) -> bool:
        return 0 <= x < self.size and 0 <= y < self.size and bool(self.rows[y] & (1 << x))


@dataclass(frozen=True)
class MaskedGrid:
    width: int
    height: int
    tile_size: int
    tile_ids: tuple[int, ...]
    masks: dict[int, CollisionMask]

    def __post_init__(self):
        if not 1 <= self.width <= 10000 or not 1 <= self.height <= 10000 or self.width * self.height > 100000:
            raise ValueError('bad grid dimensions')
        if self.tile_size < 1 or self.tile_size > 64 or len(self.tile_ids) != self.width * self.height:
            raise ValueError('bad tile size or data length')
        if any(t != EMPTY and t not in self.masks for t in self.tile_ids):
            raise ValueError('missing physical mask for occupied tile ID')
        if any(m.size != self.tile_size for m in self.masks.values()):
            raise ValueError('physical mask size differs from tile size')

    def solid_at(self, x: int, y: int) -> bool:
        """Coordinate query in integer world pixels (row 0 is the top row)."""
        tile_x, tile_y = x // self.tile_size, y // self.tile_size
        if not (0 <= tile_x < self.width and 0 <= tile_y < self.height):
            return False
        tile = self.tile_ids[tile_y * self.width + tile_x]
        return tile != EMPTY and self.masks[tile].solid(x % self.tile_size, y % self.tile_size)

    def first_feet_contact(self, x: float, half_width: float, begin_y: float, end_y: float) -> int | None:
        """First solid scanline along a downward path.

        Samples center and two edges; ignores lateral contacts and moving tiles.
        Scanning every pixel avoids tunnelling for large downward displacements.
        """
        if not all(math.isfinite(v) for v in (x, half_width, begin_y, end_y)):
            raise ValueError('non-finite contact query')
        if half_width < 0 or end_y < begin_y:
            raise ValueError('invalid downward scan range')
        # feet_y denotes the top edge of the first solid pixel, not its center.
        px = {math.floor(x - half_width), math.floor(x), math.floor(x + half_width)}
        for py in range(math.floor(begin_y), math.floor(end_y) + 1):
            if any(self.solid_at(ix, py) for ix in px):
                return py
        return None


@dataclass(frozen=True)
class Actor:
    x: float
    feet_y: float
    vertical_speed: float = 0.0
    grounded: bool = False


@dataclass(frozen=True)
class PhysicsConfig:
    gravity: float = 1200.0
    jump_speed: float = 400.0
    horizontal_speed: float = 160.0
    half_width: float = 6.0
    max_step_up: float = 12.0
    max_step_down: float = 12.0
    max_fall_speed: float = 1500.0


def step_actor(actor: Actor, grid: MaskedGrid, axis: float, jump: bool,
               dt: float, config: PhysicsConfig = PhysicsConfig()) -> Actor:
    """One fixed-size host simulation tick; supports gravity and feet landing.

    No collision checks are performed on the actor's body or sides. This does
    not claim parity with iOS movement or collision semantics.
    """
    values = (actor.x, actor.feet_y, actor.vertical_speed, axis, dt,
              config.gravity, config.jump_speed, config.horizontal_speed,
              config.half_width, config.max_step_up, config.max_step_down,
              config.max_fall_speed)
    if not all(math.isfinite(v) for v in values):
        raise ValueError('non-finite physics value')
    if not -1 <= axis <= 1 or not 0 < dt <= 1/30:
        raise ValueError('invalid axis or timestep; use fixed substeps')
    if min(config.gravity, config.jump_speed, config.horizontal_speed,
           config.max_fall_speed) <= 0 or min(config.half_width, config.max_step_up,
                                              config.max_step_down) < 0:
        raise ValueError('invalid physics configuration')
    x = actor.x + axis * config.horizontal_speed * dt
    feet = actor.feet_y
    vy = actor.vertical_speed
    grounded = actor.grounded
    if grounded and jump:
        vy = -config.jump_speed
        grounded = False
    elif grounded:
        surface = grid.first_feet_contact(x, config.half_width,
                                          feet - config.max_step_up,
                                          feet + config.max_step_down)
        if surface is not None:
            return Actor(x, float(surface), 0.0, True)
        grounded = False
        vy = 0.0
    if not grounded:
        vy = min(vy + config.gravity * dt, config.max_fall_speed)
        next_feet = feet + vy * dt
        if vy >= 0:
            hit = grid.first_feet_contact(x, config.half_width, feet, next_feet)
            if hit is not None:
                return Actor(x, float(hit), 0.0, True)
        return Actor(x, next_feet, vy, False)
    raise AssertionError('unreachable')
