#include "heman_app_tick_scheduler.h"
#include "heman_sprite_clock.h"

#include <assert.h>
#include <stdint.h>
#include <stdio.h>

static void test_one_second_combined_schedule(void) {
    static const int32_t boundaries[] = {0, 240, 480, 720};
    static const int32_t callback_ms[] = {16, 17, 17};
    hm_sprite_clock_state state = {0, 0, 1};
    int32_t accumulator = 0;
    uint32_t updates = 0u, total_updates = 0u, player_calls = 0u;
    uint32_t i, j;
    int32_t wall_ms = 0;
    int finished = 0;

    for (i = 0u; i < 60u; ++i) {
        const int32_t delta_ms = callback_ms[i % 3u];
        wall_ms += delta_ms;
        assert(hm_app_tick_scheduler_advance(&accumulator, delta_ms,
                                             &updates) == HM_APP_TICK_OK);
        total_updates += updates;
        for (j = 0u; j < updates; ++j) {
            assert(hm_sprite_clock_step(boundaries, 3u, 1, &state,
                                        0.04f, 1.0f, 1, 128u) ==
                   HM_SPRITE_CLOCK_OK);
            ++player_calls;
        }
    }

    assert(wall_ms == 1000);
    assert(total_updates == 62u && player_calls == 62u);
    assert(accumulator == 8);
    assert(state.frame_index == 2 && state.elapsed_ticks == 760 &&
           state.remaining_replays == 0);
    assert(hm_sprite_clock_is_finished(boundaries, 3u, 1, &state,
                                         &finished) == HM_SPRITE_CLOCK_OK);
    assert(finished == 1);
}

/* Stage179: isolate the fixed player delta from a short animation's finish.
   If every scheduler update still advances by 0.04f, 62 updates offer 2480
   integer time units during a fabricated second, while this long animation
   remains active. This is a deterministic code-model check, not device timing. */
static void test_one_second_fixed_delta_budget_while_animation_active(void) {
    static const int32_t boundaries[] = {0, 10000};
    static const int32_t callback_ms[] = {16, 17, 17};
    hm_sprite_clock_state state = {0, 0, -1};
    int32_t accumulator = 0;
    int32_t wall_ms = 0;
    uint32_t updates = 0u, total_updates = 0u, player_calls = 0u;
    uint32_t i, j;
    int finished = 1;

    for (i = 0u; i < 60u; ++i) {
        const int32_t delta_ms = callback_ms[i % 3u];
        wall_ms += delta_ms;
        assert(hm_app_tick_scheduler_advance(&accumulator, delta_ms,
                                             &updates) == HM_APP_TICK_OK);
        total_updates += updates;
        for (j = 0u; j < updates; ++j) {
            assert(hm_sprite_clock_step(boundaries, 1u, -1, &state,
                                        0.04f, 1.0f, 1, 128u) ==
                   HM_SPRITE_CLOCK_OK);
            ++player_calls;
        }
    }

    assert(wall_ms == 1000);
    assert(total_updates == 62u && player_calls == 62u);
    assert(accumulator == 8);
    assert(state.frame_index == 0 && state.elapsed_ticks == 2480 &&
           state.remaining_replays == -1);
    assert(hm_sprite_clock_is_finished(boundaries, 1u, -1, &state,
                                         &finished) == HM_SPRITE_CLOCK_OK);
    assert(finished == 0);
}

static void test_stall_clamp_drives_at_most_four_player_updates(void) {
    static const int32_t boundaries[] = {0, 100000};
    hm_sprite_clock_state state = {0, 0, -1};
    int32_t accumulator = 0;
    uint32_t updates = 0u, i;
    assert(hm_app_tick_scheduler_advance(&accumulator, 500, &updates) ==
           HM_APP_TICK_OK);
    assert(updates == 4u && accumulator == 2);
    for (i = 0u; i < updates; ++i) {
        assert(hm_sprite_clock_step(boundaries, 1u, -1, &state,
                                    0.04f, 1.0f, 1, 128u) ==
               HM_SPRITE_CLOCK_OK);
    }
    assert(state.frame_index == 0 && state.elapsed_ticks == 160 &&
           state.remaining_replays == -1);
}

static void test_paused_player_ignores_scheduler_updates(void) {
    static const int32_t boundaries[] = {0, 100000};
    hm_sprite_clock_state state = {0, 0, -1};
    hm_sprite_clock_state before = state;
    int32_t accumulator = 0;
    uint32_t updates = 0u, i;
    assert(hm_app_tick_scheduler_advance(&accumulator, 32, &updates) ==
           HM_APP_TICK_OK);
    assert(updates == 2u);
    for (i = 0u; i < updates; ++i) {
        assert(hm_sprite_clock_step(boundaries, 1u, -1, &state,
                                    0.04f, 1.0f, 0, 128u) ==
               HM_SPRITE_CLOCK_OK);
    }
    assert(state.frame_index == before.frame_index &&
           state.elapsed_ticks == before.elapsed_ticks &&
           state.remaining_replays == before.remaining_replays);
    assert(hm_app_tick_scheduler_advance(&accumulator, 16, &updates) ==
           HM_APP_TICK_OK);
    assert(updates == 1u);
    assert(hm_sprite_clock_step(boundaries, 1u, -1, &state,
                                0.04f, 1.0f, 1, 128u) == HM_SPRITE_CLOCK_OK);
    assert(state.elapsed_ticks == 40);
}

int main(void) {
    test_one_second_combined_schedule();
    test_one_second_fixed_delta_budget_while_animation_active();
    test_stall_clamp_drives_at_most_four_player_updates();
    test_paused_player_ignores_scheduler_updates();
    puts("PASS: 4 combined app-scheduler + sprite-clock scenarios");
    return 0;
}
