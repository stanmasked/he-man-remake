"""Stage163 fictional-only lexical anchor scans and ZIP safety tests."""
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
from heman_tools.sprite_sequence_cut_anchor_scan import (
    _packed_cut_names, _scan_known_cut_anchors, _lexical_class,
    summarize_sequence_lexical_cut_anchor_scan,
    audit_private_sequence_lexical_cut_anchor_scan,
)
from test_sprite_repo_wad_index import string, repository
from test_sprite_sequence_nested_grammar import (
    CUT_KEYS, make_fake_packs, invented_sequence, first_cut,
)


def change_payload(*, name="FakeDouble", old=None, new=None,
                   only_second=False):
    repos, wads, cuts = make_fake_packs()
    for screen in SCREENS:
        if only_second and screen == SCREENS[0]:
            continue
        if old is None:
            continue
        # Replacement has same length and changes no index offsets.
        if len(old) != len(new):
            raise ValueError("Fictional mutation changes indexed size")
        before = wads[screen]
        if before.count(old) != 1:
            raise ValueError("Expected exactly one fabricated target")
        wads[screen] = before.replace(old, new)
    return repos, wads, cuts


def change_first_word(name, value):
    repos, wads, cuts = make_fake_packs()
    for screen in SCREENS:
        idx = parse_sprite_repository(
            repos[screen], expected_label="SpriteSeqData",
            expected_wad=WAD_PATH)
        row = next(x for x in idx if x.key == name)
        payload = bytearray(wads[screen])
        struct.pack_into("<I", payload,
                         row.offset + len(string(row.key)) + 8, value)
        wads[screen] = bytes(payload)
    return repos, wads, cuts


def fake_zip(path, source=None, *, extra=(), symlink_wad=False):
    repos, wads, cuts = source or make_fake_packs()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with ZipFile(path, "w") as archive:
            for screen in SCREENS:
                prefix = "Payload/MOTU.app/" + screen + "/"
                archive.writestr(prefix + REPO_PATH, repos[screen])
                archive.writestr(prefix + CUT_REPO, cuts[screen])
                if symlink_wad:
                    member = ZipInfo(prefix + WAD_PATH)
                    member.create_system = 3
                    member.external_attr = (stat.S_IFLNK | 0o777) << 16
                    archive.writestr(member, wads[screen])
                else:
                    archive.writestr(prefix + WAD_PATH, wads[screen])
            for key, data in extra:
                archive.writestr(key, data)


