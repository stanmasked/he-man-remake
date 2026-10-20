"""Only fabricated cross-report summaries; no source game data."""
import copy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from heman_tools.first_level_report_audit import (
    _read_private_report, audit_level_report_consistency, main,
)


def reports():
    links = {
        "level": "Synthetic.lvl", "screen": "screen-med",
        "map_binding_confirmed": False,
        "real_game_object_link_confirmed": False,
        "map_object_count": 2, "available_map_count": 2,
        "map_objects": [
            {"object_index": 0, "candidate_status": "one_exact_candidate",
             "candidate_maps": [{"filename": "Example.map", "evidence":
                                 ["typed_string_property_exact:map"]}]},
            {"object_index": 1, "candidate_status": "no_exact_candidate",
             "candidate_maps": []},
        ],
        "candidate_map_structures": [
            {"filename": "Example.map",
             "unique_named_collision_layer": True,
             "collision_layer_name_occurrences": 1}],
    }
    shapes = {
        "level": "Synthetic.lvl", "object_count": 5, "shape_count": 2,
        "ownership_confirmed": False,
        "status_counts": {
            "no_exact_candidate": 1,
            "one_candidate_only": 1,
            "ambiguous_multiple_candidates": 0,
        },
        "shapes": [
            {"shape": "Untitled.shape", "candidate_status": "no_exact_candidate"},
            {"shape": "Example.shape", "candidate_status": "one_candidate_only"},
        ],
    }
    collision = {
        "map": "Example.map", "screen": "screen-med", "layer": "collision",
        "columns": 3, "rows": 2, "occupied_cells": 4, "empty_cells": 2,
    }
    return links, shapes, collision


