#include "heman_app_tick_scheduler.h"
#include "heman_sprite_clock.h"

#include <assert.h>
#include <stdio.h>

static void test_one_second_callback_pattern_against_finite_animation(void) {
    const int32_t boundaries[] = {0, 240, 480, 720};
    const int32_t wall_pattern[] = {16, 17, 17};
    hm_sprite_clock_state state = {0, 0, 1};
    int32_t accumulator = 0;
    uint32_t updates = 0u, total_updates = 0u, state_changes = 0u;
    unsigned callback, step;
    int finished = 0;

    for (callback = 0u; callback < 60u; ++callback) {
        assert(hm_app_tick_scheduler_advance(
            &accumulator, wall_pattern[callback % 3u], &updates) ==
            HM_APP_TICK_OK);
        total_updates += updates;
        for (step = 0u; step < updates; ++step) {
            const hm_sprite_clock_state before = state;
            assert(hm_sprite_clock_step(
                boundaries, 3u, 1, &state, 0.04f, 1.0f, 1, 128u) ==
                HM_SPRITE_CLOCK_OK);
            if (before.frame_index != state.frame_index ||
                before.elapsed_ticks != state.elapsed_ticks ||
                before.remaining_replays != state.remaining_replays) {
                ++state_changes;
            }
        }
    }

    assert(total_updates == 62u);
    assert(accumulator == 8);
    assert(state_changes == 37u);
    assert(state.frame_index == 2);
    assert(state.elapsed_ticks == 760);
    assert(state.remaining_replays == 0);
    assert(hm_sprite_clock_is_finished(
        boundaries, 3u, 1, &state, &finished) == HM_SPRITE_CLOCK_OK);
    assert(finished == 1);
}

static void test_long_stall_cap_limits_animation_updates(void) {
    const int32_t boundaries[] = {0, 1000, 2000};
    hm_sprite_clock_state state = {0, 0, 0};
    int32_t accumulator = 0;
    uint32_t updates = 0u, i;
    assert(hm_app_tick_scheduler_advance(&accumulator, 500, &updates) ==
           HM_APP_TICK_OK);
    assert(updates == 4u && accumulator == 2);
    for (i = 0u; i < updates; ++i) {
        assert(hm_sprite_clock_step(
            boundaries, 2u, 0, &state, 0.04f, 1.0f, 1, 128u) ==
            HM_SPRITE_CLOCK_OK);
    }
    assert(state.frame_index == 0 && state.elapsed_ticks == 160);
}

int main(void) {
    test_one_second_callback_pattern_against_finite_animation();
    test_long_stall_cap_limits_animation_updates();
    puts("PASS: 2 synthetic app-scheduler + sprite-clock integration scenarios");
    return 0;
}
