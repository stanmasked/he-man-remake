"""Stage150: all level, physics and shape bytes are wholly invented fixtures."""
from __future__ import annotations

import json
from pathlib import Path
import stat
from tempfile import TemporaryDirectory
import unittest
import warnings
from zipfile import ZipFile, ZipInfo

from heman_tools.level_physics_shape_chains import (
    FIRST_LEVEL, summarize_level_physics_shape_chains,
    audit_private_level_physics_shape_chains,
)
from test_objects import example_level, example_object
from test_level_map_links import map_object
from test_physics_records import fixture, record
from test_shapes import circle, polygon


def fake_resources():
    levels = {
        FIRST_LEVEL: example_level([
            map_object("DemoActor",name="a"),
            map_object("DemoActor",name="b"),
            map_object("DemoActorExtra",name="lookalike",
                       props=(("fake_physics", "string","DemoActor"),)),
        ],name=FIRST_LEVEL),
        "SyntheticTwo.lvl":example_level([
            map_object("OtherActor",name="c"),
            map_object("NoResource",name="d"),
        ],name="SyntheticTwo.lvl")
    }
    physics = {
        "DemoActor.ps2d":fixture([record(names=("FauxCircle","FauxPoly"))]),
        "OtherActor.pstruct2d":fixture([record(names=("FauxPoly",))]),
        "Unused.ps2d":fixture([record(names=("NotAShape",))]),
    }
    shapes = {
        "FauxCircle.shape":circle(),
        "FauxPoly.shape":polygon(),
        "Unused.shape":circle(),
    }
    return levels,physics,shapes


def synthetic_zip(path, *, divergent=False, extra=()):
    levels,physics,shapes=fake_resources()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore",UserWarning)
        with ZipFile(path,"w") as z:
            for pack in ("screen-med","screen-xlarge"):
                prefix=f"Payload/MOTU.app/{pack}/"
                for name,raw in levels.items():
                    z.writestr(prefix+"levels/"+name,raw)
                for name,raw in physics.items():
                    if divergent and pack=="screen-xlarge" and name=="DemoActor.ps2d":
                        raw=fixture([record(names=("FauxCircle",))])
                    z.writestr(prefix+"physics_struct/"+name,raw)
                for name,raw in shapes.items():
                    z.writestr(prefix+"geometry/"+name,raw)
            for name,raw in extra:
                z.writestr(name,raw)


