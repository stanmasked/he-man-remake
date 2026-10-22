"""Stage156: imaginary iOS-style sprite records, no original game assets."""
from __future__ import annotations

import json
import stat
import struct
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import warnings
from zipfile import ZipFile,ZipInfo

from heman_tools.sprite_sequence_prefix_invariants import (
    summarize_sequence_prefix_invariants,
    audit_private_sequence_prefix_invariants,
)
from heman_tools.sprite_repo_wad_index import (
    SCREENS, SpriteIndexFormatError,
)
from heman_tools.sprite_sequence_header_controls import REPO_PATH,WAD_PATH
from test_sprite_repo_wad_index import repository,string


_FICTIONAL = (
    ("ImaginaryEmpty",0,0,0,0,0),
    ("ImaginaryWalk",1,1,1,0,0),
    ("ImaginaryAttack",2,5,2,0,1),
    ("ImaginaryEffect",3,3,2,3,0),
    ("ImaginaryOther",0xFFFFFFFF,45,7,0,1),
)


def fake_pairs(*, exceptional_third=True):
    repos,wads={},{}
    for screen in SCREENS:
        offsets=[]
        records=[]
        cursor=0
        for idx,(name,marker,count,first,fourth,last) in enumerate(_FICTIONAL):
            if count==0:
                mid=b""
            else:
                third = 120 if idx!=2 else (
                    120 if screen==SCREENS[0] or not exceptional_third else 240
                )
                words=struct.pack("<5I",first,0,third,fourth,0)
                # Resolution-specific data AFTER 20-byte prefix.
                suffix=(b"fabricated-a" if screen==SCREENS[0] else
                        b"fabricated-b")
                mid=words+suffix
            payload=(string(name)+struct.pack("<II",marker,count)+mid+
                     struct.pack("<I",last))
            offsets.append(cursor)
            records.append(payload)
            cursor+=len(payload)
        repos[screen]=repository("SpriteSeqData",WAD_PATH,
                                 tuple(x[0] for x in _FICTIONAL),
                                 tuple(offsets))
        wads[screen]=b"".join(records)
    return repos,wads


def fake_archive(path, *, extra=()):
    repos,wads=fake_pairs()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore",UserWarning)
        with ZipFile(path,"w") as archive:
            for screen in SCREENS:
                prefix=f"Payload/MOTU.app/{screen}/"
                archive.writestr(prefix+REPO_PATH,repos[screen])
                archive.writestr(prefix+WAD_PATH,wads[screen])
            for entry,blob in extra:
                archive.writestr(entry,blob)


def replace_field(repos,wads, screen,index, word, newvalue):
    from heman_tools.sprite_repo_wad_index import parse_sprite_repository
    entries=parse_sprite_repository(
        repos[screen],expected_label="SpriteSeqData",expected_wad=WAD_PATH
    )
    key=_FICTIONAL[index][0]
    start=entries[index].offset+len(string(key))+8+4*word
    source=bytearray(wads[screen])
    struct.pack_into("<I",source,start,newvalue)
    wads[screen]=bytes(source)


