"""Synthetic tests for multilayer .map. Never commit copied game bytes."""
import math
import struct
import unittest

from heman_tools.tilemap import parse_tilemap, TileMapFormatError


def txt(text):
    return struct.pack('<H',len(text)) + text.encode('utf-16le')


def layer(name='collision', *, w=3, h=2, ids=(1,2,65535,4,5,6),
          atlas=(0,0,255,0,0,0), atlases=('synthetic_atlas',),
          alpha=0.5, shown=0, ident=0, tilewh=(32,32,32,32)):
    assert len(ids) == len(atlas) == w*h
    return (struct.pack('<IBf',ident,shown,alpha) + txt(name)
            + struct.pack('<7I',*tilewh,w,h,len(atlases))
            + b''.join(txt(s) for s in atlases)
            + struct.pack('<'+str(w*h)+'H',*ids) + bytes(atlas))


def sample(*layers):
    return struct.pack('<I',len(layers) if layers else 1) + b''.join(layers or (layer(),))


class TilemapTests(unittest.TestCase):
    def test_single_layer(self):
        t = parse_tilemap(sample())
        self.assertEqual(t.layer('collision').columns,3)
        self.assertEqual(t.layer('collision').occupied_count,5)
        self.assertEqual(t.layer('collision').cell(1,0).tile_id,2)
        self.assertTrue(t.layer('collision').cell(2,0).empty)

    def test_three_layers(self):
        m = parse_tilemap(sample(layer('map'),layer(),layer('destructible')))
        self.assertEqual(tuple(l.name for l in m.layers),('map','collision','destructible'))

    def test_arrays_not_interleaved(self):
        x=layer(ids=(16,17,18,19,20,21),atlas=(0,1,0,1,0,1),atlases=('A','B'))
        l=parse_tilemap(sample(x)).layers[0]
        self.assertEqual((l.cell(0,1).tile_id,l.cell(0,1).atlas_id),(19,1))

    def test_stale_empty_atlas_ignored(self):
        l=parse_tilemap(sample(layer(ids=(65535,)*6,atlas=(0,255,1,255,0,255)))).layers[0]
        self.assertEqual(l.occupied_count,0)

    def test_occupied_bad_atlas(self):
        with self.assertRaises(TileMapFormatError):
            parse_tilemap(sample(layer(atlas=(9,0,255,0,0,0))))

    def test_bounds(self):
        l=parse_tilemap(sample()).layers[0]
        for x,y in [(-1,0),(3,0),(1,-1),(1,2)]:
            with self.assertRaises(IndexError): l.cell(x,y)

    def test_truncated(self):
        with self.assertRaises(TileMapFormatError): parse_tilemap(sample()[:-1])

    def test_unsupported_count(self):
        with self.assertRaises(TileMapFormatError): parse_tilemap(struct.pack('<I',32)+b'X'*40)

    def test_missing_atlas(self):
        with self.assertRaises(TileMapFormatError): parse_tilemap(sample(layer(atlases=())))

    def test_nan_opacity(self):
        with self.assertRaises(TileMapFormatError): parse_tilemap(sample(layer(alpha=math.nan)))

    def test_huge_cells(self):
        raw=sample()
        marker=struct.pack('<7I',32,32,32,32,3,2,1)
        self.assertIn(marker,raw)
        changed=raw.replace(marker,struct.pack('<7I',32,32,32,32,2**32-1,2**32-1,1))
        with self.assertRaises(TileMapFormatError): parse_tilemap(changed)

    def test_extra_data(self):
        with self.assertRaises(TileMapFormatError): parse_tilemap(sample()+b'ignored')

    def test_invalid_utf16(self):
        changed=sample().replace('collision'.encode('utf-16le'),b'\x00\xd8'+'ollision'.encode('utf-16le'))
        with self.assertRaises(TileMapFormatError): parse_tilemap(changed)

    def test_bad_visibility(self):
        b=bytearray(sample());b[8]=2
        with self.assertRaises(TileMapFormatError): parse_tilemap(bytes(b))

    def test_background_not_collision(self):
        with self.assertRaises(KeyError):
            parse_tilemap(sample(layer(name='background'))).layer('collision')


if __name__ == '__main__':
    unittest.main()
