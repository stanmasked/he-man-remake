"""Synthetic-only tests for the first-level evidence review gate."""
import unittest
from heman_tools.level_evidence_gate import REQUIRED, assess_geometry_evidence


class LevelEvidenceGateTests(unittest.TestCase):
    def test_empty_checklist_fails_closed(self):
        result = assess_geometry_evidence({})
        self.assertEqual(result["missing_evidence"], list(REQUIRED))
        self.assertFalse(result["candidate_ready_for_manual_review"])
        self.assertFalse(result["automatic_collision_export_permitted"])

    def test_numeric_calibration_alone_is_insufficient(self):
        result = assess_geometry_evidence({
            "coordinate_scale": True,
            "cross_frame_validation": True,
            "heldout_validation": True,
        })
        self.assertIn("shape_ownership", result["missing_evidence"])
        self.assertIn("original_gameplay_trace", result["missing_evidence"])
        self.assertFalse(result["candidate_ready_for_manual_review"])

    def test_all_checks_allow_only_manual_review(self):
        result = assess_geometry_evidence(dict.fromkeys(REQUIRED, True))
        self.assertTrue(result["candidate_ready_for_manual_review"])
        self.assertFalse(result["automatic_collision_export_permitted"])
        self.assertFalse(result["physical_switch_gameplay_verified"])

    def test_single_missing_check_blocks_review(self):
        for key in REQUIRED:
            with self.subTest(key=key):
                evidence = dict.fromkeys(REQUIRED, True)
                evidence[key] = False
                result = assess_geometry_evidence(evidence)
                self.assertEqual(result["missing_evidence"], [key])
                self.assertFalse(result["candidate_ready_for_manual_review"])

    def test_unknown_keys_rejected(self):
        with self.assertRaises(ValueError):
            assess_geometry_evidence({"force_solid": True})

    def test_truthy_non_boolean_rejected(self):
        for value in (1, "yes", [], None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                assess_geometry_evidence({"shape_ownership": value})

    def test_non_dictionary_rejected(self):
        for value in (None, [], True, "ok"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                assess_geometry_evidence(value)

    def test_missing_and_false_are_both_unverified(self):
        a = assess_geometry_evidence({})
        b = assess_geometry_evidence(dict.fromkeys(REQUIRED, False))
        self.assertEqual(a["missing_evidence"], b["missing_evidence"])


if __name__ == "__main__":
    unittest.main()