class FirstLevelCrossReportTests(unittest.TestCase):
    def test_compatible_reports_still_never_authorize_export(self):
        report = audit_level_report_consistency(*reports())
        self.assertTrue(report["single_exact_text_reference"])
        self.assertTrue(report["one_named_collision_layer"])
        self.assertFalse(report["authentic_collision_verified"])
        self.assertFalse(report["automatic_collision_export_permitted"])
        self.assertIn("shape_ownership_unverified", report["unresolved_requirements"])
        self.assertEqual(report["occupied_candidate_cells"], 4)

    def test_other_level_rejected(self):
        a, b, c = reports()
        b["level"] = "Other.lvl"
        with self.assertRaisesRegex(ValueError, "different level"):
            audit_level_report_consistency(a, b, c)

    def test_other_screen_rejected(self):
        a, b, c = reports()
        c["screen"] = "screen-xlarge"
        with self.assertRaisesRegex(ValueError, "different screen"):
            audit_level_report_consistency(a, b, c)

    def test_not_collision_layer_rejected(self):
        a, b, c = reports()
        c["layer"] = "background"
        with self.assertRaisesRegex(ValueError, "collision layer"):
            audit_level_report_consistency(a, b, c)

    def test_wrong_source_map_fails_closed(self):
        a, b, c = reports()
        c["map"] = "Unknown.map"
        with self.assertRaisesRegex(ValueError, "exactly one structure"):
            audit_level_report_consistency(a, b, c)

    def test_two_objects_reference_same_map_blocks_unique_identity(self):
        a, b, c = reports()
        a["map_objects"][1] = copy.deepcopy(a["map_objects"][0])
        a["map_objects"][1]["object_index"] = 1
        result = audit_level_report_consistency(a, b, c)
        self.assertFalse(result["single_exact_text_reference"])
        self.assertIn("selected_map_lacks_one_unique_text_reference",
                      result["unresolved_requirements"])

    def test_ambiguous_map_reference_not_selected(self):
        a, b, c = reports()
        row = a["map_objects"][0]
        row["candidate_status"] = "ambiguous_multiple_candidates"
        row["candidate_maps"].append({"filename": "Other.map", "evidence": []})
        result = audit_level_report_consistency(a, b, c)
        self.assertFalse(result["single_exact_text_reference"])

    def test_missing_collision_layer_blocks(self):
        a, b, c = reports()
        a["candidate_map_structures"][0].update(
            collision_layer_name_occurrences=0,
            unique_named_collision_layer=False)
        result = audit_level_report_consistency(a, b, c)
        self.assertFalse(result["one_named_collision_layer"])
        self.assertIn("selected_map_lacks_one_collision_layer",
                      result["unresolved_requirements"])

    def test_contradictory_layer_flags_rejected(self):
        a, b, c = reports()
        a["candidate_map_structures"][0]["unique_named_collision_layer"] = False
        with self.assertRaisesRegex(ValueError, "contradictory"):
            audit_level_report_consistency(a, b, c)

    def test_count_mismatch_rejected(self):
        a, b, c = reports()
        c["occupied_cells"] = 6
        with self.assertRaisesRegex(ValueError, "grid dimensions"):
            audit_level_report_consistency(a, b, c)

    def test_shape_summary_count_mismatch_rejected(self):
        a, b, c = reports()
        b["status_counts"]["one_candidate_only"] = 2
        with self.assertRaisesRegex(ValueError, "status totals"):
            audit_level_report_consistency(a, b, c)

    def test_shape_details_disagree_with_summary_rejected(self):
        a, b, c = reports()
        b["shapes"][1]["candidate_status"] = "no_exact_candidate"
        with self.assertRaisesRegex(ValueError, "statuses"):
            audit_level_report_consistency(a, b, c)

    def test_self_asserted_ownership_does_not_pass(self):
        a, b, c = reports()
        b["ownership_confirmed"] = True
        with self.assertRaisesRegex(ValueError, "ownership"):
            audit_level_report_consistency(a, b, c)

    def test_non_boolean_confirmations_rejected(self):
        a, b, c = reports()
        a["map_binding_confirmed"] = "false"
        with self.assertRaisesRegex(ValueError, "map links"):
            audit_level_report_consistency(a, b, c)

    def test_duplicate_map_object_index_rejected(self):
        a, b, c = reports()
        a["map_objects"][1]["object_index"] = 0
        with self.assertRaisesRegex(ValueError, "duplicate"):
            audit_level_report_consistency(a, b, c)

    def test_structural_shape_object_count_rejected(self):
        a, b, c = reports()
        b["object_count"] = 1
        with self.assertRaisesRegex(ValueError, "less than"):
            audit_level_report_consistency(a, b, c)

    def test_private_cli_reports_safe_counts_not_original_tiles(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            private = root / "local_reports"
            private.mkdir()
            inputs = [private / name for name in
                      ("links.json", "shapes.json", "collision.json")]
            for path, record in zip(inputs, reports()):
                path.write_text(json.dumps(record), encoding="utf-8")
            output = private / "summary.json"
            with patch("heman_tools.frame_alignment.Path.cwd", return_value=root):
                self.assertEqual(main([
                    "--links", str(inputs[0]), "--shapes", str(inputs[1]),
                    "--collision", str(inputs[2]), "--out", str(output)]), 0)
            result = json.loads(output.read_text(encoding="utf-8"))
            self.assertFalse(result["authentic_collision_verified"])
            self.assertNotIn("tile_ids", result)
            self.assertNotIn("atlas_ids", result)
            self.assertNotIn("map_objects", result)

    def test_public_or_symlinked_report_sources_rejected(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            private = root / "local_reports"
            private.mkdir()
            with patch("heman_tools.frame_alignment.Path.cwd", return_value=root):
                with self.assertRaisesRegex(ValueError, "local_reports"):
                    _read_private_report(root / "outside.json")
            (private / "dummy.json").write_text("{}", encoding="utf-8")
            private.rename(root / "hidden")
            private.symlink_to(root / "hidden", target_is_directory=True)
            with patch("heman_tools.frame_alignment.Path.cwd", return_value=root):
                with self.assertRaisesRegex(ValueError, "symbolic link"):
                    _read_private_report(private / "dummy.json")


if __name__ == "__main__":
    unittest.main()
