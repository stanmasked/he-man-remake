"""Inert placeholder event markers and a testable HUD presentation model.

No GUI, file I/O or original game artwork required. The visual model is pure
and can be exercised in headless CI without importing Tkinter or Pillow.
"""
from dataclasses import dataclass
import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .scene_interactions import InteractiveWorld, InteractiveState

COLORS = {
    'pickup': '#f7dc6f',
    'checkpoint': '#4ade80',
    'hazard': '#fb7185',
    'exit': '#a78bfa',
    'trigger': '#38bdf8',
}


@dataclass(frozen=True)
class EventMarker:
    id: str
    kind: str
    x: float
    y: float
    radius: float
    color: str
    active: bool = False


@dataclass(frozen=True)
class EventOverlay:
    markers: tuple[EventMarker, ...]
    pickups: int
    pickup_total: int
    checkpoint: str | None
    hazards: int
    respawns: int
    completed: bool
    triggers: int


def event_overlay(world: 'InteractiveWorld', state: 'InteractiveState') -> EventOverlay:
    """Build clipped camera-relative markers and state counters.

    Hide picked-up objects. Leave activated triggers visible but dimmed.
    """
    scene = state.scene
    camera_x, camera_y = scene.camera_x, scene.camera_y
    if not math.isfinite(camera_x) or not math.isfinite(camera_y):
        raise ValueError('camera must be finite')
    width, height = world.scene.viewport_width, world.scene.viewport_height
    markers = []
    for event in world.events:
        if event.kind == 'pickup' and event.id in state.collected:
            continue
        px, py = event.x - camera_x, event.y - camera_y
        radius = event.radius
        if px + radius < 0 or px - radius > width or py + radius < 0 or py - radius > height:
            continue
        active = event.kind == 'checkpoint' and state.checkpoint == event.id
        if event.kind == 'trigger' and event.id in state.activated_triggers:
            active = True
        if event.kind == 'exit' and state.completed:
            active = True
        markers.append(EventMarker(event.id, event.kind, px, py, radius,
                                   COLORS[event.kind], active))
    pickup_total = sum(event.kind == 'pickup' for event in world.events)
    return EventOverlay(tuple(markers), len(state.collected), pickup_total,
                        state.checkpoint, state.hazard_hits, scene.respawns,
                        state.completed, len(state.activated_triggers))


def draw_event_overlay(canvas, model: EventOverlay, *, width: int = 800,
                       height: int = 480) -> None:
    """Draw plain Tk-compatible canvas primitives without external media."""
    for marker in model.markers:
        x, y, r = marker.x, marker.y, min(13.0, marker.radius)
        color = marker.color
        if marker.kind == 'hazard':
            canvas.create_polygon(x, y-r, x+r, y+r, x-r, y+r,
                                  fill=color, outline='#fff1f2', width=2)
            symbol = '!'
        elif marker.kind == 'checkpoint':
            canvas.create_rectangle(x-r*.7, y-r*.7, x+r*.7, y+r*.7,
                                    fill=color if marker.active else '#14532d',
                                    outline=color, width=3 if marker.active else 2)
            symbol = 'C'
        else:
            fill = '#334155' if marker.active else color
            canvas.create_oval(x-r, y-r, x+r, y+r, fill=fill,
                               outline=color, width=2)
            symbol = {'pickup': '+', 'trigger': 'T', 'exit': 'E'}[marker.kind]
        canvas.create_text(x, y, text=symbol, fill='#08111e',
                           font=('Arial', 10, 'bold'))
    canvas.create_rectangle(8, 61, min(width-8, 510), 101,
                            fill='#0b192d', outline='#475569')
    checkpoint = 'ACTIVE' if model.checkpoint else 'NONE'
    exit_label = 'FINISHED' if model.completed else 'OPEN'
    status = (f'Items {model.pickups}/{model.pickup_total}   '
              f'Checkpoint {checkpoint}   Hits {model.hazards}   '
              f'Respawns {model.respawns}   Exit {exit_label}')
    canvas.create_text(18, 73, anchor='nw', fill='#f8fafc',
                       font=('Arial', 11, 'bold'), text=status)
    canvas.create_text(18, 88, anchor='nw', fill='#94a3b8',
                       font=('Arial', 9),
                       text=f'Triggers {model.triggers}   |   Synthetic course - not original game scripting')
