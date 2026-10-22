#include "heman_app_tick_clock.h"

void hm_app_tick_clock_init(hm_app_tick_clock_state *state) {
    if (!state) return;
    state->last_sample_ns = 0u;
    state->initialized = 0u;
}

hm_app_tick_clock_result hm_app_tick_clock_sample(
    hm_app_tick_clock_state *state,
    uint64_t monotonic_now_ns,
    int32_t *out_elapsed_ms) {
    uint64_t delta_ns;
    int32_t elapsed_ms;

    if (!state || !out_elapsed_ms || state->initialized > 1u) {
        return HM_APP_TICK_CLOCK_INVALID;
    }

    if (!state->initialized) {
        state->last_sample_ns = monotonic_now_ns;
        state->initialized = 1u;
        *out_elapsed_ms = 0;
        return HM_APP_TICK_CLOCK_OK;
    }

    if (monotonic_now_ns < state->last_sample_ns) {
        return HM_APP_TICK_CLOCK_TIME_REGRESSION;
    }

    delta_ns = monotonic_now_ns - state->last_sample_ns;
    if (delta_ns >=
        (uint64_t)HM_APP_TICK_MAX_ACCUMULATOR_MS * UINT64_C(1000000)) {
        elapsed_ms = HM_APP_TICK_MAX_ACCUMULATOR_MS;
    } else {
        elapsed_ms = (int32_t)(delta_ns / UINT64_C(1000000));
    }

    /* Commit baseline and output only after all validation has succeeded. */
    state->last_sample_ns = monotonic_now_ns;
    *out_elapsed_ms = elapsed_ms;
    return HM_APP_TICK_CLOCK_OK;
}
