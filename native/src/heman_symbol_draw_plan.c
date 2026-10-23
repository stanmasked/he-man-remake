#include "heman_symbol_draw_plan.h"

#include <math.h>

static int hm_finite(float value) {
    return isfinite(value) != 0;
}

static int hm_command_floats_finite(const hm_symbol_draw_command *command) {
    return hm_finite(command->u0) && hm_finite(command->v0) &&
           hm_finite(command->u1) && hm_finite(command->v1) &&
           hm_finite(command->red) && hm_finite(command->green) &&
           hm_finite(command->blue) && hm_finite(command->alpha) &&
           hm_finite(command->rotation_degrees) &&
           hm_finite(command->offset_x) && hm_finite(command->offset_y) &&
           hm_finite(command->scale_x) && hm_finite(command->scale_y);
}

static int hm_command_color_in_range(const hm_symbol_draw_command *command) {
    return command->red >= 0.0f && command->red <= 1.0f &&
           command->green >= 0.0f && command->green <= 1.0f &&
           command->blue >= 0.0f && command->blue <= 1.0f &&
           command->alpha >= 0.0f && command->alpha <= 1.0f;
}

static int hm_command_blend_valid(const hm_symbol_draw_command *command) {
    if (command->blend_override_enabled == 0) {
        return command->blend_source == -1 && command->blend_destination == -1;
    }
    if (command->blend_override_enabled == 1) {
        return command->blend_source >= 0 && command->blend_destination >= 0;
    }
    return 0;
}

hm_symbol_draw_plan_status hm_symbol_draw_plan_validate(
    const hm_symbol_draw_command *commands,
    size_t count
) {
    size_t i;

    if (count != 0u && commands == NULL) {
        return HM_SYMBOL_DRAW_PLAN_INVALID_ARGUMENT;
    }
#if SIZE_MAX > UINT32_MAX
    if (count > (size_t)UINT32_MAX) {
        return HM_SYMBOL_DRAW_PLAN_INVALID_ARGUMENT;
    }
#endif

    for (i = 0u; i < count; ++i) {
        const hm_symbol_draw_command *command = &commands[i];
        if (command->source_order != (uint32_t)i) {
            return HM_SYMBOL_DRAW_PLAN_INVALID_ORDER;
        }
        if (!hm_command_floats_finite(command)) {
            return HM_SYMBOL_DRAW_PLAN_NONFINITE_VALUE;
        }
        if (!hm_command_color_in_range(command)) {
            return HM_SYMBOL_DRAW_PLAN_COLOR_OUT_OF_RANGE;
        }
        if (!hm_command_blend_valid(command)) {
            return HM_SYMBOL_DRAW_PLAN_INVALID_BLEND;
        }
    }
    return HM_SYMBOL_DRAW_PLAN_OK;
}

hm_symbol_draw_plan_status hm_symbol_draw_plan_visit(
    const hm_symbol_draw_command *commands,
    size_t count,
    int32_t active_mask,
    hm_symbol_draw_callback callback,
    void *context,
    size_t *drawn_count
) {
    size_t i;
    size_t completed = 0u;
    hm_symbol_draw_plan_status status;

    if (drawn_count != NULL) {
        *drawn_count = 0u;
    }
    if (count != 0u && callback == NULL) {
        return HM_SYMBOL_DRAW_PLAN_INVALID_ARGUMENT;
    }
    status = hm_symbol_draw_plan_validate(commands, count);
    if (status != HM_SYMBOL_DRAW_PLAN_OK) {
        return status;
    }

    for (i = 0u; i < count; ++i) {
        const hm_symbol_draw_command *command = &commands[i];
        if ((command->symbol_mask & active_mask) != 0) {
            continue;
        }
        if (callback(command, context) != 0) {
            if (drawn_count != NULL) {
                *drawn_count = completed;
            }
            return HM_SYMBOL_DRAW_PLAN_CALLBACK_FAILED;
        }
        ++completed;
    }
    if (drawn_count != NULL) {
        *drawn_count = completed;
    }
    return HM_SYMBOL_DRAW_PLAN_OK;
}
