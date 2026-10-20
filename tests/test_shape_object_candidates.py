"""Synthetic-only evidence tests. Never use original copyrighted IPA/geometry."""
import json
from pathlib import Path
import struct
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import warnings
import zipfile

from heman_tools.lvl import LevelFormatError
from heman_tools.objects import parse_level_objects
from heman_tools.shape_object_candidates import (
    annotate_single_candidate_geometry, candidate_crossrefs,
    inspect_private_ipa, main, private_report_path,
)
from heman_tools.shapes import parse_shape
from test_objects import example_level, example_object
from test_shapes import polygon, circle

LEVEL_PATH = "Payload/MOTU.app/screen-med/levels/Synthetic.lvl"
GEOM_ROOT = "Payload/MOTU.app/screen-med/geometry/"


def parsed(objects=None):
    return parse_level_objects(example_level(objects))


class ShapeObjectCandidatesTests(unittest.TestCase):
    def test_exact_shape_filename_to_instance(self):
        level = parsed([example_object(name="Stone")])
        report = candidate_crossrefs(level, {"Stone.shape": parse_shape(polygon())})
        shape = report["shapes"][0]
        self.assertEqual(shape["candidate_status"], "one_candidate_only")
        self.assertEqual(shape["candidate_objects"], [
            {"object_index": 0, "evidence": ["filename_eq_instance"]}])
        self.assertFalse(report["ownership_confirmed"])

    def test_exact_reference_to_string_property(self):
        level = parsed([example_object(name="Hero", props=[
            ("resource", "string", "CastleMap")])])
        report = candidate_crossrefs(level, {
            "Unrelated.shape": parse_shape(circle(reference="CastleMap"))})
        self.assertEqual(report["shapes"][0]["candidate_objects"], [
            {"object_index": 0, "evidence": ["reference_eq_string_property"]}])

    def test_filename_to_string_property(self):
        level = parsed([example_object(name="Hero", props=[
            ("resource", "string", "Bridge")])])
        report = candidate_crossrefs(level, {"Bridge.shape": parse_shape(polygon())})
        self.assertEqual(report["shapes"][0]["candidate_objects"][0]["evidence"],
                         ["filename_eq_string_property"])

    def test_reference_to_instance(self):
        level = parsed([example_object(name="Bridge")])
        report = candidate_crossrefs(level, {
            "Unknown.shape": parse_shape(polygon(reference="Bridge"))})
        self.assertEqual(report["shapes"][0]["candidate_objects"][0]["evidence"],
                         ["reference_eq_instance"])

    def test_duplicate_candidates_are_ambiguous(self):
        level = parsed([example_object(name="Stone"), example_object(name="Stone")])
        report = candidate_crossrefs(level, {"Stone.shape": parse_shape(polygon())})
        self.assertEqual(report["status_counts"]["ambiguous_multiple_candidates"], 1)
        self.assertEqual([x["object_index"] for x in
                          report["shapes"][0]["candidate_objects"]], [0, 1])

    def test_no_substring_or_numeric_guess(self):
        level = parsed([example_object(name="StoneLarge", props=[
            ("id", "int", 5), ("speed", "float", 5.0)])])
        report = candidate_crossrefs(level, {"Stone.shape": parse_shape(polygon())})
        self.assertEqual(report["status_counts"]["no_exact_candidate"], 1)
        self.assertEqual(report["shapes"][0]["candidate_objects"], [])

    def test_same_object_evidence_deduplicated(self):
        level = parsed([example_object(name="Stone", props=[
            ("ref", "string", "Stone")])])
        report = candidate_crossrefs(level, {
            "Stone.shape": parse_shape(polygon(reference="Stone"))})
        self.assertEqual(report["status_counts"]["one_candidate_only"], 1)
        self.assertEqual(len(report["shapes"][0]["candidate_objects"]), 1)
        self.assertEqual(len(report["shapes"][0]["candidate_objects"][0]["evidence"]), 4)

    def test_optin_single_polygon_hypothetical_bounds(self):
        level = parsed([example_object(name="Stone", x=100, y=50)])
        shapes = {"Stone.shape": parse_shape(polygon())}
        report = candidate_crossrefs(level, shapes)
        self.assertNotIn("hypothetical_geometry", report["shapes"][0])
        annotate_single_candidate_geometry(level, shapes, report)
        entry = report["shapes"][0]["hypothetical_geometry"]
        self.assertEqual(entry["hypothetical_aabb"], (100, 50, 102, 53))
        self.assertFalse(entry["association_confirmed"])
        self.assertFalse(entry["physical_collision_confirmed"])
        self.assertFalse(report["ownership_confirmed"])

    def test_optin_circle_affine_mapped_to_ellipse(self):
        level = parsed([example_object(name="Bridge", x=100, y=50)])
        shapes = {"Unknown.shape": parse_shape(circle(reference="Bridge"))}
        report = annotate_single_candidate_geometry(
            level, shapes, candidate_crossrefs(level, shapes))
        box = report["shapes"][0]["hypothetical_geometry"]["hypothetical_aabb"]
        self.assertEqual(box, (98, 44, 108, 54))

    def test_optin_ambiguous_never_assigns_bounds(self):
        level = parsed([example_object(name="Stone"),
                        example_object(name="Stone", x=2)])
        shapes = {"Stone.shape": parse_shape(polygon())}
        report = annotate_single_candidate_geometry(
            level, shapes, candidate_crossrefs(level, shapes))
        self.assertIsNone(report["shapes"][0]["hypothetical_geometry"])

    def test_optin_no_match_never_assigns_bounds(self):
        level = parsed([example_object(name="NotStone")])
        shapes = {"Stone.shape": parse_shape(polygon())}
        report = annotate_single_candidate_geometry(
            level, shapes, candidate_crossrefs(level, shapes))
        self.assertIsNone(report["shapes"][0]["hypothetical_geometry"])

    def test_optin_cli_private_json(self):
        with TemporaryDirectory() as directory:
            ipa = Path(directory) / "synthetic.ipa"
            with zipfile.ZipFile(ipa, "w") as archive:
                archive.writestr(LEVEL_PATH, example_level([
                    example_object(name="Stone", x=10, y=20)]))
                archive.writestr(GEOM_ROOT + "Stone.shape", polygon())
            destination = (Path.cwd() / "local_reports" /
                           "synthetic-hypothetical-geometry-test.json")
            try:
                self.assertEqual(main(["--ipa", str(ipa),
                                       "--level", "Synthetic.lvl",
                                       "--out", str(destination),
                                       "--hypothetical-bounds"]), 0)
                report = json.loads(destination.read_text(encoding="utf-8"))
                self.assertFalse(report["ownership_confirmed"])
                self.assertEqual(
                    report["shapes"][0]["hypothetical_geometry"]["hypothetical_aabb"],
                    [10, 20, 12, 23])
                self.assertNotIn("vertices", json.dumps(report))
                self.assertNotIn("matrix", json.dumps(report))
            finally:
                destination.unlink(missing_ok=True)

    def test_archive_read_only(self):
        with TemporaryDirectory() as directory:
            ipa = Path(directory) / "synthetic.ipa"
            with zipfile.ZipFile(ipa, "w") as archive:
                archive.writestr(LEVEL_PATH, example_level([
                    example_object(name="Stone")]))
                archive.writestr(GEOM_ROOT + "Stone.shape", polygon())
                archive.writestr(GEOM_ROOT + "Mystery.shape", circle())
            report = inspect_private_ipa(ipa, "Synthetic.lvl")
            self.assertEqual(report["shape_count"], 2)
            self.assertEqual(report["status_counts"]["one_candidate_only"], 1)
            self.assertEqual(report["status_counts"]["no_exact_candidate"], 1)
            self.assertNotIn("vertices", json.dumps(report))
            self.assertNotIn("matrix", json.dumps(report))

    def test_bad_level_name_fails(self):
        for name in ("../private.lvl", r"..\private.lvl", "levels/L.lvl",
                     "noextension", "\n.lvl", ".lvl"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                inspect_private_ipa(Path("missing"), name)

    def test_duplicate_level_entry_fails(self):
        with TemporaryDirectory() as directory:
            ipa = Path(directory) / "synthetic.ipa"
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                with zipfile.ZipFile(ipa, "w") as archive:
                    archive.writestr(LEVEL_PATH, example_level())
                    archive.writestr(LEVEL_PATH, example_level())
            with self.assertRaises(ValueError):
                inspect_private_ipa(ipa, "Synthetic.lvl")

    def test_nested_shape_entry_fails(self):
        with TemporaryDirectory() as directory:
            ipa = Path(directory) / "synthetic.ipa"
            with zipfile.ZipFile(ipa, "w") as archive:
                archive.writestr(LEVEL_PATH, example_level())
                archive.writestr(GEOM_ROOT + "nested/Stone.shape", polygon())
            with self.assertRaises(ValueError):
                inspect_private_ipa(ipa, "Synthetic.lvl")

    def test_invalid_shape_payload_fails(self):
        with TemporaryDirectory() as directory:
            ipa = Path(directory) / "synthetic.ipa"
            with zipfile.ZipFile(ipa, "w") as archive:
                archive.writestr(LEVEL_PATH, example_level())
                archive.writestr(GEOM_ROOT + "Stone.shape", b"\xff" * 12)
            with self.assertRaises(LevelFormatError):
                inspect_private_ipa(ipa, "Synthetic.lvl")

    def test_private_output_paths_only(self):
        for path in ("docs/report.json", "README.json",
                     "local_reports/../report.json", "local_reports/report.txt"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                private_report_path(Path(path))

    def test_symlinked_private_root_rejected(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "public").mkdir()
            (root / "local_reports").symlink_to(root / "public", target_is_directory=True)
            with patch("heman_tools.shape_object_candidates.Path.cwd", return_value=root):
                with self.assertRaisesRegex(ValueError, "symbolic link"):
                    private_report_path(root / "local_reports" / "report.json")

    def test_cli_produces_local_only_report(self):
        with TemporaryDirectory() as directory:
            ipa = Path(directory) / "synthetic.ipa"
            with zipfile.ZipFile(ipa, "w") as archive:
                archive.writestr(LEVEL_PATH, example_level())
                archive.writestr(GEOM_ROOT + "fixture.shape", polygon())
            dest = Path.cwd() / "local_reports" / "synthetic-shape-refs-test.json"
            try:
                code = main(["--ipa", str(ipa), "--level", "Synthetic.lvl",
                             "--out", str(dest)])
                self.assertEqual(code, 0)
                saved = json.loads(dest.read_text(encoding="utf-8"))
                self.assertEqual(saved["shape_count"], 1)
                self.assertFalse(saved["ownership_confirmed"])
            finally:
                dest.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
