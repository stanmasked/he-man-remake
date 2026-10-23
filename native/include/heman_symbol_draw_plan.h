#ifndef HEMAN_SYMBOL_DRAW_PLAN_H
#define HEMAN_SYMBOL_DRAW_PLAN_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct hm_symbol_draw_command {
    uint32_t source_order;
    int32_t cut_handle;
    float u0;
    float v0;
    float u1;
    float v1;
    float red;
    float green;
    float blue;
    float alpha;
    int32_t blend_override_enabled;
    int32_t blend_source;
    int32_t blend_destination;
    int32_t symbol_mask;
    float rotation_degrees;
    float offset_x;
    float offset_y;
    float scale_x;
    float scale_y;
} hm_symbol_draw_command;

typedef enum hm_symbol_draw_plan_status {
    HM_SYMBOL_DRAW_PLAN_OK = 0,
    HM_SYMBOL_DRAW_PLAN_INVALID_ARGUMENT = 1,
    HM_SYMBOL_DRAW_PLAN_INVALID_ORDER = 2,
    HM_SYMBOL_DRAW_PLAN_NONFINITE_VALUE = 3,
    HM_SYMBOL_DRAW_PLAN_COLOR_OUT_OF_RANGE = 4,
    HM_SYMBOL_DRAW_PLAN_INVALID_BLEND = 5,
    HM_SYMBOL_DRAW_PLAN_CALLBACK_FAILED = 6
} hm_symbol_draw_plan_status;

typedef int (*hm_symbol_draw_callback)(
    const hm_symbol_draw_command *command,
    void *context
);

/*
 * Validate a complete source-ordered command list before any drawing begins.
 * UV endpoints intentionally may be negative or exceed [0,1]; the texture's
 * native wrap mode, applied by the renderer, determines sampling behavior.
 * Colors must already be clamped to [0,1]. Negative/zero scales are preserved.
 */
hm_symbol_draw_plan_status hm_symbol_draw_plan_validate(
    const hm_symbol_draw_command *commands,
    size_t count
);

/*
 * Visit drawable commands in original source order. Commands masked by
 * (symbol_mask & active_mask) are skipped. The complete list is validated
 * before the first callback. A callback return other than zero aborts.
 * drawn_count may be NULL; on callback failure it counts completed callbacks.
 */
hm_symbol_draw_plan_status hm_symbol_draw_plan_visit(
    const hm_symbol_draw_command *commands,
    size_t count,
    int32_t active_mask,
    hm_symbol_draw_callback callback,
    void *context,
    size_t *drawn_count
);

#ifdef __cplusplus
}
#endif

#endif
