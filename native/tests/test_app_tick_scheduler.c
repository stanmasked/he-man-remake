#include "heman_app_tick_scheduler.h"

#include <assert.h>
#include <limits.h>
#include <stdio.h>

static void test_below_threshold_accumulates_without_update(void) {
    int32_t accumulator = 0;
    uint32_t updates = 99u;
    assert(hm_app_tick_scheduler_advance(&accumulator, 15, &updates) ==
           HM_APP_TICK_OK);
    assert(accumulator == 15 && updates == 0u);
}

static void test_exact_threshold_consumes_one_update(void) {
    int32_t accumulator = 0;
    uint32_t updates = 0u;
    assert(hm_app_tick_scheduler_advance(&accumulator, 16, &updates) ==
           HM_APP_TICK_OK);
    assert(accumulator == 0 && updates == 1u);
}

static void test_remainder_carries_across_callbacks(void) {
    int32_t accumulator = 0;
    uint32_t updates = 0u;
    assert(hm_app_tick_scheduler_advance(&accumulator, 17, &updates) ==
           HM_APP_TICK_OK);
    assert(accumulator == 1 && updates == 1u);
    assert(hm_app_tick_scheduler_advance(&accumulator, 17, &updates) ==
           HM_APP_TICK_OK);
    assert(accumulator == 2 && updates == 1u);
}

static void test_two_quanta_are_consumed_in_one_callback(void) {
    int32_t accumulator = 0;
    uint32_t updates = 0u;
    assert(hm_app_tick_scheduler_advance(&accumulator, 32, &updates) ==
           HM_APP_TICK_OK);
    assert(accumulator == 0 && updates == 2u);
}

static void test_66ms_cap_yields_four_updates_and_two_ms_remainder(void) {
    int32_t accumulator = 0;
    uint32_t updates = 0u;
    assert(hm_app_tick_scheduler_advance(&accumulator, 66, &updates) ==
           HM_APP_TICK_OK);
    assert(accumulator == 2 && updates == 4u);
}

static void test_long_stall_is_clamped_not_caught_up_without_bound(void) {
    int32_t accumulator = 3;
    uint32_t updates = 0u;
    assert(hm_app_tick_scheduler_advance(&accumulator, INT32_MAX, &updates) ==
           HM_APP_TICK_OK);
    assert(accumulator == 2 && updates == 4u);
}

static void test_zero_wall_delta_preserves_state(void) {
    int32_t accumulator = 7;
    uint32_t updates = 99u;
    assert(hm_app_tick_scheduler_advance(&accumulator, 0, &updates) ==
           HM_APP_TICK_OK);
    assert(accumulator == 7 && updates == 0u);
}

static void test_sixty_nominal_16ms_callbacks(void) {
    int32_t accumulator = 0;
    uint32_t updates = 0u;
    unsigned i;
    uint32_t total_updates = 0u;
    for (i = 0u; i < 60u; ++i) {
        assert(hm_app_tick_scheduler_advance(&accumulator, 16, &updates) ==
               HM_APP_TICK_OK);
        total_updates += updates;
    }
    assert(total_updates == 60u && accumulator == 0);
}

static void test_one_second_mixed_16_and_17ms_callbacks(void) {
    int32_t accumulator = 0;
    uint32_t updates = 0u;
    uint32_t total_updates = 0u;
    unsigned i;
    /* 20*16 + 40*17 = exactly 1000 ms of fabricated wall time. */
    for (i = 0u; i < 20u; ++i) {
        assert(hm_app_tick_scheduler_advance(&accumulator, 16, &updates) ==
               HM_APP_TICK_OK);
        total_updates += updates;
    }
    for (i = 0u; i < 40u; ++i) {
        assert(hm_app_tick_scheduler_advance(&accumulator, 17, &updates) ==
               HM_APP_TICK_OK);
        total_updates += updates;
    }
    assert(total_updates == 62u && accumulator == 8);
}

static void test_null_pointers_rejected(void) {
    int32_t accumulator = 0;
    uint32_t updates = 77u;
    assert(hm_app_tick_scheduler_advance(NULL, 16, &updates) ==
           HM_APP_TICK_INVALID);
    assert(hm_app_tick_scheduler_advance(&accumulator, 16, NULL) ==
           HM_APP_TICK_INVALID);
    assert(accumulator == 0 && updates == 77u);
}

static void test_negative_wall_delta_rejected_without_mutation(void) {
    int32_t accumulator = 5;
    uint32_t updates = 77u;
    assert(hm_app_tick_scheduler_advance(&accumulator, -1, &updates) ==
           HM_APP_TICK_INVALID);
    assert(accumulator == 5 && updates == 77u);
}

static void test_invalid_saved_accumulator_rejected(void) {
    uint32_t updates = 77u;
    int32_t negative = -1;
    int32_t too_large = HM_APP_TICK_QUANTUM_MS;
    assert(hm_app_tick_scheduler_advance(&negative, 1, &updates) ==
           HM_APP_TICK_INVALID);
    assert(hm_app_tick_scheduler_advance(&too_large, 1, &updates) ==
           HM_APP_TICK_INVALID);
    assert(negative == -1 && too_large == HM_APP_TICK_QUANTUM_MS &&
           updates == 77u);
}

int main(void) {
    test_below_threshold_accumulates_without_update();
    test_exact_threshold_consumes_one_update();
    test_remainder_carries_across_callbacks();
    test_two_quanta_are_consumed_in_one_callback();
    test_66ms_cap_yields_four_updates_and_two_ms_remainder();
    test_long_stall_is_clamped_not_caught_up_without_bound();
    test_zero_wall_delta_preserves_state();
    test_sixty_nominal_16ms_callbacks();
    test_one_second_mixed_16_and_17ms_callbacks();
    test_null_pointers_rejected();
    test_negative_wall_delta_rejected_without_mutation();
    test_invalid_saved_accumulator_rejected();
    puts("PASS: 12 synthetic app-tick accumulator scenarios");
    return 0;
}
