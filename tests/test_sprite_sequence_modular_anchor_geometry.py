"""Stage165 synthetic-only residue, screening and security regressions."""
from __future__ import annotations

import json
from pathlib import Path
import struct
from tempfile import TemporaryDirectory
import unittest

from heman_tools.sprite_repo_wad_index import SCREENS, SpriteIndexFormatError
from heman_tools.sprite_sequence_modular_anchor_geometry import (
    _gap_class, _tail_class, _paired_name_geometry,
    summarize_sequence_modular_anchor_geometry,
    audit_private_sequence_modular_anchor_geometry,
)
from heman_tools.sprite_sequence_cut_anchor_scan import _packed_cut_names
from test_sprite_repo_wad_index import string
from test_sprite_sequence_nested_grammar import (
    CUT_KEYS, make_fake_packs, invented_sequence, first_cut,
)
from test_sprite_sequence_cut_decoy_controls import fabricated_zip


class Stage165FabricatedModularAnchorTests(unittest.TestCase):
    def report(self, source=None):
        return summarize_sequence_modular_anchor_geometry(
            *(make_fake_packs() if source is None else source)
        )

    def one(self, source=None):
        return self.report(source)["by_firstword_and_declared_count"][
            "first_u32_one"
        ]

    def test_gap_76_family_and_82_byte_extensions(self):
        for length in (76, 158, 240, 404, 568):
            with self.subTest(length=length):
                self.assertEqual(_gap_class(length), "gap_76_plus_82n")

    def test_gap_97_family_and_82_byte_extensions(self):
        for length in (97, 179, 261, 343):
            self.assertEqual(_gap_class(length), "gap_97_plus_82n")

    def test_gap_118_family_and_82_byte_extensions(self):
        for length in (118, 200):
            self.assertEqual(_gap_class(length), "gap_118_plus_82n")

    def test_gap_other_is_retained_instead_of_silently_dropped(self):
        for length in (0, 21, 64, 65, 75, 77, 96, 98, 117, 119):
            self.assertEqual(_gap_class(length), "other_gap")

    def test_tail_64_plus_82n(self):
        for length in (64, 146, 228, 310):
            self.assertEqual(_tail_class(length), "tail_64_plus_82n")

    def test_tail_off_by_one_controls(self):
        for length in (0, 63, 65, 145, 147, 227, 229):
            self.assertEqual(_tail_class(length), "other_tail")

    def test_invalid_gap_lengths_fail_closed(self):
        for bad in (-1, None, 2.5, True, "97"):
            with self.subTest(value=bad), self.assertRaises(ValueError):
                _gap_class(bad)

    def test_invalid_tail_lengths_fail_closed(self):
        for bad in (-1, None, 2.5, True, "64"):
            with self.subTest(value=bad), self.assertRaises(ValueError):
                _tail_class(bad)

    def test_fake_registered_name_intervals_are_fully_counted(self):
        summary = self.one()
        self.assertEqual(summary["two"]["known_first_cut_records"], 3)
        self.assertEqual(summary["two"]["records_with_secondary_indexed_names"], 3)
        self.assertEqual(summary["two"]["inter_name_gap_count"], 4)

    def test_fixture_detects_76_179_and_incidental_zero_gap(self):
        counters = self.one()["two"]["inter_name_gap_modular_classes"]
        self.assertEqual(counters["gap_76_plus_82n"], 2)
        self.assertEqual(counters["gap_97_plus_82n"], 1)
        self.assertEqual(counters["other_gap"], 1)

    def test_eighty_two_is_discriminating_for_long_tails(self):
        summary = self.one()
        self.assertEqual(summary["two"]["tails_longer_than_base_64"], 1)
        self.assertEqual(summary["two"]["nonbaseline_tail_hits_by_stride"],
                         {"81": 0, "82": 1, "83": 0})

    def test_fake_odd_single_tail_not_explained_by_82(self):
        summary = self.one()["one"]["terminal_gap_modular_classes"]
        self.assertEqual(summary["tail_64_plus_82n"], 1)
        self.assertEqual(summary["other_tail"], 1)

    def test_fake_both_screens_share_gap_geometry(self):
        for group in self.one().values():
            self.assertEqual(
                group["gap_geometry_identical_across_screen_packs"],
                group["known_first_cut_records"],
            )

    def test_paired_suffix_byte_changes_do_not_alter_gap_geometry(self):
        repos, wads, cuts = make_fake_packs()
        wads[SCREENS[1]] = wads[SCREENS[1]].replace(
            b"\xfe" * 64, b"\xf1" * 64
        )
        report = self.report((repos, wads, cuts))
        for bucket in report["by_firstword_and_declared_count"][
            "first_u32_one"
        ].values():
            self.assertEqual(
                bucket["gap_geometry_identical_across_screen_packs"],
                bucket["known_first_cut_records"],
            )

    def test_paired_extra_token_in_no_fit_record_is_observed(self):
        repos, wads, cuts = make_fake_packs()
        # Only mutate the FakeReject record, not an earlier synthetic
        # run of FE bytes in FakeExtra. Both records contain FE spans.
        name = string("FakeReject")
        start = wads[SCREENS[1]].find(name)
        self.assertGreaterEqual(start, 0)
        tail_at = start + len(name) + 8 + 20 + 13 + len(first_cut())
        payload = bytearray(wads[SCREENS[1]])
        self.assertEqual(payload[tail_at:tail_at + 65], b"\xfe" * 65)
        token = string("CutB")
        payload[tail_at:tail_at + len(token)] = token
        wads[SCREENS[1]] = bytes(payload)
        # Stage158 still sees a 65-byte candidate tail and no full
        # strict parse. Stage165 must notice extra lexical evidence in
        # the second resolution pack without trusting it as a frame.
        report = self.report((repos, wads, cuts))
        self.assertEqual(report["by_firstword_and_declared_count"][
            "first_u32_one"]["one"][
                "gap_geometry_identical_across_screen_packs"
        ], 1)

    def test_bad_first_cut_pair_is_rejected_upstream(self):
        repos, wads, cuts = make_fake_packs()
        wads[SCREENS[1]] = wads[SCREENS[1]].replace(
            string("CutA") + b"\xfe" * 64,
            string("Nutz") + b"\xfe" * 64,
            1,
        )
        with self.assertRaises(SpriteIndexFormatError):
            self.report((repos, wads, cuts))

    def test_first_header_nonunit_buckets_are_separate(self):
        repos, wads, cuts = make_fake_packs()
        for screen in SCREENS:
            wad = bytearray(wads[screen])
            idx = wads[screen].find(string("FakeDouble"))
            at = idx + len(string("FakeDouble")) + 8
            struct.pack_into("<I", wad, at, 2)
            wads[screen] = bytes(wad)
        out = self.report((repos, wads, cuts))[
            "by_firstword_and_declared_count"
        ]
        self.assertEqual(out["first_u32_other"]["two"][
            "known_first_cut_records"], 1)
        self.assertEqual(out["first_u32_one"]["two"][
            "known_first_cut_records"], 2)

    def test_report_is_only_anonymous_aggregates(self):
        report = self.report()
        encoded = json.dumps(report, sort_keys=True)
        for name in ("FakeDouble", "FakeSingle", "CutB", "CutA",
                     "private_source_offset_90", "sprite_byte_payload"):
            self.assertNotIn(name, encoded)
        for flag in ("lexical_anchor_locations_proven_frame_boundaries",
                     "modular_widths_prove_animation_timing",
                     "original_sprite_import_to_switch_permitted",
                     "raw_names_values_positions_gap_series_or_bytes_exported"):
            self.assertFalse(report[flag])

    def test_synthetic_ipa_full_run(self):
        with TemporaryDirectory() as path:
            ipa = Path(path) / "fictional.ipa"
            fabricated_zip(ipa, make_fake_packs())
            result = audit_private_sequence_modular_anchor_geometry(ipa)
        self.assertTrue(
            result["stage164_independent_registered_name_controls_reconciled"])

    def test_synthetic_duplicate_zip_member_rejected(self):
        with TemporaryDirectory() as path:
            ipa = Path(path) / "fictional.ipa"
            fabricated_zip(ipa, make_fake_packs(), extra=[(
                "Payload/MOTU.app/" + SCREENS[0] +
                "/meta/SpriteSeqData.repo", b"duplicate",
            )])
            with self.assertRaisesRegex(ValueError, "Duplicate"):
                audit_private_sequence_modular_anchor_geometry(ipa)

    def test_synthetic_symlink_selected_member_rejected(self):
        with TemporaryDirectory() as path:
            ipa = Path(path) / "fictional.ipa"
            fabricated_zip(ipa, make_fake_packs(), symlink=True)
            with self.assertRaisesRegex(ValueError, "unsafe selected"):
                audit_private_sequence_modular_anchor_geometry(ipa)

    def test_missing_owner_ipa_rejected(self):
        with self.assertRaisesRegex(ValueError, "Owner-private original IPA"):
            audit_private_sequence_modular_anchor_geometry(
                Path("/not-here/private-source.ipa")
            )


if __name__ == "__main__":
    unittest.main()
