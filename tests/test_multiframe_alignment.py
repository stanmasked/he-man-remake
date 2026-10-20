"""Public synthetic-only multi-frame camera/scale consistency tests."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from heman_tools.multiframe_alignment import compare_stationary_frames, main


def frames():
    pts = [(0, 0), (10, 5), (40, 25), (90, 55), (20, 50)]
    return {'frames': [
        {'frame_id': f'synthetic-{idx}', 'anchors': [
            {'id': f'landmark-{i}', 'level_xy': [x, y],
             'screen_xy': [2*x + dx, -3*y + dy]}
            for i,(x,y) in enumerate(pts)]}
        for idx,(dx,dy) in enumerate(((10,20), (40,-5), (-12,200)))]}


class MultiFrameTests(unittest.TestCase):
    def test_same_scale_variable_camera_translation(self):
        result = compare_stationary_frames(frames())
        self.assertEqual(result['frame_offsets_px'], [[10, 20], [40, -5], [-12, 200]])
        self.assertEqual(result['reference_scale'], [2, -3])
        self.assertEqual(result['max_relative_scale_drift'], 0)
        self.assertFalse(result['authentic_camera_behavior_proven'])
        self.assertFalse(result['physical_units_verified'])

    def test_order_of_landmarks_does_not_matter(self):
        data = frames()
        data['frames'][1]['anchors'].reverse()
        self.assertTrue(compare_stationary_frames(data)['consistent_under_axis_aligned_hypothesis'])

    def test_changed_scale_rejected(self):
        data = frames()
        for p in data['frames'][1]['anchors']:
            x, y = p['level_xy']
            p['screen_xy'] = [3*x + 40, -3*y - 5]
        with self.assertRaisesRegex(ValueError, 'scale drift'):
            compare_stationary_frames(data)

    def test_axis_flip_rejected(self):
        data = frames()
        for p in data['frames'][1]['anchors']:
            x, y = p['level_xy']
            p['screen_xy'] = [-2*x+40, -3*y-5]
        with self.assertRaisesRegex(ValueError, 'scale drift'):
            compare_stationary_frames(data)

    def test_one_frame_missing_landmark(self):
        data = frames()
        data['frames'][1]['anchors'].pop()
        with self.assertRaisesRegex(ValueError, 'landmark IDs'):
            compare_stationary_frames(data)

    def test_relabelled_landmark_rejected(self):
        data = frames()
        data['frames'][1]['anchors'][0]['id'] = 'different'
        with self.assertRaisesRegex(ValueError, 'landmark IDs'):
            compare_stationary_frames(data)

    def test_same_id_different_level_coordinate(self):
        data = frames()
        data['frames'][2]['anchors'][1]['level_xy'][0] += 1
        with self.assertRaisesRegex(ValueError, 'landmark IDs'):
            compare_stationary_frames(data)

    def test_duplicate_frame_id(self):
        data = frames()
        data['frames'][1]['frame_id'] = data['frames'][0]['frame_id']
        with self.assertRaisesRegex(ValueError, 'duplicate frame'):
            compare_stationary_frames(data)

    def test_single_frame_is_not_cross_frame_proof(self):
        data = frames()
        data['frames'] = data['frames'][:1]
        with self.assertRaisesRegex(ValueError, '2–32'):
            compare_stationary_frames(data)

    def test_per_frame_rotation_rejected(self):
        data = frames()
        for p in data['frames'][2]['anchors']:
            x, y = p['level_xy']
            p['screen_xy'] = [x-y-12, x+y+200]
        with self.assertRaisesRegex(ValueError, 'residual'):
            compare_stationary_frames(data)

    def test_small_noise_tolerated(self):
        data = frames()
        data['frames'][2]['anchors'][0]['screen_xy'][0] += .25
        self.assertLess(compare_stationary_frames(data)['max_relative_scale_drift'], .02)

    def test_large_noise_rejected(self):
        data = frames()
        data['frames'][0]['anchors'][0]['screen_xy'][1] += 30
        with self.assertRaisesRegex(ValueError, 'residual'):
            compare_stationary_frames(data)

    def test_invalid_scale_tolerance_rejected(self):
        for value in (-1, 0, 0.5, True, float('nan')):
            with self.subTest(value=value), self.assertRaises(ValueError):
                compare_stationary_frames(frames(), max_relative_scale_drift=value)

    def test_cli_reports_only_private_summary(self):
        with TemporaryDirectory() as tmp:
            with patch('heman_tools.frame_alignment.Path.cwd', return_value=Path(tmp)):
                local = Path(tmp)/'local_reports'
                local.mkdir()
                inp, out = local/'input.json', local/'result.json'
                inp.write_text(json.dumps(frames()), encoding='utf-8')
                self.assertEqual(main(['--frames',str(inp),'--out',str(out)]), 0)
                result = json.loads(out.read_text(encoding='utf-8'))
                self.assertEqual(result['stationary_anchor_count'],5)
                self.assertNotIn('anchors',result)
                self.assertNotIn('screen_xy',json.dumps(result))

    def test_input_output_cannot_be_same(self):
        with TemporaryDirectory() as tmp:
            with patch('heman_tools.frame_alignment.Path.cwd', return_value=Path(tmp)):
                root = Path(tmp)/'local_reports'
                root.mkdir()
                path = root/'a.json'
                path.write_text(json.dumps(frames()),encoding='utf-8')
                with self.assertRaisesRegex(ValueError,'not be the same'):
                    main(['--frames',str(path),'--out',str(path)])


if __name__ == '__main__':
    unittest.main()
