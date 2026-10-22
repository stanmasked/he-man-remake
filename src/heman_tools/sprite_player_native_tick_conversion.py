"""Stage171: original SpritePlayer::tick(float) signed tick conversion oracle.

The owner-private ARMv7 function checks playback mode == 1, uses the
float32 custom animation rate (constructor default 1.0), multiplies the
float32 tick argument by that rate, multiplies by float32 1000.0, and
converts to a signed 32-bit integer with VCVT.S32.F32 (truncation toward
zero) before calling SpritePlayer::calc(int). The original calc checks
isFinished *before* adding the delta and advancing frames.

This pure, source-free reference models the NORMAL, finite, nonnegative
delta-time path only. It does not claim the upstream float input's time
unit has been independently established or emulate undefined/restricted
NaN, infinity, integer-overflow, negative playback, fade-state, pause
or visual behavior. Original binary code/assets/traces stay private.
Public CI only runs invented scalar values and fabricated boundaries.
"""
from __future__ import annotations

import math
import struct

from .sprite_player_native_loop_controls import (
    NativePlayerState, advance_native_player, is_native_finished,
)

_F32 = struct.Struct("<f")
_I32_MAX = (1 << 31) - 1
_I32_MIN = -(1 << 31)
_F32_ONE_THOUSAND = _F32.unpack(_F32.pack(1000.0))[0]


def _strict_f32(value: float) -> float:
    """Round a finite host scalar to IEEE-754 binary32 like ARM float regs."""
    if type(value) not in (float, int):
        raise ValueError("Expected finite float32-compatible scalar")
    if not math.isfinite(value):
        raise ValueError("Nonfinite native tick scalar unsupported")
    try:
        rounded = _F32.unpack(_F32.pack(float(value)))[0]
    except (OverflowError, ValueError, struct.error) as exc:
        raise ValueError("Native float32 scalar out of range") from exc
    if not math.isfinite(rounded):
        raise ValueError("Native float32 result is not finite")
    return rounded


def native_tick_delta_as_i32(
    elapsed_input: float, animation_rate: float = 1.0,
) -> int:
    """Emulate the inspected normal original VFP/NEON scalar lane.

    Two *separate* binary32 multiplies are required: input x rate,
    followed by x 1000.0. The integer conversion is truncated toward
    zero, NOT rounded to nearest, NOT accumulated in a float residue.
    Out-of-range conversion is refused rather than asserting an
    unsupported hardware saturation/NaN policy.
    """
    delta = _strict_f32(elapsed_input)
    rate = _strict_f32(animation_rate)
    scaled = _strict_f32(delta * rate)
    milliseconds = _strict_f32(scaled * _F32_ONE_THOUSAND)
    if not _I32_MIN <= milliseconds < _I32_MAX + 1:
        raise ValueError("Native tick conversion exceeds signed i32 bounds")
    return math.trunc(milliseconds)


def step_native_player_from_float_tick(
    boundaries: tuple[int, ...],
    loop_setting: int,
    state: NativePlayerState,
    elapsed_input: float,
    *,
    animation_rate: float = 1.0,
    playback_active: bool = True,
    max_steps: int = 16384,
) -> NativePlayerState:
    """Integrate the inspected normal active tick gate with Stage170.

    calc() tests isFinished before incrementing elapsed. We refuse
    negative converted ticks and signed overflow in this nonnegative
    oracle, because original backward-time and overflow behavior is
    outside the corroborated source test population.
    """
    if type(playback_active) is not bool:
        raise ValueError("Expected explicit active/paused player flag")
    finished_before = is_native_finished(boundaries, loop_setting, state)
    if not playback_active or finished_before:
        return state
    tick = native_tick_delta_as_i32(elapsed_input, animation_rate)
    if tick < 0:
        raise ValueError("Native reverse-time player path not yet verified")
    if state.elapsed_ticks > _I32_MAX - tick:
        raise ValueError("Native calc elapsed sum would overflow signed i32")
    progressed = NativePlayerState(
        state.frame_index,
        state.elapsed_ticks + tick,
        state.remaining_replays,
    )
    return advance_native_player(
        boundaries, loop_setting, progressed, max_steps=max_steps,
    )
