from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import zipfile

from heman_tools.shape_scan import audit_shapes
from heman_tools.lvl import LevelFormatError
from test_shapes import polygon, circle


class ShapeScanTests(unittest.TestCase):
    def test_scan_in_memory_fixture(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp)/'synthetic.ipa'
            with zipfile.ZipFile(path, 'w') as archive:
                archive.writestr('Payload/MOTU.app/screen-med/geometry/fixture_a.shape', polygon())
                archive.writestr('Payload/MOTU.app/screen-med/geometry/fixture_b.shape', circle(reference='link'))
                archive.writestr('Payload/MOTU.app/screen-xlarge/geometry/fixture_a.shape', polygon())
            med = audit_shapes(path)
            xl = audit_shapes(path, 'screen-xlarge')
            self.assertEqual((med['total'], med['polygons'], med['circles'], med['referenced']), (2,1,1,1))
            self.assertEqual(xl['total'], 1)

    def test_reject_bad_screen(self):
        with self.assertRaises(ValueError):
            audit_shapes(Path('unused'), '../../unsafe')

    def test_reject_bad_shape(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp)/'synthetic.ipa'
            with zipfile.ZipFile(path,'w') as archive:
                archive.writestr('Payload/MOTU.app/screen-med/geometry/fixture.shape', b'broken')
            with self.assertRaises(LevelFormatError):
                audit_shapes(path)


if __name__ == '__main__':
    unittest.main()
