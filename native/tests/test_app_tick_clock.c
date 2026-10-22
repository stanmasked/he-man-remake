#include "heman_app_tick_clock.h"
#include "heman_sprite_clock.h"

#include <assert.h>
#include <stdint.h>
#include <stdio.h>

static int32_t sample_and_step(
    hm_app_tick_clock_state *clock,
    uint64_t now_ns,
    int32_t *accumulator,
    hm_sprite_clock_state *player,
    uint32_t *total_updates) {
    static const int32_t boundaries[] = {0, 100000};
    int32_t elapsed_ms = -1;
    uint32_t updates = 99u, i;

    assert(hm_app_tick_clock_sample(clock, now_ns, &elapsed_ms) ==
           HM_APP_TICK_CLOCK_OK);
    assert(hm_app_tick_scheduler_advance(accumulator, elapsed_ms, &updates) ==
           HM_APP_TICK_OK);
    for (i = 0u; i < updates; ++i) {
        assert(hm_sprite_clock_step(boundaries, 1u, -1, player, 0.04f, 1.0f,
                                    1, 128u) == HM_SPRITE_CLOCK_OK);
    }
    *total_updates += updates;
    return elapsed_ms;
}

static void test_first_sample_and_integer_millisecond_conversion(void) {
    hm_app_tick_clock_state clock;
    int32_t elapsed = 77;

    hm_app_tick_clock_init(&clock);
    assert(hm_app_tick_clock_sample(&clock, UINT64_C(10000000000),
                                    &elapsed) == HM_APP_TICK_CLOCK_OK);
    assert(elapsed == 0 && clock.initialized == 1u);
    assert(clock.last_sample_ns == UINT64_C(10000000000));

    assert(hm_app_tick_clock_sample(&clock, UINT64_C(10016999999),
                                    &elapsed) == HM_APP_TICK_CLOCK_OK);
    assert(elapsed == 16);
    assert(hm_app_tick_clock_sample(&clock, UINT64_C(10033999999),
                                    &elapsed) == HM_APP_TICK_CLOCK_OK);
    assert(elapsed == 17);
}

static void test_66ms_boundary_and_cap(void) {
    hm_app_tick_clock_state clock;
    int32_t elapsed = -1;

    hm_app_tick_clock_init(&clock);
    assert(hm_app_tick_clock_sample(&clock, 0u, &elapsed) ==
           HM_APP_TICK_CLOCK_OK);
    assert(elapsed == 0);
    assert(hm_app_tick_clock_sample(&clock, UINT64_C(65999999), &elapsed) ==
           HM_APP_TICK_CLOCK_OK);
    assert(elapsed == 65);
    assert(hm_app_tick_clock_sample(&clock, UINT64_C(131999999), &elapsed) ==
           HM_APP_TICK_CLOCK_OK);
    assert(elapsed == 66);
    assert(clock.last_sample_ns == UINT64_C(131999999));
}

static void test_repeated_pause_resume_keeps_catchup_bounded(void) {
    hm_app_tick_clock_state clock;
    hm_sprite_clock_state player = {0, 0, -1};
    int32_t accumulator = 0;
    uint32_t total_updates = 0u;
    uint64_t now_ns = UINT64_C(1000000000);

    hm_app_tick_clock_init(&clock);

    /* First callback only establishes the clock baseline. */
    assert(sample_and_step(&clock, now_ns, &accumulator, &player,
                           &total_updates) == 0);
    assert(total_updates == 0u && player.elapsed_ticks == 0);

    /* Active callback, then 500 ms with no handler dispatch. */
    now_ns += UINT64_C(16000000);
    assert(sample_and_step(&clock, now_ns, &accumulator, &player,
                           &total_updates) == 16);
    assert(total_updates == 1u && accumulator == 0);
    now_ns += UINT64_C(500000000);
    assert(sample_and_step(&clock, now_ns, &accumulator, &player,
                           &total_updates) == 66);
    assert(total_updates == 5u && accumulator == 2);

    /* Normal cadence returns immediately after the resumed baseline refresh. */
    now_ns += UINT64_C(17000000);
    assert(sample_and_step(&clock, now_ns, &accumulator, &player,
                           &total_updates) == 17);
    assert(total_updates == 6u && accumulator == 3);

    /* A second 200-ms pause is capped too, including the carried 3-ms tail. */
    now_ns += UINT64_C(200000000);
    assert(sample_and_step(&clock, now_ns, &accumulator, &player,
                           &total_updates) == 66);
    assert(total_updates == 10u && accumulator == 2);
    now_ns += UINT64_C(17000000);
    assert(sample_and_step(&clock, now_ns, &accumulator, &player,
                           &total_updates) == 17);

    assert(total_updates == 11u && accumulator == 3);
    assert(player.elapsed_ticks == 440);
}

