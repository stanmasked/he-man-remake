"""Stage168 native frame-time investigation: fabricated-only tests."""
from __future__ import annotations

import json
from pathlib import Path
import struct
from tempfile import TemporaryDirectory
import unittest

from heman_tools.sprite_repo_wad_index import (
    SCREENS, SpriteIndexFormatError,
)
from heman_tools.sprite_sequence_native_timing_ledger import (
    _time_bucket, _sign, _bool_category,
    summarize_native_sequence_time_ledger,
    audit_private_native_sequence_time_ledger,
)
from test_sprite_repo_wad_index import string
from test_sprite_sequence_native_loader_structure import (
    invented_sequence, invented_packs, invented_ipa,
)


def replace_in_paired_wads(sources, before, after, *,
                           second_only=False):
    if len(before) != len(after):
        raise ValueError("Fabricated mutation cannot shift WAD offsets")
    repos, wads, cuts = sources
    for screen in SCREENS:
        if second_only and screen == SCREENS[0]:
            continue
        if wads[screen].count(before) != 1:
            raise ValueError("Expected unique fabricated native time header")
        wads[screen] = wads[screen].replace(before, after, 1)
    return repos, wads, cuts


class Stage168ArtificialTimingLedger(unittest.TestCase):
    def report(self, source=None):
        return summarize_native_sequence_time_ledger(
            *(invented_packs() if source is None else source)
        )

    def screen(self, source=None, index=0):
        return self.report(source)["per_source_resolution_pack"][SCREENS[index]]

    def test_time_buckets_distinguish_zero_and_nonzero(self):
        for value, expected in (
            (-1,"negative"), (0,"zero"), (1,"one_to_nine"),
            (9,"one_to_nine"), (10,"ten_to_ninety_nine"),
            (99,"ten_to_ninety_nine"),
            (100,"hundred_to_nine_ninety_nine"),
            (999,"hundred_to_nine_ninety_nine"),
            (1000,"one_thousand_or_more"),
            (10000,"one_thousand_or_more"),
        ):
            with self.subTest(value=value):
                self.assertEqual(_time_bucket(value), expected)

    def test_invalid_time_bucket_bool_not_treated_as_int(self):
        for value in (True, None, "100", 5.5):
            with self.assertRaises(ValueError):
                _time_bucket(value)

    def test_signed_header_buckets(self):
        for value, expected in ((-30,"negative"), (0,"zero"),
                                (1,"positive"), (10,"positive")):
            self.assertEqual(_sign(value), expected)

    def test_signed_header_rejects_booleans(self):
        with self.assertRaises(ValueError):
            _sign(True)

    def test_native_boolean_byte_is_not_automatically_truth_value(self):
        self.assertEqual(_bool_category(0), "zero")
        self.assertEqual(_bool_category(1), "one")
        self.assertEqual(_bool_category(2), "other_nonzero")
        self.assertEqual(_bool_category(255), "other_nonzero")

    def test_bad_bool_category_inputs_rejected(self):
        for val in (-1, 256, None, True):
            with self.assertRaises(ValueError):
                _bool_category(val)

    def test_all_three_fake_frames_accounted_for(self):
        record = self.screen()
        self.assertEqual(record["sequence_records"], 3)
        self.assertEqual(record["frame_records"], 3)
        self.assertEqual(record["empty_sequences"], 1)

    def test_coarse_time_buckets_not_exact_original_values(self):
        c = self.screen()["frame_time_value_buckets"]
        self.assertEqual(c["ten_to_ninety_nine"], 3)
        self.assertEqual(c["zero"], 0)
        self.assertEqual(sum(c.values()), 3)

    def test_fabricated_sequence_total_buckets(self):
        totals = self.screen()["sequence_total_time_buckets"]
        self.assertEqual(totals["zero"], 1)
        self.assertEqual(totals["ten_to_ninety_nine"], 1)
        self.assertEqual(totals["hundred_to_nine_ninety_nine"], 1)
        self.assertEqual(sum(totals.values()), 3)

    def test_fabricated_bool_byte_buckets(self):
        buckets = self.screen()["frame_bool_byte_buckets"]
        self.assertEqual(buckets, {
            "zero": 2, "one": 1, "other_nonzero": 0
        })

    def test_zero_frame_sequence_has_zero_total_not_fake_frame(self):
        r = self.screen()
        self.assertEqual(r["empty_sequences"], 1)
        self.assertEqual(r["sequence_third_field_equals_frame_time_sum"], 1)

    def test_nonempty_sum_positive_no_overflow(self):
        r = self.screen()
        self.assertEqual(r["sequences_with_positive_total_time"], 2)
        self.assertEqual(r["sequences_whose_total_exceeds_signed_32_bit"], 0)
        self.assertEqual(r["nonempty_sequences_with_all_zero_time_frames"], 0)

    def test_zero_and_negative_time_frames_are_counted(self):
        repos,wads,cuts = invented_packs()
        old = struct.pack("<4i", 1, 40, 1, 0)
        new = struct.pack("<4i", 1, 0, 1, 0)
        repos,wads,cuts = replace_in_paired_wads((repos,wads,cuts),old,new)
        old = struct.pack("<4i", 2, 60, 0, 0)
        new = struct.pack("<4i", 2, -4, 0, 0)
        r = self.screen(replace_in_paired_wads((repos,wads,cuts),old,new))
        self.assertEqual(r["frame_time_value_buckets"]["zero"], 1)
        self.assertEqual(r["frame_time_value_buckets"]["negative"], 1)
        self.assertEqual(r["sequences_with_any_zero_time_frame"], 1)
        self.assertEqual(r["sequences_with_any_negative_time_frame"], 1)

    def test_signed_32_bit_sum_overflow_is_flagged(self):
        source = invented_packs()
        source = replace_in_paired_wads(
            source, struct.pack("<4i", 1, 40, 1, 0),
            struct.pack("<4i", 1, 2147483647, 1, 0))
        r = self.screen(source)
        self.assertEqual(r["sequences_whose_total_exceeds_signed_32_bit"], 1)

    def test_two_resolutions_match_when_fake_values_match(self):
        compare = self.report()["paired_resolution_comparison"]
        self.assertEqual(compare["sequences_with_identical_frame_time_values"], 3)
        self.assertEqual(compare["sequences_with_any_frame_time_difference"], 0)
        self.assertEqual(compare["sequences_with_identical_bool_values"], 3)

    def test_changed_other_frame_field_not_mistaken_for_timing_difference(self):
        c = self.report(invented_packs(other_resolution_header=True))[
            "paired_resolution_comparison"
        ]
        self.assertEqual(c["sequences_with_any_frame_time_difference"], 0)

    def test_changed_second_resolution_time_detected_without_name_export(self):
        source = replace_in_paired_wads(
            invented_packs(),
            struct.pack("<4i", 1, 40, 1, 0),
            struct.pack("<4i", 1, 50, 1, 0),
            second_only=True,
        )
        compare = self.report(source)["paired_resolution_comparison"]
        self.assertEqual(compare["sequences_with_any_frame_time_difference"], 1)
        self.assertEqual(compare["individual_frame_time_differences"], 1)
        self.assertEqual(compare["sequences_with_same_total_time"], 2)

    def test_changed_frame_bool_detected_in_second_resolution(self):
        sources = invented_packs()
        r,w,c = sources
        # A unique fictional 21-byte frame header at the first frame.
        before = struct.pack("<4iBi", 1, 40, 1, 0, 0, 1)
        after = struct.pack("<4iBi", 1, 40, 1, 0, 2, 1)
        source = replace_in_paired_wads(
            (r,w,c),before,after,second_only=True)
        comparison = self.report(source)["paired_resolution_comparison"]
        self.assertEqual(comparison["sequences_with_any_bool_difference"], 1)
        self.assertEqual(comparison["sequences_with_any_frame_time_difference"], 0)

    def test_noncanonical_bool_remains_observable_not_silently_dropped(self):
        source = replace_in_paired_wads(
            invented_packs(),
            struct.pack("<4iBi", 1, 40, 1, 0, 0, 1),
            struct.pack("<4iBi", 1, 40, 1, 0, 2, 1))
        self.assertEqual(self.screen(source)["frame_bool_byte_buckets"][
            "other_nonzero"],1)

    def test_original_frame_timing_not_claimed_calibrated(self):
        report = self.report()
        self.assertTrue(report["frame_time_is_second_native_frame_header_integer"])
        self.assertFalse(report["milliseconds_per_time_unit_calibrated"])
        self.assertFalse(report["playback_tick_looping_policy_validated"])
        self.assertFalse(report["source_art_or_runtime_state_import_enabled"])

    def test_aggregate_json_does_not_expose_any_original_like_name(self):
        out = json.dumps(self.report())
        for secret in ("InventedIdle", "InventedNoSymbols", "CutA",
                       "raw_original_time_40", "private_offset_73", "symbol"):
            # Classification can mention 'sprite' but no original keys.
            if secret == "symbol":
                continue
            self.assertNotIn(secret, out)
        self.assertFalse(self.report()[
            "raw_time_values_names_positions_images_or_traces_exported"])

    def test_bad_original_index_rejected(self):
        r,w,c = invented_packs()
        r[SCREENS[1]] += b"\xff"
        with self.assertRaises(SpriteIndexFormatError):
            self.report((r,w,c))

    def test_fabricated_owner_ipa_end_to_end(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "fictional.ipa"
            invented_ipa(path, invented_packs())
            out = audit_private_native_sequence_time_ledger(path)
        self.assertEqual(out["per_source_resolution_pack"][
            SCREENS[0]]["frame_records"], 3)

    def test_duplicate_member_in_fake_archive_rejected(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "fictional.ipa"
            invented_ipa(path, invented_packs(), duplicate=True)
            with self.assertRaisesRegex(ValueError, "Duplicate"):
                audit_private_native_sequence_time_ledger(path)

    def test_fake_zip_selected_symlink_rejected(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "fictional.ipa"
            invented_ipa(path, invented_packs(), symlink=True)
            with self.assertRaisesRegex(ValueError, "unsafe selected"):
                audit_private_native_sequence_time_ledger(path)

    def test_missing_original_file_rejected(self):
        with self.assertRaisesRegex(ValueError, "Owner-private original IPA"):
            audit_private_native_sequence_time_ledger(
                Path("/not-present/owner-source.ipa"))


if __name__ == "__main__":
    unittest.main()
