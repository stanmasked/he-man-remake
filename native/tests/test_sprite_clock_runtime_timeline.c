/* Stage177: exact synthetic callback-to-guest-frame clock checkpoints. */
#include "heman_app_tick_scheduler.h"
#include "heman_sprite_clock.h"

#include <assert.h>
#include <stdint.h>
#include <stdio.h>

typedef struct {
    uint32_t callback;
    uint32_t total_updates;
    uint32_t callback_updates;
    int32_t frame_index;
    int32_t elapsed_ticks;
    int32_t remaining_replays;
    int finished;
} expected_checkpoint;

static const expected_checkpoint expected[] = {
    {6u,   6u,   1u, 1, 240, 1, 0},
    {12u, 12u,   1u, 2, 480, 1, 0},
    {18u, 18u,   1u, 0,   0, 0, 0},
    {30u, 31u,   1u, 2, 520, 0, 0},
    {36u, 37u,   1u, 2, 760, 0, 1},
    {120u,125u,  2u, 2, 760, 0, 1},
    {300u,312u,  1u, 2, 760, 0, 1}
};

static void assert_checkpoint(const expected_checkpoint *want,
                              uint32_t total_updates,
                              uint32_t callback_updates,
                              const hm_sprite_clock_state *state,
                              int finished) {
    assert(total_updates == want->total_updates);
    assert(callback_updates == want->callback_updates);
    assert(state->frame_index == want->frame_index);
    assert(state->elapsed_ticks == want->elapsed_ticks);
    assert(state->remaining_replays == want->remaining_replays);
    assert(finished == want->finished);
}

int main(void) {
    static const int32_t boundaries[] = {0, 240, 480, 720};
    static const int32_t callback_ms[] = {16, 17, 17};
    hm_sprite_clock_state state = {0, 0, 1};
    int32_t accumulator_ms = 0;
    uint32_t total_updates = 0u;
    uint32_t checkpoint_index = 0u;
    uint32_t callback;

    for (callback = 1u; callback <= 300u; ++callback) {
        uint32_t updates = 0u, update;
        int finished = 0;
        assert(hm_app_tick_scheduler_advance(
            &accumulator_ms, callback_ms[(callback - 1u) % 3u],
            &updates) == HM_APP_TICK_OK);
        total_updates += updates;
        for (update = 0u; update < updates; ++update) {
            assert(hm_sprite_clock_step(
                boundaries, 3u, 1, &state, 0.04f, 1.0f, 1, 128u) ==
                HM_SPRITE_CLOCK_OK);
        }
        assert(hm_sprite_clock_is_finished(
            boundaries, 3u, 1, &state, &finished) == HM_SPRITE_CLOCK_OK);
        if (checkpoint_index < sizeof expected / sizeof expected[0] &&
            callback == expected[checkpoint_index].callback) {
            assert_checkpoint(&expected[checkpoint_index], total_updates,
                              updates, &state, finished);
            ++checkpoint_index;
        }
    }
    assert(checkpoint_index == sizeof expected / sizeof expected[0]);
    puts("PASS: 7 synthetic NeXium sprite-clock callback checkpoints");
    return 0;
}
