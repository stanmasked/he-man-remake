"""Stage155: invented sprite sequences only; no original IPA data."""
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
    SCREENS, SpriteIndexFormatError,
)
from heman_tools.sprite_sequence_header_controls import (
    REPO_PATH, WAD_PATH, MAX_CANDIDATE_COUNT,
    summarize_sequence_structural_fields,
    audit_private_sequence_structural_fields,
)
from test_sprite_repo_wad_index import repository, string


FAKE_ROWS = (
    ("FictionalEmpty", 0, 0, 0),
    ("FictionalStanding", 0xFFFFFFFF, 1, 0),
    ("FictionalRunning", 3, 2, 1),
    ("FictionalAttack", 0, 45, 1),
    ("FictionalEffect", 0, 5, 0),
)


def fake_sequence_packs():
    repos, wads = {}, {}
    for screen in SCREENS:
        offsets = []
        segments = []
        pos = 0
        for name, marker, count, end_flag in FAKE_ROWS:
            if count == 0:
                body = struct.pack("<I", 0)
            else:
                # Fictional starting u32 identical between screen packs,
                # deliberately distinct opaque bytes after that point.
                body = (struct.pack("<I", 1) +
                        (b"screen-small" if screen == SCREENS[0] else
                         b"screen-large") +
                        struct.pack("<I", end_flag))
            record = string(name)+struct.pack("<II", marker, count)+body
            offsets.append(pos)
            segments.append(record)
            pos += len(record)
        repos[screen] = repository(
            "SpriteSeqData", WAD_PATH,
            tuple(row[0] for row in FAKE_ROWS),tuple(offsets))
        wads[screen] = b"".join(segments)
    return repos, wads


def fake_zip(path: Path, *, extras=()):
    repos, wads = fake_sequence_packs()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore",UserWarning)
        with ZipFile(path, "w") as archive:
            for screen in SCREENS:
                base = f"Payload/MOTU.app/{screen}/"
                archive.writestr(base+REPO_PATH,repos[screen])
                archive.writestr(base+WAD_PATH,wads[screen])
            for name,raw in extras:
                archive.writestr(name,raw)


def mutate_record(wads, screen, record_index, *, u32_from_key=0,
                  newvalue=0, extra_bytes=None):
    repos, _ = fake_sequence_packs()
    from heman_tools.sprite_repo_wad_index import parse_sprite_repository
    index = parse_sprite_repository(
        repos[screen],expected_label="SpriteSeqData",expected_wad=WAD_PATH)
    off = index[record_index].offset
    keylen = len(string(FAKE_ROWS[record_index][0]))
    original = bytearray(wads[screen])
    struct.pack_into("<I",original,off+keylen+u32_from_key,newvalue)
    if extra_bytes is not None:
        original += extra_bytes
    wads[screen] = bytes(original)


