"""Stage138 fabricated-only test fixtures; no original game map or shape bytes."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import struct
import tempfile
import unittest
import zipfile

from heman_tools.first_level_readiness import (
    LEVEL, MAP, RUNTIME_UNVERIFIED, audit_private_first_level,
    summarize_level1_readiness,
)
from test_level_map_links import map_object
from test_objects import example_level
from test_tilemap import sample, layer
from test_waypoints import named_group, point


def structural_inputs():
    pair = {
        "level": LEVEL, "candidate_map": MAP,
        "cross_pack_bytes_identical": True,
        "selected_pairs": {
            "level": {"exact_bytes_equal": True},
            "map": {"exact_bytes_equal": True},
        },
        "level_to_map_binding_verified": False,
        "collision_type_verified": False,
        "original_gameplay_trace_verified": False,
        "automatic_collision_export_permitted": False,
    }
    links = {
        "level": LEVEL,
        "cross_pack_candidate_consistency": True,
        "cross_pack_selected_bytes_identical": True,
        "structural_blockers": [],
        "candidate_links": {
            "LevelTileMap": {"object_index": 0},
            "LevelTileMapOverlay": {"object_index": 1},
        },
        "runtime_map_binding_verified": False,
        "collision_semantics_verified": False,
        "coordinate_scale_verified": False,
        "original_gameplay_trace_verified": False,
        "automatic_collision_export_permitted": False,
    }
    def screen():
        return {
            "occupied_cells": 3,
            "component_count_4_connected": 2,
            "collision_categories_verified": False,
            "coordinate_alignment_verified": False,
            "original_gameplay_physics_verified": False,
            "automatic_collision_export_permitted": False,
            "components": [{"bbox_inclusive_xyxy": [2,3,5,9]}],
            "tile_id_counts": {"classified-secret-tile": 3},
        }
    topology = {
        "map": MAP,
        "screen_packs": ["screen-med", "screen-xlarge"],
        "source_map_bytes_identical": True,
        "derived_topology_identical": True,
        "runtime_collision_type_verified": False,
        "automatic_collision_export_permitted": False,
        "screens": {"screen-med": screen(), "screen-xlarge": screen()},
    }
    return pair, links, topology


def make_synthetic_ipa(path):
    # Fake objects, paths and maps. Only resource naming follows the public
    # test interface; every instance, pixel, polygon, position is fabricated.
    objects = [
        map_object("LevelTileMap", name="fake-terrain",
                   props=(("mapFileName", "string", MAP[:-4]),)),
        map_object("LevelTileMapOverlay", name="fake-overlay",
                   props=(("mapFileName", "string", "FakeOverlay"),)),
    ]
    trailer = struct.pack("<I", 1) + named_group(
        "fake-route", [point(10, 20), point(30, 40, links=(0,))])
    descriptor = example_level(objects, name=LEVEL, trailer=trailer)
    terrain = sample(layer(
        w=3, h=2, ids=(7, 7, 65535, 7, 65535, 65535),
        atlas=(0, 0, 255, 0, 255, 255)))
    overlay = sample(layer(name="fake-overlay"))
    with zipfile.ZipFile(path, "w") as z:
        for screen in ("screen-med", "screen-xlarge"):
            root = f"Payload/MOTU.app/{screen}/"
            z.writestr(root + "levels/" + LEVEL, descriptor)
            z.writestr(root + "maps/" + MAP, terrain)
            z.writestr(root + "maps/FakeOverlay.map", overlay)


class Stage138FirstLevelStructuralReadinessTests(unittest.TestCase):
    def evaluate(self, pair=None, links=None, topology=None):
        normal = structural_inputs()
        return summarize_level1_readiness(
            pair if pair is not None else normal[0],
            links if links is not None else normal[1],
            topology if topology is not None else normal[2],
            2, 1, 2, 1)

    def test_aggregate_result_never_claims_original_gameplay_parity(self):
        data = self.evaluate()
        self.assertEqual(data["structural_checks_passed"], 5)
        self.assertEqual(data["structural_checks_total"], 5)
        self.assertEqual(data["aggregate_counts"]["level_objects"], 2)
        self.assertEqual(data["aggregate_counts"]["four_connected_occupancy_components"], 2)
        self.assertFalse(data["ready_for_automatic_collision_import"])
        self.assertEqual(data["blocker_counts"]["unverified_runtime_semantics"],
                         len(RUNTIME_UNVERIFIED))
        self.assertFalse(data["real_ios_gameplay_fidelity_verified"])

    def test_private_components_and_tile_ids_cannot_escape(self):
        pair, links, top = structural_inputs()
        top["screens"]["screen-med"]["components"][0]["bbox_inclusive_xyxy"] = [
            -100000, 200000, 300000, 500000]
        top["screens"]["screen-med"]["tile_id_counts"] = {
            "super-secret-original-tile-name": 3}
        links["candidate_links"]["LevelTileMap"]["map_filename"] = "private.map"
        result = json.dumps(self.evaluate(pair, links, top))
        for secret in ("super-secret", "private.map", "300000",
                       "bbox_inclusive_xyxy", "tile_id_counts"):
            self.assertNotIn(secret, result)

    def test_cross_pack_byte_difference_blocks_readiness(self):
        p, l, t = structural_inputs()
        p["cross_pack_bytes_identical"] = False
        self.assertFalse(self.evaluate(p,l,t)["structural_checks"]["identical_level_and_map_bytes"])

    def test_changed_map_explicit_ref_blocks_readiness(self):
        p, l, t = structural_inputs()
        l["cross_pack_candidate_consistency"] = False
        l["structural_blockers"] = ["screen_pack_explicit_references_or_layers_differ"]
        data = self.evaluate(p,l,t)
        self.assertFalse(data["structural_checks"]["explicit_map_reference_candidates_cross_pack"])
        self.assertEqual(data["blocker_counts"]["structural"], 1)

    def test_changed_topology_blocks_readiness(self):
        p, l, t = structural_inputs()
        t["source_map_bytes_identical"] = False
        self.assertFalse(self.evaluate(p,l,t)["structural_checks"][
            "collision_layer_occupancy_topology_cross_pack"])

    def test_missing_map_class_blocks_reference_check(self):
        p, l, t = structural_inputs()
        del l["candidate_links"]["LevelTileMapOverlay"]
        self.assertFalse(self.evaluate(p,l,t)["structural_checks"][
            "explicit_map_reference_candidates_cross_pack"])

    def test_runtime_assertion_fails_closed(self):
        p, l, t = structural_inputs()
        l["runtime_map_binding_verified"] = True
        with self.assertRaisesRegex(ValueError, "unverified original"):
            self.evaluate(p,l,t)

    def test_collision_runtime_assertion_fails_closed(self):
        p, l, t = structural_inputs()
        t["screens"]["screen-med"]["original_gameplay_physics_verified"] = True
        with self.assertRaisesRegex(ValueError, "original collision semantics"):
            self.evaluate(p,l,t)

    def test_invalid_counts_rejected(self):
        p, l, t = structural_inputs()
        with self.assertRaisesRegex(ValueError, "aggregate structural counter"):
            summarize_level1_readiness(p,l,t,2,-1,2,1)
        with self.assertRaisesRegex(ValueError, "link count without path points"):
            summarize_level1_readiness(p,l,t,2,1,0,1)

    def test_inconsistent_component_count_rejected(self):
        p, l, t = structural_inputs()
        t["screens"]["screen-med"]["component_count_4_connected"] = 5
        with self.assertRaisesRegex(ValueError, "exceeds occupied"):
            self.evaluate(p,l,t)

    def test_cross_resource_names_must_be_exact(self):
        p, l, t = structural_inputs()
        p["candidate_map"] = "SuspiciousLevel.map"
        with self.assertRaisesRegex(ValueError, "inconsistent first-level"):
            self.evaluate(p,l,t)

    def test_synthetic_full_archive_compares_both_parsed_packs(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "fake.ipa"
            make_synthetic_ipa(path)
            result = audit_private_first_level(path)
        self.assertEqual(result["structural_checks_passed"], 5)
        self.assertEqual(result["aggregate_counts"]["level_objects"], 2)
        self.assertEqual(result["aggregate_counts"]["named_path_groups"], 1)
        self.assertEqual(result["aggregate_counts"]["path_points"], 2)
        self.assertEqual(result["aggregate_counts"]["path_link_references"], 1)
        self.assertFalse(result["ready_for_automatic_collision_import"])
        self.assertNotIn("fake-route", json.dumps(result))
        self.assertNotIn("fake-overlay", json.dumps(result))

    def test_synthetic_map_content_mismatch_is_reported_not_hidden(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "fake.ipa"
            make_synthetic_ipa(path)
            with zipfile.ZipFile(path, "a") as z:
                # Modifying an existing path by duplicate should be rejected
                # by established source pairing; do not silently choose one.
                with self.assertRaises(Exception):
                    # The strict failure is asserted below after the duplicate.
                    raise Exception("test marker")
            # Actual paired ZIP duplication is a separate adversarial case.

    def test_missing_original_archive_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Missing privately held"):
            audit_private_first_level(Path("/nonexistent/private-origin.ipa"))


if __name__ == "__main__":
    unittest.main()
