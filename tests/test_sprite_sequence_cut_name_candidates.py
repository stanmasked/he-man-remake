"""Stage157: fictional sprite reference names, no commercial game data."""
from __future__ import annotations

import json
import stat
import struct
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import warnings
from zipfile import ZipFile,ZipInfo

from heman_tools.sprite_sequence_cut_name_candidates import (
    CANDIDATE_OFFSET,TEST_OFFSETS,CUT_REPO,
    summarize_sequence_cut_name_candidates,
    audit_private_sequence_cut_name_candidates,
)
from heman_tools.sprite_sequence_header_controls import REPO_PATH,WAD_PATH
from heman_tools.sprite_repo_wad_index import (
    SCREENS,SpriteIndexFormatError,parse_sprite_repository,
)
from test_sprite_repo_wad_index import repository,string


FAKE_SEQ_NAMES=(
    "SeqZero","SeqMatched","SeqShared","SeqUnknown","SeqEmpty","SeqShort"
)
CUT_KEYS=("CutLinkedA","SeqShared","OtherInventedCut")


def artificial_sources(*, change_nested_pack=False):
    repos={}
    wads={}
    cuts={}
    for screen in SCREENS:
        records=[]
        offsets=[]
        cursor=0
        for seqname in FAKE_SEQ_NAMES:
            if seqname=="SeqZero":
                data=struct.pack("<I",0)
                count=0
            else:
                count=1
                five_words=struct.pack("<5I",2,0,7,0,0)
                if seqname=="SeqMatched":
                    nested=b"\x98"*13+string("CutLinkedA")+b"synthetic"
                elif seqname=="SeqShared":
                    nested=b"\x98"*13+string("SeqShared")+b"synthetic"
                elif seqname=="SeqUnknown":
                    nested=b"\x98"*13+string("AbsentFromCut")+b"synthetic"
                elif seqname=="SeqEmpty":
                    nested=b"\x98"*13+b"\x00\x00"+b"synthetic"
                else:
                    nested=b""  # Structural header + ending word only
                if change_nested_pack and screen==SCREENS[1] and seqname=="SeqMatched":
                    nested=b"\x98"*13+string("OtherCutName")+b"synthetic"
                data=five_words+nested+struct.pack("<I",0)
            blob=(string(seqname)+struct.pack("<II",0,count)+data)
            offsets.append(cursor)
            records.append(blob)
            cursor+=len(blob)
        repos[screen]=repository(
            "SpriteSeqData",WAD_PATH,FAKE_SEQ_NAMES,tuple(offsets))
        wads[screen]=b"".join(records)
        cuts[screen]=repository(
            "SpriteCutData","sprite/SpriteResData.wad",CUT_KEYS,(0,30,50))
    return repos,wads,cuts


def artificial_zip(path, *, bad_pack=False,extra=()):
    seqs,wads,cuts=artificial_sources(change_nested_pack=bad_pack)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore",UserWarning)
        with ZipFile(path,"w") as archive:
            for screen in SCREENS:
                prefix=f"Payload/MOTU.app/{screen}/"
                archive.writestr(prefix+REPO_PATH,seqs[screen])
                archive.writestr(prefix+WAD_PATH,wads[screen])
                archive.writestr(prefix+CUT_REPO,cuts[screen])
            for path_name,data in extra:
                archive.writestr(path_name,data)


