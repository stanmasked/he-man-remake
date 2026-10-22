"""Stage161 synthetic-only paired-screen sprite suffix tests."""
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
from heman_tools.sprite_sequence_suffix_screen_parity import (
    _delta_band, _cut_suffix,
    summarize_sequence_single_suffix_screen_parity,
    audit_private_sequence_single_suffix_screen_parity,
)
from test_sprite_repo_wad_index import string
from test_sprite_sequence_nested_grammar import (
    make_fake_packs, CUT_KEYS, invented_sequence, first_cut,
)


def changed_suffix(*, name="FakeSingle", bytes_changed=1):
    """Fabricated second-screen modification; all headers unchanged."""
    repos, wads, cuts = make_fake_packs()
    screen = SCREENS[1]
    index = parse_sprite_repository(
        repos[screen], expected_label="SpriteSeqData", expected_wad=WAD_PATH
    )
    item = next(row for row in index if row.key == name)
    # Synthetic fixtures always use a first token named CutA here.
    at = (item.offset + len(string(name)) + 8 + 20 + 13 +
          len(string("CutA")))
    raw = bytearray(wads[screen])
    for j in range(bytes_changed):
        raw[at+j] ^= 0x7f
    wads[screen] = bytes(raw)
    return repos, wads, cuts


def zip_fake(path, source, *, extras=(), symlink=False):
    repos, wads, cuts = source
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with ZipFile(path, "w") as archive:
            for screen in SCREENS:
                prefix = "Payload/MOTU.app/" + screen + "/"
                archive.writestr(prefix + REPO_PATH, repos[screen])
                archive.writestr(prefix + CUT_REPO, cuts[screen])
                if symlink:
                    info = ZipInfo(prefix + WAD_PATH)
                    info.create_system = 3
                    info.external_attr = (stat.S_IFLNK | 0o777) << 16
                    archive.writestr(info, wads[screen])
                else:
                    archive.writestr(prefix + WAD_PATH, wads[screen])
            for member, body in extras:
                archive.writestr(member, body)


