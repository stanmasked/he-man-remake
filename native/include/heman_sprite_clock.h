#ifndef HEMAN_SPRITE_CLOCK_H
#define HEMAN_SPRITE_CLOCK_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define HM_SPRITE_CLOCK_MAX_FRAMES 1024u
#define HM_SPRITE_CLOCK_DEFAULT_MAX_STEPS 16384u

typedef enum {
    HM_SPRITE_CLOCK_OK = 0,
    HM_SPRITE_CLOCK_INVALID = -1,
    HM_SPRITE_CLOCK_RANGE = -2,
    HM_SPRITE_CLOCK_LIMIT = -3
} hm_sprite_clock_result;

/* elapsed_ticks uses the original player's integer clock domain.
   It is deliberately not named milliseconds until the caller's timebase
   has been verified independently. */
typedef struct {
    int32_t frame_index;       /* -1 only when frame_count == 0 */
    int32_t elapsed_ticks;     /* nonnegative signed integer */
    int32_t remaining_replays; /* negative loop policy stays negative */
} hm_sprite_clock_state;

/* boundaries has frame_count+1 entries: boundaries[0] must be zero,
   values must be nonnegative, monotonic, and fit signed int32.
   A zero-frame sequence still supplies boundaries[0] == 0. */
int hm_sprite_clock_validate(const int32_t *boundaries,
                             uint32_t frame_count,
                             int32_t loop_setting,
                             const hm_sprite_clock_state *state);

/* Mirrors the inspected float32 * rate, then float32 * 1000.0,
   followed by truncation toward zero. Returns RANGE before unsafe casts.
   This conversion alone accepts negative results; step() does not. */
hm_sprite_clock_result hm_sprite_tick_delta_i32(float delta_input,
                                                 float animation_rate,
                                                 int32_t *out_delta);

/* The finished predicate is true for empty sequences; otherwise it requires
   the last frame, elapsed strictly greater than its right boundary, and
   zero remaining replays. Writes *out_finished only on success. */
hm_sprite_clock_result hm_sprite_clock_is_finished(
    const int32_t *boundaries, uint32_t frame_count, int32_t loop_setting,
    const hm_sprite_clock_state *state, int *out_finished);

/* Apply all native frame/replay transitions at the state's current elapsed
   time. No allocations. max_steps must be in [1, DEFAULT_MAX_STEPS]. */
hm_sprite_clock_result hm_sprite_clock_advance(
    const int32_t *boundaries, uint32_t frame_count, int32_t loop_setting,
    hm_sprite_clock_state *state, uint32_t max_steps);

/* Bounded normal active tick path: finished check before time addition,
   float32 conversion, nonnegative elapsed accumulation and native frame
   transitions. Invalid calls leave state unchanged. playback_active is 0/1.
   Caller delta-time units remain an explicit integration responsibility. */
hm_sprite_clock_result hm_sprite_clock_step(
    const int32_t *boundaries, uint32_t frame_count, int32_t loop_setting,
    hm_sprite_clock_state *state, float delta_input, float animation_rate,
    int playback_active, uint32_t max_steps);

#ifdef __cplusplus
}
#endif
#endif
