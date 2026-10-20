"""Synthetic-only contract tests for paired explicit mapFileName references."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import zipfile

from heman_tools.paired_mapfile_links import audit_paired_reports, audit_private_ipa
from test_level_map_links import map_object
from test_objects import example_level
from test_tilemap import sample, layer


def fixture(screen: str) -> dict:
    rows = [
        {"object_index": 2, "object_class": "LevelTileMap",
         "candidate_status": "one_exact_candidate",
         "candidate_maps": [{"filename": "Floor.map",
                             "evidence": ["typed_string_property_exact:mapFileName"]}]},
        {"object_index": 5, "object_class": "LevelTileMapOverlay",
         "candidate_status": "one_exact_candidate",
         "candidate_maps": [{"filename": "Floor.overlay.map",
                             "evidence": ["typed_string_property_exact:mapFileName"]}]},
    ]
    return {
        "level": "Fictional.lvl", "screen": screen, "map_object_count": 2,
        "map_objects": rows,
        "candidate_map_structures": [
            {"filename": "Floor.map", "layer_count": 3,
             "collision_layer_name_occurrences": 1,
             "unique_named_collision_layer": True,
             "structural_parse_passed": True,
             "solid_tile_semantics_established": False},
            {"filename": "Floor.overlay.map", "layer_count": 1,
             "collision_layer_name_occurrences": 0,
             "unique_named_collision_layer": False,
             "structural_parse_passed": True,
             "solid_tile_semantics_established": False},
        ],
        "map_binding_confirmed": False,
        "collision_semantics_confirmed": False,
        "real_game_object_link_confirmed": False,
    }


class PairedMapfileLinkTests(unittest.TestCase):
    def setUp(self):
        self.med = fixture("screen-med")
        self.large = fixture("screen-xlarge")

    def evaluate(self):
        return audit_paired_reports(self.med, self.large)

    def test_matching_explicit_primary_and_overlay(self):
        result = self.evaluate()
        self.assertTrue(result["cross_pack_candidate_consistency"])
        self.assertEqual(result["candidate_links"]["LevelTileMap"]["map_filename"],
                         "Floor.map")
        self.assertEqual(result["candidate_links"]["LevelTileMapOverlay"]["layer_count"], 1)
        self.assertEqual(result["structural_blockers"], [])
        for key in ("runtime_map_binding_verified", "collision_semantics_verified",
                    "coordinate_scale_verified", "original_gameplay_trace_verified",
                    "automatic_collision_export_permitted"):
            self.assertIs(result[key], False)

    def test_one_pack_has_changed_object_index(self):
        self.large["map_objects"][1]["object_index"] = 8
        self.assertIn("screen_pack_explicit_references_or_layers_differ",
                      self.evaluate()["structural_blockers"])

    def test_mismatched_level_identity_rejected(self):
        self.large["level"] = "Other.lvl"
        with self.assertRaisesRegex(ValueError, "level identities"):
            self.evaluate()

    def test_forged_runtime_confirmation_rejected(self):
        self.large["real_game_object_link_confirmed"] = True
        with self.assertRaisesRegex(ValueError, "authenticated gameplay"):
            self.evaluate()

    def test_only_instance_match_is_not_mapfile_property(self):
        self.med["map_objects"][0]["candidate_maps"][0]["evidence"] = [
            "object_instance_exact"]
        self.assertIn("missing_unique_mapFileName_reference:LevelTileMap",
                      self.evaluate()["structural_blockers"])

    def test_two_candidate_map_names_are_not_unique(self):
        for rep in (self.med, self.large):
            row = rep["map_objects"][0]
            row["candidate_maps"].append({
                "filename": "Floor.overlay.map",
                "evidence": ["typed_string_property_exact:mapFileName"]})
            row["candidate_status"] = "ambiguous_multiple_candidates"
        self.assertIn("missing_unique_mapFileName_reference:LevelTileMap",
                      self.evaluate()["structural_blockers"])

    def test_changed_overlay_collision_layer_is_blocker(self):
        for rep in (self.med, self.large):
            structure = rep["candidate_map_structures"][1]
            structure["collision_layer_name_occurrences"] = 1
            structure["unique_named_collision_layer"] = True
        self.assertIn("overlay_contains_collision_layer",
                      self.evaluate()["structural_blockers"])

    def test_primary_without_collision_is_blocker(self):
        for rep in (self.med, self.large):
            structure = rep["candidate_map_structures"][0]
            structure["collision_layer_name_occurrences"] = 0
            structure["unique_named_collision_layer"] = False
        self.assertIn("primary_map_lacks_one_named_collision_layer",
                      self.evaluate()["structural_blockers"])

    def test_duplicate_object_index_rejected(self):
        self.med["map_objects"][1]["object_index"] = 2
        with self.assertRaisesRegex(ValueError, "duplicate"):
            self.evaluate()

    def test_duplicate_map_structure_rejected(self):
        self.med["candidate_map_structures"].append(
            deepcopy(self.med["candidate_map_structures"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate candidate"):
            self.evaluate()

    def test_claimed_solid_tile_semantics_rejected(self):
        self.med["candidate_map_structures"][0]["solid_tile_semantics_established"] = True
        with self.assertRaisesRegex(ValueError, "inconsistent"):
            self.evaluate()

    def test_swapped_screen_pack_rejected(self):
        with self.assertRaisesRegex(ValueError, "different screen"):
            audit_paired_reports(self.large, self.med)

    def test_status_count_contradiction_rejected(self):
        self.med["map_object_count"] = 1
        with self.assertRaisesRegex(ValueError, "invalid map-object"):
            self.evaluate()

    def test_real_synthetic_archive_decoding_without_original_assets(self):
        with TemporaryDirectory() as tmp:
            ipa = Path(tmp) / "made-up.ipa"
            with zipfile.ZipFile(ipa, "w") as archive:
                for screen in ("screen-med", "screen-xlarge"):
                    root = f"Payload/MOTU.app/{screen}/"
                    primary = map_object(name="floor", props=(
                        ("mapFileName", "string", "Floor"),))
                    overlay = map_object("LevelTileMapOverlay", name="overlay", props=(
                        ("mapFileName", "string", "Floor.overlay"),))
                    archive.writestr(root + "levels/Fictional.lvl",
                                     example_level([primary, overlay],
                                                   name="Fictional.lvl"))
                    archive.writestr(root + "maps/Floor.map", sample())
                    archive.writestr(root + "maps/Floor.overlay.map",
                                     sample(layer(name="overlay")))
            result = audit_private_ipa(ipa, "Fictional.lvl")
            self.assertTrue(result["cross_pack_candidate_consistency"])
            self.assertFalse(result["runtime_map_binding_verified"])
            self.assertNotIn("tile_ids", str(result))


if __name__ == "__main__":
    unittest.main()
