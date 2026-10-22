"""Stage158: entirely fabricated sequence/cut-name grammar and ZIP tests."""
from __future__ import annotations

import json
from pathlib import Path
import stat
import struct
from tempfile import TemporaryDirectory
import unittest
import warnings
from zipfile import ZipFile, ZipInfo

from heman_tools.sprite_sequence_nested_grammar import (
    MODEL_WIDTHS, count_complete_name_paths,
    summarize_nested_sequence_grammar_controls,
    audit_private_nested_sequence_grammar,
)
from heman_tools.sprite_repo_wad_index import SCREENS, SpriteIndexFormatError
from heman_tools.sprite_sequence_header_controls import REPO_PATH, WAD_PATH
from heman_tools.sprite_sequence_cut_name_candidates import CUT_REPO, CUT_WAD
from test_sprite_repo_wad_index import repository, string


CUT_KEYS = ("CutA", "CutB", "CutC", "X"*40)
_INITIAL = struct.pack("<5I", 1, 0, 0, 0, 0) + b"\xa7"*13


def invented_sequence(name, count, payload, ending=0):
    return string(name)+struct.pack("<II",0,count)+(
        _INITIAL + payload if count else b""
    )+struct.pack("<I",ending)


def first_cut(label="CutA"):
    return string(label)


def make_fake_packs(*, alternate_pack=False):
    rows = (
        ("FakeEmpty", 0, b""),
        ("FakeSingle", 1, first_cut()+b"\xfe"*64),
        ("FakeDouble", 2, first_cut()+b"\xfe"*64+b"\xcc"*12+
         first_cut("CutB")+b"\xee"*64),
        ("FakeExtra", 2, first_cut()+b"\xfe"*(64+82)+b"\xcc"*33+
         first_cut("CutC")+b"\xee"*(64+82)),
        ("FakeReject", 1, first_cut()+b"\xfe"*65),
        ("FakeMissing", 1, first_cut("Unknown")+b"\xfe"*64),
        ("FakeAmbig", 2, first_cut()+b"\xfe"*64+b"\xcc"*12+
         first_cut("X"*40)+first_cut("X"*40)+b"\xee"*64),
    )
    repos, wads, cuts = {}, {}, {}
    for screen in SCREENS:
        cursor=0
        offsets=[]
        blobs=[]
        for name,count,payload in rows:
            original=invented_sequence(name,count,payload)
            if alternate_pack and screen==SCREENS[1] and name=="FakeDouble":
                original=original.replace(string("CutB"),string("Nutz"))
            offsets.append(cursor)
            blobs.append(original)
            cursor+=len(original)
        repos[screen]=repository(
            "SpriteSeqData",WAD_PATH,
            tuple(row[0] for row in rows),tuple(offsets)
        )
        wads[screen]=b"".join(blobs)
        cuts[screen]=repository(
            "SpriteCutData",CUT_WAD,CUT_KEYS,(0,30,60,90)
        )
    return repos,wads,cuts


def fake_ipa(path, *, alternate_pack=False, extras=()):
    repos,wads,cuts=make_fake_packs(alternate_pack=alternate_pack)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore",UserWarning)
        with ZipFile(path,"w") as archive:
            for screen in SCREENS:
                prefix=f"Payload/MOTU.app/{screen}/"
                archive.writestr(prefix+REPO_PATH,repos[screen])
                archive.writestr(prefix+WAD_PATH,wads[screen])
                archive.writestr(prefix+CUT_REPO,cuts[screen])
            for name,raw in extras:
                archive.writestr(name,raw)


