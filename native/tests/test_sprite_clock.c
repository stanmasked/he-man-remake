#include "heman_sprite_clock.h"
#include <assert.h>
#include <limits.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

static int near_i32(int32_t a, int32_t b) { return a == b; }

static void test_float32_conversion(void) {
    int32_t out = 99;
    assert(hm_sprite_tick_delta_i32(0.02f, 1.0f, &out) == HM_SPRITE_CLOCK_OK);
    assert(near_i32(out, 20));
    assert(hm_sprite_tick_delta_i32(0.02f, 2.0f, &out) == HM_SPRITE_CLOCK_OK);
    assert(near_i32(out, 40));
    assert(hm_sprite_tick_delta_i32(0.02f, 0.5f, &out) == HM_SPRITE_CLOCK_OK);
    assert(near_i32(out, 10));
    assert(hm_sprite_tick_delta_i32(1.0f / 60.0f, 1.0f, &out) == HM_SPRITE_CLOCK_OK);
    assert(near_i32(out, 16));
    assert(hm_sprite_tick_delta_i32(0.0006f, 1.0f, &out) == HM_SPRITE_CLOCK_OK);
    assert(near_i32(out, 0));
    assert(hm_sprite_tick_delta_i32(0.0015f, 1.0f, &out) == HM_SPRITE_CLOCK_OK);
    assert(near_i32(out, 1));
    assert(hm_sprite_tick_delta_i32(-0.0015f, 1.0f, &out) == HM_SPRITE_CLOCK_OK);
    assert(near_i32(out, -1));
    assert(hm_sprite_tick_delta_i32(0.002f, -1.0f, &out) == HM_SPRITE_CLOCK_OK);
    assert(near_i32(out, -2));
    assert(hm_sprite_tick_delta_i32(16777216.0f, 1.0f, &out) == HM_SPRITE_CLOCK_RANGE);
    assert(hm_sprite_tick_delta_i32(INFINITY, 1.0f, &out) == HM_SPRITE_CLOCK_INVALID);
    assert(hm_sprite_tick_delta_i32(NAN, 1.0f, &out) == HM_SPRITE_CLOCK_INVALID);
    assert(hm_sprite_tick_delta_i32(0.1f, INFINITY, &out) == HM_SPRITE_CLOCK_INVALID);
    assert(hm_sprite_tick_delta_i32(0.1f, 1.0f, NULL) == HM_SPRITE_CLOCK_INVALID);
}

static void test_strict_frame_boundaries(void) {
    const int32_t b[] = {0, 40, 100};
    hm_sprite_clock_state s = {0, 39, 0};
    assert(hm_sprite_clock_step(b, 2, 0, &s, 0.001f, 1.0f, 1, 32) == HM_SPRITE_CLOCK_OK);
    assert(s.frame_index == 1 && s.elapsed_ticks == 40 && s.remaining_replays == 0);
    s.frame_index = 0; s.elapsed_ticks = 20;
    assert(hm_sprite_clock_step(b, 2, 0, &s, 0.02f, 1.0f, 1, 32) == HM_SPRITE_CLOCK_OK);
    assert(s.frame_index == 1 && s.elapsed_ticks == 40);
}

static void test_finite_and_infinite_replay(void) {
    const int32_t b[] = {0, 40, 100};
    hm_sprite_clock_state finite = {1, 90, 1};
    hm_sprite_clock_state infinite = {1, 90, -1};
    assert(hm_sprite_clock_step(b, 2, 1, &finite, 0.01f, 1.0f, 1, 32) == HM_SPRITE_CLOCK_OK);
    assert(finite.frame_index == 0 && finite.elapsed_ticks == 0 && finite.remaining_replays == 0);
    assert(hm_sprite_clock_step(b, 2, -1, &infinite, 0.02f, 1.0f, 1, 32) == HM_SPRITE_CLOCK_OK);
    assert(infinite.frame_index == 0 && infinite.elapsed_ticks == 10 && infinite.remaining_replays == -1);
}

static void test_no_replay_finish_edges(void) {
    const int32_t b[] = {0, 40, 100};
    hm_sprite_clock_state s = {1, 100, 0};
    int finished = 1;
    assert(hm_sprite_clock_is_finished(b, 2, 0, &s, &finished) == HM_SPRITE_CLOCK_OK);
    assert(finished == 0);
    assert(hm_sprite_clock_step(b, 2, 0, &s, 0.001f, 1.0f, 1, 32) == HM_SPRITE_CLOCK_OK);
    assert(s.frame_index == 1 && s.elapsed_ticks == 101);
    assert(hm_sprite_clock_is_finished(b, 2, 0, &s, &finished) == HM_SPRITE_CLOCK_OK);
    assert(finished == 1);
    assert(hm_sprite_clock_step(b, 2, 0, &s, 1.0f, 1.0f, 1, 32) == HM_SPRITE_CLOCK_OK);
    assert(s.elapsed_ticks == 101);
}

