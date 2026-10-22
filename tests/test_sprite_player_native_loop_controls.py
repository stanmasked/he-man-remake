"""Stage170: fabricated-only native replay/finished-state boundary tests."""
from __future__ import annotations

import json
from pathlib import Path
import struct
from tempfile import TemporaryDirectory
import unittest

from heman_tools.sprite_repo_wad_index import (
    SCREENS, SpriteIndexFormatError, parse_sprite_repository,
)
from heman_tools.sprite_sequence_header_controls import REPO_PATH, WAD_PATH
from heman_tools.sprite_player_native_loop_controls import (
    NativePlayerState, advance_native_player, is_native_finished,
    summarize_native_player_loop_controls,
    audit_private_native_player_loop_controls,
)
from test_sprite_repo_wad_index import string
from test_sprite_sequence_native_loader_structure import (
    invented_packs, invented_ipa,
)


def state(index, ticks, replays):
    return NativePlayerState(index, ticks, replays)


def invented_loop_packs():
    repos, wads, cuts = invented_packs()
    for screen in SCREENS:
        idx = parse_sprite_repository(
            repos[screen], expected_label="SpriteSeqData",
            expected_wad=WAD_PATH,
        )
        raw = bytearray(wads[screen])
        for key, loop_value in (("InventedEmpty", -1),
                                ("InventedNoSymbols", 3)):
            row = next(x for x in idx if x.key == key)
            struct.pack_into("<i", raw,
                             row.offset + len(string(key)), loop_value)
        wads[screen] = bytes(raw)
    return repos, wads, cuts


