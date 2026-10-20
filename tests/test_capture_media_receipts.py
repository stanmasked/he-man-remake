"""Only invented bytes, fictional clip labels and synthetic temp files in CI."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from heman_tools.capture_media_receipts import (
    audit_capture_manifest, main,
)
from heman_tools.contact_scenarios import SCENARIOS


def fictional_manifest():
    return {
        "protocol_version": 1,
        "captures": [
            {"scenario_id": name, "platform": platform,
             "capture_id": f"fictional-{name}-{platform}",
             "media_relpath": f"captures/fictional-{name}-{platform}.mov",
             "declared_source": ("ios_device" if platform == "ios"
                                 else "switch_emulator")}
            for name in SCENARIOS for platform in ("ios", "switch")
        ],
    }


def write_fake_clips(root, manifest, *, duplicate=False):
    (root / "captures").mkdir(exist_ok=True)
    for i, entry in enumerate(manifest["captures"]):
        # These bytes are NOT a valid encoded video: structural receipt
        # validation must never be confused with video or origin validation.
        body = (b"synthetic bytes of fake recording" +
                bytes([0 if duplicate else i]) * 40)
        (root / entry["media_relpath"]).write_bytes(body)


class CaptureMediaReceiptTests(unittest.TestCase):
    def test_empty_manifest_marks_all_ten_missing(self):
        with TemporaryDirectory() as tmp:
            result = audit_capture_manifest(
                {"protocol_version": 1, "captures": []}, Path(tmp))
        self.assertEqual(result["expected_capture_count"], 10)
        self.assertEqual(result["present_media_files"], 0)
        self.assertEqual(len(result["structural_blockers"]), 10)
        self.assertFalse(result["all_ten_unique_files_present_without_blockers"])
        self.assertFalse(result["original_ios_recording_provenance_authenticated"])

    def test_ten_distinct_fake_bytes_are_structurally_accepted_not_authenticated(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = fictional_manifest()
            write_fake_clips(root, manifest)
            report = audit_capture_manifest(manifest, root)
        self.assertEqual(report["declared_capture_count"], 10)
        self.assertEqual(report["present_media_files"], 10)
        self.assertTrue(report["all_ten_unique_files_present_without_blockers"])
        self.assertEqual(report["structural_blockers"], [])
        for field in ("source_video_decoding_performed",
                      "video_frame_timestamps_verified",
                      "controller_input_alignment_verified",
                      "original_ios_recording_provenance_authenticated",
                      "original_gameplay_physics_verified",
                      "automatic_collision_export_permitted"):
            self.assertFalse(report[field])

    def test_private_receipt_contains_correct_sha256_without_source_bytes(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = fictional_manifest()
            write_fake_clips(root, manifest)
            first = root / manifest["captures"][0]["media_relpath"]
            expected_hash = hashlib.sha256(first.read_bytes()).hexdigest()
            result = audit_capture_manifest(manifest, root)
        item = result["media_by_scenario_and_platform"]["landing:ios"]
        self.assertEqual(item["sha256"], expected_hash)
        self.assertNotIn("fictional-", json.dumps(result))
        self.assertNotIn("synthetic bytes", json.dumps(result))

    def test_incomplete_manifest_reports_all_missing_platforms(self):
        with TemporaryDirectory() as tmp:
            manifest = fictional_manifest()
            manifest["captures"] = manifest["captures"][:1]
            result = audit_capture_manifest(manifest, Path(tmp))
        self.assertEqual(len(result["structural_blockers"]), 10)
        self.assertIn("recording_file_missing:landing:ios",
                      result["structural_blockers"])
        self.assertIn("capture_not_supplied:landing:switch",
                      result["structural_blockers"])

    def test_duplicate_video_contents_are_flagged(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = fictional_manifest()
            write_fake_clips(root, manifest, duplicate=True)
            result = audit_capture_manifest(manifest, root)
        self.assertFalse(result["all_ten_unique_files_present_without_blockers"])
        self.assertEqual(
            len([x for x in result["structural_blockers"]
                 if x.startswith("duplicate_recording_bytes:")]), 9)

    def test_marked_synthetic_fixture_cannot_claim_complete_capture(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = fictional_manifest()
            manifest["captures"][0]["declared_source"] = "synthetic_fixture"
            write_fake_clips(root, manifest)
            result = audit_capture_manifest(manifest, root)
        self.assertIn("synthetic_fixture_not_original_capture:landing:ios",
                      result["structural_blockers"])
        self.assertFalse(result["all_ten_unique_files_present_without_blockers"])

    def test_duplicate_capture_ids_are_rejected(self):
        with TemporaryDirectory() as tmp:
            manifest = fictional_manifest()
            manifest["captures"][1]["capture_id"] = manifest["captures"][0]["capture_id"]
            with self.assertRaisesRegex(ValueError, "duplicate capture"):
                audit_capture_manifest(manifest, Path(tmp))

    def test_duplicate_scenario_platform_pair_is_rejected(self):
        with TemporaryDirectory() as tmp:
            manifest = fictional_manifest()
            manifest["captures"][1]["scenario_id"] = "landing"
            manifest["captures"][1]["platform"] = "ios"
            with self.assertRaisesRegex(ValueError, "duplicate scenario"):
                audit_capture_manifest(manifest, Path(tmp))

    def test_duplicate_file_path_is_rejected(self):
        with TemporaryDirectory() as tmp:
            manifest = fictional_manifest()
            manifest["captures"][1]["media_relpath"] = (
                manifest["captures"][0]["media_relpath"])
            with self.assertRaisesRegex(ValueError, "referenced twice"):
                audit_capture_manifest(manifest, Path(tmp))

    def test_unsafe_recording_paths_and_extensions_rejected(self):
        for bad in ("../private.ipa", "captures/../a.mov", "captures/a.ipa",
                    "captures/nested/a.mov", "captures/.hidden.mov",
                    "captures\\evil.mov", "public/movie.mp4", ""):
            with TemporaryDirectory() as tmp:
                manifest = fictional_manifest()
                manifest["captures"][0]["media_relpath"] = bad
                with self.subTest(path=bad), self.assertRaises(ValueError):
                    audit_capture_manifest(manifest, Path(tmp))

    def test_unhashable_scenario_or_platform_rejected(self):
        for field, bad in (("scenario_id", ["landing"]),
                           ("platform", {"value": "ios"}),
                           ("scenario_id", None), ("platform", True)):
            with TemporaryDirectory() as tmp:
                manifest = fictional_manifest()
                manifest["captures"][0][field] = bad
                with self.subTest(field=field, bad=bad), self.assertRaises(ValueError):
                    audit_capture_manifest(manifest, Path(tmp))

    def test_bad_origin_claim_rejected(self):
        for platform, source in (("ios", "switch_hardware"),
                                 ("switch", "ios_device"),
                                 ("ios", "authenticated"),
                                 ("ios", ["ios_device"])):
            with TemporaryDirectory() as tmp:
                manifest = fictional_manifest()
                manifest["captures"][0].update(platform=platform,
                                                declared_source=source)
                with self.subTest(source=source), self.assertRaises(ValueError):
                    audit_capture_manifest(manifest, Path(tmp))

    def test_empty_or_too_small_file_rejected(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = fictional_manifest()
            write_fake_clips(root, manifest)
            (root / manifest["captures"][0]["media_relpath"]).write_bytes(b"")
            with self.assertRaisesRegex(ValueError, "byte count"):
                audit_capture_manifest(manifest, root)

    def test_recording_directory_instead_of_regular_file_rejected(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = fictional_manifest()
            (root / "captures").mkdir()
            (root / manifest["captures"][0]["media_relpath"]).mkdir()
            with self.assertRaisesRegex(ValueError, "regular file"):
                audit_capture_manifest(manifest, root)

    def test_symlinked_media_is_rejected(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = fictional_manifest()
            (root / "captures").mkdir()
            actual = root / "captured.txt"
            actual.write_bytes(b"synthetic-data-not-a-real-video")
            (root / manifest["captures"][0]["media_relpath"]).symlink_to(actual)
            with self.assertRaisesRegex(ValueError, "symbolic link"):
                audit_capture_manifest(manifest, root)

    def test_symlinked_capture_directory_is_rejected(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = fictional_manifest()
            (root / "elsewhere").mkdir()
            (root / "captures").symlink_to(root / "elsewhere",
                                           target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "capture directory"):
                audit_capture_manifest(manifest, root)

    def test_symlinked_private_root_is_rejected(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "actual").mkdir()
            (root / "local_reports").symlink_to(
                root / "actual", target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "local_reports root"):
                audit_capture_manifest(
                    {"protocol_version": 1, "captures": []},
                    root / "local_reports")

    def test_wrong_protocol_version_and_too_many_sessions_rejected(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            for value in (0, "1", True, 2):
                with self.subTest(value=value), self.assertRaises(ValueError):
                    audit_capture_manifest({
                        "protocol_version": value, "captures": []}, root)
            manifest = fictional_manifest()
            manifest["captures"].append(deepcopy(manifest["captures"][0]))
            with self.assertRaisesRegex(ValueError, "at most ten"):
                audit_capture_manifest(manifest, root)

    def test_private_cli_writes_no_file_paths_for_blank_manifest(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            private = root / "local_reports"
            private.mkdir()
            source = private / "manifest.json"
            dest = private / "receipt.json"
            source.write_text(
                json.dumps({"protocol_version": 1, "captures": []}),
                encoding="utf-8")
            with patch("heman_tools.frame_alignment.Path.cwd", return_value=root):
                self.assertEqual(main([
                    "--manifest", str(source), "--out", str(dest)]), 0)
                report = json.loads(dest.read_text(encoding="utf-8"))
                self.assertEqual(report["present_media_files"], 0)
                with self.assertRaises(ValueError):
                    main(["--manifest", str(source), "--out", str(source)])
                with self.assertRaises(ValueError):
                    main(["--manifest", str(source),
                          "--out", str(root / "public.json")])


if __name__ == "__main__":
    unittest.main()
