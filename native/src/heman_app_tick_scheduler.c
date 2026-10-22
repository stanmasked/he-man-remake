#include "heman_app_tick_scheduler.h"

#include <stddef.h>

hm_app_tick_result hm_app_tick_scheduler_advance(
    int32_t *accumulator_ms, int32_t elapsed_wall_ms,
    uint32_t *out_update_count) {
    int32_t accumulated;
    uint32_t updates;
    if (!accumulator_ms || !out_update_count || elapsed_wall_ms < 0 ||
        *accumulator_ms < 0 ||
        *accumulator_ms >= HM_APP_TICK_QUANTUM_MS) {
        return HM_APP_TICK_INVALID;
    }
    if (elapsed_wall_ms > HM_APP_TICK_MAX_ACCUMULATOR_MS -
                          *accumulator_ms) {
        accumulated = HM_APP_TICK_MAX_ACCUMULATOR_MS;
    } else {
        accumulated = *accumulator_ms + elapsed_wall_ms;
        if (accumulated > HM_APP_TICK_MAX_ACCUMULATOR_MS) {
            accumulated = HM_APP_TICK_MAX_ACCUMULATOR_MS;
        }
    }
    updates = (uint32_t)(accumulated / HM_APP_TICK_QUANTUM_MS);
    accumulated -= (int32_t)updates * HM_APP_TICK_QUANTUM_MS;
    if (updates > HM_APP_TICK_MAX_STEPS_PER_CALLBACK ||
        accumulated < 0 || accumulated >= HM_APP_TICK_QUANTUM_MS) {
        return HM_APP_TICK_INVALID;
    }
    *accumulator_ms = accumulated;
    *out_update_count = updates;
    return HM_APP_TICK_OK;
}
