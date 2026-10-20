"""Fabricated blank worksheets only, without real iOS measurements."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from heman_tools.contact_scenarios import SCENARIOS, scripted_controls, validate_scenario_trace
from heman_tools.contact_worksheets import blank_scenario, blank_suite, main


class ContactWorksheetTests(unittest.TestCase):
    def test_all_five_have_correct_controls_and_no_source_values(self):
        for name in SCENARIOS:
            with self.subTest(name=name):
                report = blank_scenario(name)
                self.assertTrue(report["template_only"])
                self.assertEqual(report["scenario_id"], name)
                self.assertEqual(report["fps"], 60)
                for key, platform in (("reference", "ios"), ("candidate", "switch")):
                    capture = report[key]
                    self.assertEqual(capture["platform"], platform)
                    for field in ("capture_id", "evidence_kind",
                                  "stationary_anchor_id", "pixels_per_unit"):
                        self.assertIsNone(capture[field])
                    rows = capture["observations"]
                    self.assertEqual(len(rows), len(scripted_controls(name)))
                    for i, ((axis, jump), row) in enumerate(zip(scripted_controls(name), rows)):
                        self.assertEqual(row["frame"], i)
                        self.assertEqual(row["control"], {"horizontal": axis, "jump": jump})
                        self.assertIsNone(row["feet_screen_xy"])
                        self.assertIsNone(row["anchor_screen_xy"])
                        self.assertIsNone(row["contact"])

    def test_blank_forms_cannot_pass_observation_validator(self):
        for name in SCENARIOS:
            with self.subTest(name=name), self.assertRaises(ValueError):
                validate_scenario_trace(blank_scenario(name))

    def test_blank_forms_do_not_share_nested_mutable_objects(self):
        sheet = blank_scenario("landing")
        sheet["reference"]["observations"][0]["control"]["horizontal"] = 1
        self.assertEqual(sheet["candidate"]["observations"][0][
            "control"]["horizontal"], 0)
        self.assertEqual(sheet["reference"]["observations"][1][
            "control"]["horizontal"], 0)

    def test_blank_suite_contains_each_scenario_once(self):
        report = blank_suite()
        self.assertEqual([item["scenario_id"] for item in report["traces"]],
                         list(SCENARIOS))
        self.assertEqual(sum(len(item["reference"]["observations"])
                             for item in report["traces"]), 650)
        self.assertFalse(report["captured_original_ios_gameplay"])
        self.assertFalse(report["original_gameplay_physics_verified"])
        self.assertFalse(report["automatic_collision_export_permitted"])

    def test_unhashable_scenario_name_fails_cleanly(self):
        for bad in (["landing"], {"name": "landing"}, 1, None):
            with self.subTest(bad=bad), self.assertRaisesRegex(
                    ValueError, "unknown scenario"):
                blank_scenario(bad)

    def test_cli_writes_private_single_worksheet(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            root.joinpath("local_reports").mkdir()
            destination = root / "local_reports" / "blank-landing.json"
            with patch("heman_tools.frame_alignment.Path.cwd", return_value=root):
                self.assertEqual(main(["--scenario", "landing",
                                       "--out", str(destination)]), 0)
                data = json.loads(destination.read_text())
                self.assertTrue(data["template_only"])
                with self.assertRaisesRegex(ValueError, "overwrite"):
                    main(["--scenario", "landing", "--out", str(destination)])

    def test_cli_writes_suite_and_blocks_paths_outside_private_root(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            root.joinpath("local_reports").mkdir()
            destination = root / "local_reports" / "blank-suite.json"
            with patch("heman_tools.frame_alignment.Path.cwd", return_value=root):
                self.assertEqual(main(["--suite", "--out", str(destination)]), 0)
                data = json.loads(destination.read_text())
                self.assertEqual(len(data["traces"]), 5)
                with self.assertRaises(ValueError):
                    main(["--suite", "--out", str(root / "public.json")])

    def test_symlinked_private_directory_is_rejected(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            actual = root / "not-private"
            actual.mkdir()
            root.joinpath("local_reports").symlink_to(actual,
                                                        target_is_directory=True)
            destination = root / "local_reports" / "blank.json"
            with patch("heman_tools.frame_alignment.Path.cwd", return_value=root):
                with self.assertRaisesRegex(ValueError, "symbolic link"):
                    main(["--suite", "--out", str(destination)])


if __name__ == "__main__":
    unittest.main()
