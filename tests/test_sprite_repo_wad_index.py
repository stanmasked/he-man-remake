"""Stage153: fictional sprite registries and WADs ONLY; no iOS assets."""
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
    parse_sprite_repository, summarize_sprite_repo_wad_index,
    audit_private_sprite_repo_wad_index,
)


def string(value: str) -> bytes:
    raw=value.encode("utf-16le")
    return struct.pack("<H",len(raw)//2)+raw


def repository(label: str, path: str, keys: tuple[str, ...],
               offsets: tuple[int, ...]) -> bytes:
    assert len(keys)==len(offsets)
    result=bytearray(string(label)+struct.pack("<HI",0,len(keys)))
    for key,offset in zip(keys,offsets):
        result+=string(key)+struct.pack("<I",0)
        result+=string(path)+struct.pack("<I",offset)
    return bytes(result)


def invented_files(*, mismatch=False, duplicate=False):
    repos={screen:{} for screen in SCREENS}
    wads={screen:{} for screen in SCREENS}
    for label, rp, wp, with_name_header in _FAMILIES:
        if with_name_header:
            keys=("ImaginaryOne","ImaginaryTwo")
            first=string(keys[0])+b"\xff"*4
            second=string(keys[1])+b"\xab"*6
        else:
            keys=("SampleFrameOne","SampleFrameTwo")
            # Single-frame binary headers differ from repository key.
            first=string("UnrelatedFrameHandle")+b"\xff"*4
            second=string("AnotherFrameHandle")+b"\xab"*6
        offsets=(0,len(first))
        content=first+second
        index=repository(label,wp,keys,offsets)
        for screen in SCREENS:
            repos[screen][rp]=index
            wads[screen][wp]=content
    if mismatch:
        path=_FAMILIES[0][2]
        wads[SCREENS[1]][path]=wads[SCREENS[1]][path].replace(
            string("ImaginaryTwo"), string("ImaginaryBad"))
    return repos,wads


def synthetic_ipa(path: Path, *, mismatch=False, extras=()):
    repos,wads=invented_files(mismatch=mismatch)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore",UserWarning)
        with ZipFile(path,"w") as archive:
            for screen in SCREENS:
                root=f"Payload/MOTU.app/{screen}/"
                for name,data in repos[screen].items():
                    archive.writestr(root+name,data)
                for name,data in wads[screen].items():
                    archive.writestr(root+name,data)
            for path_name,blob in extras:
                archive.writestr(path_name,blob)


class Stage153SpriteRepoIndexTests(unittest.TestCase):
    def test_all_three_fake_families_have_bounded_offsets(self):
        report=summarize_sprite_repo_wad_index(*invented_files())
        self.assertEqual(report["source_repository_entries_total"],6)
        self.assertEqual(report["strict_named_wad_index_entries_per_pack"],4)
        self.assertEqual(report["paired_screen_pack_repository_count"],3)
        self.assertFalse(report["sprite_frame_structures_decoded"])

    def test_sequence_entry_name_matches_at_each_wad_offset(self):
        report=summarize_sprite_repo_wad_index(*invented_files())
        r=report["families"]["SpriteSeqData"]
        self.assertEqual(r["index_entries"],2)
        self.assertEqual(r["name_verified_entries_per_screen"],2)
        self.assertTrue(r["full_name_verified_at_indexed_offset_in_each_pack"])

    def test_cut_entry_name_matches_at_each_wad_offset(self):
        report=summarize_sprite_repo_wad_index(*invented_files())
        r=report["families"]["SpriteCutData"]
        self.assertTrue(r["full_name_verified_at_indexed_offset_in_each_pack"])

    def test_single_frame_offset_header_not_assumed_name_equal(self):
        report=summarize_sprite_repo_wad_index(*invented_files())
        r=report["families"]["SingleFrameSpriteData"]
        self.assertEqual(r["index_entries"],2)
        self.assertEqual(r["name_verified_entries_per_screen"],0)
        self.assertTrue(r["full_name_header_not_assumed_for_this_family"])

    def test_different_screen_wad_but_preserved_index_header_allowed(self):
        repos,wads=invented_files()
        path=_FAMILIES[0][2]
        wads[SCREENS[1]][path]=wads[SCREENS[1]][path][:-1]+b"\x42"
        report=summarize_sprite_repo_wad_index(repos,wads)
        self.assertEqual(report["families"]["SpriteSeqData"]["WAD_differing_byte_positions"],1)

    def test_mutated_wad_name_rejected(self):
        with self.assertRaisesRegex(SpriteIndexFormatError,"key mismatch"):
            summarize_sprite_repo_wad_index(*invented_files(mismatch=True))

    def test_missing_repository_or_wad_ref_rejected(self):
        repos,wads=invented_files()
        del repos[SCREENS[0]][_FAMILIES[0][1]]
        with self.assertRaisesRegex(ValueError,"Missing indexed"):
            summarize_sprite_repo_wad_index(repos,wads)

    def test_corrupt_header_name_rejected(self):
        label,rp,wp,_=_FAMILIES[0]
        blob=repository("WrongType",wp,("A",),(0,))
        with self.assertRaisesRegex(SpriteIndexFormatError,"identifier"):
            parse_sprite_repository(blob,expected_label=label,expected_wad=wp)

    def test_reserved_nonzero_rejected(self):
        label,rp,wp,_=_FAMILIES[0]
        b=bytearray(repository(label,wp,("A",),(0,)))
        at=len(string(label))
        struct.pack_into("<H",b,at,1)
        with self.assertRaisesRegex(SpriteIndexFormatError,"header"):
            parse_sprite_repository(bytes(b),expected_label=label,expected_wad=wp)

    def test_entry_marker_nonzero_rejected(self):
        label,rp,wp,_=_FAMILIES[0]
        b=bytearray(repository(label,wp,("A",),(0,)))
        at=len(string(label))+6+len(string("A"))
        struct.pack_into("<I",b,at,1)
        with self.assertRaisesRegex(SpriteIndexFormatError,"marker"):
            parse_sprite_repository(bytes(b),expected_label=label,expected_wad=wp)

    def test_duplicate_key_and_non_increasing_offsets_rejected(self):
        label,rp,wp,_=_FAMILIES[0]
        with self.assertRaisesRegex(SpriteIndexFormatError,"repeated"):
            parse_sprite_repository(repository(label,wp,("A","A"),(0,5)),
                                    expected_label=label,expected_wad=wp)
        with self.assertRaisesRegex(SpriteIndexFormatError,"Non-increasing"):
            parse_sprite_repository(repository(label,wp,("A","B"),(0,0)),
                                    expected_label=label,expected_wad=wp)

    def test_bad_wad_path_rejected(self):
        label,rp,wp,_=_FAMILIES[0]
        with self.assertRaisesRegex(SpriteIndexFormatError,"WAD reference"):
            parse_sprite_repository(repository(label,"unsafe/path.wad",("A",),(0,)),
                                    expected_label=label,expected_wad=wp)

    def test_nonzero_starting_offset_rejected(self):
        label,rp,wp,_=_FAMILIES[0]
        with self.assertRaisesRegex(SpriteIndexFormatError,"nonzero first"):
            parse_sprite_repository(repository(label,wp,("A",),(1,)),
                                    expected_label=label,expected_wad=wp)

    def test_truncation_and_extra_trailing_bytes_rejected(self):
        label,rp,wp,_=_FAMILIES[0]
        b=repository(label,wp,("A",),(0,))
        for sample in (b[:-1],b+b"\xff"):
            with self.subTest(sample=len(sample)),self.assertRaises(SpriteIndexFormatError):
                parse_sprite_repository(sample,expected_label=label,expected_wad=wp)

    def test_invalid_utf16_or_oversized_count_rejected(self):
        label,rp,wp,_=_FAMILIES[0]
        b=bytearray(repository(label,wp,("A",),(0,)))
        b[2:4]=b"\x00\xd8"
        with self.assertRaises(SpriteIndexFormatError):
            parse_sprite_repository(bytes(b),expected_label=label,expected_wad=wp)
        b=bytearray(repository(label,wp,("A",),(0,)))
        struct.pack_into("<I",b,len(string(label))+2,6000)
        with self.assertRaises(SpriteIndexFormatError):
            parse_sprite_repository(bytes(b),expected_label=label,expected_wad=wp)

    def test_index_past_wad_end_rejected(self):
        repos,wads=invented_files()
        rp=_FAMILIES[0][1];wp=_FAMILIES[0][2];label=_FAMILIES[0][0]
        for screen in SCREENS:
            repos[screen][rp]=repository(label,wp,("A","B"),(0,10_000))
        with self.assertRaisesRegex(SpriteIndexFormatError,"offset exceeds"):
            summarize_sprite_repo_wad_index(repos,wads)

    def test_report_never_exposes_index_names_offsets_or_raw_data(self):
        report=summarize_sprite_repo_wad_index(*invented_files())
        rendered=json.dumps(report)
        for marker in ("ImaginaryOne","ImaginaryTwo","SampleFrameOne",
                       "UnrelatedFrameHandle","offset_0","sprite header",
                       "FakeActorName"):
            self.assertNotIn(marker,rendered)
        self.assertFalse(report["raw_sprite_names_bytes_offsets_frames_and_hashes_in_report"])
        self.assertFalse(report["switch_original_asset_import_permitted"])

    def test_fictional_dual_pack_ipa_integration(self):
        with TemporaryDirectory() as directory:
            ipa=Path(directory)/"fake.ipa"
            synthetic_ipa(ipa)
            report=audit_private_sprite_repo_wad_index(ipa)
        self.assertEqual(report["strict_named_wad_index_entries_per_pack"],4)

    def test_duplicate_zip_member_rejected(self):
        with TemporaryDirectory() as directory:
            ipa=Path(directory)/"fake.ipa"
            synthetic_ipa(ipa,extras=[(
                "Payload/MOTU.app/screen-med/meta/SpriteSeqData.repo",b"fake")])
            with self.assertRaisesRegex(ValueError,"Duplicate"):
                audit_private_sprite_repo_wad_index(ipa)

    def test_symlink_source_wad_rejected(self):
        with TemporaryDirectory() as directory:
            ipa=Path(directory)/"fake.ipa"
            extras=[]
            for screen in SCREENS:
                name=f"Payload/MOTU.app/{screen}/sprite/Link.wad"
                info=ZipInfo(name)
                info.create_system=3
                info.external_attr=(stat.S_IFLNK|0o777)<<16
                extras.append((info,b"target"))
            # The linked file is not selected, so only a selected
            # symlink is a strict vulnerability regression.
            synthetic_ipa(ipa)
            # Construct selected symlink replacing an actual resource.
            repos,wads=invented_files()
            with ZipFile(ipa,"w") as z:
                for screen in SCREENS:
                    root=f"Payload/MOTU.app/{screen}/"
                    for key,val in repos[screen].items():
                        z.writestr(root+key,val)
                    for key,val in wads[screen].items():
                        if key==_FAMILIES[0][2]:
                            info=ZipInfo(root+key)
                            info.create_system=3
                            info.external_attr=(stat.S_IFLNK|0o777)<<16
                            z.writestr(info,val)
                        else:
                            z.writestr(root+key,val)
            with self.assertRaisesRegex(ValueError,"unsafe selected"):
                audit_private_sprite_repo_wad_index(ipa)

    def test_original_private_ipa_missing_fails_closed(self):
        with self.assertRaisesRegex(ValueError,"Original owner-private IPA"):
            audit_private_sprite_repo_wad_index(Path("/missing/private-original.ipa"))


if __name__=="__main__":
    unittest.main()