class Stage170FabricatedReplayControls(unittest.TestCase):
    def test_no_repeat_before_next_internal_boundary(self):
        self.assertEqual(advance_native_player(
            (0,40,100), 0, state(0,39,0)), state(0,39,0))

    def test_next_frame_selected_at_exact_internal_boundary(self):
        self.assertEqual(advance_native_player(
            (0,40,100), 0, state(0,40,0)), state(1,40,0))

    def test_no_repeat_exactly_at_total_stays_last(self):
        self.assertEqual(advance_native_player(
            (0,40,100), 0, state(0,100,0)), state(1,100,0))

    def test_no_repeat_after_total_stays_last(self):
        self.assertEqual(advance_native_player(
            (0,40,100), 0, state(0,110,0)), state(1,110,0))

    def test_finite_one_extra_replay_rewinds_time_and_counter(self):
        self.assertEqual(advance_native_player(
            (0,40,100), 1, state(0,100,1)), state(0,0,0))

    def test_finite_two_replays_can_be_consumed_in_one_step(self):
        self.assertEqual(advance_native_player(
            (0,40,100), 2, state(0,210,2)), state(0,10,0))

    def test_finite_repeat_not_decremented_before_total(self):
        self.assertEqual(advance_native_player(
            (0,40,100), 3, state(0,99,3)), state(1,99,3))

    def test_expired_replay_counter_blocks_additional_wrap(self):
        self.assertEqual(advance_native_player(
            (0,40,100), 2, state(1,201,0)), state(1,201,0))

    def test_negative_loop_never_decrements_replay_count(self):
        self.assertEqual(advance_native_player(
            (0,40,100), -1, state(0,245,-1)), state(1,45,-1))

    def test_any_negative_policy_can_stay_unchanged(self):
        self.assertEqual(advance_native_player(
            (0,40,100), -2, state(0,145,-2)), state(1,45,-2))

    def test_one_frame_zero_replay_stops_on_only_frame(self):
        self.assertEqual(advance_native_player(
            (0,100),0,state(0,110,0)),state(0,110,0))

    def test_one_frame_with_finite_replay_wraps_once(self):
        self.assertEqual(advance_native_player(
            (0,100),1,state(0,100,1)),state(0,0,0))

    def test_empty_sequence_preserves_explicit_sentinel(self):
        self.assertEqual(advance_native_player(
            (0,),0,state(-1,0,0)),state(-1,0,0))

    def test_multiple_zero_time_frames_are_skipped(self):
        self.assertEqual(advance_native_player(
            (0,0,0,40),0,state(0,0,0)),state(2,0,0))

    def test_terminal_zero_time_frame_selects_last(self):
        self.assertEqual(advance_native_player(
            (0,10,10),0,state(0,10,0)),state(1,10,0))

    def test_zero_total_infinite_replay_rejected(self):
        with self.assertRaisesRegex(ValueError,"Zero-duration"):
            advance_native_player((0,0,0),-1,state(0,0,-1))

    def test_step_budget_prevents_unbounded_work(self):
        with self.assertRaisesRegex(ValueError,"budget"):
            advance_native_player(
                (0,1,2),-1,state(0,1000,-1),max_steps=2)

    def test_finished_only_after_strict_last_right_edge(self):
        for ticks, expected in ((99,False),(100,False),(101,True)):
            with self.subTest(ticks=ticks):
                self.assertEqual(is_native_finished(
                    (0,40,100),0,state(1,ticks,0)),expected)

    def test_finished_false_if_not_on_last_frame(self):
        self.assertFalse(is_native_finished(
            (0,40,100),0,state(0,200,0)))

    def test_finished_false_if_replay_remaining(self):
        self.assertFalse(is_native_finished(
            (0,40,100),1,state(1,101,1)))
        self.assertFalse(is_native_finished(
            (0,40,100),-1,state(1,101,-1)))

    def test_empty_sequence_is_finished(self):
        self.assertTrue(is_native_finished(
            (0,),0,state(-1,0,0)))

    def test_bad_native_state_or_loop_policy_rejected(self):
        for loop, original in (
                (0,state(0,0,1)),(-1,state(0,0,0)),
                (1,state(0,0,-1)),(True,state(0,0,0)),
                (0,state(True,0,0)),(0,state(0,True,0)),
                (0,state(2,0,0))):
            with self.subTest(loop=loop,original=original):
                with self.assertRaises(ValueError):
                    advance_native_player((0,100),loop,original)

    def test_source_loop_categories_are_not_runtime_frames(self):
        result = summarize_native_player_loop_controls(
            *invented_loop_packs())
        c = result["per_original_resolution_pack"]
        self.assertEqual(c["sequences"],3)
        self.assertEqual(c["infinite_replay_settings"],1)
        self.assertEqual(c["zero_replay_settings"],1)
        self.assertEqual(c["positive_finite_replay_settings"],1)
        self.assertEqual(c["sequences_with_no_frames"],1)

    def test_aggregate_contains_no_resource_identifiers_or_traces(self):
        result = summarize_native_player_loop_controls(
            *invented_loop_packs())
        data = json.dumps(result)
        for forbidden in ("InventedIdle","CutA","original_elapsed_100",
                          "per_record_frame_position"):
            self.assertNotIn(forbidden,data)
        self.assertFalse(result[
            "original_record_loop_values_frame_names_and_timestamps_exported"])
        self.assertFalse(result[
            "native_tick_seconds_and_float_conversion_verified"])
        self.assertFalse(result[
            "runtime_mesh_texture_and_collision_playback_verified"])

    def test_fabricated_ipa_roundtrip_and_zip_security(self):
        with TemporaryDirectory() as tmp:
            p=Path(tmp)/"synthetic.ipa"
            invented_ipa(p,invented_loop_packs())
            r=audit_private_native_player_loop_controls(p)
        self.assertEqual(r["per_original_resolution_pack"]["sequences"],3)

    def test_duplicate_zip_member_or_selected_symlink_rejected(self):
        with TemporaryDirectory() as tmp:
            for label,kw in (("duplicate",{"duplicate":True}),
                             ("symlink",{"symlink":True})):
                p=Path(tmp)/(label+".ipa")
                invented_ipa(p,invented_packs(),**kw)
                with self.subTest(label=label),self.assertRaises(ValueError):
                    audit_private_native_player_loop_controls(p)

    def test_missing_ipa_rejected(self):
        with self.assertRaisesRegex(ValueError,"Owner-private original IPA"):
            audit_private_native_player_loop_controls(
                Path("/not-present/heman-owner-source.ipa"))


if __name__ == "__main__":
    unittest.main()
