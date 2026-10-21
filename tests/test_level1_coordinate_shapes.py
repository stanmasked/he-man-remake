"""Stage139: only fabricated maps, objects and shapes; no commercial IPA bytes."""
from __future__ import annotations

from dataclasses import replace
import json
import math
from pathlib import Path
import stat
import tempfile
import unittest
import warnings
from zipfile import ZipFile, ZipInfo

from heman_tools.level1_coordinate_shapes import (
    candidate_object_envelopes, aggregate_shape_links,
    audit_private_level1_geometry,
)
from heman_tools.objects import parse_level_objects
from heman_tools.tilemap import TileMap, parse_tilemap
from test_objects import example_level, example_object
from test_shapes import polygon, circle
from test_tilemap import sample, layer


def synthetic_objects():
    return parse_level_objects(example_level([
        example_object(name="FakeHero",x=32.0,y=32.0,
                       props=(("text", "string", "FriendlyName"),)),
        example_object(name="Outside",x=350.0,y=-2.0),
    ],name="MULevel1-1.lvl"))


def synthetic_map():
    return parse_tilemap(sample(layer(w=3,h=2)))


def fake_ipa(path: Path, *, shape_shift=False, map_shift=False,
             shape_symlink=False, extra=None):
    data=example_level([
        example_object(name="FakeHero",x=32.0,y=32.0),
        example_object(name="Outside",x=350.0,y=-2.0),
    ],name="MULevel1-1.lvl")
    grid=sample(layer(w=3,h=2))
    entries=[]
    for screen in ("screen-med","screen-xlarge"):
        prefix="Payload/MOTU.app/"+screen+"/"
        entries.extend([
            (prefix+"levels/MULevel1-1.lvl",data),
            (prefix+"maps/MUMap1-1.map",
             grid + b"DIFFERENT" if map_shift and screen=="screen-xlarge" else grid),
            (prefix+"geometry/FakeHero.shape",
             polygon(reference="DemoObject")
             if not shape_shift or screen=="screen-med" else circle(3)),
            (prefix+"geometry/Unused.shape",circle()),
        ])
    if extra:
        entries.extend(extra)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore",UserWarning)
        with ZipFile(path,"w") as z:
            for name,raw in entries:
                if shape_symlink and name.endswith("/screen-med/geometry/FakeHero.shape"):
                    info=ZipInfo(name)
                    info.create_system=3
                    info.external_attr=(stat.S_IFLNK|0o777)<<16
                    z.writestr(info,b"target.shape")
                else:
                    z.writestr(name,raw)