class Stage158NestedCandidateGrammarTests(unittest.TestCase):
    def summarize(self,source=None):
        return summarize_nested_sequence_grammar_controls(
            *(source or make_fake_packs()))

    def classify(self,label,count,payload,*,base=64,step=82):
        return count_complete_name_paths(
            invented_sequence(label,count,payload),
            count,frozenset(CUT_KEYS),
            terminal_base=base,step_bytes=step)

    def test_one_token_with_exact_64_byte_terminal_tail(self):
        self.assertEqual(self.classify("One",1,first_cut()+b"\xee"*64),1)

    def test_one_token_with_additional_82_byte_tail(self):
        self.assertEqual(self.classify("One",1,first_cut()+b"\xee"*146),1)

    def test_two_tokens_with_short_12_byte_extra_preamble(self):
        payload=first_cut()+b"\xfe"*64+b"\xcc"*12+first_cut("CutB")+b"\xee"*64
        self.assertEqual(self.classify("Two",2,payload),1)

    def test_two_tokens_with_alternative_33_byte_extra_preamble(self):
        payload=first_cut()+b"\xfe"*146+b"\xcc"*33+first_cut("CutC")+b"\xee"*146
        self.assertEqual(self.classify("Two",2,payload),1)

    def test_one_extra_byte_invalidates_exact_eof(self):
        self.assertEqual(self.classify("One",1,first_cut()+b"\xee"*65),0)

    def test_absent_first_cut_name_is_separate_category(self):
        self.assertEqual(self.classify("One",1,first_cut("Unknown")+b"\xee"*64),-1)

    def test_two_plausible_paths_remain_ambiguous(self):
        payload=(first_cut()+b"\xfe"*64+b"\xcc"*12+
                 first_cut("X"*40)+first_cut("X"*40)+b"\xee"*64)
        self.assertEqual(self.classify("Two",2,payload),2)

    def test_declared_group_count_must_match_header(self):
        with self.assertRaisesRegex(SpriteIndexFormatError,"count disagrees"):
            count_complete_name_paths(
                invented_sequence("One",1,first_cut()+b"\xee"*64),
                2,frozenset(CUT_KEYS))

    def test_predeclared_one_byte_negative_controls_falsify(self):
        payload=first_cut()+b"\xee"*64
        self.assertEqual(self.classify("One",1,payload,base=63),0)
        self.assertEqual(self.classify("One",1,payload,base=65),0)

    def test_stride_controls_are_not_assumed_discriminative(self):
        payload=first_cut()+b"\xee"*64
        self.assertEqual(self.classify("One",1,payload,step=80),1)
        self.assertEqual(self.classify("One",1,payload,step=84),1)

    def test_full_synthetic_7_sequence_census(self):
        report=self.summarize()
        self.assertEqual(report["nonzero_sequence_records"],6)
        self.assertEqual(report["independent_cut_registry_entries"],4)
        case=report["hypotheses_and_negative_controls"]["hypothesis_64_82"]
        self.assertEqual(case["source_records_without_matching_initial_cut_key"],1)
        self.assertEqual(case["source_records_with_first_key_but_no_exact_EOF_parse"],1)
        self.assertEqual(case["source_records_with_exactly_one_complete_parse"],3)
        self.assertEqual(case["source_records_with_multiple_complete_parses"],1)

    def test_predeclared_width_controls_all_present(self):
        report=self.summarize()
        self.assertEqual(set(report["hypotheses_and_negative_controls"]),
                         {label for label,_,_ in MODEL_WIDTHS})
        self.assertTrue(report["identical_model_classification_across_both_screen_packs"])

    def test_invalid_cut_key_content_rejected(self):
        for keyset in (frozenset(),frozenset(("",)),frozenset((7,))):
            with self.subTest(keys=keyset),self.assertRaises(ValueError):
                count_complete_name_paths(
                    invented_sequence("One",1,first_cut()+b"\xee"*64),
                    1,keyset)

    def test_invalid_record_or_model_bounds_fail_closed(self):
        for raw,count,base,step in (
            (b"",1,64,82),("not bytes",1,64,82),
            (invented_sequence("One",1,first_cut()+b"\xee"*64),0,64,82),
            (invented_sequence("One",1,first_cut()+b"\xee"*64),46,64,82),
            (invented_sequence("One",1,first_cut()+b"\xee"*64),True,64,82),
            (invented_sequence("One",1,first_cut()+b"\xee"*64),1,129,82),
            (invented_sequence("One",1,first_cut()+b"\xee"*64),1,64,0),
        ):
            with self.subTest(count=count,base=base,step=step),self.assertRaises(ValueError):
                count_complete_name_paths(raw,count,frozenset(CUT_KEYS),
                                          terminal_base=base,step_bytes=step)

    def test_cross_pack_nested_candidate_divergence_rejected(self):
        with self.assertRaisesRegex(SpriteIndexFormatError,
                                    "Nested candidate grammar differs"):
            self.summarize(make_fake_packs(alternate_pack=True))

    def test_structural_source_packs_remain_resolution_specific_safe(self):
        repos,wads,cuts=make_fake_packs()
        wads[SCREENS[1]]=wads[SCREENS[1]].replace(
            b"\xfe"*64,b"\xfa"*64
        )
        r=self.summarize((repos,wads,cuts))
        self.assertEqual(
            r["hypotheses_and_negative_controls"]["hypothesis_64_82"][
                "source_records_with_exactly_one_complete_parse"],3
        )

    def test_different_cut_registry_invalidates_matching_path(self):
        repos,wads,cuts=make_fake_packs()
        for screen in SCREENS:
            cuts[screen]=repository(
                "SpriteCutData",CUT_WAD,
                ("ChangedA","CutB","CutC","X"*40),(0,30,60,90))
        report=self.summarize((repos,wads,cuts))
        self.assertEqual(report["source_cut_name_candidate_at_first_nested_position"],0)

    def test_aggregate_json_contains_no_original_like_strings(self):
        report=self.summarize()
        rendered=json.dumps(report)
        for forbidden in (
            "FakeSingle","FakeDouble","FakeExtra","FakeAmbig","CutA",
            "CutB","Unknown","per_original_record_offset_100"
        ):
            self.assertNotIn(forbidden,rendered)
        self.assertFalse(report["private_source_keys_offsets_payloads_and_paths_in_report"])
        self.assertFalse(report["original_asset_import_to_switch_enabled"])
        self.assertFalse(report["source_unknown_count_proven_frame_count"])

    def test_synthetic_ipa_integration_without_original_assets(self):
        with TemporaryDirectory() as directory:
            ipa=Path(directory)/"fabricated.ipa"
            fake_ipa(ipa)
            result=audit_private_nested_sequence_grammar(ipa)
        self.assertEqual(result["nonzero_sequence_records"],6)

    def test_duplicate_zip_member_fails_closed(self):
        with TemporaryDirectory() as directory:
            ipa=Path(directory)/"fabricated.ipa"
            fake_ipa(ipa,extras=[(
                "Payload/MOTU.app/screen-med/meta/SpriteSeqData.repo",
                b"fabricated duplicate")])
            with self.assertRaisesRegex(ValueError,"Duplicate"):
                audit_private_nested_sequence_grammar(ipa)

    def test_selected_cut_repo_symlink_fails_closed(self):
        repos,wads,cuts=make_fake_packs()
        with TemporaryDirectory() as directory:
            ipa=Path(directory)/"fabricated.ipa"
            with ZipFile(ipa,"w") as archive:
                for screen in SCREENS:
                    prefix=f"Payload/MOTU.app/{screen}/"
                    archive.writestr(prefix+REPO_PATH,repos[screen])
                    archive.writestr(prefix+WAD_PATH,wads[screen])
                    info=ZipInfo(prefix+CUT_REPO)
                    info.create_system=3
                    info.external_attr=(stat.S_IFLNK|0o777)<<16
                    archive.writestr(info,cuts[screen])
            with self.assertRaisesRegex(ValueError,"unsafe selected"):
                audit_private_nested_sequence_grammar(ipa)

    def test_owner_private_ipa_missing_fails_closed(self):
        with self.assertRaisesRegex(ValueError,"Owner-private original IPA missing"):
            audit_private_nested_sequence_grammar(Path("/not-present/owner-source.ipa"))


if __name__=="__main__":
    unittest.main()
