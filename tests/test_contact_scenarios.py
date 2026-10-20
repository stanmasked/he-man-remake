"""Only fabricated paired traces, never original iOS recordings or game assets."""
from __future__ import annotations

from copy import deepcopy
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from heman_tools.contact_scenarios import (
    SCENARIOS, describe_scenarios, main, scripted_controls,
    validate_scenario_trace, validate_scenario_suite,
)


def artificial_trace(scenario: str) -> dict:
    """Satisfy the protocol with deliberately fictional annotations."""
    spec = SCENARIOS[scenario]
    n = spec["frames"]
    labels = []
    for i in range(n):
        if scenario == "landing":
            label = "airborne" if i < 30 else "floor"
        elif scenario == "jump":
            label = "floor" if i < 16 else (
                "airborne" if i < 75 else "floor")
        elif scenario == "wall":
            label = "wall" if 40 <= i < 50 else "floor"
        elif scenario == "ceiling":
            label = ("floor" if i < 13 or i >= 90 else
                     "ceiling" if 30 <= i < 35 else "airborne")
        elif scenario == "ledge":
            label = "floor" if i < 45 else "airborne"
        else:
            raise ValueError(scenario)
        labels.append(label)
    controls = scripted_controls(scenario)
    records = {"scenario_id": scenario, "fps": 60}
    for platform, scale in (("ios", 2.0), ("switch", 3.0)):
        observations = []
        for i, ((horizontal, jump), label) in enumerate(zip(controls, labels)):
            # Camera moves differently but relative hero-vs-anchor position
            # remains exactly the same under the explicitly supplied scale.
            ax = (100 + i if platform == "ios" else 20 - i)
            ay = (50 if platform == "ios" else 90 + 2 * i)
            observations.append({
                "frame": i,
                "control": {"horizontal": horizontal, "jump": jump},
                "feet_screen_xy": [ax + scale * (10 + i * 0.2),
                                   ay + scale * 8],
                "anchor_screen_xy": [ax, ay],
                "contact": label,
            })
        capture = {
            "platform": platform,
            "capture_id": f"entirely-fake-{platform}-{scenario}",
            "evidence_kind": "synthetic",
            "stationary_anchor_id": "fictitious-stone",
            "pixels_per_unit": scale,
            "observations": observations,
        }
        records["reference" if platform == "ios" else "candidate"] = capture
    return records


def artificial_suite() -> dict:
    return {"traces": [artificial_trace(name) for name in SCENARIOS]}