class Stage155SequenceStructuralHeaderTests(unittest.TestCase):
    def report(self,packs=None):
        return summarize_sequence_structural_fields(*(packs or fake_sequence_packs()))

    def test_all_five_fake_indexed_sequence_records_pass(self):
        report=self.report()
        self.assertEqual(report["sequence_records_examined"],5)
        self.assertEqual(report["paired_matching_first_two_u32_fields"],5)
        self.assertEqual(report["paired_matching_last_u32_field"],5)
        self.assertEqual(report["paired_matching_first_postcount_u32_field"],5)
        self.assertTrue(report["all_repository_indexed_records_checked"])

    def test_candidate_count_bucket_boundaries_are_exhaustive(self):
        report=self.report()
        for key in ("candidate_count_zero_records",
                    "candidate_count_one_records",
                    "candidate_count_two_through_four_records",
                    "candidate_count_five_through_ten_records",
                    "candidate_count_eleven_through_forty_five_records"):
            self.assertEqual(report[key],1)
        self.assertEqual(report["candidate_count_greater_than_forty_five_records"],0)

    def test_start_marker_categories_remain_unknown(self):
        report=self.report()
        self.assertEqual(report["sequence_marker_zero_records"],3)
        self.assertEqual(report["sequence_marker_all_bits_one_records"],1)
        self.assertEqual(report["sequence_marker_other_records"],1)

    def test_only_zero_candidate_record_has_minimal_u32_tail(self):
        report=self.report()
        self.assertEqual(report["zero_candidate_records_with_only_one_final_u32"],1)
        self.assertEqual(report["last_record_u32_zero"],3)
        self.assertEqual(report["last_record_u32_one"],2)

    def test_permitted_resolution_specific_body_bytes_differ(self):
        repos,wads=fake_sequence_packs()
        self.assertNotEqual(wads[SCREENS[0]],wads[SCREENS[1]])
        self.assertEqual(self.report((repos,wads))["sequence_records_examined"],5)

    def test_candidate_count_is_not_claimed_actual_frame_count(self):
        report=self.report()
        for name in ("unknown_u32_count_means_actual_animation_frames",
                     "ending_u32_means_looping_or_playback_setting",
                     "duration_timing_sprite_frames_decoded",
                     "source_object_state_to_sequence_binding_verified",
                     "original_hitbox_animation_changes_verified",
                     "safe_for_source_sprite_import_to_switch"):
            self.assertFalse(report[name])

    def test_different_candidate_count_between_screen_packs_fails(self):
        repos,wads=fake_sequence_packs()
        mutate_record(wads,SCREENS[1],1,u32_from_key=4,newvalue=7)
        with self.assertRaisesRegex(SpriteIndexFormatError,"leading fields differ"):
            self.report((repos,wads))

    def test_different_initial_marker_between_screen_packs_fails(self):
        repos,wads=fake_sequence_packs()
        mutate_record(wads,SCREENS[1],1,u32_from_key=0,newvalue=12)
        with self.assertRaisesRegex(SpriteIndexFormatError,"leading fields differ"):
            self.report((repos,wads))

    def test_different_first_following_u32_between_packs_fails(self):
        repos,wads=fake_sequence_packs()
        mutate_record(wads,SCREENS[1],1,u32_from_key=8,newvalue=3)
        with self.assertRaisesRegex(SpriteIndexFormatError,"first remaining field"):
            self.report((repos,wads))

    def test_different_trailing_word_between_screen_packs_fails(self):
        repos,wads=fake_sequence_packs()
        keylen=len(string(FAKE_ROWS[2][0]))
        from heman_tools.sprite_repo_wad_index import parse_sprite_repository
        entries=parse_sprite_repository(repos[SCREENS[1]],
               expected_label="SpriteSeqData",expected_wad=WAD_PATH)
        at=entries[3].offset-4
        raw=bytearray(wads[SCREENS[1]])
        struct.pack_into("<I",raw,at,0)
        wads[SCREENS[1]]=bytes(raw)
        with self.assertRaisesRegex(SpriteIndexFormatError,"ending field differs"):
            self.report((repos,wads))

    def test_trailing_word_non_boolean_value_rejected(self):
        repos,wads=fake_sequence_packs()
        for screen in SCREENS:
            raw=bytearray(wads[screen])
            struct.pack_into("<I",raw,len(raw)-4,14)
            wads[screen]=bytes(raw)
        with self.assertRaisesRegex(SpriteIndexFormatError,"ending u32"):
            self.report((repos,wads))

    def test_candidate_count_outside_safety_budget_rejected(self):
        repos,wads=fake_sequence_packs()
        for screen in SCREENS:
            mutate_record(wads,screen,1,u32_from_key=4,
                          newvalue=MAX_CANDIDATE_COUNT+1)
        with self.assertRaisesRegex(SpriteIndexFormatError,"safety cap"):
            self.report((repos,wads))

    def test_zero_candidate_with_appended_unexpected_bytes_rejected(self):
        repos,wads=fake_sequence_packs()
        # Give zero-count record a longer interval by moving *subsequent*
        # records one byte. The indexed offsets must be updated too.
        for screen in SCREENS:
            original=wads[screen]
            first_len=len(string(FAKE_ROWS[0][0]))+12
            wads[screen]=original[:first_len]+b"\xaa"+original[first_len:]
            from heman_tools.sprite_repo_wad_index import parse_sprite_repository
            entries=parse_sprite_repository(repos[screen],
                expected_label="SpriteSeqData",expected_wad=WAD_PATH)
            repos[screen]=repository("SpriteSeqData",WAD_PATH,
                tuple(row[0] for row in FAKE_ROWS),
                tuple(entry.offset+(i>0) for i,entry in enumerate(entries)))
        with self.assertRaisesRegex(SpriteIndexFormatError,"Zero-candidate"):
            self.report((repos,wads))

    def test_empty_nonzero_record_body_rejected(self):
        repos,wads=fake_sequence_packs()
        for screen in SCREENS:
            original=wads[screen]
            from heman_tools.sprite_repo_wad_index import parse_sprite_repository
            entries=parse_sprite_repository(repos[screen],
                expected_label="SpriteSeqData",expected_wad=WAD_PATH)
            old_start=entries[1].offset
            old_end=entries[2].offset
            new_piece=string(FAKE_ROWS[1][0])+struct.pack("<II",0xFFFFFFFF,1)+b"\0"*4
            delta=len(new_piece)-(old_end-old_start)
            wads[screen]=original[:old_start]+new_piece+original[old_end:]
            repos[screen]=repository("SpriteSeqData",WAD_PATH,
                tuple(row[0] for row in FAKE_ROWS),
                tuple(e.offset+(delta if i>1 else 0)
                      for i,e in enumerate(entries)))
        with self.assertRaisesRegex(SpriteIndexFormatError,"no payload"):
            self.report((repos,wads))

    def test_invalid_or_unpaired_registry_metadata_rejected(self):
        repos,wads=fake_sequence_packs()
        repos[SCREENS[1]]+=b"\xff"
        with self.assertRaisesRegex(SpriteIndexFormatError,"metadata differs"):
            self.report((repos,wads))

    def test_original_name_key_mismatch_rejected(self):
        repos,wads=fake_sequence_packs()
        wads[SCREENS[1]]=wads[SCREENS[1]].replace(
            string("FictionalRunning"),string("FictionalRunninx"))
        with self.assertRaisesRegex(SpriteIndexFormatError,"key mismatch"):
            self.report((repos,wads))

    def test_report_redacts_original_like_names_and_raw_values(self):
        rendered=json.dumps(self.report())
        for forbidden in ("FictionalEmpty","FictionalStanding",
                          "FictionalRunning","FictionalAttack","FictionalEffect",
                          "screen-small","screen-large","per_record_offset_120"):
            self.assertNotIn(forbidden,rendered)
        self.assertFalse(json.loads(rendered)[
            "original_keys_offsets_sprite_bytes_and_values_in_report"])

    def test_fake_paired_zip_integration(self):
        with TemporaryDirectory() as directory:
            path=Path(directory)/"fictional.ipa"
            fake_zip(path)
            result=audit_private_sequence_structural_fields(path)
        self.assertEqual(result["sequence_records_examined"],5)

    def test_duplicate_zip_entry_rejected(self):
        with TemporaryDirectory() as directory:
            path=Path(directory)/"fictional.ipa"
            fake_zip(path, extras=[(
                "Payload/MOTU.app/screen-med/meta/SpriteSeqData.repo",b"fake")])
            with self.assertRaisesRegex(ValueError,"Duplicate"):
                audit_private_sequence_structural_fields(path)

    def test_selected_zip_symlink_rejected(self):
        with TemporaryDirectory() as directory:
            path=Path(directory)/"fictional.ipa"
            repos,wads=fake_sequence_packs()
            with ZipFile(path,"w") as archive:
                for screen in SCREENS:
                    root=f"Payload/MOTU.app/{screen}/"
                    archive.writestr(root+REPO_PATH,repos[screen])
                    symlink=ZipInfo(root+WAD_PATH)
                    symlink.create_system=3
                    symlink.external_attr=(stat.S_IFLNK | 0o777)<<16
                    archive.writestr(symlink,wads[screen])
            with self.assertRaisesRegex(ValueError,"unsafe selected"):
                audit_private_sequence_structural_fields(path)

    def test_missing_owner_private_original_rejected(self):
        with self.assertRaisesRegex(ValueError,"Owner-private original iOS IPA"):
            audit_private_sequence_structural_fields(
                Path("/private/nonexistent-game.ipa"))


if __name__=="__main__":
    unittest.main()
