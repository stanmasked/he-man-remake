"""Synthetic-only .lvl/.map archive tests: no original iOS resources."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import warnings
import zipfile

from heman_tools.level_map_links import (
    _private_report_path, audit_local_ipa, candidate_map_links, main,
)
from heman_tools.objects import parse_level_objects
from heman_tools.tilemap import TileMapFormatError
from test_objects import example_level, example_object, s
from test_tilemap import sample, layer

_ROOT = "Payload/MOTU.app/screen-med/"
_LEVEL = _ROOT + "levels/Synthetic.lvl"
_MAPS = _ROOT + "maps/"


def map_object(class_name="LevelTileMap", *, name="object-1", props=()):
    raw = example_object(name=name, props=props)
    return s(class_name) + raw[len(s("DemoObject")):]


def parsed(objects=None):
    return parse_level_objects(example_level(objects or []))


class LevelMapLinkTests(unittest.TestCase):
    def test_exact_typed_reference_stem(self):
        data = parsed([map_object(props=(("resource", "string", "Castle"),))])
        report = candidate_map_links(data, ["Castle.map", "Other.map"])
        self.assertEqual(report["exact_candidate_map_count"], 1)
        item = report["map_objects"][0]
        self.assertEqual(item["candidate_status"], "one_exact_candidate")
        self.assertEqual(item["candidate_maps"], [
            {"filename": "Castle.map",
             "evidence": ["typed_string_property_exact:resource"]}])
        self.assertFalse(report["map_binding_confirmed"])

    def test_exact_instance_filename(self):
        data = parsed([map_object(name="Castle.map")])
        result = candidate_map_links(data, ["Castle.map"])
        self.assertEqual(result["map_objects"][0]["candidate_maps"][0]["evidence"],
                         ["object_instance_exact"])

    def test_overlay_class_is_included(self):
        data = parsed([map_object("LevelTileMapOverlay", props=(
            ("map", "string", "Castle.overlay"),))])
        result = candidate_map_links(data, ["Castle.overlay.map"])
        self.assertEqual(result["map_object_count"], 1)
        self.assertEqual(result["exact_candidate_map_count"], 1)

    def test_two_matches_remain_ambiguous(self):
        data = parsed([map_object(props=(
            ("one", "string", "Castle"),
            ("two", "string", "Bridge"),))])
        result = candidate_map_links(data, ["Castle.map", "Bridge.map"])
        self.assertEqual(result["map_objects"][0]["candidate_status"],
                         "ambiguous_multiple_candidates")

    def test_duplicate_evidence_not_two_map_candidates(self):
        data = parsed([map_object(name="Castle", props=(
            ("one", "string", "Castle.map"),))])
        result = candidate_map_links(data, ["Castle.map"])
        self.assertEqual(result["map_objects"][0]["candidate_status"], "one_exact_candidate")
        self.assertEqual(len(result["map_objects"][0]["candidate_maps"][0]["evidence"]), 2)

    def test_non_target_class_is_ignored(self):
        data = parsed([example_object(name="Castle", props=(
            ("map", "string", "Castle"),))])
        self.assertEqual(candidate_map_links(data, ["Castle.map"])["map_object_count"], 0)

    def test_no_substrings_and_numeric_guesses(self):
        data = parsed([map_object(name="CastleExtra", props=(
            ("number", "int", 1), ("partial", "string", "Cast"),))])
        result = candidate_map_links(data, ["Castle.map"])
        self.assertEqual(result["map_objects"][0]["candidate_status"],
                         "no_exact_candidate")

    def test_duplicate_map_names_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicate"):
            candidate_map_links(parsed([map_object()]), ["Castle.map", "Castle.map"])

    def test_bad_names_rejected(self):
        for name in ("../Castle.map", r"..\Castle.map", "nested/Castle.map",
                     ".map", "Castle.png", "Castle.map\n"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                candidate_map_links(parsed([map_object()]), [name])

    def test_private_ipa_decodes_exact_candidate_map(self):
        with TemporaryDirectory() as directory:
            ipa = Path(directory) / "fake.ipa"
            with zipfile.ZipFile(ipa, "w") as z:
                z.writestr(_LEVEL, example_level([
                    map_object(props=(("map", "string", "Castle"),))],
                    name="Synthetic.lvl"))
                z.writestr(_MAPS+"Castle.map", sample())
                z.writestr(_MAPS+"Unused.map", b"not parsed")
            result = audit_local_ipa(ipa, "Synthetic.lvl")
            self.assertEqual(result["exact_candidate_map_count"], 1)
            self.assertEqual(result["available_map_count"], 2)
            self.assertTrue(result["candidate_map_structures"][0]["unique_named_collision_layer"])
            self.assertFalse(result["real_game_object_link_confirmed"])
            self.assertFalse(result["candidate_map_structures"][0]
                             ["solid_tile_semantics_established"])

    def test_named_collision_layer_not_assumed(self):
        with TemporaryDirectory() as directory:
            ipa = Path(directory) / "fake.ipa"
            with zipfile.ZipFile(ipa, "w") as z:
                z.writestr(_LEVEL, example_level([
                    map_object(props=(("map", "string", "Castle"),))],
                    name="Synthetic.lvl"))
                z.writestr(_MAPS+"Castle.map",
                           sample(layer(name="background")))
            entry = audit_local_ipa(ipa, "Synthetic.lvl")[
                "candidate_map_structures"][0]
            self.assertFalse(entry["unique_named_collision_layer"])
            self.assertEqual(entry["collision_layer_name_occurrences"], 0)

    def test_invalid_referenced_map_fails_closed(self):
        with TemporaryDirectory() as directory:
            ipa = Path(directory) / "bad.ipa"
            with zipfile.ZipFile(ipa, "w") as z:
                z.writestr(_LEVEL, example_level([
                    map_object(props=(("map", "string", "Castle"),))],
                    name="Synthetic.lvl"))
                z.writestr(_MAPS+"Castle.map", b"not a real tilemap")
            with self.assertRaises(TileMapFormatError):
                audit_local_ipa(ipa, "Synthetic.lvl")

    def test_no_level_entry_rejected(self):
        with TemporaryDirectory() as directory:
            ipa = Path(directory) / "fake.ipa"
            with zipfile.ZipFile(ipa, "w") as z:
                z.writestr(_MAPS+"Castle.map", sample())
            with self.assertRaisesRegex(ValueError, "one requested level"):
                audit_local_ipa(ipa, "Synthetic.lvl")

    def test_bad_level_name_rejected(self):
        for name in ("../Synthetic.lvl", r"..\Synthetic.lvl",
                     "nested/Synthetic.lvl", "Synthetic.txt", ".lvl"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                audit_local_ipa(Path("missing"), name)

    def test_duplicate_archive_map_rejected(self):
        with TemporaryDirectory() as directory:
            ipa = Path(directory) / "fake.ipa"
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                with zipfile.ZipFile(ipa, "w") as z:
                    z.writestr(_LEVEL, example_level(name="Synthetic.lvl"))
                    z.writestr(_MAPS+"Castle.map", sample())
                    z.writestr(_MAPS+"Castle.map", sample())
            with self.assertRaisesRegex(ValueError, "duplicate"):
                audit_local_ipa(ipa, "Synthetic.lvl")

    def test_nested_archive_map_rejected(self):
        with TemporaryDirectory() as directory:
            ipa = Path(directory) / "fake.ipa"
            with zipfile.ZipFile(ipa, "w") as z:
                z.writestr(_LEVEL, example_level(name="Synthetic.lvl"))
                z.writestr(_MAPS+"sub/Castle.map", sample())
            with self.assertRaises(ValueError):
                audit_local_ipa(ipa, "Synthetic.lvl")

    def test_private_destination_only(self):
        for path in ("docs/report.json", "local_reports/../out.json",
                     "local_reports/report.txt"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                _private_report_path(Path(path))

    def test_symlinked_private_root_rejected(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "not-private").mkdir()
            (root / "local_reports").symlink_to(root / "not-private",
                                                  target_is_directory=True)
            with patch("heman_tools.level_map_links.Path.cwd",
                       return_value=root):
                with self.assertRaisesRegex(ValueError, "symbolic link"):
                    _private_report_path(root/"local_reports"/"x.json")

    def test_local_cli_report_omits_raw_grid(self):
        with TemporaryDirectory() as directory:
            ipa = Path(directory) / "fake.ipa"
            with zipfile.ZipFile(ipa, "w") as z:
                z.writestr(_LEVEL, example_level([
                    map_object(props=(("map", "string", "Castle"),))],
                    name="Synthetic.lvl"))
                z.writestr(_MAPS+"Castle.map", sample())
            destination = (Path.cwd()/"local_reports"/
                           "synthetic-map-link-audit-test.json")
            try:
                self.assertEqual(main(["--ipa", str(ipa), "--level",
                                       "Synthetic.lvl", "--out",
                                       str(destination)]), 0)
                report = json.loads(destination.read_text(encoding="utf-8"))
                self.assertEqual(report["exact_candidate_map_count"], 1)
                self.assertNotIn("tile_ids", report)
                self.assertNotIn("atlas_ids", report)
            finally:
                destination.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
