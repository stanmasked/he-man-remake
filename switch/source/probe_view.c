#include "probe_view.h"
#include <math.h>
#include <stdint.h>

/* Bounds are deliberately small for a text-console debug adapter.
   No data or artwork is loaded from the original game. */
static int finite_scene_value(float value) {
    return isfinite(value) && value > -1000000.0f && value < 1000000.0f;
}

static int visible_tile(const hm_world *world, uint32_t ox, uint32_t oy,
                        float x, float y, uint32_t *col, uint32_t *row) {
    uint32_t tx, ty;
    if (x < 0.0f || y < 0.0f ||
        x >= (float)world->columns * (float)world->tile_size ||
        y >= (float)world->rows * (float)world->tile_size) return 0;
    tx = (uint32_t)(x / (float)world->tile_size);
    ty = (uint32_t)(y / (float)world->tile_size);
    if (tx < ox || ty < oy || tx - ox >= HM_PROBE_COLS ||
        ty - oy >= HM_PROBE_ROWS) return 0;
    *col = tx - ox;
    *row = ty - oy;
    return 1;
}

int hm_probe_render(const hm_world *world, const hm_state *state,
                    char *out, size_t out_len) {
    uint32_t ox, oy, max_x, max_y, row, col, i;
    if (!world || !state || !out || out_len < HM_PROBE_BYTES ||
        !world->solid || !world->columns || !world->rows ||
        world->columns > 4096u || world->rows > 4096u ||
        world->tile_size < 1u || world->tile_size > 64u ||
        world->columns > 200000u / world->rows ||
        world->event_count > 32u || (world->event_count && !world->events) ||
        !finite_scene_value(state->x) ||
        !finite_scene_value(state->feet_y) ||
        !finite_scene_value(state->camera_x) ||
        !finite_scene_value(state->camera_y) ||
        !finite_scene_value(world->actor_height) ||
        state->camera_x < 0.0f || state->camera_y < 0.0f ||
        world->actor_height <= 0.0f) return 0;
    /* Validate all events before writing, so invalid inputs leave out intact. */
    for (i = 0; i < world->event_count; ++i) {
        const hm_event *e = &world->events[i];
        if (e->kind < HM_PICKUP || e->kind > HM_EXIT ||
            !finite_scene_value(e->x) || !finite_scene_value(e->y)) return 0;
    }
    max_x = world->columns > HM_PROBE_COLS ? world->columns - HM_PROBE_COLS : 0u;
    max_y = world->rows > HM_PROBE_ROWS ? world->rows - HM_PROBE_ROWS : 0u;
    ox = (uint32_t)(state->camera_x / (float)world->tile_size);
    oy = (uint32_t)(state->camera_y / (float)world->tile_size);
    if (ox > max_x) ox = max_x;
    if (oy > max_y) oy = max_y;
    for (row = 0; row < HM_PROBE_ROWS; ++row) {
        const uint32_t gy = oy + row;
        for (col = 0; col < HM_PROBE_COLS; ++col) {
            const uint32_t gx = ox + col;
            out[row * HM_PROBE_STRIDE + col] =
                (gx < world->columns && gy < world->rows &&
                 world->solid[gy * world->columns + gx]) ? '#' : ' ';
        }
        out[row * HM_PROBE_STRIDE + HM_PROBE_COLS] = '\0';
    }
    for (i = 0; i < world->event_count; ++i) {
        const hm_event *e = &world->events[i];
        char mark;
        if (!visible_tile(world, ox, oy, e->x, e->y, &col, &row)) continue;
        switch (e->kind) {
            case HM_PICKUP:
                if (state->picked & (UINT32_C(1) << i)) continue;
                mark = '*'; break;
            case HM_CHECKPOINT:
                mark = state->checkpoint == (int32_t)i ? 'c' : 'C'; break;
            case HM_HAZARD: mark = '!'; break;
            case HM_TRIGGER: mark = '?'; break;
            case HM_EXIT: mark = '>'; break;
            default: continue;
        }
        out[row * HM_PROBE_STRIDE + col] = mark;
    }
    /* Actor always wins over other marks and is drawn at body centre. */
    if (visible_tile(world, ox, oy, state->x,
                     state->feet_y - world->actor_height * 0.5f,
                     &col, &row)) out[row * HM_PROBE_STRIDE + col] = '@';
    return 1;
}

/* Optional single-cell overlay for synthetic moving enemies. */
int hm_probe_overlay_marker(const hm_world *world, const hm_state *state,
                            char *out, size_t out_len,
                            float x, float y, char glyph) {
    uint32_t col, row, ox, oy, max_x, max_y, i;
    if (!world || !state || !out || out_len < HM_PROBE_BYTES ||
        !world->columns || !world->rows || !world->tile_size ||
        world->columns > 4096u || world->rows > 4096u ||
        world->tile_size > 64u ||
        !finite_scene_value(state->camera_x) ||
        !finite_scene_value(state->camera_y) ||
        state->camera_x < 0.0f || state->camera_y < 0.0f ||
        !finite_scene_value(x) || !finite_scene_value(y) ||
        glyph < '!' || glyph > '~') return 0;
    for (i = 0; i < HM_PROBE_ROWS; ++i) {
        if (out[i * HM_PROBE_STRIDE + HM_PROBE_COLS] != '\0')
            return 0;
    }
    max_x = world->columns > HM_PROBE_COLS ? world->columns - HM_PROBE_COLS : 0u;
    max_y = world->rows > HM_PROBE_ROWS ? world->rows - HM_PROBE_ROWS : 0u;
    ox = (uint32_t)(state->camera_x / (float)world->tile_size);
    oy = (uint32_t)(state->camera_y / (float)world->tile_size);
    if (ox > max_x) ox = max_x;
    if (oy > max_y) oy = max_y;
    if (visible_tile(world, ox, oy, x, y, &col, &row)) {
        const uint32_t at = row * HM_PROBE_STRIDE + col;
        if (out[at] != '@') out[at] = glyph;
    }
    return 1;
}
