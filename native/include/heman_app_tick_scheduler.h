#ifndef HEMAN_APP_TICK_SCHEDULER_H
#define HEMAN_APP_TICK_SCHEDULER_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define HM_APP_TICK_QUANTUM_MS 16
#define HM_APP_TICK_MAX_ACCUMULATOR_MS 66
#define HM_APP_TICK_MAX_STEPS_PER_CALLBACK 4

typedef enum {
    HM_APP_TICK_OK = 0,
    HM_APP_TICK_INVALID = -1
} hm_app_tick_result;

/* Between callbacks, the original accumulator is in [0, 15] ms.
   Each callback adds a wall-clock delta, clamps totals above 66 ms,
   and consumes as many complete 16-ms quanta as remain. */
hm_app_tick_result hm_app_tick_scheduler_advance(
    int32_t *accumulator_ms, int32_t elapsed_wall_ms,
    uint32_t *out_update_count);

#ifdef __cplusplus
}
#endif
#endif
