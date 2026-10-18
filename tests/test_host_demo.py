"""Tests for the host app that never require Tkinter, Pillow or source assets."""
import unittest

from heman_tools.host_demo import _mask_rects, headless_replay, load_private_world
from heman_tools.mask_physics import CollisionMask
from heman_tools.scene import synthetic_world


class HostDemoTests(unittest.TestCase):
    def test_headless_is_deterministic(self):
        w = synthetic_world()
        self.assertEqual(headless_replay(w,110),headless_replay(w,110))
        self.assertEqual(headless_replay(w,110)['frames'],110)

    def test_invalid_replay_ticks(self):
        for count in (0,-1,3601):
            with self.assertRaises(ValueError):
                headless_replay(synthetic_world(),count)

    def test_rectangles_coalesce_solid_pixels(self):
        mask=CollisionMask(2,(3,3))
        self.assertEqual(_mask_rects(mask),((0,0,2,2),))

    def test_mask_rectangles_preserve_diagonal_holes(self):
        mask=CollisionMask(3,(0b001,0b011,0b111))
        area=sum((x1-x0)*(y1-y0) for x0,y0,x1,y1 in _mask_rects(mask))
        self.assertEqual(area,6)

    def test_private_map_path_traversal_rejected(self):
        with self.assertRaises(ValueError):
            load_private_world(None,'../private.map')

    def test_headless_without_gui_or_image_dependencies(self):
        result=headless_replay(synthetic_world(),2)
        self.assertEqual(result['frames'],2)
        self.assertIn('Host physics',result['disclaimer'])


if __name__=='__main__':
    unittest.main()
