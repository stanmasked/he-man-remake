"""Fictional candidate records only: NEVER original He-Man source resources."""
from __future__ import annotations

import copy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from heman_tools.level11_private_readiness import (
    LEVEL, assess_private_level11, main,
)
from heman_tools.level_evidence_gate import REQUIRED


def synthetic_reports():
    links = {
        "level": LEVEL, "screen": "screen-med",
        "map_binding_confirmed": False,
        "real_game_object_link_confirmed": False,
        "map_object_count": 2,
        "map_objects": [
            {"object_index": 0, "candidate_status": "one_exact_candidate",
             "candidate_maps": [{"filename": "Fictional.map"}]},
            {"object_index": 1, "candidate_status": "no_exact_candidate",
             "candidate_maps": []},
        ],
        "candidate_map_structures": [
            {"filename": "Fictional.map",
             "unique_named_collision_layer": True,
             "collision_layer_name_occurrences": 1},
        ],
    }
    shapes = {
        "level": LEVEL, "object_count": 4, "shape_count": 2,
        "ownership_confirmed": False,
        "status_counts": {
            "no_exact_candidate": 1,
            "one_candidate_only": 1,
            "ambiguous_multiple_candidates": 0,
        },
        "shapes": [
            {"candidate_status": "no_exact_candidate"},
            {"candidate_status": "one_candidate_only"},
        ],
    }
    collision = {
        "map": "Fictional.map", "screen": "screen-med",
        "layer": "collision", "columns": 3, "rows": 2,
        "occupied_cells": 4, "empty_cells": 2,
    }
    paired = {
        "schema_version": 1,
        "level": LEVEL, "candidate_map": "Fictional.map",
        "screen_variants": ["screen-med", "screen-xlarge"],
        "selected_pairs": {
            key: {
                "bytes_per_screen": {
                    "screen-med": 24, "screen-xlarge": 24,
                },
                "first_u32_per_screen": {
                    "screen-med": 1, "screen-xlarge": 1,
                },
                "exact_bytes_equal": True,
                "standard_header_observed": True,
            } for key in ("level", "map")
        },
        "cross_pack_bytes_identical": True,
        "level_to_map_binding_verified": False,
        "collision_type_verified": False,
        "original_gameplay_trace_verified": False,
        "automatic_collision_export_permitted": False,
    }
    manual = {name: True for name in REQUIRED}
    return links, shapes, collision, paired, manual


def fake_capture(*, complete=True):
    return {
        "schema_version": 1,
        "all_declarative_integrity_and_numeric_checks_met": complete,
        "genuine_ios_capture_provenance_authenticated": False,
        "recorded_video_frames_decoded": False,
        "original_ios_frame_rate_established": False,
        "original_gameplay_physics_verified": False,
        "automatic_collision_export_permitted": False,
    }


