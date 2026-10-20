"""Entirely fictional observations; no iOS gameplay or original resources in CI."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from heman_tools.contact_trace_audit import compare_contact_traces, main


def fabricated_trace():
    result = {"scenario_id": "fictional-contact",
              "fps": 60}
    for platform, scale, anchor_fn, capture_id in (
        ("ios", 2.0, lambda i: (100 + i, 30), "fake-ios-001"),
        ("switch", 3.0, lambda i: (10 - i * 2, 99 + i), "fake-switch-001"),
    ):
        obs = []
        for i in range(12):
            ax, ay = anchor_fn(i)
            contact = "airborne" if i < 4 else "floor"
            obs.append({
                "frame": i,
                "control": {"horizontal": 1 if i < 8 else 0,
                            "jump": i == 0},
                "feet_screen_xy": [ax + scale * (5 + i), ay + scale * 10],
                "anchor_screen_xy": [ax, ay],
                "contact": contact,
            })
        result["reference" if platform == "ios" else "candidate"] = {
            "platform": platform, "capture_id": capture_id,
            "evidence_kind": "synthetic",
            "stationary_anchor_id": "fictional-stone",
            "pixels_per_unit": scale, "observations": obs,
        }
    return result


class ContactTraceAuditTests(unittest.TestCase):
    def test_camera_translation_and_different_resolutions_cancel(self):
        report = compare_contact_traces(fabricated_trace())
        self.assertEqual(report["sample_count"], 12)
        self.assertEqual(report["maximum_relative_position_error_units"], 0)
        self.assertEqual(report["rms_relative_position_error_units"], 0)
        self.assertTrue(report["numeric_agreement_under_supplied_scale"])
        self.assertFalse(report["original_ios_physics_verified"])
        self.assertFalse(report["source_capture_authenticated"])
        self.assertFalse(report["automatic_collision_export_permitted"])

    def test_frame_position_drift_fails_threshold(self):
        data = fabricated_trace()
        data["candidate"]["observations"][6]["feet_screen_xy"][0] += 6
        report = compare_contact_traces(data, max_position_error_units=1.0)
        self.assertFalse(report["numeric_agreement_under_supplied_scale"])
        self.assertEqual(report["maximum_relative_position_error_units"], 2)

    def test_position_tolerance_is_explicit(self):
        data = fabricated_trace()
        data["candidate"]["observations"][6]["feet_screen_xy"][0] += 1.5
        self.assertTrue(compare_contact_traces(
            data, max_position_error_units=1)["numeric_agreement_under_supplied_scale"])
        self.assertFalse(compare_contact_traces(
            data, max_position_error_units=.1)["numeric_agreement_under_supplied_scale"])

    def test_wall_mislabeled_as_floor_detected(self):
        data = fabricated_trace()
        data["candidate"]["observations"][4]["contact"] = "wall"
        report = compare_contact_traces(data)
        self.assertEqual(report["contact_mismatch_frames"], 1)
        self.assertEqual(report["contact_mismatch_categories"], {"floor->wall": 1})
        self.assertEqual(report["contact_transition_mismatch_count"], 1)
        self.assertFalse(report["numeric_agreement_under_supplied_scale"])

    def test_contact_tolerance_does_not_authenticate(self):
        data = fabricated_trace()
        data["candidate"]["observations"][4]["contact"] = "wall"
        report = compare_contact_traces(data, max_contact_mismatches=1)
        self.assertTrue(report["numeric_agreement_under_supplied_scale"])
        self.assertFalse(report["original_ios_physics_verified"])

    def test_unknown_contact_blocks_even_if_both_equal(self):
        data = fabricated_trace()
        data["candidate"]["observations"][3]["contact"] = "unknown"
        data["reference"]["observations"][3]["contact"] = "unknown"
        report = compare_contact_traces(data)
        self.assertEqual(report["contact_mismatch_frames"], 0)
        self.assertEqual(report["unknown_contact_frames"], 1)
        self.assertFalse(report["numeric_agreement_under_supplied_scale"])

    def test_different_control_sequence_rejected(self):
        data = fabricated_trace()
        data["candidate"]["observations"][7]["control"]["jump"] = True
        with self.assertRaisesRegex(ValueError, "different inputs"):
            compare_contact_traces(data)

    def test_noncontiguous_frames_rejected(self):
        data = fabricated_trace()
        data["reference"]["observations"][6]["frame"] = 7
        with self.assertRaisesRegex(ValueError, "contiguous"):
            compare_contact_traces(data)

    def test_different_frame_counts_rejected(self):
        data = fabricated_trace()
        data["candidate"]["observations"].pop()
        with self.assertRaisesRegex(ValueError, "frame counts"):
            compare_contact_traces(data)

    def test_same_capture_id_rejected(self):
        data = fabricated_trace()
        data["candidate"]["capture_id"] = data["reference"]["capture_id"]
        with self.assertRaisesRegex(ValueError, "distinct"):
            compare_contact_traces(data)

    def test_mismatched_stationary_landmark_rejected(self):
        data = fabricated_trace()
        data["candidate"]["stationary_anchor_id"] = "different"
        with self.assertRaisesRegex(ValueError, "anchor identities"):
            compare_contact_traces(data)

    def test_unsupported_contact_kind_rejected(self):
        data = fabricated_trace()
        data["reference"]["observations"][2]["contact"] = "invisible"
        with self.assertRaisesRegex(ValueError, "contact observation"):
            compare_contact_traces(data)

    def test_unhashable_contact_label_rejected_as_invalid(self):
        for bad in (["floor"], {"kind": "floor"}, 5, None):
            data = fabricated_trace()
            data["candidate"]["observations"][2]["contact"] = bad
            with self.subTest(bad=bad), self.assertRaisesRegex(
                    ValueError, "unsupported contact observation"):
                compare_contact_traces(data)

    def test_unhashable_evidence_kind_rejected_as_invalid(self):
        for bad in (["synthetic"], {"kind": "synthetic"}, True, None):
            data = fabricated_trace()
            data["reference"]["evidence_kind"] = bad
            with self.subTest(bad=bad), self.assertRaisesRegex(
                    ValueError, "evidence_kind"):
                compare_contact_traces(data)

    def test_false_claim_of_observation_type_not_accepted(self):
        data = fabricated_trace()
        data["reference"]["evidence_kind"] = "authenticated_original"
        with self.assertRaisesRegex(ValueError, "evidence_kind"):
            compare_contact_traces(data)

    def test_marked_manual_observation_does_not_prove_provenance(self):
        data = fabricated_trace()
        data["reference"]["evidence_kind"] = "manual_observation"
        data["candidate"]["evidence_kind"] = "manual_observation"
        report = compare_contact_traces(data)
        self.assertTrue(report["numeric_agreement_under_supplied_scale"])
        self.assertFalse(report["source_capture_authenticated"])

    def test_nonfinite_and_boolean_coordinates_rejected(self):
        for value in (float("nan"), float("inf"), True, "5"):
            data = fabricated_trace()
            data["reference"]["observations"][5]["feet_screen_xy"][1] = value
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "bounded finite"):
                compare_contact_traces(data)

    def test_invalid_scale_and_error_threshold_rejected(self):
        for value in (0, -1, float("nan"), True, 1_000_001):
            data = fabricated_trace()
            data["candidate"]["pixels_per_unit"] = value
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "pixels_per_unit"):
                compare_contact_traces(data)
        for value in (0, True, -1, float("inf")):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "max_position"):
                compare_contact_traces(fabricated_trace(), max_position_error_units=value)

    def test_invalid_contact_mismatch_tolerance_rejected(self):
        for value in (-1, True, 1000, 1.5):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "max_contact"):
                compare_contact_traces(fabricated_trace(),
                                       max_contact_mismatches=value)

    def test_short_trace_and_bogus_fps_rejected(self):
        data = fabricated_trace()
        data["reference"]["observations"] = data["reference"]["observations"][:7]
        with self.assertRaisesRegex(ValueError, "8 to 600"):
            compare_contact_traces(data)
        data = fabricated_trace()
        data["fps"] = 0
        with self.assertRaisesRegex(ValueError, "fps"):
            compare_contact_traces(data)

    def test_result_never_contains_source_coordinates(self):
        report = compare_contact_traces(fabricated_trace())
        text = json.dumps(report)
        for forbidden in ("feet_screen_xy", "anchor_screen_xy",
                          "observations", "stationary_anchor_id"):
            self.assertNotIn(forbidden, text)

    def test_cli_private_only_and_input_output_distinct(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "local_reports").mkdir()
            source = root / "local_reports" / "fake-private.json"
            target = root / "local_reports" / "summary.json"
            source.write_text(json.dumps(fabricated_trace()), encoding="utf-8")
            with patch("heman_tools.frame_alignment.Path.cwd", return_value=root):
                self.assertEqual(main(["--traces", str(source),
                                       "--out", str(target)]), 0)
                self.assertTrue(json.loads(target.read_text())[
                    "numeric_agreement_under_supplied_scale"])
                with self.assertRaisesRegex(ValueError, "different"):
                    main(["--traces", str(source), "--out", str(source)])
                with self.assertRaises(ValueError):
                    main(["--traces", str(source),
                          "--out", str(root / "public.json")])


if __name__ == "__main__":
    unittest.main()
