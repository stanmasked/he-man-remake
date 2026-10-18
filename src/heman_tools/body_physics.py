"""Experimental full-body pixel-mask collisions for a host-side character.

Only static, two-way collision masks are supported. This is NOT the iOS game's
original physics and is not a Nintendo Switch build. The origin is upper-left;
+Y points down. No original game assets are embedded in these algorithms.
"""
from dataclasses import dataclass
import math

from .mask_physics import MaskedGrid

MAX_SWEEP_PIXELS = 512
MAX_BODY_SIZE = 128


@dataclass(frozen=True)
class Body:
    """Foot position and vertical state for an axis-aligned character body."""
    x: float
    feet_y: float
    vertical_speed: float = 0.0
    grounded: bool = False
    wall_hit: bool = False
    ceiling_hit: bool = False


@dataclass(frozen=True)
class BodyConfig:
    half_width: float = 5.0
    height: float = 22.0
    horizontal_speed: float = 160.0
    gravity: float = 1200.0
    jump_speed: float = 410.0
    max_fall_speed: float = 1500.0


def overlaps_body(grid: MaskedGrid, x: float, feet_y: float,
                  half_width: float, height: float) -> bool:
    """Test body's half-open rectangle against world occupied pixels.

    Pixel coverage uses [min_x, max_x) and [feet_y-height, feet_y).
    When the body stands exactly at tile top, its feet do not intersect tile.
    Outside-grid pixels are empty, as in MaskedGrid.solid_at().
    """
    args = (x, feet_y, half_width, height)
    if (not all(math.isfinite(v) for v in args)
            or half_width <= 0 or height <= 0
            or 2*half_width > MAX_BODY_SIZE or height > MAX_BODY_SIZE):
        raise ValueError('non-finite or non-positive character dimensions')
    for ix in range(math.floor(x-half_width), math.ceil(x+half_width)):
        for iy in range(math.floor(feet_y-height), math.ceil(feet_y)):
            if grid.solid_at(ix, iy):
                return True
    return False


def _sweep(grid: MaskedGrid, x: float, feet_y: float, delta: float,
           half_width: float, height: float, *, horizontal: bool) -> tuple[float, bool]:
    """Sweep one axis at <=1 pixel per step and refine first collision.

    A body initially overlapping solids is invalid; do not teleport to safety.
    """
    if not math.isfinite(delta) or abs(delta) > MAX_SWEEP_PIXELS:
        raise ValueError('invalid movement delta or sweep exceeds safety limit')
    if overlaps_body(grid, x, feet_y, half_width, height):
        raise ValueError('actor starts inside occupied collision mask')
    start = x if horizontal else feet_y
    if not delta:
        return start, False
    n = math.ceil(abs(delta))
    prev = start
    for index in range(1, n+1):
        candidate = start + delta * (index/n)
        cx = candidate if horizontal else x
        cy = feet_y if horizontal else candidate
        if overlaps_body(grid, cx, cy, half_width, height):
            safe, bad = prev, candidate
            for _ in range(14):
                middle = (safe + bad)/2
                if overlaps_body(grid, middle if horizontal else x,
                                 feet_y if horizontal else middle,
                                 half_width, height):
                    bad = middle
                else:
                    safe = middle
            return safe, True
        prev = candidate
    return start + delta, False


def _supported(grid: MaskedGrid, x: float, feet_y: float,
               half_width: float, height: float) -> bool:
    """Check for a collision pixel immediately below the body."""
    return overlaps_body(grid, x, feet_y + 0.25, half_width, height)


def step_body(actor: Body, grid: MaskedGrid, axis: float, jump: bool,
              dt: float, cfg: BodyConfig = BodyConfig()) -> Body:
    """Advance a fixed host tick with full-body horizontal and vertical sweeps.

    Horizontal moves first. Slope adhesion, one-way platforms, contact
    friction and mobile objects are *not* supported.
    """
    params = (actor.x, actor.feet_y, actor.vertical_speed, axis, dt,
              cfg.half_width, cfg.height, cfg.horizontal_speed, cfg.gravity,
              cfg.jump_speed, cfg.max_fall_speed)
    if not all(math.isfinite(v) for v in params):
        raise ValueError('non-finite body physics input')
    if not -1 <= axis <= 1 or not 0 < dt <= 1/30:
        raise ValueError('invalid axis or timestep (fixed <= 1/30 required)')
    if min(cfg.half_width, cfg.height, cfg.horizontal_speed,
           cfg.gravity, cfg.jump_speed, cfg.max_fall_speed) <= 0:
        raise ValueError('invalid body configuration')
    if cfg.half_width > MAX_BODY_SIZE/2 or cfg.height > MAX_BODY_SIZE:
        raise ValueError('body exceeds safety bounds')
    if overlaps_body(grid, actor.x, actor.feet_y, cfg.half_width, cfg.height):
        raise ValueError('actor starts inside occupied collision mask')

    x, wall = _sweep(grid, actor.x, actor.feet_y,
                     axis * cfg.horizontal_speed * dt,
                     cfg.half_width, cfg.height, horizontal=True)
    feet = actor.feet_y
    vy = actor.vertical_speed
    grounded = actor.grounded and _supported(grid, x, feet, cfg.half_width, cfg.height)
    if grounded and jump:
        vy = -cfg.jump_speed
        grounded = False
    elif grounded:
        return Body(x, feet, 0.0, True, wall, False)
    elif actor.grounded:
        # Actor stepped off a ledge; restart falling rather than retaining
        # a stale previous-frame velocity from the grounded state.
        vy = 0.0

    vy = min(vy + cfg.gravity*dt, cfg.max_fall_speed)
    new_feet, impact = _sweep(grid, x, feet, vy*dt,
                              cfg.half_width, cfg.height, horizontal=False)
    ceiling_hit = impact and vy < 0
    if impact:
        return Body(x, new_feet, 0.0, vy >= 0, wall, ceiling_hit)
    return Body(x, new_feet, vy, False, wall, False)