class Stage156SequencePrefixInvariantsTests(unittest.TestCase):
    def report(self, resources=None):
        return summarize_sequence_prefix_invariants(*(resources or fake_pairs()))

    def test_five_record_synthetic_prefix_summary(self):
        out=self.report()
        self.assertEqual(out["indexed_sequence_record_count"],5)
        self.assertEqual(out["zero_candidate_minimal_records"],1)
        self.assertEqual(out["nonzero_candidate_records_with_complete_five_word_prefix"],4)
        self.assertEqual(out["first_word_equal_across_screen_packs"],4)
        self.assertEqual(out["maximum_first_word_observed"],7)
        self.assertEqual(out["records_with_additional_opaque_bytes_after_five_word_prefix"],4)

    def test_two_resolution_pack_exceptions_are_measured_not_rejected(self):
        out=self.report()
        self.assertEqual(out["third_word_different_across_screen_packs"],1)
        self.assertEqual(out["third_word_equal_across_screen_packs"],3)
        self.assertEqual(out["entire_five_word_prefix_identical_between_packs"],3)
        self.assertTrue(out["potential_resolution_specific_third_word_preserved_as_evidence"])

    def test_unchanged_third_word_across_packs_also_accepted(self):
        out=self.report(fake_pairs(exceptional_third=False))
        self.assertEqual(out["third_word_different_across_screen_packs"],0)
        self.assertEqual(out["entire_five_word_prefix_identical_between_packs"],4)

    def test_reserved_second_and_fifth_words_zero_in_all_nonempty(self):
        out=self.report()
        self.assertEqual(out["second_word_zero_records"],4)
        self.assertEqual(out["fifth_word_zero_records"],4)
        self.assertEqual(out["second_word_equal_across_screen_packs"],4)
        self.assertEqual(out["fifth_word_equal_across_screen_packs"],4)

    def test_rare_fourth_word_nonzero_is_reported_not_guessed(self):
        out=self.report()
        self.assertEqual(out["fourth_word_zero_records"],3)
        self.assertEqual(out["fourth_word_nonzero_records"],1)
        self.assertEqual(out["fourth_word_equal_across_screen_packs"],4)

    def test_diff_first_word_across_packs_fails_closed(self):
        repos,wads=fake_pairs()
        replace_field(repos,wads,SCREENS[1],1,0,123)
        with self.assertRaisesRegex(SpriteIndexFormatError,"Stable sequence prefix"):
            self.report((repos,wads))

    def test_diff_fourth_word_across_packs_fails_closed(self):
        repos,wads=fake_pairs()
        replace_field(repos,wads,SCREENS[1],1,3,4)
        with self.assertRaisesRegex(SpriteIndexFormatError,"Stable sequence prefix"):
            self.report((repos,wads))

    def test_nonzero_second_word_in_any_pack_rejected(self):
        repos,wads=fake_pairs()
        replace_field(repos,wads,SCREENS[0],1,1,1)
        with self.assertRaisesRegex(SpriteIndexFormatError,"reserved zero"):
            self.report((repos,wads))

    def test_nonzero_fifth_word_rejected(self):
        repos,wads=fake_pairs()
        for screen in SCREENS:
            replace_field(repos,wads,screen,1,4,3)
        with self.assertRaisesRegex(SpriteIndexFormatError,"reserved zero"):
            self.report((repos,wads))

    def test_absurdly_large_first_word_rejected_without_name_leak(self):
        repos,wads=fake_pairs()
        for screen in SCREENS:
            replace_field(repos,wads,screen,1,0,100000)
        with self.assertRaisesRegex(SpriteIndexFormatError,"safety budget"):
            self.report((repos,wads))

    def test_corrupt_sequence_count_detected_by_upstream_stage155(self):
        repos,wads=fake_pairs()
        for screen in SCREENS:
            from heman_tools.sprite_repo_wad_index import parse_sprite_repository
            entries=parse_sprite_repository(repos[screen],expected_label="SpriteSeqData",expected_wad=WAD_PATH)
            at=entries[1].offset+len(string(_FICTIONAL[1][0]))+4
            x=bytearray(wads[screen]);struct.pack_into("<I",x,at,1500)
            wads[screen]=bytes(x)
        with self.assertRaisesRegex(SpriteIndexFormatError,"safety cap"):
            self.report((repos,wads))

    def test_unpaired_repository_rejected_prior_to_prefix(self):
        repos,wads=fake_pairs()
        repos[SCREENS[1]]+=b"\xff"
        with self.assertRaisesRegex(SpriteIndexFormatError,"metadata differs"):
            self.report((repos,wads))

    def test_mutated_indexed_name_rejected(self):
        repos,wads=fake_pairs()
        wads[SCREENS[1]]=wads[SCREENS[1]].replace(
            string("ImaginaryWalk"),string("ImaginaryWelk"))
        with self.assertRaisesRegex(SpriteIndexFormatError,"key mismatch"):
            self.report((repos,wads))

    def test_truncated_nonempty_record_prefix_fails(self):
        repos,wads=fake_pairs()
        for screen in SCREENS:
            from heman_tools.sprite_repo_wad_index import parse_sprite_repository
            entries=parse_sprite_repository(repos[screen],expected_label="SpriteSeqData",expected_wad=WAD_PATH)
            start=entries[1].offset
            end=entries[2].offset
            # Keep header, only first 16 bytes and final four-byte field.
            keysize=len(string("ImaginaryWalk"))
            rec=wads[screen][start:start+keysize+8+16]+b"\0"*4
            gap=end-start-len(rec)
            wads[screen]=wads[screen][:start]+rec+wads[screen][end:]
            repos[screen]=repository("SpriteSeqData",WAD_PATH,
                                     tuple(x[0] for x in _FICTIONAL),
                                     tuple(e.offset-(gap if i>1 else 0)
                                           for i,e in enumerate(entries)))
        with self.assertRaisesRegex(SpriteIndexFormatError,"five-word prefix"):
            self.report((repos,wads))

    def test_aggregate_report_contains_no_fictional_names_or_offsets(self):
        out=self.report()
        serialized=json.dumps(out)
        for forbidden in ("ImaginaryWalk","ImaginaryOther",
                          "fabricated-a","fabricated-b",
                          "source_offset_1234","WAD_original_bytes"):
            self.assertNotIn(forbidden,serialized)
        self.assertFalse(out["original_names_record_offsets_raw_fields_or_hashes_in_output"])
        self.assertFalse(out["source_animation_driven_colliders_verified"]
                         if "source_animation_driven_colliders_verified" in out
                         else out["actor_state_or_collision_shape_switching_verified"])
        self.assertFalse(out["original_sprite_bytes_or_images_export_permitted"])

    def test_owner_private_zip_fake_integration(self):
        with TemporaryDirectory() as tmp:
            path=Path(tmp)/"fictional.ipa"
            fake_archive(path)
            out=audit_private_sequence_prefix_invariants(path)
        self.assertEqual(out["indexed_sequence_record_count"],5)

    def test_duplicate_zip_entry_rejected(self):
        with TemporaryDirectory() as tmp:
            path=Path(tmp)/"fictional.ipa"
            fake_archive(path,extra=[
                ("Payload/MOTU.app/screen-med/meta/SpriteSeqData.repo",b"fake")
            ])
            with self.assertRaisesRegex(ValueError,"Duplicate"):
                audit_private_sequence_prefix_invariants(path)

    def test_symlinked_selected_wad_rejected(self):
        repos,wads=fake_pairs()
        with TemporaryDirectory() as tmp:
            path=Path(tmp)/"fictional.ipa"
            with ZipFile(path,"w") as archive:
                for screen in SCREENS:
                    root=f"Payload/MOTU.app/{screen}/"
                    archive.writestr(root+REPO_PATH,repos[screen])
                    info=ZipInfo(root+WAD_PATH)
                    info.create_system=3
                    info.external_attr=(stat.S_IFLNK|0o777)<<16
                    archive.writestr(info,wads[screen])
            with self.assertRaisesRegex(ValueError,"unsafe selected"):
                audit_private_sequence_prefix_invariants(path)

    def test_missing_private_ipa_rejected(self):
        with self.assertRaisesRegex(ValueError,"Original owner-private IPA missing"):
            audit_private_sequence_prefix_invariants(Path("/not-present/owner-source.ipa"))


if __name__=="__main__":
    unittest.main()
