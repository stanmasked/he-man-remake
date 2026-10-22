"""Stage169: fake-only exact native keyframe timestamp and selection tests."""
from __future__ import annotations

import json
from pathlib import Path
import struct
from tempfile import TemporaryDirectory
import unittest

from heman_tools.sprite_repo_wad_index import SCREENS, SpriteIndexFormatError
from heman_tools.sprite_sequence_native_frame_boundaries import (
    build_keyframe_boundaries,
    frame_index_at_elapsed_ticks,
    summarize_native_frame_boundary_controls,
    audit_private_native_frame_boundary_controls,
)
from test_sprite_sequence_native_loader_structure import (
    invented_packs, invented_ipa,
)
from test_sprite_sequence_native_timing_ledger import (
    replace_in_paired_wads,
)


class Stage169FabricatedNativeFrameBoundaries(unittest.TestCase):
    def report(self, source=None):
        return summarize_native_frame_boundary_controls(
            *(invented_packs() if source is None else source)
        )

    def test_empty_sequence_has_one_zero_boundary(self):
        self.assertEqual(build_keyframe_boundaries(()), (0,))
        self.assertEqual(frame_index_at_elapsed_ticks((0,),0), -1)

    def test_one_frame_has_start_and_end(self):
        self.assertEqual(build_keyframe_boundaries((40,)), (0, 40))
        for t in (0,1,39,40,100):
            self.assertEqual(frame_index_at_elapsed_ticks((0,40),t),0)

    def test_multiple_frames_build_cumulative_boundaries(self):
        self.assertEqual(build_keyframe_boundaries((40,60,15)),
                         (0,40,100,115))

    def test_strict_right_edge_moves_to_next_frame(self):
        boundaries = build_keyframe_boundaries((40,60,15))
        for t, expected in ((0,0),(39,0),(40,1),(99,1),
                            (100,2),(114,2)):
            with self.subTest(t=t):
                self.assertEqual(frame_index_at_elapsed_ticks(
                    boundaries,t),expected)

    def test_at_and_after_total_clamp_to_last_frame(self):
        boundaries = build_keyframe_boundaries((40,60,15))
        for t in (115,116,1500):
            self.assertEqual(frame_index_at_elapsed_ticks(boundaries,t),2)

    def test_initial_zero_duration_frame_is_skipped(self):
        boundaries = build_keyframe_boundaries((0,15,20))
        self.assertEqual(boundaries, (0,0,15,35))
        self.assertEqual(frame_index_at_elapsed_ticks(boundaries,0),1)

    def test_middle_zero_duration_frame_is_skipped_at_edge(self):
        boundaries = build_keyframe_boundaries((10,0,20))
        self.assertEqual(frame_index_at_elapsed_ticks(boundaries,9),0)
        self.assertEqual(frame_index_at_elapsed_ticks(boundaries,10),2)

    def test_final_zero_duration_frame_selected_at_or_after_end(self):
        boundaries = build_keyframe_boundaries((10,0))
        self.assertEqual(frame_index_at_elapsed_ticks(boundaries,9),0)
        self.assertEqual(frame_index_at_elapsed_ticks(boundaries,10),1)

    def test_all_zero_duration_frames_default_last_at_time_zero(self):
        bounds = build_keyframe_boundaries((0,0,0))
        self.assertEqual(frame_index_at_elapsed_ticks(bounds,0),2)

    def test_negative_elapsed_is_not_treated_as_supported_original_runtime(self):
        with self.assertRaises(ValueError):
            frame_index_at_elapsed_ticks((0,40),-1)

    def test_negative_time_fields_not_silently_reinterpreted(self):
        with self.assertRaises(ValueError):
            build_keyframe_boundaries((20,-1))

    def test_signed_overflow_is_rejected_before_timestamp_wrap(self):
        with self.assertRaises(ValueError):
            build_keyframe_boundaries(((1<<31)-1,1))

    def test_maximum_valid_signed_time_remains_bounded(self):
        boundaries = build_keyframe_boundaries(((1<<31)-1,))
        self.assertEqual(boundaries[-1],(1<<31)-1)
        self.assertEqual(frame_index_at_elapsed_ticks(boundaries,
                         (1<<31)-1),0)

    def test_booleans_strings_and_lists_fail(self):
        for bad in (None,True,[40],(40,False),(40,"20")):
            with self.subTest(value=bad),self.assertRaises(ValueError):
                build_keyframe_boundaries(bad)

    def test_broken_nonmonotonic_or_unbounded_boundary_rejected(self):
        for bad in ((),(1,),(0,5,4),(0,True),(0,-1),
                    (0,(1<<31))):
            with self.subTest(value=bad),self.assertRaises(ValueError):
                frame_index_at_elapsed_ticks(bad,0)

    def test_player_time_query_bool_or_float_not_accepted(self):
        for bad in (True,0.5,"1"):
            with self.assertRaises(ValueError):
                frame_index_at_elapsed_ticks((0,10),bad)

    def test_parent_source_counts_reconciled(self):
        a=self.report()
        p=a["per_original_resolution_pack"][SCREENS[0]]
        self.assertEqual(p["sequences"],3)
        self.assertEqual(p["frames"],3)
        self.assertEqual(p["empty_sequences"],1)
        self.assertEqual(p["last_frame_clamp_confirmed"],3)

    def test_default_two_nonempty_sequence_types(self):
        p=self.report()["per_original_resolution_pack"][SCREENS[0]]
        self.assertEqual(p["single_frame_sequences"],1)
        self.assertEqual(p["two_or_more_frame_sequences"],1)
        self.assertEqual(p["sequences_with_positive_total"],2)
        self.assertEqual(p["sequences_with_zero_total"],1)

    def test_injected_initial_zero_frame_skips_on_zero_elapsed(self):
        source=replace_in_paired_wads(
            invented_packs(),
            struct.pack("<4i",1,40,1,0),
            struct.pack("<4i",1,0,1,0))
        c=self.report(source)["per_original_resolution_pack"][SCREENS[0]]
        self.assertEqual(c["sequences_skipping_initial_zero_frames"],1)
        self.assertEqual(c["zero_duration_frames"],1)

    def test_fake_resolution_specific_time_changes_detected(self):
        source=replace_in_paired_wads(
            invented_packs(),
            struct.pack("<4i",1,40,1,0),
            struct.pack("<4i",1,50,1,0),second_only=True)
        p=self.report(source)["paired_resolution_evidence"]
        self.assertEqual(p[
            "sequences_with_different_cumulative_boundaries"],1)
        self.assertEqual(p[
            "sequences_with_identical_cumulative_boundaries"],2)
        self.assertEqual(p["sequences_with_same_total_native_ticks"],2)

    def test_report_keeps_original_names_and_frame_arrays_private(self):
        serialized=json.dumps(self.report(),sort_keys=True)
        for bad in ("InventedIdle","InventedNoSymbols","CutA",
                    "private_source_elapsed_100","offset_40"):
            self.assertNotIn(bad,serialized)
        self.assertFalse(self.report()[
            "raw_frame_timestamps_source_names_images_or_offsets_exported"])
        self.assertFalse(self.report()[
            "infinite_finite_loop_replay_semantics_implemented"])
        self.assertFalse(self.report()[
            "upstream_tick_timescale_in_seconds_verified"])

    def test_fake_native_zip_roundtrip(self):
        with TemporaryDirectory() as tmp:
            path=Path(tmp)/"fictional.ipa"
            invented_ipa(path,invented_packs())
            result=audit_private_native_frame_boundary_controls(path)
        self.assertTrue(result[
            "stage168_timing_and_stage167_source_index_reconciled"])

    def test_fake_zip_duplicate_member_fails(self):
        with TemporaryDirectory() as tmp:
            path=Path(tmp)/"fictional.ipa"
            invented_ipa(path,invented_packs(),duplicate=True)
            with self.assertRaisesRegex(ValueError,"Duplicate"):
                audit_private_native_frame_boundary_controls(path)

    def test_fake_zip_selected_symlink_fails(self):
        with TemporaryDirectory() as tmp:
            path=Path(tmp)/"fictional.ipa"
            invented_ipa(path,invented_packs(),symlink=True)
            with self.assertRaisesRegex(ValueError,"unsafe selected"):
                audit_private_native_frame_boundary_controls(path)

    def test_absent_private_original_rejected(self):
        with self.assertRaisesRegex(ValueError,"Owner-private original IPA"):
            audit_private_native_frame_boundary_controls(
                Path("/missing/original.ipa"))


if __name__=="__main__":
    unittest.main()
