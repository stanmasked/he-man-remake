"""Stage144: entirely fictional framing evidence, never original iOS bytes."""
from __future__ import annotations

import json
import stat
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZipInfo

from heman_tools.physics_tail_model_falsification import (
    complete_variable_width_paths, summarize_variable_tail_hypotheses,
    audit_private_variable_tail_models,
)
from test_physics_records import fixture, record, text16, make_ipa


def two_variable_suffixes():
    return text16("FakeOne") + b"\xff" * 3 + text16("FakeTwo") + b"\xff" * 7


def two_variable_prefixes():
    return b"\xff" * 3 + text16("FakeOne") + b"\xff" * 7 + text16("FakeTwo")


class Stage144FalsificationOnly(unittest.TestCase):
    def test_different_group_padding_lengths_can_have_full_suffix_consumption(self):
        trailer = two_variable_suffixes()
        self.assertGreater(complete_variable_width_paths(trailer, 2), 0)

    def test_different_group_padding_lengths_can_have_full_prefix_consumption(self):
        trailer = two_variable_prefixes()
        self.assertGreater(complete_variable_width_paths(trailer, 2, opaque_first=True), 0)

    def test_zero_only_payload_is_marked_ambiguous_not_decoded(self):
        trailer = bytes(20)
        self.assertEqual(complete_variable_width_paths(trailer, 2), 2)
        self.assertEqual(complete_variable_width_paths(trailer, 2, opaque_first=True), 2)

    def test_corrupt_utf16_never_claims_valid_record(self):
        self.assertEqual(complete_variable_width_paths(b"\xff" * 35, 3), 0)
        self.assertEqual(complete_variable_width_paths(
            b"\xff" * 35, 3, opaque_first=True), 0)

    def test_too_few_bytes_rejected_even_for_large_padding_search(self):
        # Every group requires at least two u16 label-length bytes.
        self.assertEqual(complete_variable_width_paths(b"\0\0", 2), 0)

    def test_too_narrow_padding_window_cannot_accept(self):
        self.assertEqual(
            complete_variable_width_paths(two_variable_suffixes(), 2, max_width=2), 0)
        self.assertGreater(
            complete_variable_width_paths(two_variable_suffixes(), 2, max_width=7), 0)

    def test_one_group_fit_is_explicitly_non_discriminating(self):
        files={"Test.ps2d":fixture(
            [record()], tail_count=1,
            opaque=text16("FakeLabel") + b"\xff"*9)}
        res=summarize_variable_tail_hypotheses(files)
        self.assertEqual(res["single_group_trailers_inherently_weak_evidence"],1)
        self.assertEqual(res["variable_suffix_width_unique_match_files"],1)
        self.assertFalse(res["actual_repeated_item_boundaries_verified"])

    def test_aggregate_reports_failing_fixed_and_matching_variable_models(self):
        files={"Test.ps2d":fixture(
            [record()], tail_count=2,
            opaque=two_variable_suffixes())}
        res=summarize_variable_tail_hypotheses(files)
        self.assertEqual(res["examined_paired_physics_resource_count"],1)
        self.assertEqual(res["declared_unknown_trailer_groups"],2)
        self.assertEqual(res["fixed_width_models_zero_match_files"],1)
        self.assertEqual(res["multi_group_trailers"],1)
        self.assertEqual(res["variable_suffix_width_zero_match_files"],0)
        self.assertFalse(res["a_fitting_model_proves_source_layout"])
        self.assertFalse(res["safe_for_switch_geometry_import"])

    def test_ambiguity_counter_preserved_without_selecting_path(self):
        res=summarize_variable_tail_hypotheses({
            "Fake.ps2d":fixture([record()],tail_count=2,opaque=bytes(20))})
        self.assertEqual(res["variable_suffix_width_ambiguous_match_files"],1)
        self.assertEqual(res["multi_group_variable_suffix_width_ambiguous_files"],1)
        self.assertEqual(res["variable_prefix_width_ambiguous_match_files"],1)
        self.assertTrue(res["all_variable_width_candidate_ways_are_saturated_at_two"])

    def test_fixed_model_can_succeed_without_proving_runtime_layout(self):
        res=summarize_variable_tail_hypotheses({
            "Fake.ps2d":fixture([record()], tail_count=2,
                                opaque=text16("One") + b"\xff"*5
                                + text16("Two") + b"\xff"*5)})
        self.assertGreaterEqual(
            res["fixed_width_models_unique_match_files"] +
            res["fixed_width_models_ambiguous_match_files"],1)
        self.assertFalse(res["original_level_shape_binding_verified"])

    def test_source_identifiers_and_padding_are_not_in_report(self):
        serial=json.dumps(summarize_variable_tail_hypotheses({
            "TopSecretActor.ps2d":fixture(
                [record()],tail_count=2,opaque=two_variable_suffixes())}))
        for private in ("TopSecretActor","FakeOne","FakeTwo","ff ff",
                        "original_shape_name","0xff"):
            self.assertNotIn(private,serial)

    def test_invalid_parameters_are_rejected(self):
        for count in (0,-1,513,True,2.0):
            with self.subTest(count=count), self.assertRaises(ValueError):
                complete_variable_width_paths(b"\0\0",count)
        for width in (-1,97,True,2.1):
            with self.subTest(width=width), self.assertRaises(ValueError):
                complete_variable_width_paths(b"\0\0",1,max_width=width)
        for payload in (b"",b"\0"*8193,"bad"):
            with self.subTest(payload=type(payload).__name__), self.assertRaises(ValueError):
                complete_variable_width_paths(payload,1)

    def test_malformed_original_envelope_fails_closed(self):
        with self.assertRaises(ValueError):
            summarize_variable_tail_hypotheses({"Fake.ps2d":b"\xff"*60})

    def test_synthetic_zip_integration_paired_resources(self):
        with TemporaryDirectory() as tmp:
            path=Path(tmp)/"fake.ipa"
            make_ipa(path)
            output=audit_private_variable_tail_models(path)
        self.assertEqual(output["examined_paired_physics_resource_count"],2)
        self.assertEqual(output["nonempty_trailer_count"],1)
        self.assertEqual(output["declared_unknown_trailer_groups"],2)
        self.assertFalse(output["source_original_physics_fidelity_verified"])

    def test_original_archive_missing_fails_closed(self):
        with self.assertRaisesRegex(ValueError,"Owner-private original IPA not found"):
            audit_private_variable_tail_models(Path("/missing/owner-private.ipa"))

    def test_source_duplicate_zip_member_rejected(self):
        with TemporaryDirectory() as tmp:
            path=Path(tmp)/"fake.ipa"
            make_ipa(path,extra=[(
                "Payload/MOTU.app/screen-med/physics_struct/FakeActor.ps2d",
                fixture([record()]))])
            with self.assertRaisesRegex(ValueError,"Duplicate"):
                audit_private_variable_tail_models(path)

    def test_cross_pack_different_bytes_rejected(self):
        with TemporaryDirectory() as tmp:
            path=Path(tmp)/"fake.ipa"
            make_ipa(path,change_large=True)
            with self.assertRaisesRegex(ValueError,"bytes differ"):
                audit_private_variable_tail_models(path)

    def test_paired_symlinks_rejected(self):
        with TemporaryDirectory() as tmp:
            path=Path(tmp)/"fake.ipa"
            extra=[]
            for screen in ("screen-med","screen-xlarge"):
                info=ZipInfo(f"Payload/MOTU.app/{screen}/physics_struct/Link.ps2d")
                info.create_system=3
                info.external_attr=(stat.S_IFLNK|0o777)<<16
                extra.append((info,b"relative"))
            make_ipa(path,extra=extra)
            with self.assertRaisesRegex(ValueError,"unsafe selected"):
                audit_private_variable_tail_models(path)


if __name__ == "__main__":
    unittest.main()
