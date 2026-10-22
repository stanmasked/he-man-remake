"""Stage171 synthetic-only original-style float32 tick conversion tests."""
from __future__ import annotations

import math
import unittest

from heman_tools.sprite_player_native_tick_conversion import (
    _strict_f32, native_tick_delta_as_i32,
    step_native_player_from_float_tick,
)
from heman_tools.sprite_player_native_loop_controls import NativePlayerState


def state(index=0, elapsed=0, replay=0):
    return NativePlayerState(index, elapsed, replay)


class Stage171InventedNativeTickTests(unittest.TestCase):
    def test_rate_default_one_is_native_constructor_default(self):
        self.assertEqual(native_tick_delta_as_i32(0.02), 20)

    def test_rate_two_doubles_nominal_delta(self):
        self.assertEqual(native_tick_delta_as_i32(0.02, 2.0), 40)

    def test_rate_half_halves_nominal_delta(self):
        self.assertEqual(native_tick_delta_as_i32(0.02, 0.5), 10)

    def test_rate_zero_produces_zero_tick(self):
        self.assertEqual(native_tick_delta_as_i32(0.4, 0.0), 0)

    def test_one_sixtieth_time_input_truncates_to_sixteen(self):
        self.assertEqual(native_tick_delta_as_i32(1.0 / 60.0), 16)

    def test_two_separate_fractional_ticks_each_truncate(self):
        self.assertEqual(native_tick_delta_as_i32(0.0006), 0)
        self.assertEqual(native_tick_delta_as_i32(0.0012), 1)

    def test_exact_millisecond_input_one(self):
        self.assertEqual(native_tick_delta_as_i32(0.001), 1)

    def test_below_one_millisecond_truncates_to_zero(self):
        self.assertEqual(native_tick_delta_as_i32(0.000999), 0)

    def test_above_one_millisecond_keeps_integer_part(self):
        self.assertEqual(native_tick_delta_as_i32(0.001001), 1)

    def test_fractional_1_5_truncates_not_rounds_nearest(self):
        self.assertEqual(native_tick_delta_as_i32(0.0015), 1)

    def test_negative_fractional_delta_truncates_toward_zero(self):
        self.assertEqual(native_tick_delta_as_i32(-0.0015), -1)

    def test_negative_submillisecond_delta_becomes_zero(self):
        self.assertEqual(native_tick_delta_as_i32(-0.0006), 0)

    def test_negative_rate_is_valid_converter_but_not_playback_oracle(self):
        self.assertEqual(native_tick_delta_as_i32(0.002, -1.0), -2)

    def test_no_uncontrolled_input_list_or_bool(self):
        for invalid in (True, False, "0.016", [], None):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    native_tick_delta_as_i32(invalid)

    def test_no_nonfinite_float_allowed_in_private_reference(self):
        for invalid in (math.inf, -math.inf, math.nan):
            with self.subTest(value=str(invalid)):
                with self.assertRaises(ValueError):
                    native_tick_delta_as_i32(invalid)

    def test_no_nonfinite_or_bool_animation_rate(self):
        for invalid in (math.nan, math.inf, True, None):
            with self.subTest(rate=str(invalid)):
                with self.assertRaises(ValueError):
                    native_tick_delta_as_i32(0.02, invalid)

    def test_float32_range_guard(self):
        with self.assertRaises(ValueError):
            native_tick_delta_as_i32(1e100)
        with self.assertRaises(ValueError):
            _strict_f32(1e100)

    def test_signed_i32_conversion_guard(self):
        with self.assertRaisesRegex(ValueError, "signed i32"):
            native_tick_delta_as_i32(3_000_000.0)

    def test_float32_roundtrip_uses_real_24bit_mantissa(self):
        self.assertEqual(_strict_f32(16777217.0), 16777216.0)

    def test_default_playback_inactive_preserves_state(self):
        old = state(0, 5, 0)
        self.assertEqual(step_native_player_from_float_tick(
            (0, 40, 100), 0, old, 0.02, playback_active=False), old)

    def test_inactive_mode_skips_delta_conversion(self):
        old = state(0, 5, 0)
        self.assertEqual(step_native_player_from_float_tick(
            (0, 40, 100), 0, old, math.nan,
            playback_active=False), old)

    def test_playback_active_must_be_boolean(self):
        with self.assertRaisesRegex(ValueError, "active"):
            step_native_player_from_float_tick(
                (0, 40), 0, state(), 0.01, playback_active=1)

    def test_active_calc_accumulates_quantized_tick(self):
        self.assertEqual(step_native_player_from_float_tick(
            (0, 40, 100), 0, state(0, 5), 0.02), state(0, 25))

    def test_active_calc_crosses_strict_frame_boundary(self):
        self.assertEqual(step_native_player_from_float_tick(
            (0, 40, 100), 0, state(0, 20), 0.02), state(1, 40))

    def test_full_end_holds_last_without_repeat(self):
        self.assertEqual(step_native_player_from_float_tick(
            (0, 40, 100), 0, state(1, 90), 0.01), state(1, 100))

    def test_finite_replay_rewinds_elapsed_on_total(self):
        self.assertEqual(step_native_player_from_float_tick(
            (0, 40, 100), 1, state(1, 90, 1), 0.01), state(0, 0, 0))

    def test_infinite_replay_preserves_negative_counter(self):
        self.assertEqual(step_native_player_from_float_tick(
            (0, 40, 100), -1, state(1, 90, -1), 0.02),
            state(0, 10, -1))

    def test_finished_before_calc_refuses_to_advance(self):
        previous = state(1, 101)
        self.assertEqual(step_native_player_from_float_tick(
            (0, 40, 100), 0, previous, 0.2), previous)

    def test_finished_at_exact_total_is_not_finished_yet(self):
        previous = state(1, 100)
        self.assertEqual(step_native_player_from_float_tick(
            (0, 40, 100), 0, previous, 0.01), state(1, 110))

    def test_zero_duration_source_frames_skipped(self):
        self.assertEqual(step_native_player_from_float_tick(
            (0, 0, 0, 40), 0, state(0, 0), 0.0), state(2, 0))

    def test_empty_sequence_skips_native_calc_even_if_active(self):
        self.assertEqual(step_native_player_from_float_tick(
            (0,), 0, state(-1), 0.2), state(-1))

    def test_reverse_time_rejected_in_playback_oracle(self):
        with self.assertRaisesRegex(ValueError, "reverse-time"):
            step_native_player_from_float_tick(
                (0, 40, 100), 0, state(), -0.01)

    def test_elapsed_accumulation_signed_overflow_fails(self):
        with self.assertRaisesRegex(ValueError, "overflow"):
            step_native_player_from_float_tick(
                (0, (1 << 31) - 1), 0,
                state(0, (1 << 31) - 6), 0.01)

    def test_synthetic_split_ticks_drop_fractional_remainder(self):
        boundaries = (0, 10_000)
        current = state()
        for _ in range(60):
            current = step_native_player_from_float_tick(
                boundaries, 0, current, 1.0 / 60.0)
        self.assertEqual(current.elapsed_ticks, 960)
        whole = step_native_player_from_float_tick(
            boundaries, 0, state(), 1.0)
        self.assertEqual(whole.elapsed_ticks, 1000)

    def test_step_budget_rejects_excessive_infinite_replays(self):
        with self.assertRaisesRegex(ValueError, "budget"):
            step_native_player_from_float_tick(
                (0, 1, 2), -1, state(0, 0, -1), 0.1,
                max_steps=2)


if __name__ == "__main__":
    unittest.main()
