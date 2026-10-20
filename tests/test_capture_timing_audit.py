"""Stage 079: fabricated clock metadata only; no real iOS recordings."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from heman_tools.capture_timing_audit import audit_timing, main
from heman_tools.contact_scenarios import scripted_controls


def fictional_timing(name="landing", kind="synthetic"):
    result = {"scenario_id": name, "nominal_fps": 60}
    for platform, shift in (("ios", 12_000_000), ("switch", 81_000_000)):
        frames = [{
            "script_tick": tick,
            "source_frame_index": 500 + tick,
            "timestamp_us": shift + round(tick * 1_000_000 / 60),
            "control": {"horizontal": axis, "jump": jump},
        } for tick, (axis, jump) in enumerate(scripted_controls(name))]
        result["reference" if platform == "ios" else "candidate"] = {
            "platform": platform,
            "capture_id": "synthetic-" + platform + "-" + name,
            "evidence_kind": kind,
            "clock_kind": "capture_monotonic",
            "frames": frames,
        }
    return result


class TimingAuditTests(unittest.TestCase):
    def test_fabricated_baseline_is_not_original_gameplay(self):
        report = audit_timing(fictional_timing())
        self.assertFalse(report["timing_consistent_under_supplied_metadata"])
        self.assertEqual(report["sample_count_per_capture"], 120)
        self.assertEqual(report["structural_blockers"], [
            "ios:synthetic_not_original_recording",
            "switch:synthetic_not_original_recording"])
        self.assertLess(report["max_relative_elapsed_skew_ms"], 0.001)
        self.assertFalse(report["original_gameplay_physics_verified"])
        self.assertFalse(report["automatic_collision_export_permitted"])

    def test_declared_manual_capture_can_pass_only_numeric_gate(self):
        report = audit_timing(fictional_timing(kind="manual_observation"))
        self.assertTrue(report["timing_consistent_under_supplied_metadata"])
        self.assertEqual(report["structural_blockers"], [])
        for k in ("source_video_decoding_performed",
                  "absolute_cross_device_time_offset_verified",
                  "source_frame_timestamps_authenticated",
                  "ios_gameplay_recording_authenticated",
                  "original_gameplay_physics_verified"):
            self.assertIs(report[k], False)

    def test_constant_cross_clock_offset_is_not_detectable(self):
        data = fictional_timing(kind="manual_observation")
        for frame in data["candidate"]["frames"]:
            frame["timestamp_us"] += 700_000_000
        report = audit_timing(data)
        self.assertTrue(report["timing_consistent_under_supplied_metadata"])
        self.assertEqual(report["max_relative_elapsed_skew_ms"], 0)
        self.assertFalse(report["absolute_cross_device_time_offset_verified"])

    def test_missing_source_index_is_detected_without_fabricating_frames(self):
        data = fictional_timing(kind="manual_observation")
        for frame in data["reference"]["frames"][40:]:
            frame["source_frame_index"] += 1
        report = audit_timing(data)
        self.assertEqual(report["missing_source_frame_count"]["ios"], 1)
        self.assertIn("ios:missing_source_frames", report["structural_blockers"])

    def test_duplicated_source_frame_counter_is_detected(self):
        data = fictional_timing(kind="manual_observation")
        frames = data["candidate"]["frames"]
        frames[30]["source_frame_index"] = frames[29]["source_frame_index"]
        report = audit_timing(data)
        self.assertEqual(report["duplicate_source_frame_count"]["switch"], 1)
        self.assertIn("switch:duplicated_source_frames", report["structural_blockers"])

    def test_source_frame_counter_cannot_go_backwards(self):
        data = fictional_timing()
        data["reference"]["frames"][20]["source_frame_index"] = 0
        with self.assertRaisesRegex(ValueError, "counter moved backward"):
            audit_timing(data)

    def test_one_frame_delay_detected_by_jitter(self):
        data = fictional_timing(kind="manual_observation")
        data["reference"]["frames"][55]["timestamp_us"] += 15_000
        report = audit_timing(data)
        self.assertIn("ios:frame_interval_jitter", report["structural_blockers"])
        self.assertGreater(report["max_frame_interval_jitter_ms"]["ios"], 10)

    def test_cumulative_clock_drift_detected(self):
        data = fictional_timing(kind="manual_observation")
        for i, frame in enumerate(data["candidate"]["frames"]):
            frame["timestamp_us"] += 80 * i
        report = audit_timing(data)
        self.assertIn("switch:capture_duration_drift", report["structural_blockers"])
        self.assertIn("cross_capture_relative_elapsed_skew",
                      report["structural_blockers"])
        self.assertNotIn("switch:frame_interval_jitter", report["structural_blockers"])

    def test_one_frame_input_mismatch_rejected(self):
        data = fictional_timing("jump")
        data["candidate"]["frames"][15]["control"]["jump"] = False
        with self.assertRaisesRegex(ValueError, "control differs at script tick 15"):
            audit_timing(data)

    def test_ledge_uses_real_scripted_horizontal_ticks(self):
        report = audit_timing(fictional_timing("ledge",
                                             kind="manual_observation"))
        self.assertEqual(report["sample_count_per_capture"], 130)
        self.assertTrue(report["timing_consistent_under_supplied_metadata"])

    def test_missing_or_duplicate_script_tick_rejected(self):
        for bad in (-1, 10, None, True):
            data = fictional_timing()
            data["reference"]["frames"][6]["script_tick"] = bad
            with self.subTest(bad=bad), self.assertRaisesRegex(
                    ValueError, "script tick"):
                audit_timing(data)

    def test_duplicate_or_reversed_timestamps_rejected(self):
        for offset in (0, -10):
            data = fictional_timing()
            frames = data["candidate"]["frames"]
            frames[30]["timestamp_us"] = frames[29]["timestamp_us"] + offset
            with self.subTest(offset=offset), self.assertRaisesRegex(
                    ValueError, "non-increasing"):
                audit_timing(data)

    def test_invalid_timestamp_and_source_index_types_rejected(self):
        for field, value, message in (
                ("timestamp_us", 22.5, "timestamp"),
                ("timestamp_us", True, "timestamp"),
                ("timestamp_us", None, "timestamp"),
                ("source_frame_index", -1, "source frame"),
                ("source_frame_index", ["17"], "source frame")):
            data = fictional_timing()
            data["reference"]["frames"][4][field] = value
            with self.subTest(field=field, value=value), self.assertRaisesRegex(
                    ValueError, message):
                audit_timing(data)

    def test_nonmonotonic_clock_mode_or_unknown_label_rejected(self):
        for bad in ("wall_clock", None, [], 10):
            data = fictional_timing()
            data["reference"]["clock_kind"] = bad
            with self.subTest(bad=bad), self.assertRaisesRegex(
                    ValueError, "clock_kind"):
                audit_timing(data)
        data = fictional_timing()
        data["reference"]["evidence_kind"] = ["manual_observation"]
        with self.assertRaisesRegex(ValueError, "evidence_kind"):
            audit_timing(data)

    def test_reject_incorrect_capture_length_and_frame_rate(self):
        data = fictional_timing()
        data["candidate"]["frames"].pop()
        with self.assertRaisesRegex(ValueError, "frame count"):
            audit_timing(data)
        for bad in (59, True, "60"):
            data = fictional_timing()
            data["nominal_fps"] = bad
            with self.subTest(bad=bad), self.assertRaisesRegex(
                    ValueError, "60 Hz"):
                audit_timing(data)

    def test_reject_duplicate_capture_id_or_wrong_platform(self):
        data = fictional_timing()
        data["candidate"]["capture_id"] = data["reference"]["capture_id"]
        with self.assertRaisesRegex(ValueError, "same identifier"):
            audit_timing(data)
        data = fictional_timing()
        data["candidate"]["platform"] = "ios"
        with self.assertRaisesRegex(ValueError, "switch capture"):
            audit_timing(data)

    def test_reject_unhashable_scenario_and_invalid_tolerances(self):
        data = fictional_timing()
        data["scenario_id"] = ["landing"]
        with self.assertRaisesRegex(ValueError, "unsupported"):
            audit_timing(data)
        for bad in (True, 0, -1, 101, float("nan"), float("inf")):
            with self.subTest(bad=bad), self.assertRaisesRegex(
                    ValueError, "tolerance"):
                audit_timing(fictional_timing(), max_elapsed_skew_ms=bad)

    def test_derived_report_omits_raw_timestamp_and_controls(self):
        report = audit_timing(fictional_timing())
        encoded = json.dumps(report)
        for forbidden in ("timestamp_us", "source_frame_index", "script_tick",
                          "control", "synthetic-ios-landing", "synthetic-switch-landing"):
            # "controller..." isn't a report field; the exact "control" word
            # could occur only if a future interpretative note adds it.
            self.assertNotIn(forbidden, encoded)

    def test_private_cli_writes_only_aggregate_json(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            local = root / "local_reports"
            local.mkdir()
            source, target = local / "timing.json", local / "summary.json"
            source.write_text(json.dumps(fictional_timing()), encoding="utf-8")
            with patch("heman_tools.frame_alignment.Path.cwd", return_value=root):
                self.assertEqual(main(["--timing", str(source),
                                       "--out", str(target)]), 0)
                result = json.loads(target.read_text(encoding="utf-8"))
                self.assertEqual(result["sample_count_per_capture"], 120)
                with self.assertRaises(ValueError):
                    main(["--timing", str(source), "--out", str(source)])
                with self.assertRaises(ValueError):
                    main(["--timing", str(source),
                          "--out", str(root / "public.json")])


if __name__ == "__main__":
    unittest.main()
