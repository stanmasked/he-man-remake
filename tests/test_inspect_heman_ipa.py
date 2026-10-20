"""Synthetic ZIP fixtures only. The commercial IPA is never used by CI."""
from __future__ import annotations

from pathlib import Path
import plistlib
import stat
import sys
import tempfile
import unittest
import warnings
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from inspect_heman_ipa import InventoryError, inspect_ipa


class LocalIPAInspectorTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.ipa = self.root / "fictional-test.ipa"
        self.bundle = "Payload/Sample.app/"

    def build(self, *, extra: dict[str, bytes] | None = None) -> None:
        files = {
            self.bundle + "Info.plist": plistlib.dumps({
                "CFBundleIdentifier": "example.synthetic.asset-free",
                "CFBundleVersion": "0.0.1",
                "MinimumOSVersion": "4.3",
                "UIDeviceFamily": [1, 2],
            }),
            self.bundle + "screen-med/levels/sample.lvl": b"synthetic-level",
            self.bundle + "screen-xlarge/levels/sample.lvl": b"synthetic-level",
            self.bundle + "screen-med/textures/sample.png": b"fake-med",
            self.bundle + "screen-xlarge/textures/sample.png": b"fake-large",
        }
        files.update(extra or {})
        with zipfile.ZipFile(self.ipa, "w", zipfile.ZIP_DEFLATED) as z:
            for name, data in files.items():
                z.writestr(name, data)

    def test_valid_inventory_counts_only_no_assets(self) -> None:
        self.build()
        report = inspect_ipa(self.ipa, check_crc=True)
        self.assertEqual(report["zip"]["file_count"], 5)
        self.assertTrue(report["zip"]["crc_verified"])
        self.assertEqual(report["resource_counts"][".lvl"], 2)
        self.assertEqual(report["resource_counts"][".png"], 2)
        self.assertEqual(report["mirror_analysis"]["common_relative_paths"], 2)
        self.assertEqual(report["mirror_analysis"]["matching_size_and_crc"], 1)
        self.assertEqual(report["application"]["bundle_version"], "0.0.1")
        self.assertTrue(report["original_assets_embedded_in_report"] is False)
        self.assertNotIn("synthetic-level", str(report))
        self.assertNotIn("sample.lvl", str(report))

    def test_extension_pair_stats_reconcile_with_global_totals(self) -> None:
        self.build()
        report = inspect_ipa(self.ipa, check_crc=True)
        self.assertEqual(report["schema_version"], 2)
        by_ext = report["mirror_analysis"]["by_extension"]
        level = by_ext[".lvl"]
        self.assertEqual(level["paired"], 1)
        self.assertEqual(level["matching_size_and_crc"], 1)
        self.assertEqual(level["different_size_or_crc"], 0)
        image = by_ext[".png"]
        self.assertEqual(image["paired"], 1)
        self.assertEqual(image["matching_size_and_crc"], 0)
        self.assertEqual(image["different_size_or_crc"], 1)
        self.assertEqual(sum(v["paired"] for v in by_ext.values()),
                         report["mirror_analysis"]["common_relative_paths"])
        self.assertEqual(sum(v["matching_size_and_crc"] for v in by_ext.values()),
                         report["mirror_analysis"]["matching_size_and_crc"])

    def test_orphans_are_counted_without_names(self) -> None:
        self.build(extra={
            self.bundle + "screen-med/maps/medium-only.map": b"med",
            self.bundle + "screen-xlarge/maps/large-only.map": b"big",
            self.bundle + "screen-med/maps/same.map": b"same",
            self.bundle + "screen-xlarge/maps/same.map": b"same",
        })
        report = inspect_ipa(self.ipa)
        m = report["mirror_analysis"]["by_extension"][".map"]
        self.assertEqual((m["screen-med"], m["screen-xlarge"]), (2, 2))
        self.assertEqual(m["paired"], 1)
        self.assertEqual(m["matching_size_and_crc"], 1)
        self.assertEqual(m["only_in_screen-med"], 1)
        self.assertEqual(m["only_in_screen-xlarge"], 1)
        output = str(report)
        self.assertNotIn("medium-only", output)
        self.assertNotIn("large-only", output)
        self.assertNotIn("same.map", output)

    def test_same_basename_in_different_directories_not_paired(self) -> None:
        self.build(extra={
            self.bundle + "screen-med/maps/common.tileset": b"x",
            self.bundle + "screen-xlarge/other/common.tileset": b"x",
        })
        m = inspect_ipa(self.ipa)["mirror_analysis"]["by_extension"][".tileset"]
        self.assertEqual(m["paired"], 0)
        self.assertEqual(m["only_in_screen-med"], 1)
        self.assertEqual(m["only_in_screen-xlarge"], 1)

    def test_nonmatching_paired_tile_variants(self) -> None:
        self.build(extra={
            self.bundle + "screen-med/tiles/shared.tileset": b"x" * 4,
            self.bundle + "screen-xlarge/tiles/shared.tileset": b"x" * 8,
        })
        m = inspect_ipa(self.ipa)["mirror_analysis"]["by_extension"][".tileset"]
        self.assertEqual(m["paired"], 1)
        self.assertEqual(m["matching_size_and_crc"], 0)
        self.assertEqual(m["different_size_or_crc"], 1)

    def test_missing_bundle_rejected(self) -> None:
        with zipfile.ZipFile(self.ipa, "w") as z:
            z.writestr("Info.plist", b"invalid")
        with self.assertRaisesRegex(InventoryError, "one iOS"):
            inspect_ipa(self.ipa)

    def test_missing_plist_rejected(self) -> None:
        with zipfile.ZipFile(self.ipa, "w") as z:
            z.writestr(self.bundle + "something.dat", b"fake")
        with self.assertRaisesRegex(InventoryError, "Info.plist"):
            inspect_ipa(self.ipa)

    def test_traversal_rejected(self) -> None:
        self.build(extra={"Payload/Sample.app/../../outside": b"x"})
        with self.assertRaisesRegex(InventoryError, "traversal"):
            inspect_ipa(self.ipa)

    def test_absolute_path_rejected(self) -> None:
        self.build(extra={"/Payload/evil": b"x"})
        with self.assertRaisesRegex(InventoryError, "unsafe ZIP member"):
            inspect_ipa(self.ipa)

    def test_backslash_rejected(self) -> None:
        self.build(extra={"Payload/Sample.app/..\\evil": b"x"})
        with self.assertRaisesRegex(InventoryError, "unsafe ZIP member"):
            inspect_ipa(self.ipa)

    def test_symlink_rejected(self) -> None:
        self.build()
        member = zipfile.ZipInfo("Payload/Sample.app/shortcut")
        member.create_system = 3
        member.external_attr = (stat.S_IFLNK | 0o777) << 16
        with zipfile.ZipFile(self.ipa, "a") as z:
            z.writestr(member, "../../../private")
        with self.assertRaisesRegex(InventoryError, "symbolic links"):
            inspect_ipa(self.ipa)

    def test_duplicates_rejected(self) -> None:
        self.build()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with zipfile.ZipFile(self.ipa, "a") as z:
                z.writestr(self.bundle + "screen-med/textures/sample.png", "extra")
        with self.assertRaisesRegex(InventoryError, "duplicate"):
            inspect_ipa(self.ipa)

    def test_not_zip_rejected(self) -> None:
        self.ipa.write_bytes(b"synthetic-not-a-zip")
        with self.assertRaisesRegex(InventoryError, "not a readable"):
            inspect_ipa(self.ipa)

    def test_double_bundle_rejected(self) -> None:
        self.build(extra={"Payload/Other.app/Info.plist": plistlib.dumps({})})
        with self.assertRaisesRegex(InventoryError, "one iOS"):
            inspect_ipa(self.ipa)


if __name__ == "__main__":
    unittest.main()
