#include "heman_symbol_draw_plan.h"

#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <string.h>

struct visit_log {
    uint32_t orders[8];
    size_t attempted;
    uint32_t fail_order;
    int fail_enabled;
};

static hm_symbol_draw_command command(uint32_t order) {
    hm_symbol_draw_command result;
    memset(&result, 0, sizeof result);
    result.source_order = order;
    result.cut_handle = (int32_t)order;
    result.u0 = -0.125f;
    result.v0 = 0.0f;
    result.u1 = 1.125f;
    result.v1 = 1.0f;
    result.red = 1.0f;
    result.green = 0.5f;
    result.blue = 0.25f;
    result.alpha = 1.0f;
    result.blend_override_enabled = 0;
    result.blend_source = -1;
    result.blend_destination = -1;
    result.symbol_mask = 0;
    result.rotation_degrees = 0.0f;
    result.offset_x = 0.0f;
    result.offset_y = 0.0f;
    result.scale_x = 1.0f;
    result.scale_y = 1.0f;
    return result;
}

static int visit(const hm_symbol_draw_command *item, void *context) {
    struct visit_log *log = (struct visit_log *)context;
    assert(log != NULL);
    assert(item != NULL);
    assert(log->attempted < 8u);
    log->orders[log->attempted++] = item->source_order;
    return log->fail_enabled && item->source_order == log->fail_order ? 1 : 0;
}

static void test_empty_and_null_plans(void) {
    assert(hm_symbol_draw_plan_validate(NULL, 0u) == HM_SYMBOL_DRAW_PLAN_OK);
    assert(hm_symbol_draw_plan_validate(NULL, 1u) ==
           HM_SYMBOL_DRAW_PLAN_INVALID_ARGUMENT);
    assert(hm_symbol_draw_plan_visit(NULL, 0u, 0, NULL, NULL, NULL) ==
           HM_SYMBOL_DRAW_PLAN_OK);
    assert(hm_symbol_draw_plan_visit(NULL, 1u, 0, visit, NULL, NULL) ==
           HM_SYMBOL_DRAW_PLAN_INVALID_ARGUMENT);
}

static void test_order_validation(void) {
    hm_symbol_draw_command items[3] = {command(0u), command(1u), command(2u)};
    assert(hm_symbol_draw_plan_validate(items, 3u) == HM_SYMBOL_DRAW_PLAN_OK);
    items[1].source_order = 2u;
    assert(hm_symbol_draw_plan_validate(items, 3u) == HM_SYMBOL_DRAW_PLAN_INVALID_ORDER);
}

static void test_out_of_range_uvs_are_preserved(void) {
    hm_symbol_draw_command item = command(0u);
    item.u0 = -7.0f;
    item.v0 = -0.25f;
    item.u1 = 5.0f;
    item.v1 = 2.0f;
    assert(hm_symbol_draw_plan_validate(&item, 1u) == HM_SYMBOL_DRAW_PLAN_OK);
    assert(item.u0 == -7.0f && item.u1 == 5.0f);
}

static void test_nonfinite_uv_and_transform_are_rejected(void) {
    hm_symbol_draw_command item = command(0u);
    item.v1 = NAN;
    assert(hm_symbol_draw_plan_validate(&item, 1u) ==
           HM_SYMBOL_DRAW_PLAN_NONFINITE_VALUE);
    item = command(0u);
    item.scale_y = INFINITY;
    assert(hm_symbol_draw_plan_validate(&item, 1u) ==
           HM_SYMBOL_DRAW_PLAN_NONFINITE_VALUE);
}

static void test_color_range_is_strict_but_negative_scale_is_valid(void) {
    hm_symbol_draw_command item = command(0u);
    item.scale_x = -2.0f;
    item.scale_y = 0.0f;
    assert(hm_symbol_draw_plan_validate(&item, 1u) == HM_SYMBOL_DRAW_PLAN_OK);
    item.alpha = -0.01f;
    assert(hm_symbol_draw_plan_validate(&item, 1u) ==
           HM_SYMBOL_DRAW_PLAN_COLOR_OUT_OF_RANGE);
    item = command(0u);
    item.blue = 1.01f;
    assert(hm_symbol_draw_plan_validate(&item, 1u) ==
           HM_SYMBOL_DRAW_PLAN_COLOR_OUT_OF_RANGE);
}