class Stage161PrivateSuffixSyntheticTests(unittest.TestCase):
    def report(self, source=None):
        return summarize_sequence_single_suffix_screen_parity(
            *(source if source is not None else make_fake_packs())
        )

    def category(self, report, motif, group="first_u32_one"):
        return report["single_candidate_known_cut_suffix_screen_pair_census"][
            group][motif]

    def test_all_synthetic_known_tails_identical_between_packs(self):
        report = self.report()
        for motif in ("suffix_64", "other_suffix"):
            entry = self.category(report, motif)
            self.assertEqual(entry["records"], 1)
            self.assertEqual(entry["compared_pairs"], 1)
            self.assertEqual(entry["screen_suffix_difference_bands"][
                "identical"], 1)

    def test_missing_cut_name_not_mistaken_for_zero_length_suffix(self):
        report = self.report()
        unknown = self.category(report, "initial_name_missing")
        self.assertEqual(unknown["records"], 1)
        self.assertEqual(unknown["compared_pairs"], 0)
        self.assertEqual(sum(
            unknown["screen_suffix_difference_bands"].values()), 0)

    def test_one_byte_changed_in_an_opaque_tail(self):
        report = self.report(changed_suffix(bytes_changed=1))
        entry = self.category(report, "suffix_64")
        self.assertEqual(entry["screen_suffix_difference_bands"][
            "changed_1_4"], 1)
        self.assertEqual(entry["screen_suffix_difference_bands"][
            "identical"], 0)

    def test_four_byte_difference_stays_in_first_band(self):
        entry = self.category(self.report(changed_suffix(bytes_changed=4)),
                              "suffix_64")
        self.assertEqual(entry["screen_suffix_difference_bands"][
            "changed_1_4"], 1)

    def test_five_byte_difference_starts_middle_band(self):
        entry = self.category(self.report(changed_suffix(bytes_changed=5)),
                              "suffix_64")
        self.assertEqual(entry["screen_suffix_difference_bands"][
            "changed_5_16"], 1)

    def test_seventeen_byte_difference_starts_large_band(self):
        entry = self.category(self.report(changed_suffix(bytes_changed=17)),
                              "suffix_64")
        self.assertEqual(entry["screen_suffix_difference_bands"][
            "changed_17_64"], 1)

    def test_sixty_five_changed_bytes_get_highest_band(self):
        entry = self.category(self.report(changed_suffix(
            name="FakeReject", bytes_changed=65)), "other_suffix")
        self.assertEqual(entry["screen_suffix_difference_bands"][
            "changed_65_plus"], 1)

    def test_comparison_does_not_assume_first_word_always_one(self):
        repos, wads, cuts = changed_suffix(bytes_changed=2)
        index = parse_sprite_repository(
            repos[SCREENS[0]], expected_label="SpriteSeqData",
            expected_wad=WAD_PATH,
        )
        row = next(item for item in index if item.key == "FakeSingle")
        at = row.offset + len(string(row.key)) + 8
        for screen in SCREENS:
            raw = bytearray(wads[screen])
            struct.pack_into("<I", raw, at, 2)
            wads[screen] = bytes(raw)
        report = self.report((repos, wads, cuts))
        self.assertEqual(self.category(
            report, "suffix_64", "first_u32_other")[
                "screen_suffix_difference_bands"]["changed_1_4"], 1)

    def test_delta_band_helper_boundaries(self):
        from heman_tools.sprite_sequence_suffix_screen_parity import _delta_band
        self.assertEqual(_delta_band(b"abc", b"abc"), "identical")
        self.assertEqual(_delta_band(b"abcd", b"bbc\x00"), "changed_1_4")
        self.assertEqual(_delta_band(b"a" * 16, b"b" * 16), "changed_5_16")
        self.assertEqual(_delta_band(b"a" * 17, b"b" * 17), "changed_17_64")
        self.assertEqual(_delta_band(b"a" * 65, b"b" * 65), "changed_65_plus")

    def test_mismatched_suffix_length_rejected_directly(self):
        with self.assertRaises(SpriteIndexFormatError):
            _delta_band(b"a", b"ab")

    def test_missing_direct_cut_is_not_a_suffix_payload(self):
        fake = invented_sequence("FakeSingle", 1,
                                 first_cut("NoSuchCut") + b"\xfe" * 64)
        at = len(string("FakeSingle")) + 8 + 20 + 13
        motif, suffix = _cut_suffix(fake, at, frozenset(CUT_KEYS))
        self.assertEqual(motif, "initial_name_missing")
        self.assertIsNone(suffix)

    def test_mismatched_source_pack_headers_fail_closed(self):
        repos, wads, cuts = make_fake_packs()
        index = parse_sprite_repository(
            repos[SCREENS[1]], expected_label="SpriteSeqData",
            expected_wad=WAD_PATH,
        )
        row = next(item for item in index if item.key == "FakeSingle")
        raw = bytearray(wads[SCREENS[1]])
        struct.pack_into("<I", raw, row.offset + len(string(row.key)) + 8, 3)
        wads[SCREENS[1]] = bytes(raw)
        with self.assertRaises(SpriteIndexFormatError):
            self.report((repos, wads, cuts))

    def test_output_redacts_original_like_strings_and_offsets(self):
        serialized = json.dumps(self.report(), sort_keys=True)
        for secret in ("FakeSingle", "FakeDouble", "CutA", "CutB",
                       "per_record_offset_456", "bytes_changed_positions"):
            self.assertNotIn(secret, serialized)
        report = self.report()
        for key in (
            "no_per_record_or_changed_byte_positions_exported",
            "no_raw_sprite_bytes_names_fields_or_exact_suffix_lengths_exported",
        ):
            self.assertTrue(report[key])
        for key in (
            "identical_suffix_proves_metadata_or_frame_layout",
            "different_suffix_proves_graphics_pixels",
            "original_frame_count_or_timing_decoded",
            "switch_original_sprite_import_allowed",
        ):
            self.assertFalse(report[key])

    def test_fictional_ipa_end_to_end(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "fictional.ipa"
            zip_fake(path, changed_suffix(bytes_changed=2))
            report = audit_private_sequence_single_suffix_screen_parity(path)
        self.assertEqual(self.category(report, "suffix_64")[
            "screen_suffix_difference_bands"]["changed_1_4"], 1)

    def test_zip_duplicate_rejected(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "fictional.ipa"
            zip_fake(path, make_fake_packs(), extras=[(
                "Payload/MOTU.app/" + SCREENS[0] + "/" + CUT_REPO,
                b"duplicate",
            )])
            with self.assertRaisesRegex(ValueError, "Duplicate"):
                audit_private_sequence_single_suffix_screen_parity(path)

    def test_zip_selected_symlink_rejected(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "fictional.ipa"
            zip_fake(path, make_fake_packs(), symlink=True)
            with self.assertRaisesRegex(ValueError, "unsafe selected"):
                audit_private_sequence_single_suffix_screen_parity(path)

    def test_owner_ipa_missing_rejected(self):
        with self.assertRaisesRegex(ValueError, "Owner-private original IPA"):
            audit_private_sequence_single_suffix_screen_parity(
                Path("/missing/owner-private.ipa")
            )


if __name__ == "__main__":
    unittest.main()