class Stage139CoordinateShapeTests(unittest.TestCase):
    def test_candidate_pixel_extent_not_claimed_as_verified_transform(self):
        report=candidate_object_envelopes(synthetic_objects(),synthetic_map())
        self.assertEqual(report["tile_grid_columns"],3)
        self.assertEqual(report["tile_grid_rows"],2)
        self.assertEqual(report["cell_width_units_as_serialized"],32)
        self.assertEqual(report["candidate_pixel_units_origin_zero"][
            "objects_within_candidate_extent"],1)
        self.assertEqual(report["candidate_direct_cell_indices_origin_zero"][
            "objects_within_candidate_extent"],0)
        self.assertFalse(report["object_to_collision_scale_verified"])
        self.assertFalse(report["automatically_usable_collision_geometry"])

    def test_left_and_top_boundaries_are_exclusive(self):
        parsed=parse_level_objects(example_level([
            example_object(x=0,y=0),
            example_object(x=96,y=0),
            example_object(x=95,y=64),
            example_object(x=95,y=63),
        ]))
        report=candidate_object_envelopes(parsed,synthetic_map())
        self.assertEqual(report["candidate_pixel_units_origin_zero"][
            "objects_within_candidate_extent"],2)
        self.assertEqual(report["candidate_pixel_units_origin_zero"]["outside_x_extent"],1)
        self.assertEqual(report["candidate_pixel_units_origin_zero"]["outside_y_extent"],1)

    def test_empty_object_table_rejected(self):
        empty=parse_level_objects(example_level([]))
        with self.assertRaisesRegex(ValueError,"empty"):
            candidate_object_envelopes(empty,synthetic_map())

    def test_invalid_nonfinite_transform_rejected(self):
        level=synthetic_objects()
        bad=replace(level,objects=(replace(level.objects[0],x=math.inf),))
        with self.assertRaisesRegex(ValueError,"Nonfinite"):
            candidate_object_envelopes(bad,synthetic_map())

    def test_source_layer_must_have_unique_collision(self):
        with self.assertRaises(KeyError):
            candidate_object_envelopes(synthetic_objects(),
                parse_tilemap(sample(layer(name="map"))))

    def test_lexical_shapes_do_not_prove_gameplay_owner(self):
        shapes=[
            ("FakeHero.shape", polygon(reference="DemoObject")),
            ("FriendlyName.shape",circle()),
            ("Unmatched.shape",circle()),
        ]
        result=aggregate_shape_links(synthetic_objects(),shapes)
        self.assertEqual(result["paired_shape_library_entries"],3)
        self.assertEqual(result["filename_stem_matching_level_object_identity"],1)
        self.assertEqual(result["filename_stem_matching_level_text_property"],1)
        self.assertEqual(result["embedded_reference_matching_level_object_identity"],1)
        self.assertFalse(result["original_shape_to_level_object_owner_verified"])
        self.assertNotIn("FakeHero",json.dumps(result))

    def test_duplicate_shape_name_rejected(self):
        with self.assertRaisesRegex(ValueError,"Duplicate"):
            aggregate_shape_links(synthetic_objects(),[
                ("Copy.shape",circle()),("Copy.shape",circle())])

    def test_invalid_shape_payload_rejected(self):
        with self.assertRaises(Exception):
            aggregate_shape_links(synthetic_objects(),[
                ("Bad.shape",b"not a shape")])

    def test_synthetic_dual_screen_ipa_integrates_local_source_readers(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"fictional.ipa"
            fake_ipa(path)
            result=audit_private_level1_geometry(path)
        self.assertTrue(result["shape_library_both_screens_byte_identical"])
        self.assertEqual(result["shape_to_object_textual_candidates"][
            "paired_shape_library_entries"],2)
        self.assertEqual(result["shape_to_object_textual_candidates"][
            "filename_stem_matching_level_object_identity"],1)
        self.assertFalse(result["original_game_coordinate_system_proven"])
        self.assertFalse(result["native_switch_world_geometry_import_authorized"])
        rendered=json.dumps(result)
        for item in ("FakeHero","Outside","DemoObject","Unused.shape",
                     "geometry/","collision_tile_ids","MULevel1-1.lvl"):
            self.assertNotIn(item,rendered)

    def test_different_shape_bytes_across_screens_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"fictional.ipa"
            fake_ipa(path,shape_shift=True)
            with self.assertRaisesRegex(ValueError,"differ in bytes"):
                audit_private_level1_geometry(path)

    def test_different_tilemap_bytes_across_screens_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"fictional.ipa"
            fake_ipa(path,map_shift=True)
            with self.assertRaisesRegex(ValueError,"level/map bytes differ"):
                audit_private_level1_geometry(path)

    def test_symlinked_source_shape_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"fictional.ipa"
            fake_ipa(path,shape_symlink=True)
            with self.assertRaisesRegex(ValueError,"unsafe"):
                audit_private_level1_geometry(path)

    def test_duplicate_zip_member_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"fictional.ipa"
            fake_ipa(path,extra=[(
                "Payload/MOTU.app/screen-med/geometry/Unused.shape",circle())])
            with self.assertRaisesRegex(ValueError,"Duplicate"):
                audit_private_level1_geometry(path)

    def test_missing_ipa_rejected(self):
        with self.assertRaisesRegex(ValueError,"Missing original local IPA"):
            audit_private_level1_geometry(Path("/not-there/private.ipa"))


if __name__ == "__main__":
    unittest.main()
