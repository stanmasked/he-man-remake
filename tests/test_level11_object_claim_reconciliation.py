"""Purely fictional files: test private evidence integrity, NEVER original IPA."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from heman_tools.level11_object_claim_reconciliation import (
    assess_private_correspondence, main,
)
from test_level11_event_binding_preflight import (
    readiness, event_manifest,
)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def make_claims(root: Path) -> tuple[dict, dict]:
    roles = ("left_gate", "skeletor_bio", "concept_art_09")
    result = []
    (root / "fictional_receipts").mkdir(exist_ok=True)
    for channel in ("resource_candidate", "observation_annotation"):
        claims = []
        for role, index in zip(roles, (0, 1, 2)):
            # A separate fake receipt file for each assertion, verified
            # by the real hashlib implementation in the source CLI.
            filename = f"fictional_receipts/{channel}-{role}.bin"
            raw = f"fictional/{channel}/{role}/v1".encode()
            (root / filename).write_bytes(raw)
            claims.append({
                "role": role,
                "native_event_index": index,
                "source_object_digest": digest(f"fictional-object/{role}".encode()),
                "artifact_file": filename,
                "artifact_sha256": digest(raw),
                "original_contact_verified": False,
            })
        result.append({
            "schema_version": 1,
            "level_key": "original-level-1-1",
            "channel": channel,
            "claims": claims,
            "original_ios_provenance_authenticated": False,
            "automatic_event_bindings_permitted": False,
        })
    return result[0], result[1]


class LocalPrivateObjectClaimsTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.cwd = Path(self.temporary.name)
        self.root = self.cwd / "local_reports"
        self.root.mkdir()
        self.resource, self.observation = make_claims(self.root)
        self.readiness = readiness()
        self.events = event_manifest()

    def audit(self):
        return assess_private_correspondence(
            self.readiness, self.events,
            self.resource, self.observation, self.root,
        )

    def test_all_six_real_checksums_match_synthetic_receipts(self):
        out = self.audit()
        self.assertTrue(out["stage109_event_role_types_consistent"])
        self.assertTrue(out["private_claim_channels_structurally_consistent"])
        self.assertEqual(out["local_evidence_artifacts_integrity_checked"], 6)
        self.assertEqual(out["distinct_matching_object_claims"], 3)

    def test_even_matching_local_evidence_never_authorizes_original_source(self):
        out = self.audit()
        self.assertFalse(out["original_ios_source_object_ownership_authenticated"])
        self.assertFalse(out["original_ios_contact_timing_authenticated"])
        self.assertFalse(out["original_geometry_verified"])
        self.assertFalse(out["automatic_collision_export_permitted"])
        self.assertFalse(out["switch_original_level_integration_permitted"])

    def test_redacted_report_has_no_private_ids_indices_or_paths(self):
        text = json.dumps(self.audit())
        for item in (
            "fictional_receipts", "source_object_digest",
            "artifact_sha256", "artifact_file",
            "native_event_index", "left_gate",
            "skeletor_bio", "concept_art_09",
            "MULevel1-1", "He-Man-v2.0.0.ipa",
        ):
            self.assertNotIn(item, text)

    def test_swap_same_kind_lore_indices_in_observation_fails(self):
        records = self.observation["claims"]
        records[1]["native_event_index"], records[2]["native_event_index"] = (
            records[2]["native_event_index"], records[1]["native_event_index"])
        with self.assertRaisesRegex(ValueError, "Stage109 native event mapping"):
            self.audit()

    def test_swap_object_fingerprints_between_lore_records_fails(self):
        records = self.observation["claims"]
        records[1]["source_object_digest"], records[2]["source_object_digest"] = (
            records[2]["source_object_digest"], records[1]["source_object_digest"])
        with self.assertRaisesRegex(ValueError, "identities disagree"):
            self.audit()

    def test_two_different_lore_roles_cannot_share_source_object_id(self):
        self.resource["claims"][1]["source_object_digest"] = (
            self.resource["claims"][2]["source_object_digest"])
        with self.assertRaisesRegex(ValueError, "must be unique"):
            self.audit()

    def test_same_evidence_path_across_channels_forbidden(self):
        record = self.observation["claims"][1]
        record["artifact_file"] = self.resource["claims"][1]["artifact_file"]
        record["artifact_sha256"] = self.resource["claims"][1]["artifact_sha256"]
        with self.assertRaisesRegex(ValueError, "artifact reused"):
            self.audit()

    def test_different_file_with_identical_bytes_is_not_independent_evidence(self):
        resource = self.resource["claims"][1]
        observation = self.observation["claims"][1]
        data = (self.root / resource["artifact_file"]).read_bytes()
        (self.root / observation["artifact_file"]).write_bytes(data)
        observation["artifact_sha256"] = digest(data)
        with self.assertRaisesRegex(ValueError, "identical evidence bytes"):
            self.audit()

    def test_changed_real_receipt_bytes_detected(self):
        entry = self.observation["claims"][0]
        (self.root / entry["artifact_file"]).write_bytes(b"fictional/tampered")
        with self.assertRaisesRegex(ValueError, "checksum mismatch"):
            self.audit()

    def test_wrong_checksum_declared_detected(self):
        self.resource["claims"][0]["artifact_sha256"] = "1" * 64
        with self.assertRaisesRegex(ValueError, "checksum mismatch"):
            self.audit()

    def test_invalid_nonhex_or_zero_sha_rejected(self):
        for value in ("g" * 64, "0" * 64, "A" * 64, "abcd", True):
            with self.subTest(value=value):
                self.resource["claims"][0]["source_object_digest"] = value
                with self.assertRaisesRegex(ValueError, "SHA-256"):
                    self.audit()

    def test_unknown_role_rejected(self):
        self.observation["claims"][2]["role"] = "made_up"
        with self.assertRaisesRegex(ValueError, "unknown object role"):
            self.audit()

    def test_duplicate_role_rejected(self):
        self.observation["claims"][2]["role"] = "skeletor_bio"
        with self.assertRaisesRegex(ValueError, "duplicate"):
            self.audit()

    def test_wrong_native_role_kind_rejected_before_receipt_scan(self):
        self.events["events"][2]["kind"] = "HM_TRIGGER"
        with self.assertRaisesRegex(ValueError, "does not match"):
            self.audit()

    def test_wrong_original_level_id_rejected(self):
        self.observation["level_key"] = "not-level-1-1"
        with self.assertRaisesRegex(ValueError, "different level|wrong original level"):
            self.audit()

    def test_source_channel_mislabeled_rejected(self):
        self.observation["channel"] = "resource_candidate"
        with self.assertRaisesRegex(ValueError, "evidence channel"):
            self.audit()

    def test_asserting_ios_capture_authenticity_rejected(self):
        self.observation["original_ios_provenance_authenticated"] = True
        with self.assertRaisesRegex(ValueError, "cannot assert original-source"):
            self.audit()

    def test_asserting_c99_binding_release_permission_rejected(self):
        self.resource["automatic_event_bindings_permitted"] = True
        with self.assertRaisesRegex(ValueError, "cannot assert original-source"):
            self.audit()

    def test_claimed_original_contact_verified_rejected(self):
        self.observation["claims"][0]["original_contact_verified"] = True
        with self.assertRaisesRegex(ValueError, "cannot be asserted"):
            self.audit()

    def test_source_geometry_extra_field_rejected(self):
        self.resource["claims"][1]["x"] = 128.0
        with self.assertRaisesRegex(ValueError, "forbidden or missing"):
            self.audit()

    def test_path_traversal_rejected(self):
        self.resource["claims"][0]["artifact_file"] = "../private-video.png"
        with self.assertRaisesRegex(ValueError, "traversal"):
            self.audit()

    def test_absolute_path_rejected(self):
        self.resource["claims"][0]["artifact_file"] = "/tmp/fake.png"
        with self.assertRaisesRegex(ValueError, "path is invalid"):
            self.audit()

    def test_symlink_to_external_source_rejected(self):
        target = self.cwd / "private_external.bin"
        target.write_bytes(b"Fictional file outside local reports")
        link = self.root / "fictional_receipts" / "out.bin"
        link.symlink_to(target)
        self.resource["claims"][0]["artifact_file"] = "fictional_receipts/out.bin"
        with self.assertRaisesRegex(ValueError, "symlink"):
            self.audit()

    def test_missing_artifact_rejected(self):
        self.resource["claims"][0]["artifact_file"] = "fictional_receipts/missing.bin"
        with self.assertRaisesRegex(ValueError, "missing or exceeds"):
            self.audit()

    def test_empty_artifact_rejected(self):
        record = self.resource["claims"][0]
        (self.root / record["artifact_file"]).write_bytes(b"")
        record["artifact_sha256"] = digest(b"")
        with self.assertRaisesRegex(ValueError, "missing or exceeds"):
            self.audit()

    def test_oversized_artifact_rejected_with_bounded_limit(self):
        record = self.resource["claims"][0]
        (self.root / record["artifact_file"]).write_bytes(b"5 bytes")
        with patch("heman_tools.level11_object_claim_reconciliation.MAX_EVIDENCE_BYTES", 5):
            with self.assertRaisesRegex(ValueError, "missing or exceeds"):
                self.audit()

    def test_source_readiness_attested_true_rejected(self):
        self.readiness["original_gameplay_physics_verified"] = True
        with self.assertRaisesRegex(ValueError, "cannot grant iOS authority"):
            self.audit()

    def test_incomplete_source_evidence_remains_blocked_even_if_claims_agree(self):
        self.readiness["manual_checks_declared_complete"] = False
        out = self.audit()
        self.assertFalse(out["source_readiness_structurally_complete"])
        self.assertFalse(out["switch_original_level_integration_permitted"])

    def test_cli_private_only_and_redacted(self):
        rp = self.root / "readiness.json"
        ep = self.root / "native-events.json"
        resource = self.root / "resource-claims.json"
        observation = self.root / "observations.json"
        out = self.root / "stage110-redacted-report.json"
        for path, item in (
            (rp, self.readiness), (ep, self.events),
            (resource, self.resource), (observation, self.observation),
        ):
            path.write_text(json.dumps(item))
        args = [
            "--readiness", str(rp), "--native", str(ep),
            "--resource", str(resource), "--observation", str(observation),
            "--out", str(out),
        ]
        with patch("heman_tools.frame_alignment.Path.cwd", return_value=self.cwd):
            self.assertEqual(main(args), 0)
        self.assertEqual(json.loads(out.read_text())["local_evidence_artifacts_integrity_checked"], 6)
        self.assertNotIn("source_object_digest", out.read_text())
        self.assertNotIn("fictional_receipts", out.read_text())

    def test_cli_rejects_public_output_path(self):
        rp = self.root / "readiness.json"
        ep = self.root / "native.json"
        resource = self.root / "resource.json"
        observation = self.root / "observation.json"
        for path, item in ((rp, self.readiness), (ep, self.events),
                           (resource, self.resource), (observation, self.observation)):
            path.write_text(json.dumps(item))
        args = [
            "--readiness", str(rp), "--native", str(ep),
            "--resource", str(resource), "--observation", str(observation),
        ]
        with patch("heman_tools.frame_alignment.Path.cwd", return_value=self.cwd):
            with self.assertRaisesRegex(ValueError, "local_reports"):
                main(args + ["--out", str(self.cwd / "public.json")])
            with self.assertRaisesRegex(ValueError, "cannot share paths"):
                main(args + ["--out", str(resource)])
