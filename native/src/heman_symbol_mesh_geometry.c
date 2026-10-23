#include "heman_symbol_mesh_geometry.h"

#include <math.h>
#include <string.h>

#define HM_DEGREES_TO_RADIANS 0.0174532924f

static float hm_add(float a, float b) {
    volatile float result = a + b;
    return result;
}

static float hm_sub(float a, float b) {
    volatile float result = a - b;
    return result;
}

static float hm_mul(float a, float b) {
    volatile float result = a * b;
    return result;
}

static int hm_finite(float value) {
    return isfinite(value) != 0;
}

static int hm_player_transform_finite(const hm_symbol_player_transform *t) {
    return hm_finite(t->rotation_degrees) &&
           hm_finite(t->rotation_pivot_x) &&
           hm_finite(t->rotation_pivot_y) &&
           hm_finite(t->scale_x) && hm_finite(t->scale_y) &&
           hm_finite(t->scale_pivot_x) && hm_finite(t->scale_pivot_y) &&
           hm_finite(t->translation_x) && hm_finite(t->translation_y);
}

static void hm_rotate_about(
    float *x, float *y, float degrees, float pivot_x, float pivot_y
) {
    const float theta = hm_mul(degrees, HM_DEGREES_TO_RADIANS);
    const float cosine = cosf(theta);
    const float sine = sinf(theta);
    const float dx = hm_sub(*x, pivot_x);
    const float dy = hm_sub(*y, pivot_y);
    const float x_delta = hm_sub(hm_mul(cosine, dx), hm_mul(sine, dy));
    const float y_delta = hm_add(hm_mul(sine, dx), hm_mul(cosine, dy));
    *x = hm_add(pivot_x, x_delta);
    *y = hm_add(pivot_y, y_delta);
}

static void hm_apply_player_transform(
    float *x, float *y, const hm_symbol_player_transform *t
) {
    hm_rotate_about(x, y, t->rotation_degrees,
                    t->rotation_pivot_x, t->rotation_pivot_y);
    *x = hm_add(t->scale_pivot_x,
                hm_mul(hm_sub(*x, t->scale_pivot_x), t->scale_x));
    *y = hm_add(t->scale_pivot_y,
                hm_mul(hm_sub(*y, t->scale_pivot_y), t->scale_y));
    *x = hm_add(*x, t->translation_x);
    *y = hm_add(*y, t->translation_y);
}

hm_symbol_mesh_status hm_symbol_mesh_build_quad(
    const hm_symbol_draw_command *command,
    int32_t cut_width,
    int32_t cut_height,
    const hm_symbol_player_transform *player_transform,
    hm_symbol_quad_geometry *out_geometry
) {
    hm_symbol_draw_command checked;
    hm_symbol_player_transform identity;
    const hm_symbol_player_transform *player = player_transform;
    hm_symbol_quad_geometry result;
    float half_width;
    float half_height;
    float theta;
    float cosine;
    float sine;
    float area;
    size_t i;
    static const float x_sign[4] = {-1.0f, -1.0f, 1.0f, 1.0f};
    static const float y_sign[4] = {-1.0f, 1.0f, 1.0f, -1.0f};

    if (command == NULL || out_geometry == NULL) {
        return HM_SYMBOL_MESH_INVALID_ARGUMENT;
    }
    checked = *command;
    /* This function accepts a single command from any source-order position. */
    checked.source_order = 0u;
    if (hm_symbol_draw_plan_validate(&checked, 1u) != HM_SYMBOL_DRAW_PLAN_OK) {
        return HM_SYMBOL_MESH_INVALID_DRAW_COMMAND;
    }
    if (player == NULL) {
        memset(&identity, 0, sizeof identity);
        identity.scale_x = 1.0f;
        identity.scale_y = 1.0f;
        player = &identity;
    }
    if (!hm_player_transform_finite(player)) {
        return HM_SYMBOL_MESH_NONFINITE_TRANSFORM;
    }

    half_width = hm_mul((float)cut_width, 0.5f);
    half_height = hm_mul((float)cut_height, 0.5f);
    theta = hm_mul((float)command->rotation_degrees, HM_DEGREES_TO_RADIANS);
    cosine = cosf(theta);
    sine = sinf(theta);

    for (i = 0u; i < 4u; ++i) {
        float x = hm_mul(hm_mul(x_sign[i], half_width), command->scale_x);
        float y = hm_mul(hm_mul(y_sign[i], half_height), command->scale_y);

        if (command->rotation_degrees != 0) {
            const float rotated_x = hm_sub(hm_mul(cosine, x), hm_mul(sine, y));
            const float rotated_y = hm_add(hm_mul(sine, x), hm_mul(cosine, y));
            x = rotated_x;
            y = rotated_y;
        }
        x = hm_add(x, (float)command->offset_x);
        y = hm_add(y, (float)command->offset_y);
        hm_apply_player_transform(&x, &y, player);
        if (!hm_finite(x) || !hm_finite(y)) {
            return HM_SYMBOL_MESH_NONFINITE_GEOMETRY;
        }
        result.xy[i * 2u] = x;
        result.xy[i * 2u + 1u] = y;
    }

    /* Match the native signed-area winding test; do not reorder vertices. */
    area = hm_sub(
        hm_mul(hm_sub(result.xy[2], result.xy[0]),
               hm_sub(result.xy[5], result.xy[1])),
        hm_mul(hm_sub(result.xy[3], result.xy[1]),
               hm_sub(result.xy[4], result.xy[0]))
    );
    if (!hm_finite(area)) {
        return HM_SYMBOL_MESH_NONFINITE_GEOMETRY;
    }
    result.front_face_flip = area <= 0.0f ? 1 : 0;
    *out_geometry = result;
    return HM_SYMBOL_MESH_OK;
}
