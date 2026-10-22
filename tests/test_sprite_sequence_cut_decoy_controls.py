"""Stage164 fake-only registered-token vs decoy-token control tests."""
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
from heman_tools.sprite_sequence_cut_decoy_controls import (
    _DECOY_ALPHABET, _same_length_decoy_keys,
    summarize_sequence_cut_decoy_controls,
    audit_private_sequence_cut_decoy_controls,
)
from test_sprite_repo_wad_index import string
from test_sprite_sequence_nested_grammar import (
    CUT_KEYS, first_cut, make_fake_packs,
)


def fake_decoy(length=4):
    return sorted(x for x in _same_length_decoy_keys(frozenset(CUT_KEYS))
                  if len(x) == length)[0]


def inject_synthetic_decoy(*, name="FakeSingle",
                           second_screen_only=False, without_prefix=False):
    repos, wads, cuts = make_fake_packs()
    word = fake_decoy()
    token = string(word) if not without_prefix else word.encode("utf-16le")
    for screen in SCREENS:
        if second_screen_only and screen == SCREENS[0]:
            continue
        index = parse_sprite_repository(
            repos[screen], expected_label="SpriteSeqData", expected_wad=WAD_PATH
        )
        row = next(x for x in index if x.key == name)
        at = row.offset + len(string(name)) + 8 + 20 + 13 + len(first_cut())
        if name == "FakeDouble":
            at += 64 + 12 + len(first_cut("CutB"))
        blob = bytearray(wads[screen])
        blob[at:at+len(token)] = token
        wads[screen] = bytes(blob)
    return repos, wads, cuts


def fabricated_zip(path, sources, *, extra=(), symlink=False):
    repos, wads, cuts = sources
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with ZipFile(path, "w") as archive:
            for screen in SCREENS:
                root = "Payload/MOTU.app/" + screen + "/"
                archive.writestr(root + REPO_PATH, repos[screen])
                archive.writestr(root + CUT_REPO, cuts[screen])
                if symlink:
                    item = ZipInfo(root + WAD_PATH)
                    item.create_system = 3
                    item.external_attr = (stat.S_IFLNK | 0o777) << 16
                    archive.writestr(item, wads[screen])
                else:
                    archive.writestr(root + WAD_PATH, wads[screen])
            for name, data in extra:
                archive.writestr(name, data)