class ContactScenarioTests(unittest.TestCase):
    def test_five_named_public_scenarios(self):
        self.assertEqual(list(SCENARIOS),
                         ["landing", "jump", "wall", "ceiling", "ledge"])
        d = describe_scenarios()
        self.assertEqual(d["scenario_count"], 5)
        self.assertFalse(d["iOS_contact_capture_available"])
        self.assertFalse(d["original_gameplay_fidelity_verified"])

    def test_provisional_initial_conditions_explicit(self):
        for name in SCENARIOS:
            with self.subTest(name=name):
                self.assertTrue(describe_scenarios()["scenarios"][name][
                    "manual_initial_condition"])

    def test_wall_span_half_open_edges(self):
        controls = scripted_controls("wall")
        self.assertEqual(len(controls), 120)
        self.assertEqual(controls[9], (0, False))
        self.assertEqual(controls[10], (1, False))
        self.assertEqual(controls[89], (1, False))
        self.assertEqual(controls[90], (0, False))

    def test_ledge_span_has_no_jump(self):
        controls = scripted_controls("ledge")
        self.assertEqual(controls[9], (0, False))
        self.assertEqual(controls[10], (1, False))
        self.assertEqual(controls[119], (1, False))
        self.assertEqual(controls[120], (0, False))
        self.assertFalse(any(jump for _, jump in controls))

    def test_jump_and_ceiling_have_one_frame_jump_edges(self):
        for name, frame in (("jump", 15), ("ceiling", 12)):
            with self.subTest(name=name):
                controls = scripted_controls(name)
                self.assertEqual([i for i, (_, jump)
                                  in enumerate(controls) if jump], [frame])

    def test_unsupported_protocol_rejected(self):
        with self.assertRaisesRegex(ValueError, "unsupported"):
            scripted_controls("fake-level")

    def test_all_five_synthetic_protocols_pass_numeric_coverage(self):
        for name in SCENARIOS:
            with self.subTest(name=name):
                result = validate_scenario_trace(artificial_trace(name))
                self.assertTrue(result[
                    "protocol_and_numeric_consistency_on_supplied_records"])
                self.assertEqual(result["frames"], SCENARIOS[name]["frames"])
                self.assertFalse(result["original_gameplay_physics_verified"])
                self.assertFalse(result["both_captures_independently_authenticated"])
                self.assertFalse(result["automatic_collision_export_permitted"])

    def test_landing_missing_transition_is_blocker(self):
        data = artificial_trace("landing")
        for side in ("reference", "candidate"):
            for item in data[side]["observations"]:
                item["contact"] = "floor"
        result = validate_scenario_trace(data)
        self.assertFalse(result[
            "protocol_and_numeric_consistency_on_supplied_records"])
        self.assertEqual(result["per_platform"]["ios"]["missing_transitions"],
                         [["airborne", "floor"]])

    def test_jump_missing_return_to_floor_is_blocker(self):
        data = artificial_trace("jump")
        for side in ("reference", "candidate"):
            for item in data[side]["observations"][75:]:
                item["contact"] = "airborne"
        result = validate_scenario_trace(data)
        self.assertEqual(result["per_platform"]["ios"]["missing_transitions"],
                         [["airborne", "floor"]])

    def test_wall_never_observed_is_blocker(self):
        data = artificial_trace("wall")
        for side in ("reference", "candidate"):
            for item in data[side]["observations"]:
                item["contact"] = "floor"
        result = validate_scenario_trace(data)
        self.assertEqual(result["per_platform"]["switch"]["missing_contact_states"],
                         ["wall"])
        self.assertFalse(result[
            "protocol_and_numeric_consistency_on_supplied_records"])

    def test_ceiling_not_observed_is_blocker(self):
        data = artificial_trace("ceiling")
        for side in ("reference", "candidate"):
            for item in data[side]["observations"]:
                if item["contact"] == "ceiling":
                    item["contact"] = "airborne"
        report = validate_scenario_trace(data)
        self.assertIn("ceiling", report["per_platform"]["ios"][
            "missing_contact_states"])

    def test_ledge_no_step_off_is_blocker(self):
        data = artificial_trace("ledge")
        for side in ("reference", "candidate"):
            for item in data[side]["observations"]:
                item["contact"] = "floor"
        report = validate_scenario_trace(data)
        self.assertEqual(report["per_platform"]["ios"]["missing_transitions"],
                         [["floor", "airborne"]])

    def test_unknown_even_matching_labels_is_blocker(self):
        data = artificial_trace("landing")
        for side in ("reference", "candidate"):
            data[side]["observations"][50]["contact"] = "unknown"
        report = validate_scenario_trace(data)
        self.assertFalse(report["protocol_and_numeric_consistency_on_supplied_records"])
        self.assertEqual(report["per_platform"]["ios"]["unknown_contact_frames"], 1)

    def test_wrong_ios_input_frame_is_rejected(self):
        data = artificial_trace("wall")
        data["reference"]["observations"][10]["control"]["horizontal"] = 0
        with self.assertRaisesRegex(ValueError, "scripted frame 10"):
            validate_scenario_trace(data)

    def test_wrong_switch_input_frame_is_rejected(self):
        data = artificial_trace("ceiling")
        data["candidate"]["observations"][12]["control"]["jump"] = False
        with self.assertRaisesRegex(ValueError, "scripted frame 12"):
            validate_scenario_trace(data)

    def test_frame_count_and_fps_are_strict(self):
        data = artificial_trace("landing")
        data["reference"]["observations"].pop()
        with self.assertRaises(ValueError):
            validate_scenario_trace(data)
        data = artificial_trace("landing")
        data["fps"] = 30
        with self.assertRaisesRegex(ValueError, "FPS"):
            validate_scenario_trace(data)

    def test_contact_disagreement_blocks_even_with_events_present(self):
        data = artificial_trace("wall")
        for item in data["candidate"]["observations"][40:44]:
            item["contact"] = "floor"
        report = validate_scenario_trace(data)
        self.assertEqual(report["comparison"]["contact_mismatch_frames"], 4)
        self.assertFalse(report["protocol_and_numeric_consistency_on_supplied_records"])

    def test_synthetic_suite_all_five_provisionally_consistent(self):
        result = validate_scenario_suite(artificial_suite())
        self.assertEqual(result["scenario_count"], 5)
        self.assertTrue(result["numerical_and_event_contracts_all_met"])
        self.assertFalse(result["real_original_ios_traces_authenticated"])
        self.assertFalse(result["original_gameplay_physics_verified"])

    def test_suite_missing_or_duplicate_scenario_rejected(self):
        suite = artificial_suite()
        suite["traces"].pop()
        with self.assertRaisesRegex(ValueError, "exactly five"):
            validate_scenario_suite(suite)
        suite = artificial_suite()
        suite["traces"][1] = deepcopy(suite["traces"][0])
        with self.assertRaisesRegex(ValueError, "each required scenario"):
            validate_scenario_suite(suite)

    def test_suite_reused_capture_id_rejected(self):
        suite = artificial_suite()
        suite["traces"][1]["reference"]["capture_id"] = suite["traces"][0][
            "reference"]["capture_id"]
        with self.assertRaisesRegex(ValueError, "reuses a capture"):
            validate_scenario_suite(suite)

    def test_suite_with_no_wall_event_not_clean(self):
        suite = artificial_suite()
        for side in ("reference", "candidate"):
            for item in suite["traces"][2][side]["observations"]:
                item["contact"] = "floor"
        result = validate_scenario_suite(suite)
        self.assertFalse(result["numerical_and_event_contracts_all_met"])

    def test_scenario_result_never_exports_original_positions(self):
        text = json.dumps(validate_scenario_trace(artificial_trace("landing")))
        for key in ("feet_screen_xy", "anchor_screen_xy",
                    "stationary_anchor_id", "observations"):
            self.assertNotIn(key, text)

    def test_describe_cli_outputs_no_images_or_evidence(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.assertEqual(main(["--describe"]), 0)
        description = json.loads(buf.getvalue())
        self.assertEqual(len(description["scenarios"]), 5)
        self.assertFalse(description["iOS_contact_capture_available"])
        with self.assertRaises(SystemExit):
            main(["--describe", "--suite"])

    def test_private_cli_single_and_suite(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            private = root / "local_reports"
            private.mkdir()
            inp = private / "synthetic.json"
            output = private / "summary.json"
            with patch("heman_tools.frame_alignment.Path.cwd", return_value=root):
                inp.write_text(json.dumps(artificial_trace("landing")))
                self.assertEqual(main(["--traces", str(inp),
                                       "--out", str(output)]), 0)
                self.assertTrue(json.loads(output.read_text())[
                    "protocol_and_numeric_consistency_on_supplied_records"])
                inp.write_text(json.dumps(artificial_suite()))
                self.assertEqual(main(["--traces", str(inp),
                                       "--out", str(output), "--suite"]), 0)
                self.assertTrue(json.loads(output.read_text())[
                    "numerical_and_event_contracts_all_met"])
                with self.assertRaises(ValueError):
                    main(["--traces", str(inp), "--out", str(inp)])
                with self.assertRaises(ValueError):
                    main(["--traces", str(inp),
                          "--out", str(root / "public.json")])


if __name__ == "__main__":
    unittest.main()