static void test_regressing_timestamp_fails_closed(void) {
    hm_app_tick_clock_state clock;
    int32_t elapsed = -1;
    uint64_t baseline;

    hm_app_tick_clock_init(&clock);
    assert(hm_app_tick_clock_sample(&clock, UINT64_C(1000000000), &elapsed) ==
           HM_APP_TICK_CLOCK_OK);
    assert(elapsed == 0);
    assert(hm_app_tick_clock_sample(&clock, UINT64_C(1017000000), &elapsed) ==
           HM_APP_TICK_CLOCK_OK);
    assert(elapsed == 17);
    baseline = clock.last_sample_ns;

    elapsed = 123;
    assert(hm_app_tick_clock_sample(&clock, UINT64_C(1016999999), &elapsed) ==
           HM_APP_TICK_CLOCK_TIME_REGRESSION);
    assert(clock.last_sample_ns == baseline && clock.initialized == 1u);
    assert(elapsed == 123);

    assert(hm_app_tick_clock_sample(&clock, UINT64_C(1018000000), &elapsed) ==
           HM_APP_TICK_CLOCK_OK);
    assert(elapsed == 1);
}

static void test_extreme_delta_saturates_without_integer_overflow(void) {
    hm_app_tick_clock_state clock;
    int32_t elapsed = -1;

    hm_app_tick_clock_init(&clock);
    assert(hm_app_tick_clock_sample(&clock, 0u, &elapsed) ==
           HM_APP_TICK_CLOCK_OK);
    assert(hm_app_tick_clock_sample(&clock, UINT64_MAX, &elapsed) ==
           HM_APP_TICK_CLOCK_OK);
    assert(elapsed == HM_APP_TICK_MAX_ACCUMULATOR_MS);
    assert(clock.last_sample_ns == UINT64_MAX);

    elapsed = 41;
    assert(hm_app_tick_clock_sample(&clock, UINT64_MAX - 1u, &elapsed) ==
           HM_APP_TICK_CLOCK_TIME_REGRESSION);
    assert(elapsed == 41 && clock.last_sample_ns == UINT64_MAX);
}

static void test_invalid_arguments_and_corrupt_state(void) {
    hm_app_tick_clock_state clock;
    int32_t elapsed = 71;
    uint64_t baseline;

    hm_app_tick_clock_init(&clock);
    assert(hm_app_tick_clock_sample(NULL, 0u, &elapsed) ==
           HM_APP_TICK_CLOCK_INVALID);
    assert(elapsed == 71);
    assert(hm_app_tick_clock_sample(&clock, 0u, NULL) ==
           HM_APP_TICK_CLOCK_INVALID);
    assert(clock.initialized == 0u);

    clock.last_sample_ns = 55u;
    clock.initialized = 2u;
    baseline = clock.last_sample_ns;
    assert(hm_app_tick_clock_sample(&clock, 100u, &elapsed) ==
           HM_APP_TICK_CLOCK_INVALID);
    assert(clock.last_sample_ns == baseline && clock.initialized == 2u);
    assert(elapsed == 71);
}

int main(void) {
    test_first_sample_and_integer_millisecond_conversion();
    test_66ms_boundary_and_cap();
    test_repeated_pause_resume_keeps_catchup_bounded();
    test_regressing_timestamp_fails_closed();
    test_extreme_delta_saturates_without_integer_overflow();
    test_invalid_arguments_and_corrupt_state();
    puts("PASS: 6 monotonic app-clock bridge scenarios");
    return 0;
}
