"""Stage162 fictional joint-association tests; no original source content."""
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
from heman_tools.sprite_sequence_cut_name_candidates import CUT_REPO, CUT_WAD
from heman_tools.sprite_sequence_joint_header_suffix_controls import (
    _PROFILE_LABELS, summarize_sequence_joint_header_suffix_controls,
    audit_private_sequence_joint_header_suffix_controls,
)
from test_sprite_repo_wad_index import repository, string
from test_sprite_sequence_nested_grammar import (
    CUT_KEYS, invented_sequence, first_cut, make_fake_packs,
)

_ROWS = (
    ("UniformChangedA", 2, 162, False),
    ("UniformChangedB", 2, 162, True),
    ("VariableEqualA", 3, 162, False),
    ("VariableEqualB", 3, 576, False),
    ("VariableChangedA", 4, 576, True),
    ("VariableChangedB", 4, 162, False),
    ("UniformEqualA", 5, 576, False),
    ("UniformEqualB", 5, 576, False),
    ("Singleton", 6, 65, False),
    ("ControlWordOne", 1, 64, True),
)


def invented_joint_packs(*, add_other_pair=False, unknown_name=False):
    rows = list(_ROWS)
    if add_other_pair:
        rows += [
            ("OtherSuffixA", 7, 65, False),
            ("OtherSuffixB", 7, 66, False),
        ]
    if unknown_name:
        rows.append(("UnknownFirstCut", 2, 65, False))
    repos, wads, cuts = {}, {}, {}
    for screen in SCREENS:
        records, offsets = [], []
        total = 0
        for name, firstword, suffix_length, changed in rows:
            label = "CutUnknown" if name == "UnknownFirstCut" else "CutA"
            source_suffix = b"\xfe" * suffix_length
            if changed and screen == SCREENS[1]:
                source_suffix = b"\x99" + source_suffix[1:]
            payload = first_cut(label) + source_suffix
            seq = bytearray(invented_sequence(name, 1, payload))
            struct.pack_into("<I", seq, len(string(name)) + 8, firstword)
            record = bytes(seq)
            offsets.append(total)
            records.append(record)
            total += len(record)
        repos[screen] = repository(
            "SpriteSeqData", WAD_PATH,
            tuple(x[0] for x in rows), tuple(offsets),
        )
        wads[screen] = b"".join(records)
        cuts[screen] = repository(
            "SpriteCutData", CUT_WAD, CUT_KEYS,
            (0, 30, 60, 90),
        )
    return repos, wads, cuts


def fake_ipa(path, source, *, extra=(), symlink=False):
    repos, wads, cuts = source
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with ZipFile(path, "w") as archive:
            for screen in SCREENS:
                prefix = "Payload/MOTU.app/" + screen + "/"
                archive.writestr(prefix + REPO_PATH, repos[screen])
                archive.writestr(prefix + CUT_REPO, cuts[screen])
                if symlink:
                    item = ZipInfo(prefix + WAD_PATH)
                    item.create_system = 3
                    item.external_attr = (stat.S_IFLNK | 0o777) << 16
                    archive.writestr(item, wads[screen])
                else:
                    archive.writestr(prefix + WAD_PATH, wads[screen])
            for name, value in extra:
                archive.writestr(name, value)


