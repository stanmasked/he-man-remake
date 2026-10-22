"""Fictional sequence grammar stratification tests; no original game data."""
from __future__ import annotations

import json
from pathlib import Path
import stat
import struct
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZipFile,ZipInfo

from heman_tools.sprite_sequence_failure_strata import (
    _single_tail_category,_count_group,
    summarize_sequence_firstword_failure_strata,
    audit_private_sequence_firstword_failure_strata,
)
from heman_tools.sprite_repo_wad_index import SCREENS,SpriteIndexFormatError,parse_sprite_repository
from heman_tools.sprite_sequence_header_controls import REPO_PATH,WAD_PATH
from heman_tools.sprite_sequence_cut_name_candidates import CUT_REPO,CUT_WAD
from test_sprite_repo_wad_index import string,repository
from test_sprite_sequence_nested_grammar import (
    CUT_KEYS,invented_sequence,first_cut,make_fake_packs,fake_ipa,
)


def changed_first_word(*, single_screen=False):
    repos,wads,cuts=make_fake_packs()
    for screen in (SCREENS[1],) if single_screen else SCREENS:
        index=parse_sprite_repository(repos[screen],expected_label="SpriteSeqData",expected_wad=WAD_PATH)
        entry=next(e for e in index if e.key=="FakeSingle")
        at=entry.offset+len(string(entry.key))+8
        raw=bytearray(wads[screen]);struct.pack_into("<I",raw,at,2)
        wads[screen]=bytes(raw)
    return repos,wads,cuts


class Stage159FictionalStrataTests(unittest.TestCase):
    def report(self,source=None):
        return summarize_sequence_firstword_failure_strata(*(source or make_fake_packs()))

    def test_synthetic_total_and_firstword_one_strata(self):
        out=self.report()
        self.assertEqual(out["nonzero_unknown_candidate_count_records"],6)
        group=out["grammar_result_by_first_prefix_word"]["first_u32_one"]
        self.assertEqual(list(group.values()),[1,1,3,1])
        self.assertEqual(sum(out["grammar_result_by_first_prefix_word"]["first_u32_other"].values()),0)

    def test_unknown_count_single_double_breakdown(self):
        groups=self.report()["grammar_result_by_unknown_candidate_count_group"]
        self.assertEqual(list(groups["one"].values()),[1,1,1,0])
        self.assertEqual(list(groups["two"].values()),[0,0,2,1])
        for label in ("three_four","five_ten","eleven_plus"):
            self.assertEqual(sum(groups[label].values()),0)

    def test_single_candidate_suffixs_and_missing_candidate(self):
        first=self.report()["single_candidate_initial_name_suffix_motifs_by_first_word"]["first_u32_one"]
        self.assertEqual(first["suffix_64"],1)
        self.assertEqual(first["other_suffix"],1)
        self.assertEqual(first["initial_name_missing"],1)

    def test_firstword_change_moves_group_without_forcing_new_parse(self):
        out=self.report(changed_first_word())
        self.assertEqual(out["grammar_result_by_first_prefix_word"]["first_u32_other"]["exactly_one_complete_candidate_path"],1)
        self.assertEqual(out["single_candidate_initial_name_suffix_motifs_by_first_word"]["first_u32_other"]["suffix_64"],1)
        self.assertFalse(out["first_prefix_word_controls_nested_record_count_verified"])

    def test_tail_162_and_576_classified_separately(self):
        for tail,expect in ((64,"suffix_64"),(162,"suffix_162"),(576,"suffix_576"),(65,"other_suffix")):
            rec=invented_sequence("Artificial",1,first_cut()+b"\xee"*tail)
            pos=len(string("Artificial"))+8+20+13
            with self.subTest(tail=tail):
                self.assertEqual(_single_tail_category(rec,pos,frozenset(CUT_KEYS)),expect)

    def test_unrecognized_cut_name_cannot_be_guessed(self):
        rec=invented_sequence("Artificial",1,first_cut("NotInCut")+b"\xee"*64)
        at=len(string("Artificial"))+8+20+13
        self.assertEqual(_single_tail_category(rec,at,frozenset(CUT_KEYS)),"initial_name_missing")

    def test_unknown_count_bucket_endpoints(self):
        self.assertEqual([_count_group(x) for x in (1,2,3,4,5,10,11,45)],
                         ["one","two","three_four","three_four","five_ten",
                          "five_ten","eleven_plus","eleven_plus"])

    def test_screen_pack_header_disagreement_is_rejected(self):
        with self.assertRaisesRegex(SpriteIndexFormatError,"first remaining field differs"):
            self.report(changed_first_word(single_screen=True))

    def test_modified_cut_index_removes_first_key_matches(self):
        repos,wads,cuts=make_fake_packs()
        for s in SCREENS:
            cuts[s]=repository("SpriteCutData",CUT_WAD,
                ("ChangedA","CutB","CutC","X"*40),(0,30,60,90))
        out=self.report((repos,wads,cuts))
        self.assertGreater(out["grammar_result_by_first_prefix_word"]["first_u32_one"]["no_independent_initial_cut_key"],1)

    def test_corrupt_index_is_rejected(self):
        repos,wads,cuts=make_fake_packs()
        for s in SCREENS:repos[s]+=b"\0"
        with self.assertRaises(SpriteIndexFormatError):
            self.report((repos,wads,cuts))

    def test_output_redacts_artificial_keys(self):
        out=self.report()
        serialized=json.dumps(out)
        for bad in ("FakeDouble","CutA","FakeAmbig","individual_byte_offset_123"):
            self.assertNotIn(bad,serialized)
        for flag in ("source_names_raw_values_offsets_pixels_and_hashes_exported",
                     "automatic_source_sprite_import_to_switch_permitted",
                     "original_sprite_timing_or_animation_playback_verified",
                     "independent_lexical_name_match_counts_as_frame_proof"):
            self.assertFalse(out[flag])

    def test_paired_fake_ipa_integration(self):
        with TemporaryDirectory() as directory:
            f=Path(directory)/"sample.ipa";fake_ipa(f)
            result=audit_private_sequence_firstword_failure_strata(f)
        self.assertEqual(result["nonzero_unknown_candidate_count_records"],6)

    def test_duplicate_zip_member_rejected(self):
        with TemporaryDirectory() as directory:
            f=Path(directory)/"sample.ipa"
            fake_ipa(f,extras=[("Payload/MOTU.app/screen-med/meta/SpriteCutData.repo",b"duplicate")])
            with self.assertRaisesRegex(ValueError,"Duplicate"):
                audit_private_sequence_firstword_failure_strata(f)

    def test_selected_zip_symlink_rejected(self):
        repos,wads,cuts=make_fake_packs()
        with TemporaryDirectory() as directory:
            f=Path(directory)/"sample.ipa"
            with ZipFile(f,"w") as z:
                for screen in SCREENS:
                    prefix=f"Payload/MOTU.app/{screen}/"
                    z.writestr(prefix+REPO_PATH,repos[screen])
                    z.writestr(prefix+CUT_REPO,cuts[screen])
                    link=ZipInfo(prefix+WAD_PATH)
                    link.create_system=3
                    link.external_attr=(stat.S_IFLNK|0o777)<<16
                    z.writestr(link,wads[screen])
            with self.assertRaisesRegex(ValueError,"unsafe selected"):
                audit_private_sequence_firstword_failure_strata(f)

    def test_missing_owner_archive_fails_closed(self):
        with self.assertRaisesRegex(ValueError,"Original owner-private IPA"):
            audit_private_sequence_firstword_failure_strata(
                Path("/not-present/original.ipa"))


if __name__=="__main__":
    unittest.main()
