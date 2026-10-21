"""Stage154: synthetic indexed sprite records, never original iOS sprites."""
from __future__ import annotations

import json
from pathlib import Path
import stat
import struct
from tempfile import TemporaryDirectory
import unittest
import warnings
from zipfile import ZipFile, ZipInfo

from heman_tools.sprite_repo_wad_index import (
    _FAMILIES, SCREENS, SpriteIndexFormatError,
)
from heman_tools.sprite_wad_record_intervals import (
    MAX_RECORD_BYTES, summarize_sprite_record_intervals,
    audit_private_sprite_record_intervals,
)
from test_sprite_repo_wad_index import repository, string


def fake_packs():
    repos = {pack:{} for pack in SCREENS}
    wads = {pack:{} for pack in SCREENS}
    for label,rp,wp,seq_or_cut in _FAMILIES:
        names = ("MadeUpOne","MadeUpTwo","MadeUpThree")
        for pack in SCREENS:
            entries = []
            if label == "SpriteSeqData":
                markers = (0,0xFFFFFFFF,3)
                entries = [
                    string(name)+struct.pack("<I", marker)+
                    (b"fake-a" if pack==SCREENS[0] else b"fake-b")
                    for name,marker in zip(names,markers)
                ]
            elif label == "SpriteCutData":
                entries = [
                    string(name)+string("FakeSheetReference")+
                    (b"fake-cut-a" if pack==SCREENS[0] else b"fake-cut-b")
                    for name in names
                ]
            else:
                entries = [
                    string("IndirectFrameName")+
                    (b"frame-a" if pack==SCREENS[0] else b"frame-b")
                    for _ in names
                ]
            offsets = []
            pos = 0
            for rec in entries:
                offsets.append(pos)
                pos += len(rec)
            wads[pack][wp] = b"".join(entries)
            repos[pack][rp] = repository(label,wp,names,tuple(offsets))
    return repos,wads


def synthetic_archive(path, *, extra=()):
    repos,wads=fake_packs()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore",UserWarning)
        with ZipFile(path,"w") as z:
            for screen in SCREENS:
                prefix=f"Payload/MOTU.app/{screen}/"
                for key,blob in repos[screen].items():
                    z.writestr(prefix+key,blob)
                for key,blob in wads[screen].items():
                    z.writestr(prefix+key,blob)
            for name,blob in extra:
                z.writestr(name,blob)


