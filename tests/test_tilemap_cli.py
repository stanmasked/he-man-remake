"""Synthetic-only local IPA CLI tests."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import zipfile

from heman_tools.tilemap_cli import inspect_map
from heman_tools.tilemap import TileMapFormatError
from test_tilemap import sample


class TilemapCliTests(unittest.TestCase):
    def test_local_archive(self):
        with TemporaryDirectory() as folder:
            path=Path(folder)/'fake.ipa'
            with zipfile.ZipFile(path,'w') as a:
                a.writestr('Payload/MOTU.app/screen-med/maps/Synthetic.map', sample())
            report=inspect_map(path,'Synthetic.map')
            self.assertEqual(report['layers'][0]['occupied_cells'],5)
            self.assertEqual(report['layers'][0]['name'],'collision')
            self.assertIn('NOT yet verified',report['disclaimer'])

    def test_path_traversal(self):
        with self.assertRaises(ValueError): inspect_map(Path('unused'),'../private.map')
        with self.assertRaises(ValueError): inspect_map(Path('unused'),'..\\private.map')

    def test_bad_screen(self):
        with self.assertRaises(ValueError): inspect_map(Path('unused'),'Synthetic.map','../../outside')

    def test_corrupt_archive_entry(self):
        with TemporaryDirectory() as folder:
            path=Path(folder)/'fake.ipa'
            with zipfile.ZipFile(path,'w') as a:
                a.writestr('Payload/MOTU.app/screen-med/maps/Synthetic.map',b'not a map')
            with self.assertRaises(TileMapFormatError): inspect_map(path,'Synthetic.map')


if __name__ == '__main__':
    unittest.main()
