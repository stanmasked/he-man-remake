"""Synthetic-only tests for event GUI view; no Tk display or game assets."""
from dataclasses import dataclass
from types import SimpleNamespace
import math
import unittest
from heman_tools.event_view import COLORS, draw_event_overlay, event_overlay


@dataclass(frozen=True)
class Event:
    id: str
    kind: str
    x: float
    y: float
    radius: float = 10.0


class FakeCanvas:
    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        if not name.startswith('create_'):
            raise AttributeError(name)
        def draw(*args, **kwargs):
            self.calls.append((name, args, kwargs))
        return draw


def fixture(*, collected=(), checkpoint=None, triggered=(), completed=False,
            camera=(0, 0), hazards=0, respawns=0):
    events = (
        Event('p', 'pickup', 30, 30),
        Event('c', 'checkpoint', 70, 30),
        Event('h', 'hazard', 110, 30),
        Event('t', 'trigger', 150, 30),
        Event('e', 'exit', 190, 30),
        Event('far', 'pickup', 1000, 30),
    )
    scene = SimpleNamespace(viewport_width=320, viewport_height=240)
    state = SimpleNamespace(
        scene=SimpleNamespace(camera_x=camera[0], camera_y=camera[1],
                              respawns=respawns),
        collected=collected, checkpoint=checkpoint,
        activated_triggers=triggered, hazard_hits=hazards,
        completed=completed,
    )
    return SimpleNamespace(scene=scene, events=events), state


class EventViewTests(unittest.TestCase):
    def test_render_all_visible_kinds(self):
        w, s = fixture()
        result = event_overlay(w, s)
        self.assertEqual([m.kind for m in result.markers],
                         ['pickup', 'checkpoint', 'hazard', 'trigger', 'exit'])
        self.assertEqual(result.pickup_total, 2)
        self.assertEqual(result.pickups, 0)

    def test_collected_pickup_hidden(self):
        w, s = fixture(collected=('p',))
        model = event_overlay(w, s)
        self.assertNotIn('p', [m.id for m in model.markers])
        self.assertEqual(model.pickups, 1)

    def test_active_checkpoint_and_trigger_and_exit(self):
        w, s = fixture(checkpoint='c', triggered=('t',), completed=True)
        model = event_overlay(w, s)
        self.assertTrue(model.completed)
        self.assertEqual(model.triggers, 1)
        self.assertTrue(all(m.active for m in model.markers
                            if m.kind in ('checkpoint', 'trigger', 'exit')))

    def test_checkpoint_not_yet_active(self):
        w, s = fixture()
        self.assertFalse(next(m.active for m in event_overlay(w, s).markers
                              if m.kind == 'checkpoint'))

    def test_camera_scrolling_coordinates(self):
        w, s = fixture(camera=(100, 10))
        markers = event_overlay(w, s).markers
        self.assertNotIn('p', [m.id for m in markers])
        self.assertEqual(next(m.x for m in markers if m.id == 'h'), 10)
        self.assertEqual(next(m.y for m in markers if m.id == 'h'), 20)

    def test_different_counter_fields(self):
        w, s = fixture(hazards=3, respawns=7)
        model = event_overlay(w, s)
        self.assertEqual((model.hazards, model.respawns), (3, 7))

    def test_offscreen_culling(self):
        w, s = fixture(camera=(800, 0))
        self.assertEqual([m.id for m in event_overlay(w, s).markers], ['far'])

    def test_invalid_camera(self):
        w, s = fixture(camera=(math.nan, 0))
        with self.assertRaises(ValueError):
            event_overlay(w, s)

    def test_draws_plain_canvas_primitives(self):
        w, s = fixture()
        canvas = FakeCanvas()
        draw_event_overlay(canvas, event_overlay(w, s), width=320, height=240)
        methods = [call[0] for call in canvas.calls]
        self.assertIn('create_polygon', methods)
        self.assertIn('create_oval', methods)
        self.assertIn('create_rectangle', methods)
        self.assertIn('create_text', methods)
        self.assertNotIn('create_image', methods)

    def test_hud_includes_state_and_no_source_artwork(self):
        w, s = fixture(collected=('p',), checkpoint='c', hazards=2,
                       completed=True)
        canvas = FakeCanvas()
        draw_event_overlay(canvas, event_overlay(w, s))
        texts = ' '.join(str(kwargs.get('text', ''))
                         for _, _, kwargs in canvas.calls)
        for value in ('Items 1/2', 'Checkpoint ACTIVE', 'Hits 2', 'Exit FINISHED'):
            self.assertIn(value, texts)
        self.assertEqual(set(COLORS), {'pickup', 'checkpoint', 'hazard',
                                       'trigger', 'exit'})

    def test_output_deterministic(self):
        w, s = fixture(camera=(21, 0))
        self.assertEqual(event_overlay(w, s), event_overlay(w, s))


if __name__ == '__main__':
    unittest.main()
