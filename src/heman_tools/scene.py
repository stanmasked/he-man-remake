"""Deterministic host scene: original game assets are never bundled here."""
from dataclasses import dataclass
import math

from .body_physics import Body, BodyConfig, overlaps_body
from .mask_physics import CollisionMask, EMPTY, MaskedGrid
from .slope_physics import SlopeConfig, step_body_slopes


@dataclass(frozen=True)
class SceneControls:
    axis: float = 0.0
    jump: bool = False
    reset: bool = False


@dataclass(frozen=True)
class SceneWorld:
    grid: MaskedGrid
    spawn_x: float
    spawn_feet_y: float
    physics: BodyConfig = BodyConfig()
    slope: SlopeConfig = SlopeConfig()
    viewport_width: int = 800
    viewport_height: int = 480
    death_margin: int = 96

    def __post_init__(self):
        if not all(math.isfinite(v) for v in (self.spawn_x, self.spawn_feet_y)):
            raise ValueError('invalid spawn coordinates')
        if not 320 <= self.viewport_width <= 8192 or not 240 <= self.viewport_height <= 4096:
            raise ValueError('viewport dimensions out of bounds')
        if not 0 <= self.death_margin <= 8192:
            raise ValueError('invalid death margin')
        if overlaps_body(self.grid, self.spawn_x, self.spawn_feet_y,
                         self.physics.half_width, self.physics.height):
            raise ValueError('spawn intersects solid terrain')


@dataclass(frozen=True)
class SceneState:
    actor: Body
    camera_x: float = 0.0
    camera_y: float = 0.0
    frame: int = 0
    respawns: int = 0
    landings: int = 0


def new_scene(world: SceneWorld) -> SceneState:
    return SceneState(Body(world.spawn_x, world.spawn_feet_y))


def _clamp(value, minimum, maximum):
    return min(maximum, max(minimum, value))


def advance_scene(state: SceneState, world: SceneWorld,
                  controls: SceneControls = SceneControls(),
                  dt: float = 1/60) -> SceneState:
    """One reproducible physics and camera tick; no GUI/clock dependencies."""
    if not math.isfinite(dt) or not 0 < dt <= 1/30:
        raise ValueError('invalid fixed timestep')
    if not math.isfinite(controls.axis) or not -1 <= controls.axis <= 1:
        raise ValueError('invalid axis')
    if min(state.frame, state.respawns, state.landings) < 0:
        raise ValueError('invalid counters')
    if controls.reset:
        actor = Body(world.spawn_x, world.spawn_feet_y)
        respawns = state.respawns + 1
    else:
        actor = step_body_slopes(state.actor, world.grid, controls.axis,
                                 controls.jump, dt, world.physics, world.slope)
        respawns = state.respawns
        if actor.feet_y > world.grid.height * world.grid.tile_size + world.death_margin:
            actor = Body(world.spawn_x, world.spawn_feet_y)
            respawns += 1
    landed = state.landings + int(actor.grounded and not state.actor.grounded)
    full_width = world.grid.width * world.grid.tile_size
    full_height = world.grid.height * world.grid.tile_size
    target_x = _clamp(actor.x - world.viewport_width * .42,
                      0, max(0, full_width - world.viewport_width))
    target_y = _clamp(actor.feet_y - world.viewport_height * .64,
                      0, max(0, full_height - world.viewport_height))
    factor = min(1.0, dt * 10.0)
    camera_x = _clamp(state.camera_x + factor * (target_x-state.camera_x),
                      0, max(0, full_width-world.viewport_width))
    camera_y = _clamp(state.camera_y + factor * (target_y-state.camera_y),
                      0, max(0, full_height-world.viewport_height))
    return SceneState(actor, camera_x, camera_y, state.frame+1, respawns, landed)


def synthetic_world() -> SceneWorld:
    """An independently designed collision exercise course; no original tiles."""
    tile_size, width, height = 16, 100, 30
    cells = [EMPTY] * (width * height)
    for y in range(23, 30):
        for x in range(width):
            if not 30 <= x <= 34:
                cells[y * width + x] = 5
    for x in (13, 14):
        cells[22 * width + x] = 5
    cells[22 * width + 18] = 6
    cells[22 * width + 19] = 5
    for x in range(39, 45):
        cells[18 * width + x] = 5
    for x in range(48, 54):
        cells[20 * width + x] = 5
    for x in range(66, 68):
        for y in range(20, 23):
            cells[y * width + x] = 5
    full = CollisionMask(tile_size, ((1 << tile_size)-1,) * tile_size)
    ramp = CollisionMask.from_alpha([
        [255 if y >= tile_size - x - 1 else 0 for x in range(tile_size)]
        for y in range(tile_size)])
    grid = MaskedGrid(width, height, tile_size, tuple(cells), {5: full, 6: ramp})
    return SceneWorld(grid, 56, 368,
                      physics=BodyConfig(half_width=5, height=22,
                                         horizontal_speed=160, gravity=1200,
                                         jump_speed=420),
                      slope=SlopeConfig(max_rise=7, max_drop=6))


def run_script(world: SceneWorld, inputs: list[SceneControls], dt: float = 1/60) -> SceneState:
    if len(inputs) > 100_000:
        raise ValueError('too many scripted input frames')
    state = new_scene(world)
    for controls in inputs:
        state = advance_scene(state, world, controls, dt)
    return state