static void test_blend_override_sentinels(void) {
    hm_symbol_draw_command item = command(0u);
    assert(hm_symbol_draw_plan_validate(&item, 1u) == HM_SYMBOL_DRAW_PLAN_OK);
    item.blend_destination = 1;
    assert(hm_symbol_draw_plan_validate(&item, 1u) == HM_SYMBOL_DRAW_PLAN_INVALID_BLEND);
    item = command(0u);
    item.blend_override_enabled = 1;
    item.blend_source = 1;
    item.blend_destination = 2;
    assert(hm_symbol_draw_plan_validate(&item, 1u) == HM_SYMBOL_DRAW_PLAN_OK);
    item.blend_override_enabled = 2;
    assert(hm_symbol_draw_plan_validate(&item, 1u) == HM_SYMBOL_DRAW_PLAN_INVALID_BLEND);
}

static void test_visit_preserves_order_and_applies_mask(void) {
    hm_symbol_draw_command items[4] = {
        command(0u), command(1u), command(2u), command(3u)
    };
    struct visit_log log;
    size_t drawn = 0u;
    memset(&log, 0, sizeof log);
    items[1].symbol_mask = 4;
    items[3].symbol_mask = 8;
    assert(hm_symbol_draw_plan_visit(items, 4u, 4, visit, &log, &drawn) ==
           HM_SYMBOL_DRAW_PLAN_OK);
    assert(drawn == 3u);
    assert(log.attempted == 3u);
    assert(log.orders[0] == 0u && log.orders[1] == 2u && log.orders[2] == 3u);
}

static void test_full_validation_precedes_first_callback(void) {
    hm_symbol_draw_command items[2] = {command(0u), command(1u)};
    struct visit_log log;
    size_t drawn = 99u;
    memset(&log, 0, sizeof log);
    items[1].source_order = 7u;
    assert(hm_symbol_draw_plan_visit(items, 2u, 0, visit, &log, &drawn) ==
           HM_SYMBOL_DRAW_PLAN_INVALID_ORDER);
    assert(log.attempted == 0u);
    assert(drawn == 0u);
}

static void test_callback_failure_stops_in_source_order(void) {
    hm_symbol_draw_command items[3] = {command(0u), command(1u), command(2u)};
    struct visit_log log;
    size_t drawn = 0u;
    memset(&log, 0, sizeof log);
    log.fail_enabled = 1;
    log.fail_order = 1u;
    assert(hm_symbol_draw_plan_visit(items, 3u, 0, visit, &log, &drawn) ==
           HM_SYMBOL_DRAW_PLAN_CALLBACK_FAILED);
    assert(log.attempted == 2u);
    assert(drawn == 1u);
    assert(log.orders[0] == 0u && log.orders[1] == 1u);
}

static void test_blend_and_mask_do_not_mutate_commands(void) {
    hm_symbol_draw_command item = command(0u);
    hm_symbol_draw_command before = item;
    struct visit_log log;
    memset(&log, 0, sizeof log);
    assert(hm_symbol_draw_plan_visit(&item, 1u, 0, visit, &log, NULL) ==
           HM_SYMBOL_DRAW_PLAN_OK);
    assert(memcmp(&item, &before, sizeof item) == 0);
}

int main(void) {
    test_empty_and_null_plans();
    test_order_validation();
    test_out_of_range_uvs_are_preserved();
    test_nonfinite_uv_and_transform_are_rejected();
    test_color_range_is_strict_but_negative_scale_is_valid();
    test_blend_override_sentinels();
    test_visit_preserves_order_and_applies_mask();
    test_full_validation_precedes_first_callback();
    test_callback_failure_stops_in_source_order();
    test_blend_and_mask_do_not_mutate_commands();
    puts("Stage198 C99 Symbol draw-plan tests passed");
    return 0;
}
