"""Opt-in host-side slope adhesion for the experimental full-body collider.

Uses only pixel-mask geometry and does not claim parity with the original
iOS game's physics. Existing step_body remains unchanged.
"""
from dataclasses import dataclass
import math

from .body_physics import (
    Body, BodyConfig, MAX_BODY_SIZE, MAX_SWEEP_PIXELS,
    _supported, _sweep, overlaps_body, step_body,
)
from .mask_physics import MaskedGrid


@dataclass(frozen=True)
class SlopeConfig:
    max_rise: int = 6
    max_drop: int = 6


def step_body_slopes(actor: Body, grid: MaskedGrid, axis: float, jump: bool,
                     dt: float, config: BodyConfig = BodyConfig(),
                     slope: SlopeConfig = SlopeConfig()) -> Body:
    """Follow short static slopes while grounded, otherwise use body physics.

    Rising is permitted only if the entire character has clearance during the
    vertical lift and horizontal sweep AND a nearby support surface is found
    at the destination. Stops at tall walls and ceiling obstructions.
    """
    values = (actor.x, actor.feet_y, actor.vertical_speed, axis, dt,
              config.half_width, config.height, config.horizontal_speed,
              config.gravity, config.jump_speed, config.max_fall_speed)
    if not all(math.isfinite(value) for value in values):
        raise ValueError('non-finite slope physics input')
    if not -1 <= axis <= 1 or not 0 < dt <= 1 / 30:
        raise ValueError('invalid input axis or fixed timestep')
    if (min(config.half_width, config.height, config.horizontal_speed,
            config.gravity, config.jump_speed, config.max_fall_speed) <= 0
            or config.height > MAX_BODY_SIZE
            or config.half_width > MAX_BODY_SIZE / 2):
        raise ValueError('invalid body configuration')
    if (not isinstance(slope.max_rise, int)
            or not isinstance(slope.max_drop, int)
            or not 0 <= slope.max_rise <= 32
            or not 0 <= slope.max_drop <= 32):
        raise ValueError('invalid slope configuration')

    dx = axis * config.horizontal_speed * dt
    if abs(dx) > MAX_SWEEP_PIXELS:
        raise ValueError('movement exceeds safety limit')
    if overlaps_body(grid, actor.x, actor.feet_y, config.half_width, config.height):
        raise ValueError('actor starts overlapping geometry')

    # Do not attach an airborne or jumping character to a nearby slope.
    if (not actor.grounded or jump or
            not _supported(grid, actor.x, actor.feet_y,
                           config.half_width, config.height)):
        return step_body(actor, grid, axis, jump, dt, config)

    x, blocked = _sweep(grid, actor.x, actor.feet_y, dx,
                        config.half_width, config.height, horizontal=True)
    base_feet = actor.feet_y

    if blocked and dx and slope.max_rise:
        # Raise by increasing integral pixel steps. The entire path (upward
        # and sideways) must be clear. No pass-through from a high wall.
        for rise in range(1, slope.max_rise + 1):
            raised_feet, ceiling = _sweep(
                grid, actor.x, base_feet, -rise,
                config.half_width, config.height, horizontal=False)
            if ceiling or abs(raised_feet - (base_feet - rise)) > 1e-6:
                break
            candidate_x, still_blocked = _sweep(
                grid, actor.x, raised_feet, dx,
                config.half_width, config.height, horizontal=True)
            if still_blocked:
                continue
            # Require actual support near target; never climb into empty air.
            foot, landed = _sweep(
                grid, candidate_x, raised_feet,
                rise + slope.max_drop + 0.5,
                config.half_width, config.height, horizontal=False)
            if landed and foot <= base_feet + slope.max_drop + 1e-6:
                return Body(candidate_x, foot, 0.0, True, False, False)
        # Preserve normal wall contact when slope clearance fails.
        return step_body(actor, grid, axis, False, dt, config)

    # When motion is unblocked, retain ground contact while descending.
    foot, landed = _sweep(grid, x, base_feet, slope.max_drop + 0.5,
                          config.half_width, config.height, horizontal=False)
    if landed:
        return Body(x, foot, 0.0, True, False, False)
    # No nearby surface; begin falling without moving horizontally twice.
    return step_body(Body(x, base_feet, 0.0, False), grid,
                     0.0, False, dt, config)
