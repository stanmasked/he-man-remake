"""Synthetic host-scene tests: no proprietary game assets, display or IPA."""
import math
import unittest

from heman_tools.body_physics import Body, overlaps_body
from heman_tools.scene import (
    SceneControls, SceneState, SceneWorld, advance_scene, new_scene,
    run_script, synthetic_world,
)
from test_body_physics import world as wall_world


class SceneTests(unittest.TestCase):
    def setUp(self):
        self.world = synthetic_world()

    def test_synthetic_world_is_self_contained(self):
        self.assertEqual(self.world.grid.width, 100)
        self.assertEqual(self.world.grid.height, 30)
        self.assertEqual(set(self.world.grid.masks), {5, 6})

    def test_spawn_clear_of_terrain(self):
        s = new_scene(self.world)
        self.assertFalse(overlaps_body(self.world.grid, s.actor.x, s.actor.feet_y,
                                       self.world.physics.half_width,
                                       self.world.physics.height))

    def test_walk_and_camera_follow(self):
        s = run_script(self.world, [SceneControls(axis=1)] * 70)
        self.assertGreater(s.actor.x, self.world.spawn_x)
        followed = advance_scene(SceneState(Body(900,368,grounded=True)), self.world)
        self.assertGreater(followed.camera_x, 0)

    def test_camera_bounds(self):
        s = run_script(self.world, [SceneControls(axis=1)] * 550)
        self.assertGreaterEqual(s.camera_x, 0)
        self.assertLessEqual(s.camera_x, self.world.grid.width*16-self.world.viewport_width)
        self.assertGreaterEqual(s.camera_y, 0)

    def test_small_world_camera_clamped(self):
        w = SceneWorld(wall_world(), 20, 64, viewport_width=800, viewport_height=480)
        s = run_script(w, [SceneControls()] * 20)
        self.assertEqual((s.camera_x, s.camera_y), (0, 0))

    def test_jump_after_initial_contact(self):
        s = new_scene(self.world)
        first = advance_scene(s, self.world, SceneControls(jump=True))
        self.assertTrue(first.actor.grounded)  # initial state had not yet detected support
        landed = run_script(self.world, [SceneControls()] * 20)
        self.assertTrue(landed.actor.grounded)
        jump = advance_scene(landed, self.world, SceneControls(jump=True))
        self.assertLess(jump.actor.feet_y, landed.actor.feet_y)

    def test_game_start_lands(self):
        s = run_script(self.world, [SceneControls()] * 20)
        self.assertTrue(s.actor.grounded)
        self.assertGreaterEqual(s.landings, 1)

    def test_manual_reset(self):
        s = advance_scene(new_scene(self.world), self.world, SceneControls(reset=True))
        self.assertEqual(s.respawns, 1)
        self.assertEqual(s.actor.x, self.world.spawn_x)

    def test_fall_out_of_world_respawns(self):
        falling = SceneState(Body(31*16,self.world.grid.height*16+self.world.death_margin+1),frame=3)
        s = advance_scene(falling, self.world)
        self.assertEqual(s.respawns, 1)
        self.assertEqual((s.actor.x,s.actor.feet_y),(self.world.spawn_x,self.world.spawn_feet_y))

    def test_deterministic_replay(self):
        instructions = ([SceneControls()]*20+[SceneControls(axis=1)]*30+
                        [SceneControls(axis=1,jump=True)]+[SceneControls(axis=1)]*60)
        self.assertEqual(run_script(self.world,instructions),
                         run_script(self.world,instructions))
        self.assertEqual(new_scene(self.world).frame,0)

    def test_bad_time(self):
        for dt in (0,math.nan,0.2):
            with self.assertRaises(ValueError):
                advance_scene(new_scene(self.world),self.world,dt=dt)

    def test_bad_axis(self):
        with self.assertRaises(ValueError):
            advance_scene(new_scene(self.world),self.world,SceneControls(axis=10))

    def test_invalid_viewport_and_spawn(self):
        with self.assertRaises(ValueError):
            SceneWorld(self.world.grid,0,0,viewport_width=50)
        with self.assertRaises(ValueError):
            SceneWorld(self.world.grid,math.inf,0)
        with self.assertRaises(ValueError):
            SceneWorld(self.world.grid,56,388)  # inside terrain

    def test_script_length_bounded(self):
        with self.assertRaises(ValueError):
            run_script(self.world,[SceneControls()]*100_001)

    def test_ground_is_stable(self):
        s=run_script(self.world,[SceneControls()]*240)
        self.assertTrue(s.actor.grounded)
        self.assertAlmostEqual(s.actor.feet_y,368,delta=.005)


if __name__=='__main__':
    unittest.main()
