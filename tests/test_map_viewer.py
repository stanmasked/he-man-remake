"""Asset-free tests for schematic diagram renderer."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import xml.etree.ElementTree as ET
import zipfile

from heman_tools.map_viewer import category, render_level_svg
from heman_tools.objects import parse_level_objects
from heman_tools.waypoints import parse_waypoints
from heman_tools.viewer_cli import render_ipa
from test_waypoints import synthetic_level
from test_objects import example_level, example_object


class MapViewerTests(unittest.TestCase):
    def setUp(self):
        raw = synthetic_level()
        self.level = parse_level_objects(raw)
        self.graph = parse_waypoints(raw)

    def test_svg_valid_xml(self):
        tree = ET.fromstring(render_level_svg(self.level, self.graph))
        self.assertTrue(tree.tag.endswith('svg'))

    def test_coordinates_and_points(self):
        text = render_level_svg(self.level, self.graph)
        self.assertIn('Synthetic.lvl', text)
        self.assertIn('named points', text)
        self.assertIn('synthetic_path', text)
        self.assertIn('DemoObject', text)

    def test_absence_of_script_embedded_media(self):
        text = render_level_svg(self.level, self.graph)
        self.assertNotIn('<script', text)
        self.assertNotIn('<image', text)
        self.assertNotIn('foreignObject', text)
        self.assertNotIn('https://', text)

    def test_xml_escaping_of_game_metadata(self):
        raw = example_level([example_object(name='AT&T <script>"')])
        text = render_level_svg(parse_level_objects(raw), parse_waypoints(raw))
        ET.fromstring(text)
        self.assertIn('AT&amp;T &lt;script&gt;', text)

    def test_zoom_bounds(self):
        text = render_level_svg(self.level, self.graph, min_x=0, max_x=50)
        self.assertIn('X 0…50', text)

    def test_inverted_view_error(self):
        with self.assertRaises(ValueError):
            render_level_svg(self.level, self.graph, min_x=100, max_x=100)

    def test_small_canvas_error(self):
        with self.assertRaises(ValueError):
            render_level_svg(self.level, self.graph, width=200)

    def test_category(self):
        self.assertEqual(category('MUEnemyHoverBot'), 'enemy')
        self.assertEqual(category('MUDoor'), 'door')
        self.assertEqual(category('LevelTileMap'), 'terrain')
        self.assertEqual(category('ProximityScriptTrigger'), 'trigger')

    def test_mismatch_error(self):
        raw = example_level(name='Other.lvl')
        with self.assertRaises(ValueError):
            render_level_svg(parse_level_objects(raw), self.graph)

    def test_local_archive_render(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / 'test.ipa'
            with zipfile.ZipFile(path, 'w') as archive:
                archive.writestr('Payload/MOTU.app/screen-med/levels/Synthetic.lvl', synthetic_level())
            self.assertIn('<svg', render_ipa(path, 'Synthetic.lvl'))

    def test_reject_traversal(self):
        with self.assertRaises(ValueError):
            render_ipa(Path('/nonexistent/ipa'), '../path.lvl')


if __name__ == '__main__':
    unittest.main()