class SourceReadinessGateTests(unittest.TestCase):
    def test_all_green_metadata_still_denies_unverified_level_import(self):
        result = assess_private_level11(*synthetic_reports(), fake_capture())
        self.assertTrue(result["map_candidate_unique"])
        self.assertTrue(result["named_collision_layer_unique"])
        self.assertTrue(result["manual_checks_declared_complete"])
        self.assertFalse(result["switch_original_level_import_permitted"])
        self.assertFalse(result["automatic_collision_export_permitted"])
        self.assertFalse(result["original_gameplay_physics_verified"])
        self.assertIn(
            "source_original_ios_gameplay_not_independently_authenticated",
            result["blockers"],
        )

    def test_private_source_names_absent_from_redacted_summary(self):
        payload = json.dumps(assess_private_level11(*synthetic_reports()))
        self.assertNotIn("Fictional.map", payload)
        self.assertNotIn("MULevel1-1.lvl", payload)
        self.assertNotIn("tile_ids", payload)
        self.assertNotIn("atlas", payload)
        self.assertNotIn("source_sha256", payload)

    def test_missing_original_capture_is_explicit(self):
        result = assess_private_level11(*synthetic_reports())
        self.assertIn("original_ios_contact_capture_not_supplied",
                      result["blockers"])

    def test_incomplete_capture_report_warns(self):
        result = assess_private_level11(*synthetic_reports(), fake_capture(complete=False))
        self.assertIn("capture_metadata_incomplete", result["blockers"])

    def test_forced_true_capture_provenance_rejected(self):
        item = fake_capture()
        item["genuine_ios_capture_provenance_authenticated"] = True
        with self.assertRaisesRegex(ValueError, "cannot authenticate"):
            assess_private_level11(*synthetic_reports(), item)

    def test_wrong_source_level_rejected(self):
        reports = list(synthetic_reports())
        reports[0]["level"] = reports[1]["level"] = "Other.lvl"
        reports[3]["level"] = "Other.lvl"
        with self.assertRaisesRegex(ValueError, "original Level 1-1"):
            assess_private_level11(*reports)

    def test_cross_report_identity_conflict_rejected(self):
        reports = list(synthetic_reports())
        reports[3]["candidate_map"] = "Wrong.map"
        with self.assertRaisesRegex(ValueError, "different level/map"):
            assess_private_level11(*reports)

    def test_screen_variant_identity_conflict_rejected(self):
        reports = list(synthetic_reports())
        reports[3]["screen_variants"] = ["screen-xlarge", "screen-med"]
        with self.assertRaisesRegex(ValueError, "screen variants"):
            assess_private_level11(*reports)

    def test_single_map_reference_required(self):
        reports = list(synthetic_reports())
        reports[0]["map_objects"][1] = copy.deepcopy(reports[0]["map_objects"][0])
        reports[0]["map_objects"][1]["object_index"] = 1
        result = assess_private_level11(*reports)
        self.assertIn("map_identity_has_no_unique_candidate", result["blockers"])

    def test_one_collision_layer_required(self):
        reports = list(synthetic_reports())
        structure = reports[0]["candidate_map_structures"][0]
        structure.update(collision_layer_name_occurrences=2,
                         unique_named_collision_layer=False)
        result = assess_private_level11(*reports)
        self.assertIn("map_collision_layer_not_unique", result["blockers"])

    def test_mixed_screen_contents_require_private_review(self):
        reports = list(synthetic_reports())
        reports[3]["selected_pairs"]["map"]["exact_bytes_equal"] = False
        reports[3]["cross_pack_bytes_identical"] = False
        result = assess_private_level11(*reports)
        self.assertIn("screen_variant_binary_differences_need_private_review",
                      result["blockers"])

    def test_aggregate_and_individual_resource_equality_cannot_contradict(self):
        reports = list(synthetic_reports())
        reports[3]["selected_pairs"]["map"]["exact_bytes_equal"] = False
        with self.assertRaisesRegex(ValueError, "equality disagree"):
            assess_private_level11(*reports)

    def test_invalid_binary_header_requires_review(self):
        reports = list(synthetic_reports())
        reports[3]["selected_pairs"]["level"]["standard_header_observed"] = False
        result = assess_private_level11(*reports)
        self.assertIn("resource_format_header_not_confirmed", result["blockers"])

    def test_wrong_header_or_size_types_rejected(self):
        for field, value in (("first_u32_per_screen", True),
                             ("bytes_per_screen", -10)):
            with self.subTest(field=field):
                reports = list(synthetic_reports())
                reports[3]["selected_pairs"]["level"][field]["screen-med"] = value
                with self.assertRaisesRegex(ValueError, "malformed|file size"):
                    assess_private_level11(*reports)

    def test_ambiguous_shape_objects_cause_blocker(self):
        reports = list(synthetic_reports())
        reports[1]["shapes"][0]["candidate_status"] = "ambiguous_multiple_candidates"
        reports[1]["status_counts"]["no_exact_candidate"] = 0
        reports[1]["status_counts"]["ambiguous_multiple_candidates"] = 1
        result = assess_private_level11(*reports)
        self.assertIn("ambiguous_shape_object_matches", result["blockers"])

    def test_manual_checklist_missing_is_reported_but_not_authenticated(self):
        reports = list(synthetic_reports())
        reports[4]["collision_category"] = False
        result = assess_private_level11(*reports)
        self.assertFalse(result["manual_checks_declared_complete"])
        self.assertIn("manual_collision_category", result["blockers"])

    def test_self_asserted_source_map_ownership_rejected(self):
        reports = list(synthetic_reports())
        reports[0]["map_binding_confirmed"] = True
        with self.assertRaisesRegex(ValueError, "unverified candidates"):
            assess_private_level11(*reports)

    def test_invalid_capture_verification_flag_rejected(self):
        item = fake_capture()
        item["automatic_collision_export_permitted"] = "false"
        with self.assertRaisesRegex(ValueError, "cannot authenticate"):
            assess_private_level11(*synthetic_reports(), item)

    def test_cli_writes_only_redacted_private_report(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            private = root / "local_reports"
            private.mkdir()
            names = ("links", "shapes", "collision", "pair", "manual")
            for name, value in zip(names, synthetic_reports()):
                (private / (name + ".json")).write_text(json.dumps(value))
            dest = private / "level11-readiness.json"
            args = [arg for name in names for arg in
                    ("--" + name, str(private / (name + ".json")))]
            args += ["--out", str(dest)]
            with patch("heman_tools.frame_alignment.Path.cwd", return_value=root):
                self.assertEqual(main(args), 0)
            summary = dest.read_text()
            self.assertNotIn("Fictional.map", summary)
            self.assertIn("original_ios_contact_capture_not_supplied", summary)

    def test_cli_rejects_public_output_and_path_reuse(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            private = root / "local_reports"
            private.mkdir()
            names = ("links", "shapes", "collision", "pair", "manual")
            for name, value in zip(names, synthetic_reports()):
                (private / (name + ".json")).write_text(json.dumps(value))
            args = [arg for name in names for arg in
                    ("--" + name, str(private / (name + ".json")))]
            with patch("heman_tools.frame_alignment.Path.cwd", return_value=root):
                with self.assertRaisesRegex(ValueError, "local_reports"):
                    main(args + ["--out", str(root / "public.json")])
                with self.assertRaisesRegex(ValueError, "share paths"):
                    main(args + ["--out", str(private / "links.json")])


if __name__ == "__main__":
    unittest.main()