class Stage163FabricatedAnchorTests(unittest.TestCase):
    def report(self, source=None):
        return summarize_sequence_lexical_cut_anchor_scan(
            *(source or make_fake_packs()))

    def by(self, group="first_u32_one", count="two"):
        return self.report()[
            "candidate_lexical_anchor_status_by_firstword_and_count"
        ][group][count]

    def test_default_two_candidate_categories_are_ambiguous(self):
        r = self.by()
        self.assertEqual(r["records"], 3)
        c = r["candidate_lexical_anchor_classes"]
        self.assertEqual(c["multi_candidate_matches_count_minus_one"], 2)
        self.assertEqual(c["multi_candidate_above_count_minus_one"], 1)

    def test_default_one_candidate_records_include_missing_first_name(self):
        r = self.by(count="one")
        self.assertEqual(r["records"], 3)
        c = r["candidate_lexical_anchor_classes"]
        self.assertEqual(c["initial_cut_name_missing"], 1)
        self.assertEqual(c["one_candidate_no_later_cut_name"], 2)

    def test_firstword_other_group_uses_opaque_header_word_not_count(self):
        r = self.report(change_first_word("FakeDouble", 2))
        groups = r["candidate_lexical_anchor_status_by_firstword_and_count"]
        self.assertEqual(groups["first_u32_other"]["two"]["records"], 1)
        self.assertEqual(groups["first_u32_one"]["two"]["records"], 2)

    def test_exact_serialized_token_scan_does_not_require_64_82_layout(self):
        record = invented_sequence(
            "Fictional", 2,
            first_cut() + b"\xa5" * 7 + first_cut("CutB") + b"\xee" * 31)
        start = len(string("Fictional")) + 8 + 20 + 13 + len(first_cut())
        hits = _scan_known_cut_anchors(
            record, start, _packed_cut_names(frozenset(CUT_KEYS)))
        self.assertEqual(len(hits), 1)

    def test_scan_is_bytewise_not_guessed_even_alignment(self):
        record = invented_sequence(
            "Fictional", 2,
            first_cut() + b"\x7f" + first_cut("CutC") + b"\xee" * 10)
        start = len(string("Fictional")) + 8 + 20 + 13 + len(first_cut())
        self.assertEqual(len(_scan_known_cut_anchors(
            record, start, _packed_cut_names(frozenset(CUT_KEYS)))), 1)

    def test_cut_name_without_u16_prefix_not_matched(self):
        record = invented_sequence(
            "Fictional", 2,
            first_cut() + b"\x7f" + "CutB".encode("utf-16le") + b"\xff" * 9)
        start = len(string("Fictional")) + 8 + 20 + 13 + len(first_cut())
        self.assertEqual(_scan_known_cut_anchors(
            record, start, _packed_cut_names(frozenset(CUT_KEYS))), ())

    def test_unknown_cut_name_never_counted(self):
        record = invented_sequence(
            "Fictional", 2,
            first_cut() + first_cut("NotIndexed") + b"\xff" * 15)
        start = len(string("Fictional")) + 8 + 20 + 13 + len(first_cut())
        self.assertFalse(_scan_known_cut_anchors(
            record, start, _packed_cut_names(frozenset(CUT_KEYS))))

    def test_no_lexical_token_can_cross_last_u32(self):
        prefix = string("CutB")
        self.assertFalse(_scan_known_cut_anchors(
            prefix, 0, _packed_cut_names(frozenset(CUT_KEYS))))

    def test_bound_on_more_than_512_lexical_matches(self):
        payload = b"".join(first_cut("CutB") for _ in range(513))
        record = invented_sequence("Fictional", 2, first_cut() + payload)
        start = len(string("Fictional")) + 8 + 20 + 13 + len(first_cut())
        with self.assertRaisesRegex(SpriteIndexFormatError, "Excessive lexical"):
            _scan_known_cut_anchors(
                record, start, _packed_cut_names(frozenset(CUT_KEYS)))

    def test_lexical_class_is_not_child_frame_validation(self):
        self.assertEqual(_lexical_class(1, True, 1),
                         "one_candidate_with_later_cut_name")
        self.assertEqual(_lexical_class(2, True, 0),
                         "multi_candidate_no_later_cut_name")
        self.assertEqual(_lexical_class(3, True, 1),
                         "multi_candidate_some_but_below_count")
        self.assertEqual(_lexical_class(3, True, 2),
                         "multi_candidate_matches_count_minus_one")
        self.assertEqual(_lexical_class(2, True, 2),
                         "multi_candidate_above_count_minus_one")
        self.assertEqual(_lexical_class(1, False, 9),
                         "initial_cut_name_missing")

    def test_count_one_with_embedded_known_name_is_only_a_lexical_warning(self):
        repos, wads, cuts = make_fake_packs()
        for screen in SCREENS:
            idx = parse_sprite_repository(
                repos[screen], expected_label="SpriteSeqData",
                expected_wad=WAD_PATH)
            row = next(x for x in idx if x.key == "FakeSingle")
            at = (row.offset + len(string(row.key)) + 8 + 20 + 13 +
                  len(first_cut()))
            blob = bytearray(wads[screen])
            token = first_cut("CutB")
            blob[at:at+len(token)] = token
            wads[screen] = bytes(blob)
        r = self.report((repos, wads, cuts))
        c = r["candidate_lexical_anchor_status_by_firstword_and_count"][
            "first_u32_one"]["one"]["candidate_lexical_anchor_classes"]
        self.assertEqual(c["one_candidate_with_later_cut_name"], 1)

    def test_paired_name_changed_without_layout_change_is_counted(self):
        r = self.report(change_payload(
            old=first_cut("CutB"), new=first_cut("CutC"), only_second=True))
        c = r["candidate_lexical_anchor_status_by_firstword_and_count"][
            "first_u32_one"]["two"]
        self.assertEqual(c["later_anchor_lists_differ_across_packs"], 1)
        self.assertEqual(c["later_anchor_lists_identical_across_packs"], 2)

    def test_opaque_data_changes_without_new_names_keep_parity(self):
        repos, wads, cuts = make_fake_packs()
        wads[SCREENS[1]] = wads[SCREENS[1]].replace(
            b"\xfe" * 64, b"\x87" * 64)
        r = self.report((repos, wads, cuts))
        c = r["candidate_lexical_anchor_status_by_firstword_and_count"][
            "first_u32_one"]["two"]
        self.assertEqual(c["later_anchor_lists_identical_across_packs"], 3)

    def test_bad_screen_index_or_firstword_rejected(self):
        repos, wads, cuts = make_fake_packs()
        cuts[SCREENS[1]] += b"\x00"
        with self.assertRaises(SpriteIndexFormatError):
            self.report((repos, wads, cuts))

    def test_invalid_cut_registry_fails_closed(self):
        for v in (frozenset(), frozenset([""]), frozenset(["Ω"])):
            with self.subTest(v=v), self.assertRaises(ValueError):
                _packed_cut_names(v)

    def test_report_does_not_expose_source_names_or_offsets(self):
        r = self.report()
        encoded = json.dumps(r, sort_keys=True)
        for forbidden in ("FakeDouble", "FakeAmbig", "CutA", "CutB",
                          "private_byte_offset_1000", "raw_word_4"):
            self.assertNotIn(forbidden, encoded)
        self.assertFalse(r["source_sprite_animation_boundaries_verified"])
        self.assertFalse(r["source_unknown_count_proven_to_equal_child_names"])
        self.assertFalse(r["source_frame_duration_or_playback_verified"])
        self.assertFalse(r["automated_source_sprite_import_permitted"])
        self.assertFalse(r["source_names_header_values_offsets_and_bytes_exported"])

    def test_paired_fake_ipa_runs_end_to_end(self):
        with TemporaryDirectory() as d:
            ipa = Path(d) / "invented.ipa"
            fake_zip(ipa)
            r = audit_private_sequence_lexical_cut_anchor_scan(ipa)
        self.assertEqual(sum(
            entry["records"]
            for group in r["candidate_lexical_anchor_status_by_firstword_and_count"].values()
            for entry in group.values()), 6)

    def test_duplicate_source_zip_member_rejected(self):
        with TemporaryDirectory() as d:
            ipa = Path(d) / "invented.ipa"
            fake_zip(ipa, extra=[(
                "Payload/MOTU.app/" + SCREENS[0] + "/" + CUT_REPO,
                b"duplicate")])
            with self.assertRaisesRegex(ValueError, "Duplicate"):
                audit_private_sequence_lexical_cut_anchor_scan(ipa)

    def test_selected_source_zip_symlink_rejected(self):
        with TemporaryDirectory() as d:
            ipa = Path(d) / "invented.ipa"
            fake_zip(ipa, symlink_wad=True)
            with self.assertRaisesRegex(ValueError, "unsafe selected"):
                audit_private_sequence_lexical_cut_anchor_scan(ipa)

    def test_missing_owner_archive_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "Owner-private original IPA"):
            audit_private_sequence_lexical_cut_anchor_scan(
                Path("/not-present/owner.ipa"))


if __name__ == "__main__":
    unittest.main()
