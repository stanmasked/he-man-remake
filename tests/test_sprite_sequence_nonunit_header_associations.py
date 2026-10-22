"""Stage160 synthetic-only firstword association controls; no owner assets."""
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
    SCREENS, SpriteIndexFormatError, parse_sprite_repository,
)
from heman_tools.sprite_sequence_header_controls import REPO_PATH, WAD_PATH
from heman_tools.sprite_sequence_cut_name_candidates import CUT_REPO
from heman_tools.sprite_sequence_nonunit_header_associations import (
    _known_single_suffix_length, _motif,
    summarize_sequence_nonunit_header_associations,
    audit_private_sequence_nonunit_header_associations,
)
from test_sprite_repo_wad_index import string
from test_sprite_sequence_nested_grammar import (
    CUT_KEYS, make_fake_packs, first_cut, invented_sequence,
)


def fake_changed_words(assignments, *, only_second_screen=False):
    repos, wads, cuts = make_fake_packs()
    for screen in SCREENS:
        if only_second_screen and screen == SCREENS[0]:
            continue
        index = parse_sprite_repository(
            repos[screen], expected_label="SpriteSeqData",
            expected_wad=WAD_PATH,
        )
        data = bytearray(wads[screen])
        for item in index:
            if item.key in assignments:
                at = item.offset + len(string(item.key)) + 8
                struct.pack_into("<I", data, at, assignments[item.key])
        wads[screen] = bytes(data)
    return repos, wads, cuts


def diverse_source():
    return fake_changed_words({
        "FakeSingle": 2, "FakeReject": 2, "FakeMissing": 2,
        "FakeDouble": 3, "FakeExtra": 3, "FakeAmbig": 5,
    })


def fake_zip(path, source, *, extra=(), symlink_wad=False):
    repos, wads, cuts = source
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with ZipFile(path, "w") as archive:
            for screen in SCREENS:
                prefix = "Payload/MOTU.app/" + screen + "/"
                archive.writestr(prefix + REPO_PATH, repos[screen])
                archive.writestr(prefix + CUT_REPO, cuts[screen])
                if symlink_wad:
                    info = ZipInfo(prefix + WAD_PATH)
                    info.create_system = 3
                    info.external_attr = (stat.S_IFLNK | 0o777) << 16
                    archive.writestr(info, wads[screen])
                else:
                    archive.writestr(prefix + WAD_PATH, wads[screen])
            for name, payload in extra:
                archive.writestr(name, payload)


