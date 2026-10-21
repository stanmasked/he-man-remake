"""Only fabricated event descriptors; no source IPA or original map data."""
from __future__ import annotations

import copy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from heman_tools.level11_event_binding_preflight import (
    assess_event_bindings, main,
)


def readiness():
    return {
        "schema_version": 1,
        "intended_level": "original-level-1-1",
        "map_candidate_unique": True,
        "named_collision_layer_unique": True,
        "shape_object_candidates_ambiguous": False,
        "resource_pair_schema_consistent": True,
        "screen_pack_binary_parity_declared": True,
        "manual_checks_declared_complete": True,
        "blockers": ["source_original_ios_gameplay_not_independently_authenticated"],
        "external_original_ios_frames_verified": False,
        "original_map_collision_semantics_verified": False,
        "original_asset_fidelity_verified": False,
        "original_gameplay_physics_verified": False,
        "automatic_collision_export_permitted": False,
        "switch_original_level_import_permitted": False,
    }


def event_manifest():
    return {
        "schema_version": 1,
        "level_key": "original-level-1-1",
        "native_world_event_count": 4,
        "events": [
            {"index": 0, "kind": "HM_TRIGGER"},
            {"index": 1, "kind": "HM_PICKUP"},
            {"index": 2, "kind": "HM_PICKUP"},
            {"index": 3, "kind": "HM_EXIT"},
        ],
        "roles": [
            {"role": "left_gate", "event_index": 0,
             "event_kind": "HM_TRIGGER", "source_contact_verified": False},
            {"role": "skeletor_bio", "event_index": 1,
             "event_kind": "HM_PICKUP", "source_contact_verified": False},
            {"role": "concept_art_09", "event_index": 2,
             "event_kind": "HM_PICKUP", "source_contact_verified": False},
        ],
        "world_coordinate_transform_verified": False,
        "original_collision_semantics_verified": False,
        "ios_capture_contact_timing_verified": False,
        "automatic_gameplay_enable_permitted": False,
    }