class Stage164FictionalCutDecoyControls(unittest.TestCase):
    def report(self, source=None):
        return summarize_sequence_cut_decoy_controls(
            *(source if source is not None else make_fake_packs())
        )

    def row(self, source=None, group="first_u32_one", count="one"):
        return self.report(source)["controls_by_firstword_and_unknown_count"][
            group][count]

    def test_all_invented_registry_keys_have_unregistered_decoys(self):
        keys = frozenset(CUT_KEYS)
        decoys = _same_length_decoy_keys(keys)
        self.assertEqual(len(decoys), len(keys))
        self.assertFalse(keys.intersection(decoys))
        self.assertEqual(sorted(map(len, keys)), sorted(map(len, decoys)))
        self.assertTrue(all(all(32 <= ord(ch) <= 126 for ch in x)
                            for x in decoys))

    def test_decoy_generation_is_stable_for_different_key_order(self):
        self.assertEqual(_same_length_decoy_keys(frozenset(CUT_KEYS)),
                         _same_length_decoy_keys(frozenset(reversed(CUT_KEYS))))

    def test_empty_cut_registry_rejected(self):
        with self.assertRaises(ValueError):
            _same_length_decoy_keys(frozenset())

    def test_exhausted_one_character_alphabet_fails_closed(self):
        with self.assertRaisesRegex(SpriteIndexFormatError,
                                    "No independent same-length"):
            _same_length_decoy_keys(frozenset(_DECOY_ALPHABET))

    def test_unscannable_unicode_key_not_exported_as_decoy(self):
        decoys = _same_length_decoy_keys(frozenset(["CutA", "Ω"]))
        self.assertEqual(len(decoys), 1)

    def test_baseline_synthetic_real_anchor_counts(self):
        r = self.row(count="two")
        self.assertEqual(r["known_first_cut_records"], 3)
        self.assertEqual(r["real_later_cut_in_first_screen"], 3)
        self.assertEqual(r["real_later_cut_in_second_screen"], 3)
        self.assertEqual(r["real_later_cut_in_both_screens"], 3)
        self.assertEqual(r["real_later_anchor_lists_identical_across_screens"], 3)

    def test_no_fabricated_decoy_token_by_default(self):
        r = self.report()
        for group in r["controls_by_firstword_and_unknown_count"].values():
            for bucket in group.values():
                for key in (
                    "decoy_later_cut_in_first_screen",
                    "decoy_later_cut_in_second_screen",
                    "decoy_later_cut_in_both_screens",
                    "real_and_decoy_later_tokens_in_same_screen",
                ):
                    self.assertEqual(bucket[key], 0)

    def test_unknown_first_cut_excluded_from_decoy_comparison(self):
        self.assertEqual(self.row()["known_first_cut_records"], 2)
        self.assertEqual(self.row()["real_later_cut_in_first_screen"], 0)

    def test_deliberate_decoy_in_both_source_packs_counted(self):
        source = inject_synthetic_decoy()
        r = self.row(source)
        self.assertEqual(r["decoy_later_cut_in_first_screen"], 1)
        self.assertEqual(r["decoy_later_cut_in_second_screen"], 1)
        self.assertEqual(r["decoy_later_cut_in_both_screens"], 1)
        self.assertEqual(r["real_later_cut_in_first_screen"], 0)

    def test_deliberate_decoy_only_second_pack_distinguished(self):
        r = self.row(inject_synthetic_decoy(second_screen_only=True))
        self.assertEqual(r["decoy_later_cut_in_first_screen"], 0)
        self.assertEqual(r["decoy_later_cut_in_second_screen"], 1)
        self.assertEqual(r["decoy_later_cut_in_both_screens"], 0)

    def test_decoy_without_serialized_length_does_not_match(self):
        r = self.row(inject_synthetic_decoy(without_prefix=True))
        self.assertEqual(r["decoy_later_cut_in_both_screens"], 0)

    def test_real_and_decoy_can_coexist_without_proving_frames(self):
        r = self.row(inject_synthetic_decoy(name="FakeDouble"), count="two")
        self.assertEqual(r["real_later_cut_in_first_screen"], 3)
        self.assertEqual(r["decoy_later_cut_in_first_screen"], 1)
        self.assertEqual(r["real_and_decoy_later_tokens_in_same_screen"], 1)

    def test_two_firstword_populations_do_not_mix(self):
        repos, wads, cuts = inject_synthetic_decoy()
        index = parse_sprite_repository(
            repos[SCREENS[0]], expected_label="SpriteSeqData", expected_wad=WAD_PATH
        )
        row = next(x for x in index if x.key == "FakeSingle")
        for screen in SCREENS:
            payload = bytearray(wads[screen])
            struct.pack_into("<I", payload, row.offset + len(string(row.key)) + 8, 2)
            wads[screen] = bytes(payload)
        out = self.report((repos, wads, cuts))
        self.assertEqual(out["controls_by_firstword_and_unknown_count"][
            "first_u32_other"]["one"]["decoy_later_cut_in_both_screens"], 1)
        self.assertEqual(out["controls_by_firstword_and_unknown_count"][
            "first_u32_one"]["one"]["decoy_later_cut_in_both_screens"], 0)

    def test_later_real_anchor_pack_divergence_counted(self):
        repos, wads, cuts = make_fake_packs()
        wads[SCREENS[1]] = wads[SCREENS[1]].replace(
            string("CutB"), string("CutC"))
        r = self.row((repos, wads, cuts), count="two")
        self.assertEqual(r["real_later_anchor_lists_identical_across_screens"], 2)
        self.assertEqual(r["real_later_cut_in_both_screens"], 3)

    def test_source_cut_index_corruption_rejected(self):
        repos, wads, cuts = make_fake_packs()
        cuts[SCREENS[1]] += b"\xff"
        with self.assertRaises(SpriteIndexFormatError):
            self.report((repos, wads, cuts))

    def test_raw_names_bytes_and_decoy_values_never_in_public_summary(self):
        data = json.dumps(self.report(inject_synthetic_decoy()), sort_keys=True)
        for secret in (fake_decoy(), "FakeSingle", "FakeDouble", "CutB",
                       "private_original_offset_120", "raw_header_2"):
            self.assertNotIn(secret, data)
        report = self.report()
        self.assertFalse(report["null_results_prove_animation_frame_boundaries"])
        self.assertFalse(report["source_name_lists_header_values_byte_positions_or_decoys_exported"])
        self.assertFalse(report["original_frame_durations_or_playback_verified"])
        self.assertFalse(report["original_sprite_import_to_switch_enabled"])

    def test_fictional_zip_end_to_end(self):
        with TemporaryDirectory() as folder:
            ipa = Path(folder) / "synthetic.ipa"
            fabricated_zip(ipa, inject_synthetic_decoy())
            report = audit_private_sequence_cut_decoy_controls(ipa)
        self.assertEqual(report["controls_by_firstword_and_unknown_count"][
            "first_u32_one"]["one"]["decoy_later_cut_in_both_screens"], 1)

    def test_duplicate_source_zip_member_rejected(self):
        with TemporaryDirectory() as folder:
            ipa = Path(folder) / "synthetic.ipa"
            fabricated_zip(ipa, make_fake_packs(), extra=[(
                "Payload/MOTU.app/" + SCREENS[0] + "/" + CUT_REPO, b"duplicate"
            )])
            with self.assertRaisesRegex(ValueError, "Duplicate"):
                audit_private_sequence_cut_decoy_controls(ipa)

    def test_selected_source_zip_symlink_rejected(self):
        with TemporaryDirectory() as folder:
            ipa = Path(folder) / "synthetic.ipa"
            fabricated_zip(ipa, make_fake_packs(), symlink=True)
            with self.assertRaisesRegex(ValueError, "unsafe selected"):
                audit_private_sequence_cut_decoy_controls(ipa)

    def test_original_ipa_missing_rejected(self):
        with self.assertRaisesRegex(ValueError, "Owner-private original IPA"):
            audit_private_sequence_cut_decoy_controls(
                Path("/missing/private-source.ipa"))


if __name__ == "__main__":
    unittest.main()
