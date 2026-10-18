"""Entirely synthetic mask fixtures; no game assets committed."""
import math
import unittest

from heman_tools.mask_physics import (
    Actor, CollisionMask, MaskedGrid, PhysicsConfig, step_actor, EMPTY,
)


def full(size=16):
    return CollisionMask(size, tuple(((1 << size) - 1) for _ in range(size)))


def slope(size=16):
    return CollisionMask.from_alpha([[255 if y >= size - x - 1 else 0
                                      for x in range(size)] for y in range(size)])


def flat_world():
    return MaskedGrid(5, 3, 16, (EMPTY,)*10 + (5,)*5, {5: full()})


class PrototypePhysicsTests(unittest.TestCase):
    def test_mask_from_alpha_and_edge_threshold(self):
        m = CollisionMask.from_alpha([[0, 127],[128, 255]])
        self.assertFalse(m.solid(1, 0))
        self.assertTrue(m.solid(0, 1))
        self.assertTrue(m.solid(1, 1))

    def test_shape_validation(self):
        with self.assertRaises(ValueError): CollisionMask(2, (4, 0))
        with self.assertRaises(ValueError): CollisionMask.from_alpha([[255, 0]])

    def test_empty_cell_even_with_mask(self):
        g = flat_world()
        self.assertFalse(g.solid_at(1, 5))
        self.assertTrue(g.solid_at(1, 32))
        self.assertFalse(g.solid_at(-1, 35))

    def test_missing_profile_fails_closed(self):
        with self.assertRaises(ValueError): MaskedGrid(1,1,16,(3,),{5: full()})

    def test_scan_first_contact(self):
        self.assertEqual(flat_world().first_feet_contact(12, 4, 0, 45), 32)

    def test_scan_edges_and_no_contact(self):
        self.assertIsNone(flat_world().first_feet_contact(12, 2, 0, 30))
        self.assertEqual(flat_world().first_feet_contact(12, 2, 30, 60), 32)

    def test_drop_and_land(self):
        actor = Actor(x=18, feet_y=0)
        for _ in range(180):
            actor = step_actor(actor, flat_world(), 0, False, 1/60)
        self.assertTrue(actor.grounded)
        self.assertEqual(actor.feet_y, 32)
        self.assertEqual(actor.vertical_speed, 0)

    def test_jump_then_land(self):
        actor = Actor(x=18, feet_y=32, grounded=True)
        actor = step_actor(actor, flat_world(), 0, True, 1/60)
        self.assertFalse(actor.grounded)
        self.assertLess(actor.feet_y, 32)
        for _ in range(180):
            actor = step_actor(actor, flat_world(), 0, False, 1/60)
        self.assertTrue(actor.grounded)
        self.assertEqual(actor.feet_y, 32)

    def test_flat_walk(self):
        actor = Actor(x=20, feet_y=32, grounded=True)
        for _ in range(10):
            actor = step_actor(actor, flat_world(), 1, False, 1/60)
        self.assertTrue(actor.grounded)
        self.assertGreater(actor.x, 20)
        self.assertEqual(actor.feet_y, 32)

    def test_step_off_edge_falls(self):
        g = MaskedGrid(2,3,16,(EMPTY,)*4 + (5,EMPTY),{5:full()})
        actor = Actor(x=12, feet_y=32, grounded=True)
        for _ in range(15):
            actor = step_actor(actor, g, 1, False, 1/60)
        self.assertFalse(actor.grounded)
        self.assertGreater(actor.feet_y, 32)

    def test_slope_columns(self):
        g = MaskedGrid(1,1,16,(6,),{6:slope()})
        self.assertEqual(g.first_feet_contact(0,0,0,16),15)
        self.assertEqual(g.first_feet_contact(15,0,0,16),0)

    def test_slope_step_up(self):
        g = MaskedGrid(1,1,16,(6,),{6:slope()})
        actor = Actor(3,12,grounded=True)
        actor = step_actor(actor,g,1,False,1/60,PhysicsConfig(horizontal_speed=60,half_width=0))
        self.assertTrue(actor.grounded)
        self.assertLess(actor.feet_y,12)

    def test_finite_checks(self):
        with self.assertRaises(ValueError): step_actor(Actor(0,0),flat_world(),float('nan'),False,1/60)
        with self.assertRaises(ValueError): step_actor(Actor(0,0),flat_world(),0,False,1/10)
        with self.assertRaises(ValueError): flat_world().first_feet_contact(float('inf'),0,0,1)

    def test_no_phantom_floor(self):
        g=MaskedGrid(1,1,16,(EMPTY,),{5:full()})
        a=Actor(8,0)
        for _ in range(15): a=step_actor(a,g,0,False,1/60)
        self.assertFalse(a.grounded)
        self.assertGreater(a.feet_y,0)


if __name__ == '__main__': unittest.main()
