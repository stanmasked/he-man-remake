"""Synthetic game-object interaction regressions; no commercial source assets."""
from dataclasses import replace
import math
import unittest

from heman_tools.body_physics import Body
from heman_tools.scene import SceneControls, SceneState
from heman_tools.scene_interactions import (
    SceneEvent, InteractiveWorld, InteractiveState, _crossed,
    advance_interactive, new_interactive_scene, synthetic_interactive_world,
)


class SceneInteractionTests(unittest.TestCase):
    def setUp(self):
        self.world = synthetic_interactive_world()

    def place(self, x, y=368, *, grounded=True):
        state = new_interactive_scene(self.world)
        return replace(state, scene=replace(
            state.scene, actor=Body(x, y, grounded=grounded)))

    def test_world_is_independent_synthetic_fixture(self):
        self.assertEqual(len(self.world.events), 5)
        self.assertEqual({e.kind for e in self.world.events},
                         {"pickup", "checkpoint", "trigger", "hazard", "exit"})

    def test_pickup_is_one_shot(self):
        state = advance_interactive(self.place(116), self.world)
        self.assertEqual(state.collected, ("pickup_a",))
        state = advance_interactive(state, self.world)
        self.assertEqual(state.collected, ("pickup_a",))

    def test_checkpoint_activation(self):
        state = advance_interactive(self.place(260), self.world)
        self.assertEqual(state.checkpoint, "checkpoint_a")

    def test_checkpoint_persists_after_manual_reset(self):
        state = advance_interactive(self.place(260), self.world)
        state = advance_interactive(state, self.world, SceneControls(reset=True))
        self.assertEqual(state.checkpoint, "checkpoint_a")
        self.assertEqual(state.scene.actor.x, 260)
        self.assertEqual(state.scene.actor.feet_y, 368)
        self.assertEqual(state.scene.respawns, 1)

    def test_checkpoint_restores_after_fall(self):
        state = advance_interactive(self.place(260), self.world)
        death_y = self.world.scene.grid.height * self.world.scene.grid.tile_size + 120
        state = replace(state, scene=replace(
            state.scene, actor=Body(530, death_y)))
        state = advance_interactive(state, self.world)
        self.assertEqual(state.scene.actor.x, 260)
        self.assertEqual(state.scene.respawns, 1)

    def test_pickups_persist_across_reset(self):
        state = advance_interactive(self.place(116), self.world)
        state = replace(state, scene=replace(
            state.scene, actor=Body(260, 368, grounded=True)))
        state = advance_interactive(state, self.world)
        state = advance_interactive(state, self.world, SceneControls(reset=True))
        self.assertEqual(state.collected, ("pickup_a",))

    def test_hazard_respawns_at_checkpoint(self):
        state = advance_interactive(self.place(260), self.world)
        state = replace(state, scene=replace(
            state.scene, actor=Body(394, 368, grounded=True)))
        state = advance_interactive(state, self.world)
        self.assertEqual(state.hazard_hits, 1)
        self.assertEqual(state.scene.respawns, 1)
        self.assertEqual(state.scene.actor.x, 260)

    def test_hazard_without_checkpoint_uses_origin(self):
        state = advance_interactive(self.place(394), self.world)
        self.assertEqual(state.hazard_hits, 1)
        self.assertEqual(state.scene.actor.x, self.world.scene.spawn_x)

    def test_trigger_once(self):
        state = advance_interactive(self.place(275), self.world)
        self.assertEqual(state.activated_triggers, ("switch_a",))
        state = advance_interactive(state, self.world)
        self.assertEqual(state.activated_triggers, ("switch_a",))

    def test_exit_is_persistent(self):
        state = advance_interactive(self.place(1380), self.world)
        self.assertTrue(state.completed)
        state = advance_interactive(state, self.world)
        self.assertTrue(state.completed)

    def test_segment_detects_fast_pass_through(self):
        event = SceneEvent("fast", "pickup", 100, 350, 4)
        self.assertTrue(_crossed(event, Body(50,368), Body(150,368), 5, 22))

    def test_marker_far_from_character(self):
        state = advance_interactive(self.place(56), self.world)
        self.assertEqual(state.collected, ())
        self.assertIsNone(state.checkpoint)

    def test_invalid_events_and_duplicates(self):
        with self.assertRaises(ValueError): SceneEvent("", "pickup", 0, 0)
        with self.assertRaises(ValueError): SceneEvent("x", "unknown", 0, 0)
        with self.assertRaises(ValueError): SceneEvent("x", "pickup", math.nan, 0)
        with self.assertRaises(ValueError): SceneEvent("x", "pickup", 0, 0, 500)
        event = SceneEvent("dup", "pickup", 116, 352)
        with self.assertRaises(ValueError):
            InteractiveWorld(self.world.scene, (event, event))

    def test_checkpoint_spawn_inside_wall_rejected(self):
        with self.assertRaises(ValueError):
            InteractiveWorld(self.world.scene,
                (SceneEvent("bad", "checkpoint", 100, 384),))

    def test_saved_unknown_checkpoint_rejected(self):
        bad = replace(new_interactive_scene(self.world), checkpoint="missing")
        with self.assertRaises(ValueError):
            advance_interactive(bad, self.world)


if __name__ == "__main__":
    unittest.main()
