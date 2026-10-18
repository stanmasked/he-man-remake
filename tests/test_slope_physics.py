"""Synthetic-only slope tests; no original tiles or game assets."""
import math
import unittest

from heman_tools.body_physics import Body, BodyConfig, overlaps_body
from heman_tools.mask_physics import CollisionMask, MaskedGrid, EMPTY
from heman_tools.slope_physics import SlopeConfig, step_body_slopes


def full(n=16):
    return CollisionMask(n, tuple([(1 << n) - 1] * n))


def uphill(n=16):
    return CollisionMask.from_alpha([
        [255 if row >= n - column - 1 else 0 for column in range(n)]
        for row in range(n)
    ])


def slope_world():
    return MaskedGrid(2, 2, 16, (6, 5, EMPTY, EMPTY),
                      {6: uphill(), 5: full()})


CFG = BodyConfig(half_width=0.4, height=5, horizontal_speed=60)
SLOPE = SlopeConfig(max_rise=3, max_drop=3)


class SlopePhysicsTests(unittest.TestCase):
    def test_walk_up_slope(self):
        grid = slope_world()
        actor = Body(2, 13, grounded=True)
        feet = []
        for _ in range(10):
            actor = step_body_slopes(actor, grid, 1, False, 1/60, CFG, SLOPE)
            feet.append(actor.feet_y)
            self.assertTrue(actor.grounded)
            self.assertFalse(overlaps_body(grid, actor.x, actor.feet_y, CFG.half_width, CFG.height))
        self.assertGreater(actor.x, 2)
        self.assertLess(actor.feet_y, 13)
        self.assertTrue(all(b <= a + 0.01 for a,b in zip(feet,feet[1:])))

    def test_walk_down_slope(self):
        grid = slope_world()
        actor = Body(12, 3, grounded=True)
        for _ in range(8):
            actor = step_body_slopes(actor, grid, -1, False, 1/60, CFG, SLOPE)
            self.assertTrue(actor.grounded)
        self.assertLess(actor.x, 12)
        self.assertGreater(actor.feet_y, 3)

    def test_full_wall_not_climbed(self):
        grid = MaskedGrid(2, 2, 16, (EMPTY,5,5,5), {5:full()})
        actor = Body(13,16,grounded=True)
        for _ in range(10):
            actor = step_body_slopes(actor,grid,1,False,1/60,CFG,SLOPE)
        self.assertLessEqual(actor.x+CFG.half_width,16.001)
        self.assertTrue(actor.wall_hit)

    def test_small_step_up_can_climb_with_clearance(self):
        n = 16
        step_mask = CollisionMask(n, tuple([0]*14 + [(1<<n)-1]*2))
        grid = MaskedGrid(2,2,n,(EMPTY,7,5,5),{7:step_mask,5:full()})
        actor = Body(14,16,grounded=True)
        for _ in range(6):
            actor = step_body_slopes(actor,grid,1,False,1/60,CFG,SLOPE)
        self.assertGreater(actor.x,16)
        self.assertLess(actor.feet_y,16)
        self.assertTrue(actor.grounded)

    def test_ceiling_prevents_lift(self):
        n = 16
        mask = uphill()
        rows = list(mask.rows)
        rows[5] = (1<<n)-1
        grid = MaskedGrid(1,1,n,(6,),{6:CollisionMask(n,tuple(rows))})
        actor = Body(2,13,grounded=True)
        new = step_body_slopes(actor,grid,1,False,1/60,CFG,SLOPE)
        self.assertLess(new.x,3.001)
        self.assertFalse(overlaps_body(grid,new.x,new.feet_y,CFG.half_width,CFG.height))

    def test_step_off_edge_resumes_gravity(self):
        grid = MaskedGrid(2,2,16,(EMPTY,EMPTY,5,EMPTY),{5:full()})
        actor = Body(12,16,grounded=True)
        for _ in range(14):
            actor = step_body_slopes(actor,grid,1,False,1/60,CFG,SLOPE)
        self.assertFalse(actor.grounded)
        self.assertGreater(actor.feet_y,16)

    def test_jump_does_not_snap_to_slope(self):
        actor = step_body_slopes(Body(2,13,grounded=True),slope_world(),0,True,1/60,CFG,SLOPE)
        self.assertFalse(actor.grounded)
        self.assertLess(actor.feet_y,13)

    def test_airborne_does_not_teleport_to_slope(self):
        actor = step_body_slopes(Body(2,-10),slope_world(),1,False,1/60,CFG,SLOPE)
        self.assertFalse(actor.grounded)
        self.assertGreater(actor.feet_y,-10)

    def test_zero_axis_grounded(self):
        actor = step_body_slopes(Body(2,13,grounded=True),slope_world(),0,False,1/60,CFG,SLOPE)
        self.assertTrue(actor.grounded)
        self.assertAlmostEqual(actor.feet_y,13,delta=.01)

    def test_bad_slope_limits(self):
        for s in (SlopeConfig(-1,2),SlopeConfig(33,2),SlopeConfig(2,33)):
            with self.assertRaises(ValueError):
                step_body_slopes(Body(2,13,grounded=True),slope_world(),1,False,1/60,CFG,s)

    def test_nonfinite_rejected(self):
        with self.assertRaises(ValueError):
            step_body_slopes(Body(math.nan,13),slope_world(),1,False,1/60,CFG,SLOPE)

    def test_oversized_motion_rejected(self):
        with self.assertRaises(ValueError):
            step_body_slopes(Body(2,13,grounded=True),slope_world(),1,False,1/30,
                             BodyConfig(half_width=.4,height=5,horizontal_speed=30000),SLOPE)

    def test_repeatability(self):
        def run():
            a = Body(2,13,grounded=True)
            for tick in range(20):
                a = step_body_slopes(a,slope_world(),1 if tick<10 else -1,False,1/60,CFG,SLOPE)
            return a
        self.assertEqual(run(),run())


if __name__ == '__main__':
    unittest.main()