static void test_zero_duration_and_empty(void) {
    const int32_t zeroes[] = {0, 0, 0, 40};
    const int32_t empty[] = {0};
    hm_sprite_clock_state s = {0, 0, 0};
    hm_sprite_clock_state e = {-1, 0, 0};
    int finished = 0;
    assert(hm_sprite_clock_step(zeroes, 3, 0, &s, 0.0f, 1.0f, 1, 32) == HM_SPRITE_CLOCK_OK);
    assert(s.frame_index == 2 && s.elapsed_ticks == 0);
    assert(hm_sprite_clock_is_finished(empty, 0, 0, &e, &finished) == HM_SPRITE_CLOCK_OK);
    assert(finished == 1);
    assert(hm_sprite_clock_step(empty, 0, 0, &e, 0.2f, 1.0f, 1, 32) == HM_SPRITE_CLOCK_OK);
    assert(e.frame_index == -1 && e.elapsed_ticks == 0);
}

static void test_pause_invalid_delta_and_rollback(void) {
    const int32_t b[] = {0, 40, 100};
    hm_sprite_clock_state s = {0, 10, 0}, before;
    before = s;
    assert(hm_sprite_clock_step(b, 2, 0, &s, NAN, 1.0f, 0, 32) == HM_SPRITE_CLOCK_OK);
    assert(memcmp(&s, &before, sizeof s) == 0);
    assert(hm_sprite_clock_step(b, 2, 0, &s, -0.01f, 1.0f, 1, 32) == HM_SPRITE_CLOCK_INVALID);
    assert(memcmp(&s, &before, sizeof s) == 0);
    assert(hm_sprite_clock_step(b, 2, 0, &s, 0.01f, 1.0f, 2, 32) == HM_SPRITE_CLOCK_INVALID);
    assert(memcmp(&s, &before, sizeof s) == 0);
    assert(hm_sprite_clock_step(b, 2, 0, &s, 0.01f, 1.0f, 1, 0) == HM_SPRITE_CLOCK_INVALID);
    assert(memcmp(&s, &before, sizeof s) == 0);
}

static void test_bounds_and_counter_validation(void) {
    const int32_t b[] = {0, INT32_MAX};
    const int32_t nonmonotonic[] = {0, 40, 30};
    hm_sprite_clock_state s = {0, INT32_MAX - 5, 0}, before;
    before = s;
    assert(hm_sprite_clock_step(b, 1, 0, &s, 0.01f, 1.0f, 1, 32) == HM_SPRITE_CLOCK_RANGE);
    assert(memcmp(&s, &before, sizeof s) == 0);
    s.frame_index = 0; s.elapsed_ticks = 0; s.remaining_replays = 1;
    before = s;
    assert(hm_sprite_clock_step(b, 1, 0, &s, 0.01f, 1.0f, 1, 32) == HM_SPRITE_CLOCK_INVALID);
    assert(memcmp(&s, &before, sizeof s) == 0);
    s.remaining_replays = 0;
    assert(hm_sprite_clock_validate(nonmonotonic, 2, 0, &s) == 0);
    assert(hm_sprite_clock_advance(b, 1, 0, &s, HM_SPRITE_CLOCK_DEFAULT_MAX_STEPS + 1u) == HM_SPRITE_CLOCK_INVALID);
}

static void test_transition_budget_and_zero_total_guard(void) {
    const int32_t short_loop[] = {0, 1, 2};
    const int32_t all_zero[] = {0, 0, 0};
    hm_sprite_clock_state s = {0, 1000, -1}, before = s;
    assert(hm_sprite_clock_advance(short_loop, 2, -1, &s, 2u) ==
           HM_SPRITE_CLOCK_LIMIT);
    assert(memcmp(&s, &before, sizeof s) == 0);
    s.frame_index = 0;
    s.elapsed_ticks = 0;
    s.remaining_replays = -1;
    before = s;
    assert(hm_sprite_clock_advance(all_zero, 2, -1, &s, 32u) ==
           HM_SPRITE_CLOCK_RANGE);
    assert(memcmp(&s, &before, sizeof s) == 0);
}

static void test_repeated_fractional_ticks_are_quantized_each_call(void) {
    const int32_t b[] = {0, 10000};
    hm_sprite_clock_state many = {0, 0, 0}, one = {0, 0, 0};
    unsigned i;
    for (i = 0; i < 60; ++i)
        assert(hm_sprite_clock_step(b, 1, 0, &many, 1.0f/60.0f, 1.0f, 1, 32) == HM_SPRITE_CLOCK_OK);
    assert(many.elapsed_ticks == 960);
    assert(hm_sprite_clock_step(b, 1, 0, &one, 1.0f, 1.0f, 1, 32) == HM_SPRITE_CLOCK_OK);
    assert(one.elapsed_ticks == 1000);
}

int main(void) {
    test_float32_conversion();
    test_strict_frame_boundaries();
    test_finite_and_infinite_replay();
    test_no_replay_finish_edges();
    test_zero_duration_and_empty();
    test_pause_invalid_delta_and_rollback();
    test_bounds_and_counter_validation();
    test_transition_budget_and_zero_total_guard();
    test_repeated_fractional_ticks_are_quantized_each_call();
    puts("PASS: 9 synthetic C99 sprite-clock scenarios");
    return 0;
}