class Stage160SyntheticHeaderAssociations(unittest.TestCase):
    def report(self, source=None):
        return summarize_sequence_nonunit_header_associations(
            *(source if source is not None else diverse_source())
        )

    def test_source_with_only_firstword_one_has_empty_nonunit_subfamily(self):
        report = self.report(make_fake_packs())
        self.assertEqual(report["nonunit_records"], 0)
        self.assertEqual(report["distinct_nonunit_values"], 0)
        self.assertEqual(report["largest_nonunit_value_group"], 0)
        self.assertEqual(report[
            "nonunit_values_with_two_or_more_known_single_suffixes"], 0)

    def test_fake_nonunit_records_and_value_groups(self):
        report = self.report()
        self.assertEqual(report["nonunit_records"], 6)
        self.assertEqual(report["distinct_nonunit_values"], 3)
        self.assertEqual(report["largest_nonunit_value_group"], 3)
        self.assertEqual(report["nonunit_value_support"],
                         {"one_record": 1, "two_to_nine_records": 2,
                          "ten_plus_records": 0})

    def test_count_groups_stay_independent_of_header_values(self):
        report = self.report()
        self.assertEqual(report["nonunit_candidate_count_groups"]["one"], 3)
        self.assertEqual(report["nonunit_candidate_count_groups"]["two"], 3)
        self.assertEqual(report[
            "nonunit_values_shared_across_multiple_count_groups"], 0)

    def test_different_declared_counts_can_share_same_header_value(self):
        source = fake_changed_words({
            "FakeSingle": 2, "FakeReject": 2, "FakeMissing": 2,
            "FakeDouble": 2, "FakeExtra": 3, "FakeAmbig": 5,
        })
        report = self.report(source)
        self.assertEqual(report[
            "nonunit_values_shared_across_multiple_count_groups"], 1)
        self.assertEqual(report[
            "nonunit_values_shared_between_single_and_multi_count"], 1)

    def test_nonunit_suffix_categories_follow_stage159(self):
        motifs = self.report()["nonunit_single_candidate_suffix_motifs"]
        self.assertEqual(motifs["suffix_64"]["records"], 1)
        self.assertEqual(motifs["other_suffix"]["records"], 1)
        self.assertEqual(motifs["initial_name_missing"]["records"], 1)
        self.assertEqual(motifs["suffix_162"]["records"], 0)
        self.assertEqual(motifs["suffix_576"]["records"], 0)
        self.assertEqual(motifs["suffix_64"][
            "distinct_nonunit_first_u32_values"], 1)

    def test_equal_header_value_does_not_imply_equal_suffix_length(self):
        report = self.report()
        self.assertEqual(report[
            "nonunit_values_with_two_or_more_known_single_suffixes"], 1)
        self.assertEqual(report[
            "eligible_nonunit_values_with_variable_exact_suffix_length"], 1)
        self.assertEqual(report[
            "eligible_nonunit_values_with_uniform_exact_suffix_length"], 0)

    def test_failure_and_complete_model_paths_can_share_header_value(self):
        self.assertEqual(self.report()[
            "nonunit_values_with_both_unfitted_and_fitted_paths"], 1)

    def test_suffix_helper_distinguishes_missing_names_and_known_lengths(self):
        keyset = frozenset(CUT_KEYS)
        for tail in (64, 162, 576, 65):
            record = invented_sequence(
                "Invented", 1, first_cut() + b"q" * tail,
            )
            position = len(string("Invented")) + 8 + 20 + 13
            with self.subTest(tail=tail):
                self.assertEqual(
                    _known_single_suffix_length(record, position, keyset), tail
                )
        missing = invented_sequence(
            "Invented", 1, first_cut("NotARegisteredCut") + b"q" * 64
        )
        self.assertIsNone(_known_single_suffix_length(
            missing, position, keyset))

    def test_suffix_motif_never_guesses_other_exact_length(self):
        self.assertEqual(_motif(None), "initial_name_missing")
        self.assertEqual(_motif(64), "suffix_64")
        self.assertEqual(_motif(162), "suffix_162")
        self.assertEqual(_motif(576), "suffix_576")
        self.assertEqual(_motif(65), "other_suffix")
        self.assertEqual(_motif(66), "other_suffix")

    def test_cross_pack_first_word_divergence_fails_closed(self):
        source = fake_changed_words(
            {"FakeSingle": 2}, only_second_screen=True)
        with self.assertRaises(SpriteIndexFormatError):
            self.report(source)

    def test_cut_index_tampering_is_rejected(self):
        repos, wads, cuts = diverse_source()
        cuts[SCREENS[1]] += b"\x00"
        with self.assertRaises(SpriteIndexFormatError):
            self.report((repos, wads, cuts))

    def test_aggregate_report_never_exposes_private_header_values_or_keys(self):
        report = self.report()
        data = json.dumps(report, sort_keys=True)
        for key in ("FakeSingle", "FakeReject", "FakeAmbig",
                    "CutA", "CutB", "individual_record_offset_321"):
            self.assertNotIn(key, data)
        for flag in (
            "raw_nonunit_header_values_or_name_strings_exported",
            "individual_suffix_lengths_or_record_offsets_exported",
            "fixed_suffix_length_proves_nested_frame_layout",
            "header_value_proven_sprite_type_or_child_count",
            "original_frame_durations_or_playback_verified",
            "automatic_original_asset_import_permitted",
        ):
            self.assertFalse(report[flag])

    def test_paired_fake_ipa_reads_to_aggregate(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / "fictional.ipa"
            fake_zip(path, diverse_source())
            report = audit_private_sequence_nonunit_header_associations(path)
        self.assertEqual(report["nonunit_records"], 6)

    def test_duplicate_archive_member_rejected(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / "fictional.ipa"
            fake_zip(path, diverse_source(), extra=[(
                "Payload/MOTU.app/" + SCREENS[0] + "/" + CUT_REPO,
                b"duplicate",
            )])
            with self.assertRaisesRegex(ValueError, "Duplicate"):
                audit_private_sequence_nonunit_header_associations(path)

    def test_selected_symlink_archive_member_rejected(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / "fictional.ipa"
            fake_zip(path, diverse_source(), symlink_wad=True)
            with self.assertRaisesRegex(ValueError, "unsafe selected"):
                audit_private_sequence_nonunit_header_associations(path)

    def test_missing_owner_ipa_rejected(self):
        with self.assertRaisesRegex(ValueError, "Owner-private original IPA"):
            audit_private_sequence_nonunit_header_associations(
                Path("/missing/original-private.ipa")
            )


if __name__ == "__main__":
    unittest.main()
