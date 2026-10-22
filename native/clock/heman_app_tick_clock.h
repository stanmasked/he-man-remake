#ifndef HEMAN_APP_TICK_CLOCK_H
#define HEMAN_APP_TICK_CLOCK_H

#include <stdint.h>

#include "heman_app_tick_scheduler.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    HM_APP_TICK_CLOCK_OK = 0,
    HM_APP_TICK_CLOCK_INVALID = -1,
    HM_APP_TICK_CLOCK_TIME_REGRESSION = -2
} hm_app_tick_clock_result;

/* Portable boundary between a monotonic platform clock and the existing
   integer-millisecond app-tick scheduler. The platform supplies timestamps
   in nanoseconds; this module contains no libnx or OS calls. */
typedef struct {
    uint64_t last_sample_ns;
    uint8_t initialized;
} hm_app_tick_clock_state;

void hm_app_tick_clock_init(hm_app_tick_clock_state *state);

/* Call only when the app-level gate dispatches the tick handler. Do not call
   while dispatch is skipped: the next sample must include the elapsed pause.
   First sample establishes a baseline and outputs 0 ms. Later deltas truncate
   sub-millisecond fractions and clamp at the scheduler's 66-ms maximum before
   narrowing to int32. A regressing timestamp fails closed without mutation. */
hm_app_tick_clock_result hm_app_tick_clock_sample(
    hm_app_tick_clock_state *state,
    uint64_t monotonic_now_ns,
    int32_t *out_elapsed_ms);

#ifdef __cplusplus
}
#endif

#endif
