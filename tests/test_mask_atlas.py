import unittest
from heman_tools.mask_atlas import extract_masks_from_alpha

class AtlasExtractionTests(unittest.TestCase):
    def test_two_by_one_tile_atlas(self):
        # Two tiles, 2x2; one square and one diagonal.
        data = bytes([255, 255, 0, 255,
                      255, 255, 255, 255])
        m = extract_masks_from_alpha(4, 2, data, 2, {0, 1})
        self.assertEqual(sum(v.bit_count() for v in m[0].rows), 4)
        self.assertEqual(sum(v.bit_count() for v in m[1].rows), 3)
        self.assertFalse(m[1].solid(0, 0))
        self.assertTrue(m[1].solid(0, 1))

    def test_bad_index(self):
        with self.assertRaises(ValueError):
            extract_masks_from_alpha(4, 2, bytes(8), 2, {2})

    def test_bad_dimensions(self):
        with self.assertRaises(ValueError):
            extract_masks_from_alpha(3, 2, bytes(6), 2, {0})

    def test_bad_alpha_length(self):
        with self.assertRaises(ValueError):
            extract_masks_from_alpha(4, 2, b'abc', 2, {0})

if __name__=='__main__': unittest.main()