class Stage150ExactResourceChainContract(unittest.TestCase):
    def evaluate(self,levels=None,physics=None,shapes=None):
        base=fake_resources()
        return summarize_level_physics_shape_chains(
            levels if levels is not None else base[0],
            physics if physics is not None else base[1],
            shapes if shapes is not None else base[2],
        )

    def test_full_synthetic_two_level_chain_count(self):
        result=self.evaluate()
        self.assertEqual(result["paired_original_levels_examined"],2)
        self.assertEqual(result["original_level_object_instances_decoded"],5)
        self.assertEqual(result["levels_with_exact_class_name_physics_resource_stem"],2)
        self.assertEqual(result["level_objects_with_exact_class_name_physics_resource_stem"],3)
        self.assertEqual(result["distinct_matched_physics_resource_stems"],2)
        self.assertEqual(result["level_objects_with_complete_class_physics_shape_name_chain"],3)
        self.assertEqual(result["matched_physics_main_record_shape_name_occurrences"],3)
        self.assertEqual(result["distinct_validated_shape_names_referenced_in_chains"],2)

    def test_first_level_has_independent_resource_chain_census(self):
        first=self.evaluate()["first_level"]
        self.assertEqual(first["source_objects"],3)
        self.assertEqual(first["objects_with_exact_class_name_physics_resource_stem"],2)
        self.assertEqual(first["distinct_matching_physics_resources"],1)
        self.assertEqual(first["validated_shape_name_reference_occurrences"],2)
        self.assertEqual(first["distinct_shape_names_in_completed_local_chains"],2)

    def test_property_string_is_not_mistaken_for_class_name(self):
        report=self.evaluate()
        # Third first-level object has a typed property value "DemoActor",
        # but its class is "DemoActorExtra" and must NOT link.
        self.assertEqual(report["first_level"][
            "objects_with_exact_class_name_physics_resource_stem"],2)

    def test_fuzzy_prefix_class_names_do_not_match(self):
        l,p,s=fake_resources()
        l[FIRST_LEVEL]=example_level([map_object("DemoActorExtended")],
                                     name=FIRST_LEVEL)
        result=self.evaluate(l,p,s)
        self.assertEqual(result["first_level"][
            "objects_with_exact_class_name_physics_resource_stem"],0)

    def test_shape_name_matching_must_be_complete(self):
        levels,physics,shapes=fake_resources()
        del shapes["FauxCircle.shape"]
        result=self.evaluate(levels,physics,shapes)
        self.assertEqual(result["matched_physics_main_record_shape_name_occurrences"],2)
        self.assertEqual(result["distinct_validated_shape_names_referenced_in_chains"],1)

    def test_missing_shape_does_not_claim_completed_chain(self):
        l,p,s=fake_resources()
        s.clear();s["TotallyDifferent.shape"]=circle()
        report=self.evaluate(l,p,s)
        self.assertEqual(report["level_objects_with_exact_class_name_physics_resource_stem"],3)
        self.assertEqual(report["level_objects_with_complete_class_physics_shape_name_chain"],0)
        self.assertEqual(report["physics_resources_with_at_least_one_valid_shape_name_match"],0)

    def test_never_assume_game_runtime_physics_from_text_equalities(self):
        result=self.evaluate()
        self.assertTrue(result["class_name_and_shape_name_exact_matches_are_verified"])
        for field in (
            "game_engine_runtime_resource_bindings_verified",
            "original_collision_body_shape_ownership_verified",
            "player_hitbox_sensors_materials_or_physics_verified",
            "original_ios_to_switch_gameplay_parity_verified",
            "safe_for_automatic_original_collision_import",
            "original_names_coordinates_shapes_pixels_or_hashes_in_output",
        ):
            self.assertFalse(result[field])

    def test_only_aggregate_names_not_original_ids_or_coords(self):
        text=json.dumps(self.evaluate())
        for secret in (
            "DemoActor","OtherActor","FauxCircle","FauxPoly",
            "SyntheticTwo","lookalike","fake_physics","NotAShape",
            "0.0,","geometry/","levels/","physics_struct/"
        ):
            self.assertNotIn(secret,text)

    def test_unused_physics_and_unused_shape_are_not_linked(self):
        result=self.evaluate()
        self.assertEqual(result["paired_original_physics_resources_examined"],3)
        self.assertEqual(result["paired_original_shape_resources_validated"],3)
        self.assertEqual(result["distinct_matched_physics_resource_stems"],2)
        self.assertEqual(result["distinct_validated_shape_names_referenced_in_chains"],2)

    def test_ambiguous_physics_stems_with_different_extensions_rejected(self):
        levels,physics,shapes=fake_resources()
        physics["DemoActor.pstruct2d"]=physics["DemoActor.ps2d"]
        with self.assertRaisesRegex(ValueError,"Ambiguous"):
            self.evaluate(levels,physics,shapes)

    def test_corrupt_physics_envelope_rejected_before_shape_match(self):
        l,p,s=fake_resources()
        p["DemoActor.ps2d"]=b"\xff"*80
        with self.assertRaises(ValueError):
            self.evaluate(l,p,s)

    def test_corrupt_shape_geometry_rejected_before_links(self):
        l,p,s=fake_resources()
        s["FauxCircle.shape"]=b"not a valid original format"
        with self.assertRaises(ValueError):
            self.evaluate(l,p,s)

    def test_bad_level_embedded_name_fails_closed(self):
        l,p,s=fake_resources()
        l[FIRST_LEVEL]=example_level([example_object()],name="Wrong.lvl")
        with self.assertRaisesRegex(ValueError,"embedded name"):
            self.evaluate(l,p,s)

    def test_bad_level_object_record_fails_closed(self):
        l,p,s=fake_resources()
        l[FIRST_LEVEL]=l[FIRST_LEVEL][:-8]
        with self.assertRaises(ValueError):
            self.evaluate(l,p,s)

    def test_missing_first_level_rejected(self):
        l,p,s=fake_resources()
        del l[FIRST_LEVEL]
        with self.assertRaisesRegex(ValueError,"first level"):
            self.evaluate(l,p,s)

    def test_empty_or_unsafe_source_name_rejected(self):
        l,p,s=fake_resources()
        with self.assertRaises(ValueError):
            self.evaluate({},p,s)
        l["../Unsafe.lvl"]=l[FIRST_LEVEL]
        with self.assertRaisesRegex(ValueError,"Unsafe original level"):
            self.evaluate(l,p,s)

    def test_synthetic_paired_screen_ipa_audit(self):
        with TemporaryDirectory() as directory:
            path=Path(directory)/"fictional.ipa"
            synthetic_zip(path)
            result=audit_private_level_physics_shape_chains(path)
        self.assertEqual(result["paired_original_levels_examined"],2)
        self.assertEqual(result["first_level"][
            "objects_with_exact_class_name_physics_resource_stem"],2)
        self.assertFalse(result["safe_for_automatic_original_collision_import"])

    def test_paired_screen_byte_divergence_rejected(self):
        with TemporaryDirectory() as directory:
            path=Path(directory)/"fictional.ipa"
            synthetic_zip(path,divergent=True)
            with self.assertRaisesRegex(ValueError,"bytes differ"):
                audit_private_level_physics_shape_chains(path)

    def test_duplicate_original_zip_member_rejected(self):
        with TemporaryDirectory() as directory:
            path=Path(directory)/"fictional.ipa"
            synthetic_zip(path,extra=[(
                f"Payload/MOTU.app/screen-med/physics_struct/DemoActor.ps2d",
                fixture([record()]))])
            with self.assertRaisesRegex(ValueError,"Duplicate"):
                audit_private_level_physics_shape_chains(path)

    def test_paired_symlink_source_rejected(self):
        with TemporaryDirectory() as directory:
            path=Path(directory)/"fictional.ipa"
            extra=[]
            for pack in ("screen-med","screen-xlarge"):
                link=ZipInfo(f"Payload/MOTU.app/{pack}/geometry/Link.shape")
                link.create_system=3
                link.external_attr=(stat.S_IFLNK | 0o777)<<16
                extra.append((link,b"relative"))
            synthetic_zip(path,extra=extra)
            with self.assertRaisesRegex(ValueError,"unsafe selected"):
                audit_private_level_physics_shape_chains(path)

    def test_missing_owner_ipa_fails_closed(self):
        with self.assertRaisesRegex(ValueError,"Owner-private original"):
            audit_private_level_physics_shape_chains(
                Path("/no-owner-iOS-archive.ipa"))


if __name__ == "__main__":
    unittest.main()