class Stage154WadIntervalTests(unittest.TestCase):
    def report(self, packs=None):
        return summarize_sprite_record_intervals(*(packs or fake_packs()))

    def test_three_families_partition_nine_fictional_records(self):
        result=self.report()
        self.assertEqual(result["source_indexed_wad_record_total"],9)
        self.assertEqual(result["source_screen_packs"],2)
        self.assertTrue(result["all_indexed_record_intervals_validated"])
        for family in ("SpriteSeqData","SpriteCutData","SingleFrameSpriteData"):
            self.assertEqual(result["families"][family]["indexed_record_count"],3)
            self.assertEqual(result["families"][family]["positive_bounded_interval_count"],3)
            self.assertTrue(result["families"][family]["all_records_partition_entire_wad"])

    def test_sequence_marker_count_three_categories(self):
        result=self.report()["families"]["SpriteSeqData"]
        self.assertEqual(result["sequence_following_u32_marker_zero"],1)
        self.assertEqual(result["sequence_following_u32_marker_all_bits_one"],1)
        self.assertEqual(result["sequence_following_u32_marker_other"],1)
        self.assertFalse(result["sequence_marker_meaning_verified"])

    def test_seq_cut_headers_equal_between_both_screen_packs(self):
        result=self.report()["families"]
        for family in ("SpriteSeqData","SpriteCutData"):
            self.assertEqual(result[family]["first_utf16_headers_equal_between_packs"],3)
            self.assertEqual(result[family]["first_utf16_headers_matching_repository_key"],3)

    def test_cut_second_utf16_matches_between_screen_packs(self):
        result=self.report()["families"]["SpriteCutData"]
        self.assertEqual(result["secondary_utf16_headers_equal_between_packs"],3)
        self.assertFalse(result["cut_secondary_token_meaning_verified"])

    def test_single_frame_different_name_not_mistaken_for_repo_key(self):
        result=self.report()["families"]["SingleFrameSpriteData"]
        self.assertEqual(result["first_utf16_headers_equal_between_packs"],3)
        self.assertEqual(result["first_utf16_headers_matching_repository_key"],0)
        self.assertFalse(result["single_frame_first_token_is_repo_key_proven"])

    def test_screen_specific_body_differences_accepted(self):
        result=self.report()["families"]
        for name in result:
            self.assertEqual(result[name]["complete_record_bytes_identical_between_packs"],0)

    def test_wholly_identical_resources_are_accepted(self):
        repos,wads=fake_packs()
        for _,_,wp,_ in _FAMILIES:
            wads[SCREENS[1]][wp]=wads[SCREENS[0]][wp]
        result=self.report((repos,wads))["families"]
        for family in result:
            self.assertEqual(result[family]["complete_record_bytes_identical_between_packs"],3)

    def test_mutated_seq_marker_second_pack_fails(self):
        repos,wads=fake_packs()
        key=_FAMILIES[0][2]
        raw=bytearray(wads[SCREENS[1]][key])
        pos=len(string("MadeUpOne"))
        struct.pack_into("<I",raw,pos,15)
        wads[SCREENS[1]][key]=bytes(raw)
        with self.assertRaisesRegex(SpriteIndexFormatError,"marker diverges"):
            self.report((repos,wads))

    def test_mutated_cut_second_token_fails(self):
        repos,wads=fake_packs()
        key=_FAMILIES[1][2]
        changed=wads[SCREENS[1]][key].replace(string("FakeSheetReference"),
                                                string("FakeSheetReferenceX"))
        # This changes byte length and shifts index intervals too, so
        # modify one existing UTF16 code unit rather than adding bytes.
        changed=wads[SCREENS[1]][key].replace(
            string("FakeSheetReference"),string("FakeSheetReferencX"))
        self.assertEqual(len(changed),len(wads[SCREENS[1]][key]))
        wads[SCREENS[1]][key]=changed
        with self.assertRaisesRegex(SpriteIndexFormatError,"secondary token diverges"):
            self.report((repos,wads))

    def test_bad_cut_utf16_second_token_rejected(self):
        repos,wads=fake_packs()
        key=_FAMILIES[1][2]
        raw=bytearray(wads[SCREENS[1]][key])
        at=len(string("MadeUpOne"))
        raw[at:at+2]=b"\xff\xff"
        wads[SCREENS[1]][key]=bytes(raw)
        with self.assertRaises(SpriteIndexFormatError):
            self.report((repos,wads))

    def test_seq_cut_wad_name_mismatch_fails_prior_to_marker(self):
        repos,wads=fake_packs()
        key=_FAMILIES[0][2]
        wads[SCREENS[1]][key]=wads[SCREENS[1]][key].replace(
            string("MadeUpTwo"),string("MadeUpZoo"))
        with self.assertRaisesRegex(SpriteIndexFormatError,"key mismatch"):
            self.report((repos,wads))

    def test_non_increasing_or_skipped_offset_rejected(self):
        repos,wads=fake_packs()
        label,rp,wp,_ = _FAMILIES[0]
        for offsets in ((0,0,100),(1,100,200)):
            with self.subTest(offsets=offsets):
                altered={s:dict(repos[s]) for s in SCREENS}
                for s in SCREENS:
                    altered[s][rp]=repository(label,wp,
                         ("MadeUpOne","MadeUpTwo","MadeUpThree"),offsets)
                with self.assertRaises(SpriteIndexFormatError):
                    self.report((altered,wads))

    def test_abnormally_large_record_is_rejected(self):
        repos,wads=fake_packs()
        label,rp,wp,_ = _FAMILIES[0]
        for s in SCREENS:
            # Increase the final record beyond the explicit budget.
            wads[s][wp]+=b"\xff"*(MAX_RECORD_BYTES+1)
        with self.assertRaisesRegex(SpriteIndexFormatError,"oversized"):
            self.report((repos,wads))

    def test_empty_wad_fails_closed(self):
        repos,wads=fake_packs()
        for s in SCREENS:wads[s][_FAMILIES[0][2]]=b""
        with self.assertRaises(SpriteIndexFormatError):
            self.report((repos,wads))

    def test_sprite_records_do_not_imply_animation_state_link(self):
        result=self.report()
        for flag in ("sprite_frame_count_or_duration_decoded",
                     "sprite_pixel_data_decoded",
                     "source_actor_state_to_animation_verified",
                     "source_animation_driven_colliders_verified",
                     "original_switch_gameplay_parity_verified",
                     "source_original_asset_export_permitted"):
            self.assertFalse(result[flag])

    def test_aggregate_report_never_contains_fake_resource_keys(self):
        report=json.dumps(self.report())
        for private in ("MadeUpOne","MadeUpTwo","MadeUpThree",
                        "FakeSheetReference","IndirectFrameName",
                        "fake-cut-a","fake-a","frame-a","offsets"):
            self.assertNotIn(private,report)
        self.assertFalse(json.loads(report)["source_record_keys_raw_bytes_offsets_and_sprites_in_report"])

    def test_missing_selected_sprite_repo_is_rejected(self):
        repos,wads=fake_packs()
        del repos[SCREENS[0]][_FAMILIES[0][1]]
        with self.assertRaisesRegex(ValueError,"missing"):
            self.report((repos,wads))

    def test_screen_pack_index_byte_mismatch_rejected(self):
        repos,wads=fake_packs()
        label,rp,wp,_=_FAMILIES[0]
        repos[SCREENS[1]][rp]=repository(label,wp,
            ("MadeUpOne","MadeUpTwo","AnotherThree"),
            (0,len(string("MadeUpOne"))+10,len(string("MadeUpOne"))+10+len(string("MadeUpTwo"))+10))
        with self.assertRaisesRegex(SpriteIndexFormatError,"not paired"):
            self.report((repos,wads))

    def test_fake_ipa_end_to_end_needs_no_source_game(self):
        with TemporaryDirectory() as d:
            path=Path(d)/"synthetic.ipa"
            synthetic_archive(path)
            report=audit_private_sprite_record_intervals(path)
        self.assertEqual(report["source_indexed_wad_record_total"],9)

    def test_fake_ipa_duplicate_archive_entry_rejected(self):
        with TemporaryDirectory() as d:
            path=Path(d)/"synthetic.ipa"
            synthetic_archive(path,extra=[(
                "Payload/MOTU.app/screen-med/meta/SpriteSeqData.repo",b"faux")])
            with self.assertRaisesRegex(ValueError,"duplicate"):
                audit_private_sprite_record_intervals(path)

    def test_synthetic_selected_symlink_rejected(self):
        with TemporaryDirectory() as d:
            path=Path(d)/"synthetic.ipa"
            repos,wads=fake_packs()
            with ZipFile(path,"w") as archive:
                for screen in SCREENS:
                    prefix=f"Payload/MOTU.app/{screen}/"
                    for name,blob in repos[screen].items():
                        archive.writestr(prefix+name,blob)
                    for name,blob in wads[screen].items():
                        if name==_FAMILIES[0][2]:
                            symlink=ZipInfo(prefix+name)
                            symlink.create_system=3
                            symlink.external_attr=(stat.S_IFLNK|0o777)<<16
                            archive.writestr(symlink,blob)
                        else:
                            archive.writestr(prefix+name,blob)
            with self.assertRaisesRegex(ValueError,"unsafe selected"):
                audit_private_sprite_record_intervals(path)

    def test_private_original_ipa_absent_is_rejected(self):
        with self.assertRaisesRegex(ValueError,"Owner-private original IPA"):
            audit_private_sprite_record_intervals(Path("/missing/original.ipa"))


if __name__=="__main__":
    unittest.main()
