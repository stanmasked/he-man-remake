"""Asset-free event interactions for the experimental desktop scene.

This module contains independent prototype rules, not recovered iOS scripts.
An interaction has a stable ID, a kind and a local world-space circle; objects
are never loaded from original game scripts or embedded binary records.
"""
from dataclasses import dataclass, replace
import math

from .body_physics import Body, overlaps_body
from .scene import (SceneControls, SceneState, SceneWorld,
                    advance_scene, new_scene, synthetic_world)

KINDS = frozenset({"pickup", "checkpoint", "hazard", "exit", "trigger"})
MAX_EVENTS = 2048


@dataclass(frozen=True)
class SceneEvent:
    id: str
    kind: str
    x: float
    y: float
    radius: float = 12.0

    def __post_init__(self):
        if not self.id or len(self.id) > 80 or not self.id.isascii() or not self.id.isprintable():
            raise ValueError("invalid event ID")
        if self.kind not in KINDS:
            raise ValueError("unsupported event kind")
        if not all(math.isfinite(v) for v in (self.x, self.y, self.radius)):
            raise ValueError("event coordinates must be finite")
        if not 1 <= self.radius <= 128:
            raise ValueError("event radius out of range")


@dataclass(frozen=True)
class InteractiveWorld:
    scene: SceneWorld
    events: tuple[SceneEvent, ...]

    def __post_init__(self):
        if len(self.events) > MAX_EVENTS:
            raise ValueError("too many events")
        ids = [event.id for event in self.events]
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate event IDs")
        for event in self.events:
            if event.kind == "checkpoint":
                if overlaps_body(self.scene.grid, event.x, event.y,
                                 self.scene.physics.half_width, self.scene.physics.height):
                    raise ValueError("checkpoint respawn point overlaps terrain")


@dataclass(frozen=True)
class InteractiveState:
    scene: SceneState
    checkpoint: str | None = None
    collected: tuple[str, ...] = ()
    activated_triggers: tuple[str, ...] = ()
    hazard_hits: int = 0
    completed: bool = False


def new_interactive_scene(world: InteractiveWorld) -> InteractiveState:
    return InteractiveState(new_scene(world.scene))


def _touches(event: SceneEvent, actor: Body, half_width: float, height: float) -> bool:
    """Circle-vs-character AABB intersection, including actor's head and sides."""
    dx = max(0.0, abs(event.x - actor.x) - half_width)
    top = actor.feet_y - height
    dy = max(0.0, top - event.y, event.y - actor.feet_y)
    return dx * dx + dy * dy <= event.radius * event.radius


def _crossed(event: SceneEvent, previous: Body, current: Body,
             half_width: float, height: float) -> bool:
    """Sample intervening body positions so fast input cannot skip small items.

    This is bounded by the physics engine's per-step displacement safety
    limit; if a teleport or invalid huge transition is encountered, only
    test the new position (respawns are handled separately).
    """
    dx, dy = current.x - previous.x, current.feet_y - previous.feet_y
    n = math.ceil(max(abs(dx), abs(dy)))
    if n > 512:
        return _touches(event, current, half_width, height)
    for i in range(n + 1):
        fraction = i / max(1, n)
        body = Body(previous.x + dx * fraction,
                    previous.feet_y + dy * fraction)
        if _touches(event, body, half_width, height):
            return True
    return False


def _checkpoint_spawn(world: InteractiveWorld, checkpoint: str | None) -> Body:
    if checkpoint is None:
        return Body(world.scene.spawn_x, world.scene.spawn_feet_y)
    for event in world.events:
        if event.id == checkpoint and event.kind == "checkpoint":
            return Body(event.x, event.y)
    raise ValueError("checkpoint ID is not present in world")


def advance_interactive(state: InteractiveState, world: InteractiveWorld,
                        controls: SceneControls = SceneControls(),
                        dt: float = 1 / 60) -> InteractiveState:
    """Update physics, followed by pickups, checkpoints, hazards and exit flags.

    Pickups/triggers are one-shot; checkpoints persist through reset/death.
    Hazard hits reset to latest checkpoint, preserving collected items.
    """
    if state.hazard_hits < 0:
        raise ValueError("invalid hazard-hit counter")
    ids = {e.id for e in world.events}
    if state.checkpoint is not None and state.checkpoint not in ids:
        raise ValueError("unknown active checkpoint")
    if any(i not in ids for i in (*state.collected, *state.activated_triggers)):
        raise ValueError("unknown saved event ID")
    next_scene = advance_scene(state.scene, world.scene, controls, dt)
    respawned = next_scene.respawns > state.scene.respawns
    checkpoint = state.checkpoint

    # Physical scene may respawn for a fall or a manual reset.
    if respawned:
        next_scene = replace(next_scene, actor=_checkpoint_spawn(world, checkpoint))

    collected = list(state.collected)
    triggers = list(state.activated_triggers)
    completed = state.completed
    hazards = 0

    for event in world.events:
        touched = _touches(event, next_scene.actor, world.scene.physics.half_width,
                           world.scene.physics.height) if respawned else _crossed(
                               event, state.scene.actor, next_scene.actor,
                               world.scene.physics.half_width, world.scene.physics.height)
        if not touched:
            continue
        if event.kind == "pickup" and event.id not in collected:
            collected.append(event.id)
        elif event.kind == "checkpoint":
            checkpoint = event.id
        elif event.kind == "trigger" and event.id not in triggers:
            triggers.append(event.id)
        elif event.kind == "exit":
            completed = True
        elif event.kind == "hazard":
            hazards = 1
    if hazards:
        next_scene = replace(next_scene, actor=_checkpoint_spawn(world, checkpoint),
                             respawns=next_scene.respawns + 1)

    return InteractiveState(next_scene, checkpoint, tuple(collected),
                            tuple(triggers), state.hazard_hits + hazards, completed)


def synthetic_interactive_world() -> InteractiveWorld:
    """Fictional event course; not a map or scenario from the commercial game."""
    base = synthetic_world()
    return InteractiveWorld(base, (
        SceneEvent("pickup_a", "pickup", 116, 352, 10),
        SceneEvent("checkpoint_a", "checkpoint", 240, 368, 12),
        SceneEvent("switch_a", "trigger", 285, 352, 8),
        SceneEvent("spikes_a", "hazard", 394, 353, 9),
        SceneEvent("exit_a", "exit", 1380, 350, 16),
    ))
