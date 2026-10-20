"""Synthetic-only evidence joining. Fake movie files contain NO video."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from heman_tools.capture_evidence_join import audit_evidence_bundle, main
from heman_tools.contact_scenarios import SCENARIOS
from test_capture_media_receipts import fictional_manifest, write_fake_clips
from test_capture_timing_audit import fictional_timing
from test_contact_scenarios import artificial_suite


def fixtures():
    media = fictional_manifest()
    contacts = artificial_suite()
    timings = {"traces": [fictional_timing(scene, kind="manual_observation")
                          for scene in SCENARIOS]}
    paired = {item["scenario_id"]: item for item in contacts["traces"]}
    timed = {item["scenario_id"]: item for item in timings["traces"]}
    for item in media["captures"]:
        scene, platform = item["scenario_id"], item["platform"]
        side = "reference" if platform == "ios" else "candidate"
        cap = paired[scene][side]
        cap["evidence_kind"] = "manual_observation"
        item["capture_id"] = cap["capture_id"]
        timed[scene][side]["capture_id"] = cap["capture_id"]
    return media, timings, contacts


class EvidenceJoinTests(unittest.TestCase):
    def all_files(self, root):
        media, timings, contacts = fixtures()
        write_fake_clips(root, media)
        return media, timings, contacts

    def test_complete_fake_bundle_numerically_consistent_but_not_authentic(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = self.all_files(root)
            result = audit_evidence_bundle(*data, root)
        self.assertTrue(result["all_declarative_integrity_and_numeric_checks_met"])
        self.assertEqual(result["present_media_files"], 10)
        self.assertEqual(len(result["by_scenario"]), 5)
        for field in ("genuine_ios_capture_provenance_authenticated",
                      "recorded_video_frames_decoded",
                      "original_ios_frame_rate_established",
                      "cross_device_absolute_clock_synchronized",
                      "original_gameplay_physics_verified",
                      "automatic_collision_export_permitted"):
            self.assertFalse(result[field])

    def test_media_to_timing_id_swap_rejected(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            media, timings, contacts = self.all_files(root)
            timings["traces"][0]["reference"]["capture_id"] = "different"
            with self.assertRaisesRegex(ValueError, "capture IDs differ"):
                audit_evidence_bundle(media, timings, contacts, root)

    def test_contact_to_media_id_swap_rejected(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            media, timings, contacts = self.all_files(root)
            media["captures"][0]["capture_id"] = "changed-to-another-recording"
            with self.assertRaisesRegex(ValueError, "capture IDs differ"):
                audit_evidence_bundle(media, timings, contacts, root)

    def test_mismatched_evidence_kind_rejected(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            media, timings, contacts = self.all_files(root)
            timings["traces"][0]["reference"]["evidence_kind"] = "synthetic"
            with self.assertRaisesRegex(ValueError, "evidence labels disagree"):
                audit_evidence_bundle(media, timings, contacts, root)

    def test_contact_disagreement_blocks_structural_bundle_success(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            media, timings, contacts = self.all_files(root)
            contacts["traces"][0]["candidate"]["observations"][45][
                "contact"] = "airborne"
            result = audit_evidence_bundle(media, timings, contacts, root)
        self.assertFalse(result["all_declarative_integrity_and_numeric_checks_met"])
        self.assertFalse(result["by_scenario"]["landing"][
            "contact_and_numeric_contract_met"])

    def test_timing_gap_blocks_structural_bundle_success(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            media, timings, contacts = self.all_files(root)
            for frame in timings["traces"][0]["reference"]["frames"][40:]:
                frame["source_frame_index"] += 1
            result = audit_evidence_bundle(media, timings, contacts, root)
        self.assertFalse(result["all_declarative_integrity_and_numeric_checks_met"])
        self.assertIn("ios:missing_source_frames",
                      result["by_scenario"]["landing"]["timing_blockers"])

    def test_one_missing_file_is_a_hard_blocker(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            media, timings, contacts = self.all_files(root)
            first = root / media["captures"][0]["media_relpath"]
            first.unlink()
            result = audit_evidence_bundle(media, timings, contacts, root)
        self.assertFalse(result["all_declarative_integrity_and_numeric_checks_met"])
        self.assertEqual(result["present_media_files"], 9)
        self.assertIn("recording_file_missing:landing:ios",
                      result["media_integrity_blockers"])

    def test_duplicate_fake_media_bytes_block_but_do_not_crash(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            media, timings, contacts = fixtures()
            write_fake_clips(root, media, duplicate=True)
            result = audit_evidence_bundle(media, timings, contacts, root)
        self.assertFalse(result["all_declarative_integrity_and_numeric_checks_met"])
        self.assertTrue(any(x.startswith("duplicate_recording_bytes:")
                            for x in result["media_integrity_blockers"]))

    def test_synthetic_evidence_flags_never_prove_original(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            media, timings, contacts = self.all_files(root)
            scene = "landing"
            for report in (timings, contacts):
                row = next(x for x in report["traces"]
                           if x["scenario_id"] == scene)
                row["reference"]["evidence_kind"] = "synthetic"
            result = audit_evidence_bundle(media, timings, contacts, root)
        self.assertFalse(result["all_declarative_integrity_and_numeric_checks_met"])
        self.assertFalse(result["genuine_ios_capture_provenance_authenticated"])

    def test_media_manifest_requires_ten_distinct_slots(self):
        with TemporaryDirectory() as tmp:
            media, timings, contacts = fixtures()
            media["captures"].pop()
            with self.assertRaisesRegex(ValueError, "ten declared"):
                audit_evidence_bundle(media, timings, contacts, Path(tmp))

    def test_media_duplicate_pair_rejected_before_hashes(self):
        with TemporaryDirectory() as tmp:
            media, timings, contacts = fixtures()
            media["captures"][1]["scenario_id"] = "landing"
            media["captures"][1]["platform"] = "ios"
            with self.assertRaisesRegex(ValueError, "duplicate media capture pair"):
                audit_evidence_bundle(media, timings, contacts, Path(tmp))

    def test_missing_or_repeated_timing_scenario_rejected(self):
        with TemporaryDirectory() as tmp:
            media, timings, contacts = fixtures()
            timings["traces"].pop()
            with self.assertRaisesRegex(ValueError, "exactly five"):
                audit_evidence_bundle(media, timings, contacts, Path(tmp))
            media, timings, contacts = fixtures()
            timings["traces"][1]["scenario_id"] = "landing"
            with self.assertRaisesRegex(ValueError, "repeats a scenario"):
                audit_evidence_bundle(media, timings, contacts, Path(tmp))

    def test_wrong_platform_in_timing_source_rejected(self):
        with TemporaryDirectory() as tmp:
            media, timings, contacts = fixtures()
            timings["traces"][0]["candidate"]["platform"] = "ios"
            with self.assertRaises(ValueError):
                audit_evidence_bundle(media, timings, contacts, Path(tmp))

    def test_result_has_no_private_ids_hashes_or_coordinates(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = audit_evidence_bundle(*self.all_files(root), root)
        content = json.dumps(result)
        for forbidden in ("capture_id", "sha256", "media_relpath",
                          "feet_screen_xy", "timestamp_us", "observations",
                          "fictional-landing-ios", "entirely-fake"):
            self.assertNotIn(forbidden, content)

    def test_private_cli_enforces_paths_and_outputs_safe_summary(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            private = root / "local_reports"
            private.mkdir()
            media, timing, contact = self.all_files(private)
            paths = [private / f"{key}.json" for key in (
                "media", "timing", "contacts", "joined")]
            for source, content in zip(paths[:3], (media, timing, contact)):
                source.write_text(json.dumps(content), encoding="utf-8")
            with patch("heman_tools.frame_alignment.Path.cwd", return_value=root):
                self.assertEqual(main([
                    "--media", str(paths[0]), "--timing", str(paths[1]),
                    "--contacts", str(paths[2]), "--out", str(paths[3])]), 0)
                result = json.loads(paths[3].read_text())
                self.assertTrue(result[
                    "all_declarative_integrity_and_numeric_checks_met"])
                with self.assertRaisesRegex(ValueError, "must differ"):
                    main(["--media", str(paths[0]), "--timing", str(paths[1]),
                          "--contacts", str(paths[2]), "--out", str(paths[0])])
                with self.assertRaises(ValueError):
                    main(["--media", str(paths[0]), "--timing", str(paths[1]),
                          "--contacts", str(paths[2]),
                          "--out", str(root / "public-summary.json")])


if __name__ == "__main__":
    unittest.main()
