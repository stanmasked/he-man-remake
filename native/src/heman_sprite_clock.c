#include "heman_sprite_clock.h"

#include <math.h>
#include <stddef.h>

#define HM_SPRITE_CLOCK_I32_MIN_F (-2147483648.0f)
#define HM_SPRITE_CLOCK_I32_LIMIT_F (2147483648.0f)

int hm_sprite_clock_validate(const int32_t *boundaries,
                             uint32_t frame_count,
                             int32_t loop_setting,
                             const hm_sprite_clock_state *state) {
    uint32_t i;
    if (!boundaries || !state || frame_count > HM_SPRITE_CLOCK_MAX_FRAMES ||
        boundaries[0] != 0 || state->elapsed_ticks < 0 ||
        (frame_count == 0u ? state->frame_index != -1 :
         (state->frame_index < 0 ||
          (uint32_t)state->frame_index >= frame_count))) {
        return 0;
    }
    for (i = 1u; i <= frame_count; ++i) {
        if (boundaries[i] < 0 || boundaries[i] < boundaries[i - 1u]) {
            return 0;
        }
    }
    if (loop_setting < 0) {
        if (state->remaining_replays != loop_setting) return 0;
    } else if (state->remaining_replays < 0 ||
               state->remaining_replays > loop_setting) {
        return 0;
    }
    return 1;
}

hm_sprite_clock_result hm_sprite_tick_delta_i32(float delta_input,
                                                 float animation_rate,
                                                 int32_t *out_delta) {
    volatile float rate_product;
    volatile float scaled;
    float value;
    if (!out_delta || !isfinite(delta_input) || !isfinite(animation_rate)) {
        return HM_SPRITE_CLOCK_INVALID;
    }

    /* Volatile float intermediates force each multiply to round to binary32
       instead of allowing a compiler to retain excess intermediate precision. */
    rate_product = delta_input * animation_rate;
    scaled = rate_product * 1000.0f;
    value = scaled;
    if (!isfinite(value)) return HM_SPRITE_CLOCK_RANGE;
    /* 2^31 is exactly representable as float32; the upper comparison must be
       exclusive because converting +2^31 to int32_t is undefined in C. */
    if (value < HM_SPRITE_CLOCK_I32_MIN_F ||
        value >= HM_SPRITE_CLOCK_I32_LIMIT_F) {
        return HM_SPRITE_CLOCK_RANGE;
    }
    *out_delta = (int32_t)value; /* C truncates finite in-range floats to zero. */
    return HM_SPRITE_CLOCK_OK;
}

hm_sprite_clock_result hm_sprite_clock_is_finished(
    const int32_t *boundaries, uint32_t frame_count, int32_t loop_setting,
    const hm_sprite_clock_state *state, int *out_finished) {
    if (!out_finished ||
        !hm_sprite_clock_validate(boundaries, frame_count, loop_setting, state)) {
        return HM_SPRITE_CLOCK_INVALID;
    }
    if (frame_count == 0u) {
        *out_finished = 1;
    } else {
        const uint32_t last = frame_count - 1u;
        *out_finished =
            (uint32_t)state->frame_index == last &&
            state->elapsed_ticks > boundaries[last + 1u] &&
            state->remaining_replays == 0;
    }
    return HM_SPRITE_CLOCK_OK;
}

hm_sprite_clock_result hm_sprite_clock_advance(
    const int32_t *boundaries, uint32_t frame_count, int32_t loop_setting,
    hm_sprite_clock_state *state, uint32_t max_steps) {
    hm_sprite_clock_state next_state;
    int32_t previous, next_index, elapsed, remaining;
    int done = 0;
    uint32_t step;
    int32_t total;
    if (!state || max_steps == 0u ||
        max_steps > HM_SPRITE_CLOCK_DEFAULT_MAX_STEPS ||
        !hm_sprite_clock_validate(boundaries, frame_count, loop_setting, state)) {
        return HM_SPRITE_CLOCK_INVALID;
    }
    if (frame_count == 0u) return HM_SPRITE_CLOCK_OK;

    next_state = *state;
    previous = next_state.frame_index;
    next_index = (previous + 1) % (int32_t)frame_count;
    elapsed = next_state.elapsed_ticks;
    remaining = next_state.remaining_replays;
    total = boundaries[frame_count];

    for (step = 0u; step < max_steps; ++step) {
        if (next_index <= previous) {
            if (elapsed < total) {
                next_index = (int32_t)frame_count; /* end sentinel */
            } else {
                if (loop_setting >= 0) {
                    if (remaining == 0) {
                        done = 1;
                        break;
                    }
                    --remaining;
                }
                if (total == 0) return HM_SPRITE_CLOCK_RANGE;
                elapsed -= total;
            }
        }
        if (elapsed < boundaries[(uint32_t)next_index]) {
            done = 1;
            break;
        }
        previous = next_index;
        next_index = (previous + 1) % (int32_t)frame_count;
    }
    if (!done) return HM_SPRITE_CLOCK_LIMIT;
    next_state.frame_index = previous;
    next_state.elapsed_ticks = elapsed;
    next_state.remaining_replays = remaining;
    *state = next_state;
    return HM_SPRITE_CLOCK_OK;
}

hm_sprite_clock_result hm_sprite_clock_step(
    const int32_t *boundaries, uint32_t frame_count, int32_t loop_setting,
    hm_sprite_clock_state *state, float delta_input, float animation_rate,
    int playback_active, uint32_t max_steps) {
    hm_sprite_clock_state next_state;
    hm_sprite_clock_result result;
    int finished;
    int32_t delta;
    if (!state || (playback_active != 0 && playback_active != 1) ||
        !hm_sprite_clock_validate(boundaries, frame_count, loop_setting, state)) {
        return HM_SPRITE_CLOCK_INVALID;
    }
    result = hm_sprite_clock_is_finished(
        boundaries, frame_count, loop_setting, state, &finished);
    if (result != HM_SPRITE_CLOCK_OK) return result;
    if (!playback_active || finished) return HM_SPRITE_CLOCK_OK;

    result = hm_sprite_tick_delta_i32(delta_input, animation_rate, &delta);
    if (result != HM_SPRITE_CLOCK_OK) return result;
    if (delta < 0) return HM_SPRITE_CLOCK_INVALID;
    if (state->elapsed_ticks > INT32_MAX - delta) return HM_SPRITE_CLOCK_RANGE;

    next_state = *state;
    next_state.elapsed_ticks += delta;
    result = hm_sprite_clock_advance(
        boundaries, frame_count, loop_setting, &next_state, max_steps);
    if (result != HM_SPRITE_CLOCK_OK) return result;
    *state = next_state;
    return HM_SPRITE_CLOCK_OK;
}
