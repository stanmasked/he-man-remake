"""Stage137 source-only tests. All fake ZIP contents generated in memory.

No commercial levels, maps, graphics, iOS executable or metadata dump here.
"""
from __future__ import annotations

import contextlib
import io
import json
import stat
import tempfile
import unittest
import warnings
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile, ZipInfo

from heman_tools.pack_parity import (
    PrivatePackError, audit_local_ipa, main,
)


def fake_name(pack, folder, leaf):
    return f"Payload/MOTU.app/{pack}/{folder}/{leaf}"


class LocalIosPackParityTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.ipa = self.root / "synthetic.ipa"

    def archive(self, extra=(), *, base=True):
        entries = []
        if base:
            for pack in ("screen-med", "screen-xlarge"):
                entries.extend([
                    (fake_name(pack, "levels", "FakeLevel.lvl"), b"FAKELEVEL!"),
                    (fake_name(pack, "maps", "FakeCollision.map"), b"FAKECOLLISION"),
                    (fake_name(pack, "shapes", "FakeShape.shape"), b"FAKESHAPE"),
                ])
        entries.extend(extra)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with ZipFile(self.ipa, "w") as z:
                for name, raw in entries:
                    z.writestr(name, raw)

    def test_equal_synthetic_packs_report_aggregate_only(self):
        self.archive()
        data = audit_local_ipa(self.ipa)
        self.assertEqual(data["sections"]["levels"]["paired_count"], 1)
        self.assertEqual(data["sections"]["maps"]["matching_bytes_count"], 1)
        self.assertEqual(data["sections"]["shapes"]["matching_bytes_count"], 1)
        self.assertFalse(data["raw_original_bytes_in_report"])
        rendered = json.dumps(data)
        for secret in ("FakeLevel", "FakeCollision", "FakeShape",
                       str(self.ipa), "FAKELEVEL"):
            self.assertNotIn(secret, rendered)

    def test_known_sky_exception_reported_as_boolean_without_filename(self):
        self.archive([
            (fake_name("screen-med", "maps", "gs_background_sky.map"), b"AAAA"),
            (fake_name("screen-xlarge", "maps", "gs_background_sky.map"), b"BBBB"),
        ])
        data = audit_local_ipa(self.ipa)
        maps = data["sections"]["maps"]
        self.assertEqual(maps["paired_count"], 2)
        self.assertEqual(maps["matching_bytes_count"], 1)
        self.assertEqual(maps["different_bytes_count"], 1)
        self.assertTrue(maps["expected_special_sky_difference"])
        self.assertEqual(maps["unclassified_difference_count"], 0)
        self.assertNotIn("gs_background_sky", json.dumps(data))

    def test_other_differences_are_counted_without_disclosing_name(self):
        self.archive([
            (fake_name("screen-med", "maps", "secret_map.map"), b"ABCDE"),
            (fake_name("screen-xlarge", "maps", "secret_map.map"), b"ABCDF"),
        ])
        data = audit_local_ipa(self.ipa)["sections"]["maps"]
        self.assertEqual(data["unclassified_difference_count"], 1)
        self.assertEqual(data["different_bytes_count"], 1)
        self.assertFalse(data["expected_special_sky_difference"])

    def test_single_pack_missing_level_not_invented(self):
        self.archive([
            (fake_name("screen-med", "levels", "HiddenOnly.lvl"), b"LEVEL"),
        ])
        data = audit_local_ipa(self.ipa)["sections"]["levels"]
        self.assertEqual(data["paired_count"], 1)
        self.assertEqual(data["only_med_count"], 1)
        self.assertEqual(data["only_xlarge_count"], 0)

    def test_duplicate_zip_member_rejected_without_read(self):
        name = fake_name("screen-med", "levels", "FakeLevel.lvl")
        self.archive([(name, b"DUPLICATE")])
        with self.assertRaisesRegex(PrivatePackError, "Duplicate ZIP"):
            audit_local_ipa(self.ipa)

    def test_path_traversal_member_rejected(self):
        self.archive([
            ("Payload/MOTU.app/screen-med/levels/../escape.lvl", b"NO"),
        ])
        with self.assertRaisesRegex(PrivatePackError, "Unsafe ZIP"):
            audit_local_ipa(self.ipa)

    def test_selected_symbolic_link_disallowed(self):
        self.archive(base=False)
        bad = ZipInfo(fake_name("screen-med", "levels", "symlink.lvl"))
        bad.create_system = 3
        bad.external_attr = ((stat.S_IFLNK | 0o777) << 16)
        with ZipFile(self.ipa, "w") as z:
            z.writestr(bad, b"target.lvl")
        with self.assertRaisesRegex(PrivatePackError, "unsupported ZIP member"):
            audit_local_ipa(self.ipa)

    def test_zip_member_budget_fails_closed(self):
        self.archive()
        with patch("heman_tools.pack_parity.MAX_MEMBER_BYTES", 2):
            with self.assertRaisesRegex(PrivatePackError, "size bound"):
                audit_local_ipa(self.ipa)

    def test_archive_aggregate_budget_fails_closed(self):
        self.archive()
        with patch("heman_tools.pack_parity.MAX_SUM_BYTES", 10):
            with self.assertRaisesRegex(PrivatePackError, "Aggregate"):
                audit_local_ipa(self.ipa)

    def test_strict_original_ios_v2_baseline_rejects_fake_zip(self):
        self.archive()
        with self.assertRaisesRegex(PrivatePackError, "does not match"):
            audit_local_ipa(self.ipa, require_ios_v2_baseline=True)

    def test_output_json_is_aggregate_only_and_private_path_is_not_printed(self):
        self.archive()
        dest = self.root / "local_reports" / "private_aggregate.json"
        capture = io.StringIO()
        with contextlib.redirect_stdout(capture):
            result = main(["--ipa", str(self.ipa), "--out", str(dest)])
        self.assertEqual(result, 0)
        report = json.loads(dest.read_text())
        self.assertEqual(report["sections"]["levels"]["paired_count"], 1)
        self.assertNotIn(str(self.ipa), capture.getvalue())
        self.assertNotIn("FakeLevel", dest.read_text())

    def test_non_zip_bytes_are_not_accepted(self):
        self.ipa.write_bytes(b"NOT AN IOS ZIP")
        with self.assertRaises(PrivatePackError):
            audit_local_ipa(self.ipa)


if __name__ == "__main__":
    unittest.main()
