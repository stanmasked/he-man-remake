"""Stage151: all level, physics, shape and property values are invented."""
from __future__ import annotations

import json
from pathlib import Path
import stat
from tempfile import TemporaryDirectory
import unittest
import warnings
from zipfile import ZipFile, ZipInfo

from heman_tools.level1_shape_flag_properties import (
    summarize_level1_shape_flags_and_properties,
    audit_private_level1_shape_flags_and_properties,
)
from heman_tools.level_physics_shape_chains import FIRST_LEVEL
from test_objects import example_level
from test_level_map_links import map_object
from test_physics_records import fixture, record
from test_shapes import polygon, circle


QUAD = ((0,0),(3,0),(3,2),(0,2))


def fake_evidence():
    # Fake first level: six name-linked objects in two physics classes,
    # with five invented string properties and one prop-free record.
    level = example_level([
        map_object("FakeActorA",name="FakeInst1",
                   props=(("SourceTag","string","FakeStringOne"),)),
        map_object("FakeActorA",name="FakeInst2",
                   props=(("SourceTag","string","FakeStringTwo"),)),
        map_object("FakeActorA",name="FakeInst3",
                   props=(("SourceTag","string","FakeStringOne"),)),
        map_object("FakeActorA",name="FakeInst4",
                   props=(("SourceTag","string","FakeStringTwo"),)),
        map_object("FakeActorB",name="FakeInst5",
                   props=(("SourceTag","string","FakeStringTwo"),)),
        map_object("FakeActorB",name="FakeInst6"),
        # Not a linked class: typed string property and similar prefix
        # must NOT be promoted to evidence of physical resource ownership.
        map_object("FakeActorAExtra",name="FakeLookalike",
                   props=(("PhysicsHint","string","FakeActorA"),)),
    ],name=FIRST_LEVEL)
    physics = {
        "FakeActorA.ps2d": fixture([record(names=(
            "FakeQuad1","FakeQuad2","FakeQuad3","FakeQuad1"))]),
        "FakeActorB.pstruct2d": fixture([record(names=(
            "FakeQuad2","FakeQuad3","FakeQuad4"))]),
        "FakeUnlinked.ps2d": fixture([record(names=("FakeCircle",))]),
    }
    shape_blobs = {
        f"FakeQuad{i}.shape":polygon(QUAD,flags=1,
                                    reference="FakeRemoteAsset")
        for i in range(1,5)
    }
    shape_blobs["FakeUnrelatedQuad.shape"]=polygon(QUAD,flags=1)
    shape_blobs["FakeCircle.shape"]=circle(flags=0)
    return level,physics,shape_blobs


def fake_ipa(path, *, corrupt_peer=False, extras=()):
    level,physics,shapes=fake_evidence()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore",UserWarning)
        with ZipFile(path,"w") as z:
            for pack in ("screen-med","screen-xlarge"):
                root=f"Payload/MOTU.app/{pack}/"
                z.writestr(root+"levels/"+FIRST_LEVEL,level)
                for name,raw in physics.items():
                    if corrupt_peer and pack=="screen-xlarge" and name=="FakeActorA.ps2d":
                        raw=fixture([record(names=("FakeQuad1",))])
                    z.writestr(root+"physics_struct/"+name,raw)
                for name,raw in shapes.items():
                    z.writestr(root+"geometry/"+name,raw)
            for name,raw in extras:
                z.writestr(name,raw)