class Level11BindingPreflightTests(unittest.TestCase):
    def test_consistent_private_metadata_never_promotes_level(self):
        result = assess_event_bindings(readiness(), event_manifest())
        self.assertTrue(result["native_event_table_consistent"])
        self.assertTrue(result["distinct_correctly_typed_gate_and_lore_roles"])
        self.assertTrue(result["source_readiness_structurally_complete"])
        self.assertFalse(result["switch_original_level_integration_permitted"])
        self.assertFalse(result["automatic_collision_export_permitted"])
        self.assertFalse(result["private_source_contacts_authenticated"])
        self.assertIn("manual_source_review_required", result["blockers"])

    def test_no_private_event_indexes_or_resource_ids_are_exported(self):
        data = json.dumps(assess_event_bindings(readiness(), event_manifest()))
        for item in ('"events"', '"roles"', '"event_index"', "MULevel1-1",
                     "Fictional.map", "sprite", "atlas", "source_sha256"):
            self.assertNotIn(item, data)

    def test_original_readiness_incomplete_never_promotes_level(self):
        r = readiness()
        r["manual_checks_declared_complete"] = False
        out = assess_event_bindings(r, event_manifest())
        self.assertFalse(out["source_readiness_structurally_complete"])
        self.assertIn("stage103_source_readiness_incomplete", out["blockers"])

    def test_source_private_blocker_text_never_reaches_report(self):
        r = readiness()
        r["blockers"] = ["/private/fictional-collision-map.map"]
        self.assertNotIn("private/fictional", json.dumps(
            assess_event_bindings(r, event_manifest())))

    def test_requires_exact_original_level_key(self):
        m = event_manifest()
        m["level_key"] = "another-level"
        with self.assertRaisesRegex(ValueError, "different level"):
            assess_event_bindings(readiness(), m)

    def test_reject_same_lore_event_index(self):
        m = event_manifest()
        m["roles"][2]["event_index"] = 1
        with self.assertRaisesRegex(ValueError, "same event index"):
            assess_event_bindings(readiness(), m)

    def test_reject_different_event_kind_at_role(self):
        m = event_manifest()
        m["roles"][1]["event_index"] = 3
        with self.assertRaisesRegex(ValueError, "does not match"):
            assess_event_bindings(readiness(), m)

    def test_reject_lore_pretending_to_be_trigger(self):
        m = event_manifest()
        m["roles"][2]["event_kind"] = "HM_TRIGGER"
        with self.assertRaisesRegex(ValueError, "does not match"):
            assess_event_bindings(readiness(), m)

    def test_reject_noncontiguous_native_event_table(self):
        m = event_manifest()
        m["events"][2]["index"] = 3
        with self.assertRaisesRegex(ValueError, "contiguous"):
            assess_event_bindings(readiness(), m)

    def test_reject_duplicate_role(self):
        m = event_manifest()
        m["roles"][2]["role"] = "skeletor_bio"
        with self.assertRaisesRegex(ValueError, "duplicate or unknown"):
            assess_event_bindings(readiness(), m)

    def test_reject_incomplete_role_list(self):
        m = event_manifest()
        m["roles"].pop()
        with self.assertRaisesRegex(ValueError, "exactly three"):
            assess_event_bindings(readiness(), m)

    def test_reject_missing_events(self):
        m = event_manifest()
        m["events"].pop()
        with self.assertRaisesRegex(ValueError, "every native world event"):
            assess_event_bindings(readiness(), m)

    def test_reject_out_of_range_or_boolean_indexes(self):
        for bad in (-1, 4, True, 1.0):
            with self.subTest(bad=bad):
                m = event_manifest()
                m["roles"][2]["event_index"] = bad
                with self.assertRaisesRegex(ValueError, "role event index"):
                    assess_event_bindings(readiness(), m)

    def test_reject_wrong_table_count(self):
        m = event_manifest()
        m["native_world_event_count"] = 5
        with self.assertRaisesRegex(ValueError, "every native world event"):
            assess_event_bindings(readiness(), m)

    def test_reject_source_geometry_in_manifest(self):
        m = event_manifest()
        m["events"][1]["x"] = 200.0
        with self.assertRaisesRegex(ValueError, "cannot include geometry"):
            assess_event_bindings(readiness(), m)

    def test_reject_extra_source_filename_key(self):
        m = event_manifest()
        m["source_ipa"] = "He-Man-v2.0.0.ipa"
        with self.assertRaisesRegex(ValueError, "manifest schema"):
            assess_event_bindings(readiness(), m)

    def test_reject_unverified_ownership_assertion(self):
        m = event_manifest()
        m["roles"][0]["source_contact_verified"] = True
        with self.assertRaisesRegex(ValueError, "cannot be asserted"):
            assess_event_bindings(readiness(), m)

    def test_reject_manifest_asserting_verified_gameplay(self):
        for key in (
            "original_collision_semantics_verified",
            "world_coordinate_transform_verified",
            "ios_capture_contact_timing_verified",
            "automatic_gameplay_enable_permitted",
        ):
            with self.subTest(key=key):
                m = event_manifest()
                m[key] = True
                with self.assertRaisesRegex(ValueError, "cannot independently"):
                    assess_event_bindings(readiness(), m)

    def test_reject_upstream_asserting_authentic_ios_physics(self):
        r = readiness()
        r["original_gameplay_physics_verified"] = True
        with self.assertRaisesRegex(ValueError, "cannot grant"):
            assess_event_bindings(r, event_manifest())

    def test_reject_fake_readiness_booleans(self):
        r = readiness()
        r["map_candidate_unique"] = "true"
        with self.assertRaisesRegex(ValueError, "structural flags"):
            assess_event_bindings(r, event_manifest())

    def test_reject_oversized_or_malformed_upstream_blocker_list(self):
        r = readiness()
        r["blockers"] = ["x"] * 65
        with self.assertRaisesRegex(ValueError, "readiness blockers"):
            assess_event_bindings(r, event_manifest())

    def test_cli_inputs_and_output_private_and_redacted(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            private = root / "local_reports"
            private.mkdir()
            rp = private / "readiness.json"
            ev = private / "events.json"
            out = private / "stage109-event-audit.json"
            rp.write_text(json.dumps(readiness()))
            ev.write_text(json.dumps(event_manifest()))
            with patch("heman_tools.frame_alignment.Path.cwd", return_value=root):
                self.assertEqual(main([
                    "--readiness", str(rp), "--events", str(ev),
                    "--out", str(out)]), 0)
            summary = json.loads(out.read_text())
            self.assertTrue(summary["native_event_table_consistent"])
            self.assertFalse(summary["switch_original_level_integration_permitted"])
            self.assertNotIn("roles", summary)
            self.assertNotIn("events", summary)

    def test_cli_rejects_public_output_and_input_reuse(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            private = root / "local_reports"
            private.mkdir()
            rp = private / "readiness.json"
            ev = private / "events.json"
            rp.write_text(json.dumps(readiness()))
            ev.write_text(json.dumps(event_manifest()))
            with patch("heman_tools.frame_alignment.Path.cwd", return_value=root):
                with self.assertRaisesRegex(ValueError, "local_reports"):
                    main(["--readiness", str(rp), "--events", str(ev),
                          "--out", str(root / "public.json")])
                with self.assertRaisesRegex(ValueError, "share paths"):
                    main(["--readiness", str(rp), "--events", str(ev),
                          "--out", str(ev)])

    def test_cli_rejects_edited_manifest_without_creating_report(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            private = root / "local_reports"
            private.mkdir()
            rp = private / "readiness.json"
            ev = private / "events.json"
            out = private / "audit.json"
            rp.write_text(json.dumps(readiness()))
            bad = event_manifest()
            bad["roles"][1]["event_index"] = 0
            ev.write_text(json.dumps(bad))
            with patch("heman_tools.frame_alignment.Path.cwd", return_value=root):
                with self.assertRaisesRegex(ValueError, "does not match"):
                    main(["--readiness", str(rp), "--events", str(ev),
                          "--out", str(out)])
            self.assertFalse(out.exists())


if __name__ == "__main__":
    unittest.main()