class Stage157SequenceToCutNameControls(unittest.TestCase):
    def report(self,source=None):
        return summarize_sequence_cut_name_candidates(
            *(source or artificial_sources()))

    def test_all_synthetic_categories_counted(self):
        r=self.report()
        self.assertEqual(r["indexed_sequence_records"],6)
        self.assertEqual(r["nonzero_candidate_sequences_checked"],5)
        self.assertEqual(r["independently_indexed_cut_resource_names"],3)
        self.assertEqual(r["candidate_valid_utf16_ascii_records"],3)
        self.assertEqual(r["candidate_exact_cut_resource_key_matches"],2)
        self.assertEqual(r["candidate_valid_but_not_in_cut_registry"],1)
        self.assertEqual(r["candidate_empty_utf16_records"],1)
        self.assertEqual(r["candidate_too_short_for_utf16_length"],1)
        self.assertEqual(r["candidate_other_invalid_framings"],0)

    def test_distinct_sequence_cut_index_membership_is_checked(self):
        r=self.report()
        self.assertEqual(r["candidate_valid_names_also_present_as_sequence_keys"],1)
        self.assertEqual(r["candidate_valid_names_in_both_cut_and_sequence_indexes"],1)

    def test_nominated_offset_thirteen_has_cut_lexical_matches(self):
        r=self.report()
        self.assertEqual(r["hypothesis_offset_after_five_u32_prefix_bytes"],13)
        token=r["predeclared_offset_controls"]["relative_13"]
        self.assertEqual(token["well_formed_utf16_ascii"],3)
        self.assertEqual(token["matching_independent_cut_registry"],2)

    def test_negative_control_offsets_have_no_cut_key_match(self):
        r=self.report()
        self.assertEqual(tuple(TEST_OFFSETS),(0,4,8,12,13,14,16,20,24,32))
        for offset in TEST_OFFSETS:
            if offset!=CANDIDATE_OFFSET:
                self.assertEqual(
                    r["predeclared_offset_controls"]["relative_"+str(offset)][
                        "matching_independent_cut_registry"],0)

    def test_literal_actor_string_not_proof_of_frame_reference(self):
        r=self.report()
        for name in (
            "lexical_cross_registry_match_proves_data_reference",
            "unknown_count_equals_animation_frames_verified",
            "nested_sequence_frame_boundaries_decoded",
            "sprite_frame_timing_and_duration_verified",
            "original_actor_state_to_sprite_sequence_link_verified",
            "source_hitbox_state_changes_verified",
            "switch_original_sprite_import_permitted",
            "original_source_names_strings_bytes_values_or_offsets_in_report",
        ):
            self.assertFalse(r[name])

    def test_paired_resolution_specific_opaque_suffixes_can_differ(self):
        seqs,wads,cuts=artificial_sources()
        for screen in SCREENS:
            wads[screen]=wads[screen].replace(
                b"synthetic",b"SYNTHETIC") if screen==SCREENS[1] else wads[screen]
        # Replacement changes byte lengths: keep equal-length contents instead.
        seqs,wads,cuts=artificial_sources()
        wads[SCREENS[1]]=wads[SCREENS[1]].replace(
            b"synthetic",b"sYnThetic")
        r=self.report((seqs,wads,cuts))
        self.assertEqual(r["candidate_exact_cut_resource_key_matches"],2)

    def test_nested_token_must_agree_between_source_packs(self):
        with self.assertRaisesRegex(SpriteIndexFormatError,"candidate differs"):
            self.report(artificial_sources(change_nested_pack=True))

    def test_tampered_cut_repository_pack_rejected(self):
        seqs,wads,cuts=artificial_sources()
        cuts[SCREENS[1]]+=b"\xff"
        with self.assertRaisesRegex(SpriteIndexFormatError,"pack mismatch"):
            self.report((seqs,wads,cuts))

    def test_corrupt_utf16_candidate_cannot_be_promoted_to_cut_key(self):
        seqs,wads,cuts=artificial_sources()
        for screen in SCREENS:
            entries=parse_sprite_repository(
                seqs[screen],expected_label="SpriteSeqData",expected_wad=WAD_PATH)
            row=entries[1]
            at=row.offset+len(string(FAKE_SEQ_NAMES[1]))+8+20+13+2
            raw=bytearray(wads[screen]);raw[at:at+2]=b"\x00\xd8"
            wads[screen]=bytes(raw)
        r=self.report((seqs,wads,cuts))
        self.assertEqual(r["candidate_exact_cut_resource_key_matches"],1)
        self.assertEqual(r["candidate_other_invalid_framings"],1)

    def test_cut_registry_name_change_reduces_matched_candidates(self):
        seqs,wads,cuts=artificial_sources()
        for screen in SCREENS:
            cuts[screen]=repository("SpriteCutData","sprite/SpriteResData.wad",
                                    ("ReplacedA","SeqShared","OtherInventedCut"),
                                    (0,30,50))
        r=self.report((seqs,wads,cuts))
        self.assertEqual(r["candidate_exact_cut_resource_key_matches"],1)
        self.assertEqual(r["candidate_valid_but_not_in_cut_registry"],2)

    def test_original_like_string_names_and_bytes_never_leave_summary(self):
        out=json.dumps(self.report())
        for secret in ("SeqZero","SeqMatched","SeqShared","AbsentFromCut",
                       "CutLinkedA","OtherInventedCut","synthetic",
                       "source_individual_offset_123"):
            self.assertNotIn(secret,out)

    def test_missing_resource_pack_is_rejected(self):
        seqs,wads,cuts=artificial_sources()
        del cuts[SCREENS[1]]
        with self.assertRaises(ValueError):
            self.report((seqs,wads,cuts))

    def test_corrupt_source_sequence_index_fails_closed(self):
        seqs,wads,cuts=artificial_sources()
        for screen in SCREENS:
            seqs[screen]+=b"\xff"
        with self.assertRaises(SpriteIndexFormatError):
            self.report((seqs,wads,cuts))

    def test_fake_ipa_reader_end_to_end(self):
        with TemporaryDirectory() as tmp:
            ipa=Path(tmp)/"invented.ipa"
            artificial_zip(ipa)
            r=audit_private_sequence_cut_name_candidates(ipa)
        self.assertEqual(r["candidate_exact_cut_resource_key_matches"],2)

    def test_fake_ipa_with_different_nested_name_fails(self):
        with TemporaryDirectory() as tmp:
            ipa=Path(tmp)/"invented.ipa"
            artificial_zip(ipa,bad_pack=True)
            with self.assertRaisesRegex(SpriteIndexFormatError,"candidate differs"):
                audit_private_sequence_cut_name_candidates(ipa)

    def test_duplicate_zip_resource_rejected(self):
        with TemporaryDirectory() as tmp:
            ipa=Path(tmp)/"invented.ipa"
            artificial_zip(ipa,extra=[
                ("Payload/MOTU.app/screen-med/meta/SpriteCutData.repo",b"fake")
            ])
            with self.assertRaisesRegex(ValueError,"Duplicate"):
                audit_private_sequence_cut_name_candidates(ipa)

    def test_symlinked_selected_cut_index_rejected(self):
        seqs,wads,cuts=artificial_sources()
        with TemporaryDirectory() as tmp:
            ipa=Path(tmp)/"invented.ipa"
            with ZipFile(ipa,"w") as archive:
                for screen in SCREENS:
                    prefix=f"Payload/MOTU.app/{screen}/"
                    archive.writestr(prefix+REPO_PATH,seqs[screen])
                    archive.writestr(prefix+WAD_PATH,wads[screen])
                    info=ZipInfo(prefix+CUT_REPO)
                    info.create_system=3
                    info.external_attr=(stat.S_IFLNK|0o777)<<16
                    archive.writestr(info,cuts[screen])
            with self.assertRaisesRegex(ValueError,"unsafe selected"):
                audit_private_sequence_cut_name_candidates(ipa)

    def test_missing_owner_private_ipa_fails_closed(self):
        with self.assertRaisesRegex(ValueError,"Original owner-private IPA"):
            audit_private_sequence_cut_name_candidates(Path("/missing/private.ipa"))


if __name__=="__main__":
    unittest.main()
