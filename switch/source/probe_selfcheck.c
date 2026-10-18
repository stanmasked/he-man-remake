#include "probe_selfcheck.h"
#include "probe_view.h"
#include "heman_core.h"

#include <stdint.h>
#include <string.h>

#define PROBE_W 32u
#define PROBE_H 20u
#define PROBE_TILE 16u
#define PROBE_FRAMES 180u

/* All data here is independently authored and synthetic. Static geometry
   is intentionally simple so the same test can execute on GCC, Clang and
   devkitA64 without IO, malloc, controllers, or a running emulator. */
hm_probe_check_result hm_probe_boot_selfcheck(void) {
    uint8_t cells[PROBE_W * PROBE_H];
    static const hm_event events[] = {
        { HM_PICKUP, 80.0f, 209.0f, 8.0f },
        { HM_CHECKPOINT, 128.0f, 209.0f, 8.0f },
        { HM_EXIT, 184.0f, 209.0f, 8.0f },
        { HM_HAZARD, 400.0f, 209.0f, 8.0f }
    };
    hm_world world;
    hm_state state;
    char view[HM_PROBE_BYTES];
    uint32_t x, frame, row, col;
    int actor_visible = 0;

    memset(&world, 0, sizeof(world));
    memset(cells, 0, sizeof(cells));
    for (x = 0; x < PROBE_W; ++x)
        cells[14u * PROBE_W + x] = 1u;
    world.solid = cells;
    world.columns = PROBE_W;
    world.rows = PROBE_H;
    world.tile_size = PROBE_TILE;
    world.spawn_x = 32.0f;
    world.spawn_feet_y = 224.0f;
    world.actor_half_width = 5.0f;
    world.actor_height = 22.0f;
    world.speed = 120.0f;
    world.gravity = 1200.0f;
    world.jump_speed = 420.0f;
    world.terminal_speed = 1400.0f;
    world.viewport_width = 320.0f;
    world.viewport_height = 240.0f;
    world.death_margin = 96.0f;
    world.events = events;
    world.event_count = (uint32_t)(sizeof(events) / sizeof(events[0]));

    if (hm_init(&world, &state) != HM_OK)
        return HM_PROBE_CHECK_SETUP;
    for (frame = 0; frame < PROBE_FRAMES; ++frame) {
        hm_input input = {0.0f, 0u, 0u};
        if (frame < 90u) input.axis = 1.0f;
        if (frame == 100u) input.jump = 1u;
        if (hm_step(&world, &state, input, 1.0f / 60.0f) != HM_OK)
            return HM_PROBE_CHECK_STEP;
    }
    /* Stable behavioural invariants rather than compiler-specific exact
       floating-point hashes. Captures simulated movement, a jump/landing,
       pickup, checkpoint, exit, and camera progress in 180 fixed steps. */
    if (state.frame != PROBE_FRAMES ||
        state.x <= 180.0f || state.x >= 240.0f ||
        state.camera_x <= 0.0f || !state.grounded ||
        (state.picked & UINT32_C(1)) == 0u ||
        state.checkpoint != 1 || !state.completed ||
        state.hazards != 0u || state.respawns != 0u)
        return HM_PROBE_CHECK_STATE;
    if (!hm_probe_render(&world, &state, view, sizeof(view)))
        return HM_PROBE_CHECK_VIEW;
    for (row = 0; row < HM_PROBE_ROWS; ++row) {
        for (col = 0; col < HM_PROBE_COLS; ++col)
            if (view[row * HM_PROBE_STRIDE + col] == '@')
                ++actor_visible;
    }
    if (actor_visible != 1)
        return HM_PROBE_CHECK_VIEW;
    return HM_PROBE_CHECK_OK;
}
