"""Synthetic-only body collider integration tests; no game assets included."""
import math
import unittest

from heman_tools.body_physics import Body, BodyConfig, overlaps_body, step_body
from heman_tools.mask_physics import CollisionMask, MaskedGrid, EMPTY


def full(size=16):
    return CollisionMask(size, tuple([(1 << size)-1]*size))


def world():
    # 6x6, floor row 4; wall occupies x=48..63 from y=16..63.
    w, h = 6, 6
    ids = [EMPTY]*(w*h)
    for x in range(w):
        ids[4*w+x] = 5
    for y in (1,2,3):
        ids[y*w+3] = 5
    return MaskedGrid(w, h, 16, tuple(ids), {5: full()})


def roof_world():
    w, h = 6, 6
    ids = [EMPTY]*(w*h)
    for x in range(w):
        ids[w+x] = 5    # ceiling y=16..31
        ids[4*w+x] = 5  # floor y=64..79
    return MaskedGrid(w, h, 16, tuple(ids), {5: full()})


class FullBodyPhysicsTests(unittest.TestCase):
    def test_half_open_foot_boundary(self):
        g = world()
        self.assertFalse(overlaps_body(g, 20, 64, 4, 18))
        self.assertTrue(overlaps_body(g, 20, 64.01, 4, 18))

    def test_initial_overlap_rejected(self):
        with self.assertRaises(ValueError):
            step_body(Body(50,64,grounded=True),world(),0,False,1/60)

    def test_walk_right_blocked_by_wall(self):
        g=world()
        a=Body(35,64,grounded=True)
        for _ in range(40):
            a=step_body(a,g,1,False,1/60)
        self.assertTrue(a.wall_hit)
        self.assertAlmostEqual(a.x+5,48,delta=0.01)
        self.assertTrue(a.grounded)

    def test_walk_left_blocked_from_other_side(self):
        g=world()
        a=Body(73,64,grounded=True)
        for _ in range(40):
            a=step_body(a,g,-1,False,1/60)
        self.assertTrue(a.wall_hit)
        self.assertAlmostEqual(a.x-5,64,delta=0.01)

    def test_fast_horizontal_displacement_no_tunnel(self):
        a=step_body(Body(35,64,grounded=True),world(),1,False,1/30,
                    BodyConfig(horizontal_speed=2000))
        self.assertTrue(a.wall_hit)
        self.assertLessEqual(a.x,43.01)

    def test_jumping_into_ceiling_stops_vertical_speed(self):
        g=roof_world()
        a=Body(40,64,grounded=True)
        hit=False
        for i in range(24):
            a=step_body(a,g,0,i==0,1/60)
            if a.ceiling_hit:
                hit=True
                self.assertEqual(a.vertical_speed,0)
                self.assertGreaterEqual(a.feet_y-20,32-0.001)
                break
        self.assertTrue(hit)

    def test_ceil_hit_then_fall_again(self):
        g=roof_world()
        a=Body(40,64,grounded=True)
        for i in range(160):
            a=step_body(a,g,0,i==0,1/60)
        self.assertTrue(a.grounded)
        self.assertAlmostEqual(a.feet_y,64,delta=0.01)

    def test_free_fall_to_floor_no_tunnel(self):
        a=Body(20,40,vertical_speed=1000)
        a=step_body(a,world(),0,False,1/30)
        self.assertTrue(a.grounded)
        self.assertAlmostEqual(a.feet_y,64,delta=0.01)

    def test_standing_maintains_ground(self):
        a=step_body(Body(20,64,grounded=True),world(),0,False,1/60)
        self.assertEqual(a.feet_y,64)
        self.assertTrue(a.grounded)

    def test_ledge_drop_without_ghost_ground(self):
        ids=[EMPTY]*4*4
        ids[3*4+0]=5
        g=MaskedGrid(4,4,16,tuple(ids),{5:full()})
        a=Body(10,48,grounded=True)
        for _ in range(25):
            a=step_body(a,g,1,False,1/60)
        self.assertFalse(a.grounded)
        self.assertGreater(a.feet_y,48)

    def test_diagonal_move_towards_wall_then_fall(self):
        g=world()
        a=Body(20,20,vertical_speed=100)
        for _ in range(40):
            a=step_body(a,g,1,False,1/60)
        self.assertLessEqual(a.x+5,48.01)
        self.assertTrue(a.grounded)

    def test_negative_world_coordinates_empty(self):
        self.assertFalse(overlaps_body(world(),-20,20,4,15))

    def test_invalid_parameters(self):
        with self.assertRaises(ValueError): step_body(Body(0,0),world(),math.inf,False,1/60)
        with self.assertRaises(ValueError): step_body(Body(0,0),world(),0,False,1/10)
        with self.assertRaises(ValueError): step_body(Body(0,0),world(),0,False,1/60,BodyConfig(height=0))
        with self.assertRaises(ValueError): overlaps_body(world(),math.nan,20,5,20)

    def test_excessive_sweep_rejected(self):
        with self.assertRaises(ValueError):
            step_body(Body(20,64,grounded=True),world(),1,False,1/30,
                      BodyConfig(horizontal_speed=100000))

    def test_overlarge_body_rejected(self):
        with self.assertRaises(ValueError):
            step_body(Body(20,64,grounded=True),world(),0,False,1/60,
                      BodyConfig(height=200))

    def test_full_body_overlaps_at_head_not_just_feet(self):
        g=roof_world()
        self.assertTrue(overlaps_body(g,40,38,5,20))
        self.assertFalse(overlaps_body(g,40,64,5,20))

    def test_reproducible_fixed_frame_simulation(self):
        def simulate():
            a=Body(20,64,grounded=True)
            for frame in range(120):
                a=step_body(a,world(),1 if frame < 30 else -1,
                            frame == 48,1/60)
            return a
        self.assertEqual(simulate(),simulate())


if __name__=='__main__':
    unittest.main()