class Stage151LinkedShapesAndPropertiesTests(unittest.TestCase):
    def evaluate(self, level=None, physics=None, shapes=None):
        source=fake_evidence()
        return summarize_level1_shape_flags_and_properties(
            level if level is not None else source[0],
            physics if physics is not None else source[1],
            shapes if shapes is not None else source[2])

    def test_exact_first_level_shape_and_physics_chain_counts(self):
        report=self.evaluate()
        self.assertEqual(report["level1_total_objects"],7)
        self.assertEqual(report["level1_exact_class_name_matching_physics_instances"],6)
        self.assertEqual(report["level1_distinct_matched_physics_resources"],2)
        self.assertEqual(report["level1_physics_main_record_valid_shape_name_occurrences"],7)
        self.assertEqual(report["level1_distinct_validated_linked_shape_resources"],4)
        self.assertTrue(report["name_matched_class_physics_shape_chain_observed"])

    def test_four_linked_quads_with_flag_one(self):
        report=self.evaluate()
        self.assertEqual(report["level1_linked_polygon_shape_count"],4)
        self.assertEqual(report["level1_linked_circle_shape_count"],0)
        self.assertEqual(report["level1_linked_four_vertex_polygon_count"],4)
        self.assertEqual(report["level1_linked_shapes_with_flag_exactly_one"],4)
        self.assertEqual(report["level1_linked_four_vertex_polygons_with_flag_one"],4)

    def test_global_flag_one_quads_include_unrelated_control(self):
        report=self.evaluate()
        self.assertEqual(report["global_validated_shape_resources"],6)
        self.assertEqual(report["global_polygon_shape_count"],5)
        self.assertEqual(report["global_circle_shape_count"],1)
        self.assertEqual(report["global_four_vertex_polygons_with_flag_one"],5)
        self.assertFalse(report["original_flag_one_meaning_verified"])

    def test_five_string_properties_and_one_no_property(self):
        report=self.evaluate()
        self.assertEqual(report["level1_linked_objects_with_no_typed_properties"],1)
        self.assertEqual(report["level1_linked_objects_with_one_typed_property"],5)
        self.assertEqual(report["level1_linked_objects_with_multiple_typed_properties"],0)
        self.assertEqual(report["level1_linked_typed_string_property_count"],5)
        for kind in ("bool","int","float"):
            self.assertEqual(report[f"level1_linked_typed_{kind}_property_count"],0)

    def test_unlinked_property_with_physics_name_not_counted(self):
        report=self.evaluate()
        self.assertEqual(report["level1_linked_typed_string_values_matching_physics_stems"],0)
        self.assertEqual(report["level1_linked_typed_string_values_matching_shape_stems"],0)

    def test_embedded_shape_text_not_same_as_actor_identity(self):
        report=self.evaluate()
        self.assertEqual(report["level1_linked_shape_embedded_reference_nonempty"],4)
        self.assertEqual(report[
            "level1_linked_shape_embedded_reference_exact_object_identity_matches"],0)

    def test_all_linked_fictional_actors_have_identity_linear_transform(self):
        report=self.evaluate()
        self.assertEqual(report[
            "level1_linked_objects_with_identity_linear_affine_component"],6)

    def test_shape_with_different_flag_decreases_linked_flag_one_count(self):
        level,physics,shapes=fake_evidence()
        shapes["FakeQuad1.shape"]=polygon(QUAD,flags=4)
        result=self.evaluate(level,physics,shapes)
        self.assertEqual(result["level1_linked_shapes_with_flag_exactly_one"],3)
        self.assertFalse(result["original_flag_one_meaning_verified"])

    def test_shape_with_five_vertices_not_counted_as_quad(self):
        level,physics,shapes=fake_evidence()
        pentagon=QUAD+((1,3),)
        shapes["FakeQuad1.shape"]=polygon(pentagon,flags=1)
        result=self.evaluate(level,physics,shapes)
        self.assertEqual(result["level1_linked_four_vertex_polygon_count"],3)
        self.assertEqual(result["level1_linked_polygon_shape_count"],4)

    def test_linked_circle_counted_and_not_promoted_to_polygon(self):
        level,physics,shapes=fake_evidence()
        shapes["FakeQuad1.shape"]=circle(flags=1)
        result=self.evaluate(level,physics,shapes)
        self.assertEqual(result["level1_linked_polygon_shape_count"],3)
        self.assertEqual(result["level1_linked_circle_shape_count"],1)
        self.assertEqual(result["level1_linked_four_vertex_polygons_with_flag_one"],3)

    def test_embedded_reference_exact_identity_remains_only_metadata(self):
        level,physics,shapes=fake_evidence()
        shapes["FakeQuad1.shape"]=polygon(QUAD,flags=1,reference="FakeActorA")
        report=self.evaluate(level,physics,shapes)
        self.assertEqual(report[
            "level1_linked_shape_embedded_reference_exact_object_identity_matches"],1)
        self.assertFalse(report["original_shape_embedded_reference_runtime_role_verified"])

    def test_typed_string_exact_shape_name_still_not_runtime_binding(self):
        level,physics,shapes=fake_evidence()
        level=example_level([
            map_object("FakeActorA",props=(("SomeKey","string","FakeQuad1"),)),
            map_object("FakeActorB"),
        ],name=FIRST_LEVEL)
        report=self.evaluate(level,physics,shapes)
        self.assertEqual(report["level1_linked_typed_string_values_matching_shape_stems"],1)
        self.assertFalse(report["typed_string_property_runtime_physics_role_verified"])

    def test_typed_bool_int_float_counted_separately(self):
        level,physics,shapes=fake_evidence()
        level=example_level([
            map_object("FakeActorA",props=(
                ("Bool","bool",True),("Int","int",5),
                ("Float","float",2.5)))
        ],name=FIRST_LEVEL)
        report=self.evaluate(level,physics,shapes)
        self.assertEqual(report["level1_linked_objects_with_multiple_typed_properties"],1)
        self.assertEqual(report["level1_linked_typed_bool_property_count"],1)
        self.assertEqual(report["level1_linked_typed_int_property_count"],1)
        self.assertEqual(report["level1_linked_typed_float_property_count"],1)

    def test_no_exact_physics_class_match_does_not_infer_shape_chain(self):
        level,physics,shapes=fake_evidence()
        level=example_level([map_object("FakeActorAPlus")],name=FIRST_LEVEL)
        result=self.evaluate(level,physics,shapes)
        self.assertEqual(result["level1_exact_class_name_matching_physics_instances"],0)
        self.assertFalse(result["name_matched_class_physics_shape_chain_observed"])

    def test_missing_linked_shape_reduces_chain_without_fabrication(self):
        level,physics,shapes=fake_evidence()
        del shapes["FakeQuad4.shape"]
        result=self.evaluate(level,physics,shapes)
        self.assertEqual(result["level1_distinct_validated_linked_shape_resources"],3)
        self.assertEqual(result["level1_physics_main_record_valid_shape_name_occurrences"],6)

    def test_unsafe_or_duplicate_physics_stems_fail_closed(self):
        level,physics,shapes=fake_evidence()
        physics["FakeActorA.pstruct2d"]=physics["FakeActorA.ps2d"]
        with self.assertRaisesRegex(ValueError,"Ambiguous"):
            self.evaluate(level,physics,shapes)

    def test_corrupt_original_shape_or_physics_fails_closed(self):
        level,physics,shapes=fake_evidence()
        shapes["FakeQuad1.shape"]=b"invalid shape"
        with self.assertRaises(ValueError):
            self.evaluate(level,physics,shapes)
        level,physics,shapes=fake_evidence()
        physics["FakeActorA.ps2d"]=b"\xff"*20
        with self.assertRaises(ValueError):
            self.evaluate(level,physics,shapes)

    def test_wrong_first_level_identity_or_truncated_object_fails_closed(self):
        level,physics,shapes=fake_evidence()
        with self.assertRaisesRegex(ValueError,"first level"):
            self.evaluate(example_level([],name="Different.lvl"),physics,shapes)
        with self.assertRaises(ValueError):
            self.evaluate(level[:-6],physics,shapes)

    def test_reports_never_contain_original_like_resource_strings_or_coordinates(self):
        serialized=json.dumps(self.evaluate())
        for secret in ("FakeActorA","FakeActorB","FakeQuad1","FakeRemoteAsset",
                       "FakeStringOne","SourceTag","FakeInst1","shape_vertex",
                       "geometry/","levels/","physics_struct/"):
            self.assertNotIn(secret,serialized)
        result=json.loads(serialized)
        for key in ("original_collision_trigger_sensor_or_material_type_verified",
                    "original_player_hitbox_or_gameplay_fidelity_verified",
                    "automatic_switch_collision_import_permitted",
                    "original_object_names_values_vertices_coords_or_hashes_in_report"):
            self.assertFalse(result[key])

    def test_synthetic_paired_archive_end_to_end(self):
        with TemporaryDirectory() as directory:
            ipa=Path(directory)/"invented.ipa"
            fake_ipa(ipa)
            result=audit_private_level1_shape_flags_and_properties(ipa)
        self.assertEqual(result["level1_distinct_validated_linked_shape_resources"],4)

    def test_different_screen_pack_bytes_fail_closed(self):
        with TemporaryDirectory() as directory:
            ipa=Path(directory)/"invented.ipa"
            fake_ipa(ipa,corrupt_peer=True)
            with self.assertRaisesRegex(ValueError,"bytes differ"):
                audit_private_level1_shape_flags_and_properties(ipa)

    def test_duplicate_member_rejected(self):
        with TemporaryDirectory() as directory:
            ipa=Path(directory)/"invented.ipa"
            fake_ipa(ipa,extras=[(
                "Payload/MOTU.app/screen-med/geometry/FakeQuad1.shape",
                polygon(QUAD))])
            with self.assertRaisesRegex(ValueError,"Duplicate"):
                audit_private_level1_shape_flags_and_properties(ipa)

    def test_zip_symlinked_geometry_rejected(self):
        with TemporaryDirectory() as directory:
            ipa=Path(directory)/"invented.ipa"
            links=[]
            for pack in ("screen-med","screen-xlarge"):
                name=f"Payload/MOTU.app/{pack}/geometry/Link.shape"
                i=ZipInfo(name);i.create_system=3
                i.external_attr=(stat.S_IFLNK|0o777)<<16
                links.append((i,b"relative"))
            fake_ipa(ipa,extras=links)
            with self.assertRaisesRegex(ValueError,"unsafe selected"):
                audit_private_level1_shape_flags_and_properties(ipa)

    def test_missing_private_ipa_fails_closed(self):
        with self.assertRaisesRegex(ValueError,"Owner-private original IPA"):
            audit_private_level1_shape_flags_and_properties(
                Path("/not-present/original-game.ipa"))


if __name__=="__main__":
    unittest.main()