class Stage162JointFakeControls(unittest.TestCase):
    def report(self, source=None):
        return summarize_sequence_joint_header_suffix_controls(
            *(source if source is not None else invented_joint_packs())
        )

    def test_joint_value_group_populations(self):
        r = self.report()
        self.assertEqual(r["nonunit_known_single_candidate_pairs_compared"], 9)
        self.assertEqual(r["distinct_nonunit_firstword_values_with_known_single_suffix"], 5)
        self.assertEqual(r["singleton_nonunit_firstword_values_with_known_single_suffix"], 1)
        self.assertEqual(r["eligible_repeated_nonunit_firstword_groups"], 4)

    def test_all_four_joint_profiles_represented(self):
        r = self.report()
        self.assertEqual(set(_PROFILE_LABELS), set(
            r["eligible_repeated_nonunit_firstword_groups_by_joint_profile"]))
        self.assertTrue(all(n == 1 for n in r[
            "eligible_repeated_nonunit_firstword_groups_by_joint_profile"].values()))

    def test_paired_suffix_counts_are_independently_reconciled(self):
        r = self.report()
        self.assertEqual(r["nonunit_known_single_candidate_suffix_changed_pairs"], 2)
        self.assertEqual(r["nonunit_known_single_candidate_suffix_identical_pairs"], 7)
        self.assertTrue(r["stage160_and_stage161_private_aggregate_controls_agree"])

    def test_mixed_motifs_observed_only_when_lengths_vary(self):
        self.assertEqual(self.report()[
            "repeated_nonunit_firstword_groups_with_multiple_length_motifs"], 2)

    def test_different_exact_lengths_can_share_other_coarse_motif(self):
        r = self.report(invented_joint_packs(add_other_pair=True))
        self.assertEqual(r[
            "repeated_nonunit_firstword_groups_with_multiple_exact_other_lengths"], 1)
        self.assertEqual(r["eligible_repeated_nonunit_firstword_groups"], 5)
        self.assertEqual(r[
            "eligible_repeated_nonunit_firstword_groups_by_joint_profile"
        ]["variable_length_all_screen_suffixes_identical"], 2)

    def test_unknown_cut_key_not_considered_known_suffix(self):
        r = self.report(invented_joint_packs(unknown_name=True))
        self.assertEqual(r["nonunit_known_single_candidate_pairs_compared"], 9)
        self.assertEqual(r["eligible_repeated_nonunit_firstword_groups"], 4)

    def test_all_firstword_one_sequences_excluded(self):
        r = self.report(make_fake_packs())
        self.assertEqual(r["nonunit_known_single_candidate_pairs_compared"], 0)
        self.assertEqual(r["eligible_repeated_nonunit_firstword_groups"], 0)
        self.assertEqual(r["distinct_nonunit_firstword_values_with_known_single_suffix"], 0)

    def test_firstword_one_screen_differences_do_not_inflate_nonunit(self):
        r = self.report()
        self.assertEqual(r["nonunit_known_single_candidate_suffix_changed_pairs"], 2)
        # There is a changed synthetic firstword=1 control in the same IPA.
        self.assertEqual(r["nonunit_known_single_candidate_pairs_compared"], 9)

    def test_original_semantics_not_inferred_from_joint_signatures(self):
        r = self.report()
        for flag in ("singletons_are_evidence_of_fixed_serialized_layout",
                     "header_value_proven_to_select_nested_record_type",
                     "suffix_byte_changes_prove_sprite_pixels",
                     "original_frame_boundaries_timing_and_states_verified",
                     "private_values_names_bytes_offsets_or_positions_exported",
                     "original_asset_import_permitted"):
            self.assertFalse(r[flag])

    def test_source_names_private_values_and_offsets_not_exported(self):
        serialized = json.dumps(self.report(), sort_keys=True)
        for forbidden in ("UniformChangedA", "VariableEqualB",
                          "CutA", "CutB", "private_offset_902",
                          "changed_index_3", "raw_header_value_2"):
            self.assertNotIn(forbidden, serialized)

    def test_prefix_change_in_only_one_screen_rejected(self):
        repos, wads, cuts = invented_joint_packs()
        idx = parse_sprite_repository(
            repos[SCREENS[1]], expected_label="SpriteSeqData",
            expected_wad=WAD_PATH,
        )
        row = idx[0]
        raw = bytearray(wads[SCREENS[1]])
        struct.pack_into("<I", raw, row.offset + len(string(row.key)) + 8, 99)
        wads[SCREENS[1]] = bytes(raw)
        with self.assertRaises(SpriteIndexFormatError):
            self.report((repos, wads, cuts))

    def test_mismatched_second_pack_lengths_rejected(self):
        repos, wads, cuts = invented_joint_packs()
        wads[SCREENS[1]] += b"\x00"
        with self.assertRaises(SpriteIndexFormatError):
            self.report((repos, wads, cuts))

    def test_tampered_cut_index_rejected(self):
        repos, wads, cuts = invented_joint_packs()
        cuts[SCREENS[1]] += b"\x00"
        with self.assertRaises(SpriteIndexFormatError):
            self.report((repos, wads, cuts))

    def test_synthetic_zip_integration(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "fictional.ipa"
            fake_ipa(path, invented_joint_packs())
            r = audit_private_sequence_joint_header_suffix_controls(path)
        self.assertEqual(r["eligible_repeated_nonunit_firstword_groups"], 4)

    def test_duplicate_zip_member_rejected(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "fictional.ipa"
            fake_ipa(path, invented_joint_packs(), extra=[(
                "Payload/MOTU.app/" + SCREENS[0] + "/" + CUT_REPO,
                b"duplicate",
            )])
            with self.assertRaisesRegex(ValueError, "Duplicate"):
                audit_private_sequence_joint_header_suffix_controls(path)

    def test_zip_selected_symlink_rejected(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "fictional.ipa"
            fake_ipa(path, invented_joint_packs(), symlink=True)
            with self.assertRaisesRegex(ValueError, "unsafe selected"):
                audit_private_sequence_joint_header_suffix_controls(path)

    def test_missing_owner_archive_rejected(self):
        with self.assertRaisesRegex(ValueError, "Owner-private original IPA"):
            audit_private_sequence_joint_header_suffix_controls(
                Path("/not-present/private-original.ipa")
            )


if __name__ == "__main__":
    unittest.main()
