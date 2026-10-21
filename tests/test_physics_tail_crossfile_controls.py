"""Stage146: source-free cross-file holdout and sensitivity controls."""
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import stat
import unittest
from zipfile import ZipInfo

from heman_tools.physics_tail_crossfile_controls import (
    WIDTH_CAPS, CONTROL_MODES, summarize_crossfile_tail_controls,
    audit_private_crossfile_controls,
)
from test_physics_records import fixture, record, text16, make_ipa


def heldout_sources():
    # First resource has no "External" label; it must come from another file.
    return {
        "FakeStage.ps2d": fixture([record("OnlyHere")],
                                tail_count=2,
                                opaque=(text16("External")+b"\xff"*40
                                        +text16("External")+b"\xfd"*40)),
        "FakeReference.pstruct2d": fixture([record("External")]),
        "FakeAnother.ps2d": fixture([record("External")]),
    }


def single_owned_source():
    return {
        "FakeOwned.ps2d": fixture([record("LocalOnly")],
                                 tail_count=1,
                                 opaque=text16("LocalOnly")+b"\xff"*40),
    }


def summary_column(report, mode, cap=96, key="one_complete_frame"):
    return report["controls"][mode]["cap_"+str(cap)][key]


class Stage146CrossfileHeldoutContractTests(unittest.TestCase):
    def test_all_controls_and_declared_width_caps_exist(self):
        report=summarize_crossfile_tail_controls(heldout_sources())
        self.assertEqual(set(report["controls"]),set(CONTROL_MODES))
        for mode in CONTROL_MODES:
            self.assertEqual(set(report["controls"][mode]),
                             {"cap_"+str(cap) for cap in WIDTH_CAPS})

    def test_other_file_label_survives_heldout(self):
        result=summarize_crossfile_tail_controls(heldout_sources())
        self.assertEqual(summary_column(result,"all_sources"),1)
        self.assertEqual(summary_column(result,"heldout_other_sources"),1)
        self.assertEqual(summary_column(result,"exclusively_other_sources"),1)
        self.assertEqual(summary_column(result,"same_source_only"),0)
        self.assertTrue(result["global_vs_heldout_unique_candidate_counts_equal"])
        self.assertFalse(result["global_vs_same_source_unique_candidate_counts_equal"])

    def test_shared_labels_are_counted_per_file_not_duplicate_records(self):
        result=summarize_crossfile_tail_controls(heldout_sources())
        self.assertEqual(result["main_record_labels_seen_in_two_or_more_source_files"],1)
        self.assertEqual(summary_column(result,"shared_across_at_least_two_sources"),1)

    def test_owned_label_is_removed_by_heldout_control(self):
        result=summarize_crossfile_tail_controls(single_owned_source())
        self.assertEqual(summary_column(result,"all_sources"),1)
        self.assertEqual(summary_column(result,"same_source_only"),1)
        self.assertEqual(summary_column(result,"heldout_other_sources"),0)
        self.assertEqual(summary_column(result,"shared_across_at_least_two_sources"),0)

    def test_same_label_twice_in_one_file_not_counted_as_crossfile_shared(self):
        data={
            "FakeSingle.ps2d": fixture(
                [record("Repeat"),record("Repeat")],
                tail_count=1,opaque=text16("Repeat")+b"\xff"*5)
        }
        result=summarize_crossfile_tail_controls(data)
        self.assertEqual(result["main_record_labels_seen_in_two_or_more_source_files"],0)
        self.assertEqual(summary_column(result,"shared_across_at_least_two_sources"),0)

    def test_32_byte_cap_rejects_40_byte_unknown_block(self):
        result=summarize_crossfile_tail_controls(heldout_sources())
        self.assertEqual(summary_column(result,"heldout_other_sources",32),0)
        self.assertEqual(summary_column(result,"heldout_other_sources",48),1)
        self.assertEqual(summary_column(result,"heldout_other_sources",96),1)
        self.assertFalse(result["max_width_threshold_implies_original_field_size"])

    def test_each_multi_group_counter_accounts_for_each_source(self):
        report=summarize_crossfile_tail_controls(heldout_sources())
        self.assertEqual(report["files_with_unknown_nonempty_trailer"],1)
        self.assertEqual(report["multi_group_unknown_trailer_files"],1)
        for mode in CONTROL_MODES:
            for cap in WIDTH_CAPS:
                counters=report["controls"][mode]["cap_"+str(cap)]
                self.assertEqual(sum(counters[k] for k in (
                    "no_complete_frame","one_complete_frame",
                    "ambiguous_multiple_frames")),1)
                self.assertEqual(sum(counters[k] for k in (
                    "multi_group_no_complete_frame",
                    "multi_group_one_complete_frame",
                    "multi_group_ambiguous_multiple_frames")),1)

    def test_one_group_holdout_not_original_geometry_proof(self):
        report=summarize_crossfile_tail_controls(single_owned_source())
        self.assertEqual(report["multi_group_unknown_trailer_files"],0)
        self.assertFalse(report["cross_file_lexical_agreement_proves_true_record_boundaries"])
        self.assertFalse(report["original_physics_and_collision_semantics_verified"])
        self.assertFalse(report["automatically_import_source_geometry_to_switch"])

    def test_ambiguous_zero_prefix_vocabulary_is_excluded(self):
        # Empty labels are *intentionally* not eligible source names.
        first=fixture([record("")],tail_count=2,opaque=bytes(30))
        result=summarize_crossfile_tail_controls({
            "F.ps2d":first,
            "Other.ps2d":fixture([record("Unrelated")]),
        })
        self.assertEqual(summary_column(result,"all_sources",96,"no_complete_frame"),1)
        self.assertEqual(result["different_nonempty_main_record_labels"],1)

    def test_corrupted_original_record_envelope_fails_closed(self):
        with self.assertRaises(ValueError):
            summarize_crossfile_tail_controls({"Fake.ps2d":b"\xff"*24})

    def test_invalid_empty_or_untrusted_filename_fails_closed(self):
        for sources in ({}, {"../../bad.ps2d":fixture([record()])},
                        {"F.exe":fixture([record()])},
                        {"F.ps2d":"bytes must remain bytes"}):
            with self.subTest(keys=tuple(sources)),self.assertRaises(ValueError):
                summarize_crossfile_tail_controls(sources)

    def test_original_source_strings_and_padding_never_emitted(self):
        value=json.dumps(summarize_crossfile_tail_controls(heldout_sources()))
        for secret in ("FakeStage","FakeReference","FakeAnother","OnlyHere",
                       "External","ff ff","physics_struct/"):
            self.assertNotIn(secret,value)

    def test_fake_dual_pack_ipa_integration(self):
        with TemporaryDirectory() as directory:
            ipa=Path(directory)/"synthetic.ipa"
            make_ipa(ipa)
            value=audit_private_crossfile_controls(ipa)
        self.assertEqual(value["paired_physics_files_examined"],2)
        self.assertEqual(value["files_with_unknown_nonempty_trailer"],1)
        self.assertEqual(value["predeclared_maximum_unknown_width_tiers"],
                         [16,32,48,96])

    def test_source_resolution_mismatch_rejected(self):
        with TemporaryDirectory() as directory:
            ipa=Path(directory)/"synthetic.ipa"
            make_ipa(ipa,change_large=True)
            with self.assertRaisesRegex(ValueError,"bytes differ"):
                audit_private_crossfile_controls(ipa)

    def test_duplicate_archive_entry_rejected(self):
        with TemporaryDirectory() as directory:
            ipa=Path(directory)/"synthetic.ipa"
            make_ipa(ipa,extra=[
                ("Payload/MOTU.app/screen-med/physics_struct/FakeActor.ps2d",
                 fixture([record()]))])
            with self.assertRaisesRegex(ValueError,"Duplicate"):
                audit_private_crossfile_controls(ipa)

    def test_symlinked_file_rejected_even_if_both_packs_match(self):
        with TemporaryDirectory() as directory:
            ipa=Path(directory)/"synthetic.ipa"
            extras=[]
            for pack in ("screen-med","screen-xlarge"):
                info=ZipInfo(f"Payload/MOTU.app/{pack}/physics_struct/Link.ps2d")
                info.create_system=3
                info.external_attr=(stat.S_IFLNK | 0o777)<<16
                extras.append((info,b"relative"))
            make_ipa(ipa,extra=extras)
            with self.assertRaisesRegex(ValueError,"unsafe selected"):
                audit_private_crossfile_controls(ipa)

    def test_missing_private_original_rejected(self):
        with self.assertRaisesRegex(ValueError,"Privately held original iOS archive not found"):
            audit_private_crossfile_controls(Path("/private/unavailable.ipa"))


if __name__=="__main__":
    unittest.main()
