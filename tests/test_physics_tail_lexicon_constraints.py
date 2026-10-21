"""Stage145: invented UTF-16 trailer tokens and source-free shape fixtures only."""
from __future__ import annotations

import json
from pathlib import Path
import stat
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZipInfo

from heman_tools.physics_tail_lexicon_constraints import (
    lexically_constrained_paths, summarize_lexicon_restrictions,
    audit_private_tail_lexicons,
)
from test_physics_records import fixture, record, text16, make_ipa
from test_shapes import circle, polygon


def fake_data(token="FakeShape"):
    return {
        "FakeActor.ps2d": fixture(
            [record("FakeLabel",names=("FakeShape",))],
            tail_count=1, opaque=text16(token)+b"\xff"*5),
        "FakeOther.pstruct2d": fixture(
            [record("FakeOtherLabel",names=("FakeShape",))]),
    }


class Stage145LexicalConstraintsTests(unittest.TestCase):
    def test_source_label_constraint_accepts_exact_two_record_tokens(self):
        original=(text16("First")+b"\xff"*3
                  +text16("Second")+b"\xfd"*7)
        count=lexically_constrained_paths(
            original,2,frozenset(("First","Second")))
        self.assertGreaterEqual(count,1)

    def test_source_label_constraint_rejects_unseen_token(self):
        original=(text16("First")+b"\xff"*3
                  +text16("Second")+b"\xfd"*7)
        self.assertEqual(lexically_constrained_paths(
            original,2,frozenset(("First",))),0)

    def test_source_shape_lexicon_mismatch_rejects_candidate(self):
        original=text16("PrivateSourceName")+b"\xff"*4
        self.assertEqual(lexically_constrained_paths(
            original,1,frozenset(("UnrelatedShape",))),0)

    def test_one_group_lexical_match_not_physics_proof(self):
        found=lexically_constrained_paths(
            text16("Known")+b"\xff"*5,1,frozenset(("Known",)))
        self.assertEqual(found,1)

    def test_empty_main_label_is_modeled_separately(self):
        original=text16("")+b"\xff"*8
        self.assertEqual(lexically_constrained_paths(
            original,1,frozenset(("",))),1)
        self.assertEqual(lexically_constrained_paths(
            original,1,frozenset(("Known",))),0)

    def test_ambiguous_null_bytes_saturate_at_two(self):
        original=bytes(20)
        self.assertEqual(lexically_constrained_paths(
            original,2,frozenset(("",))),2)

    def test_utf16_without_correct_u16_prefix_rejected(self):
        original="Exact".encode("utf-16le")+b"\xff"*4
        self.assertEqual(lexically_constrained_paths(
            original,1,frozenset(("Exact",))),0)

    def test_corrupted_utf16_surrogate_rejected(self):
        original=b"\x01\x00\x00\xd8"+b"\xff"*7
        self.assertEqual(lexically_constrained_paths(
            original,1,frozenset(("\ud83d",))),0)

    def test_short_or_extra_bytes_fail_when_no_full_exact_parse(self):
        original=text16("Known")+b"\xff"*5
        allowed=frozenset(("Known",))
        self.assertEqual(lexically_constrained_paths(
            original,1,allowed,max_padding=4),0)
        self.assertEqual(lexically_constrained_paths(
            original+b"\xfe",1,allowed,max_padding=5),0)

    def test_invalid_candidate_bounds_fail_closed(self):
        for source,count,vocabulary,width in (
            (b"",1,frozenset(("Known",)),0),
            (bytes(1025),1,frozenset(("Known",)),0),
            ("bad",1,frozenset(("Known",)),0),
            (bytes(4),0,frozenset(("Known",)),0),
            (bytes(4),65,frozenset(("Known",)),0),
            (bytes(4),True,frozenset(("Known",)),0),
            (bytes(4),1,{"Known"},0),
            (bytes(4),1,frozenset((3,)),0),
            (bytes(4),1,frozenset(("Known",)),97),
        ):
            with self.subTest(count=count,width=width), self.assertRaises(ValueError):
                lexically_constrained_paths(source,count,vocabulary,max_padding=width)

    def test_empty_lexicon_has_zero_paths(self):
        self.assertEqual(lexically_constrained_paths(
            text16("Known"),1,frozenset()),0)

    def test_aggregate_source_reference_vocab_but_not_level_ownership(self):
        result=summarize_lexicon_restrictions(
            fake_data("FakeShape"),
            {"FakeShape.shape":circle(), "Other.shape":polygon()})
        self.assertEqual(result["source_physics_file_count"],2)
        self.assertEqual(result["source_shape_file_count"],2)
        self.assertEqual(result["nonempty_trailer_file_count"],1)
        self.assertEqual(result["main_record_shape_reference_strings_one_complete_parse"],1)
        self.assertEqual(result["validated_shape_file_stems_one_complete_parse"],1)
        self.assertEqual(result["nonempty_main_record_labels_no_complete_parses"],1)
        self.assertFalse(result["lexical_shape_references_prove_runtime_links"])
        self.assertFalse(result["allow_switch_original_geometry_import"])

    def test_aggregate_named_labels_and_shape_disagreement(self):
        result=summarize_lexicon_restrictions(
            fake_data("FakeLabel"),
            {"FakeShape.shape":circle()})
        self.assertEqual(result["nonempty_main_record_labels_one_complete_parse"],1)
        self.assertEqual(result["validated_shape_file_stems_no_complete_parses"],1)

    def test_aggregates_never_expose_original_strings_or_file_names(self):
        report=json.dumps(summarize_lexicon_restrictions(
            fake_data("TopSecretTail"),
            {"FakeShape.shape":circle()}))
        for forbidden in ("FakeActor","FakeOther","FakeShape","TopSecretTail",
                          "FakeLabel","TopSecret","opaque_payload","geometry/"):
            self.assertNotIn(forbidden,report)

    def test_source_envelope_corruption_is_rejected(self):
        fake={"Bad.ps2d":fixture([record()],tail_count=1,
                                  opaque=text16("Known")+b"\xff")[:-4]}
        with self.assertRaises(ValueError):
            summarize_lexicon_restrictions(fake,{"Known.shape":circle()})

    def test_unparsed_shape_is_rejected(self):
        with self.assertRaises(ValueError):
            summarize_lexicon_restrictions(
                fake_data(),
                {"FakeShape.shape":b"invalid original shape bytes"})

    def test_private_ipa_missing_fails_closed(self):
        with self.assertRaisesRegex(ValueError,"Original private source archive missing"):
            audit_private_tail_lexicons(Path("/not-found/original-owner.ipa"))

    def test_synthetic_paired_ipa_integration(self):
        with TemporaryDirectory() as directory:
            path=Path(directory)/"fictional.ipa"
            make_ipa(path)
            result=audit_private_tail_lexicons(path)
        self.assertEqual(result["source_physics_file_count"],2)
        self.assertEqual(result["source_shape_file_count"],2)
        self.assertEqual(result["nonempty_trailer_file_count"],1)
        self.assertFalse(result["a_unique_candidate_proves_record_boundaries"])

    def test_cross_pack_divergence_and_duplicate_rejected(self):
        with TemporaryDirectory() as directory:
            path=Path(directory)/"fictional.ipa"
            make_ipa(path,change_large=True)
            with self.assertRaisesRegex(ValueError,"bytes differ"):
                audit_private_tail_lexicons(path)
            make_ipa(path,extra=[(
                "Payload/MOTU.app/screen-med/physics_struct/FakeActor.ps2d",
                fixture([record()]))])
            with self.assertRaisesRegex(ValueError,"Duplicate"):
                audit_private_tail_lexicons(path)

    def test_symlinked_member_rejected(self):
        with TemporaryDirectory() as directory:
            path=Path(directory)/"fictional.ipa"
            entries=[]
            for pack in ("screen-med","screen-xlarge"):
                info=ZipInfo(
                    f"Payload/MOTU.app/{pack}/physics_struct/Link.ps2d")
                info.create_system=3
                info.external_attr=(stat.S_IFLNK|0o777)<<16
                entries.append((info,b"relative"))
            make_ipa(path,extra=entries)
            with self.assertRaisesRegex(ValueError,"unsafe selected"):
                audit_private_tail_lexicons(path)


if __name__=="__main__":
    unittest.main()
