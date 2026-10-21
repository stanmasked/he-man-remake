#include "heman_level11_lab.h"
#include <string.h>

/* Source-authored tutorial ground and three fictional events: DO NOT claim
 * these as original Level 1-1 layouts, art, coordinates or collision types. */
static const hm_event lab_events[3] = {
    {HM_TRIGGER, 104.0f, 114.0f, 4.0f},
    {HM_PICKUP, 148.0f, 114.0f, 4.0f},
    {HM_PICKUP, 56.0f, 114.0f, 4.0f}
};
static const hm_level11_event_bindings lab_roles = {0u, 1u, 2u};

hm_lore_result hm_level11_lab_init(hm_world *world, uint8_t *solid,
                                  size_t capacity,
                                  hm_level11_native_session *session) {
    hm_world candidate;
    uint32_t x;
    if (!world || !solid || !session || capacity != HM_LORE_LAB_CELLS)
        return HM_LORE_INVALID;
    memset(&candidate, 0, sizeof(candidate));
    memset(solid, 0, capacity);
    for (x = 0u; x < HM_LORE_LAB_COLS; ++x)
        solid[8u * HM_LORE_LAB_COLS + x] = 1u;
    candidate.solid = solid;
    candidate.columns = HM_LORE_LAB_COLS;
    candidate.rows = HM_LORE_LAB_ROWS;
    candidate.tile_size = 16u;
    candidate.spawn_x = 24.0f;
    candidate.spawn_feet_y = 128.0f;
    candidate.actor_half_width = 5.0f;
    candidate.actor_height = 20.0f;
    candidate.speed = 120.0f;
    candidate.gravity = 1200.0f;
    candidate.jump_speed = 420.0f;
    candidate.terminal_speed = 1400.0f;
    candidate.viewport_width = 320.0f;
    candidate.viewport_height = 192.0f;
    candidate.death_margin = 96.0f;
    candidate.events = lab_events;
    candidate.event_count = 3u;
    /* Lifetime caveat: caller must pass a persistent, stable 'world'
       descriptor. The native session seals the address, not a copy. */
    *world = candidate;
    return hm_level11_session_init(session, world, &lab_roles);
}

hm_lore_result hm_level11_lab_tick(hm_level11_native_session *session,
                                  hm_level11_lab_save *save,
                                  uint32_t held, uint32_t down) {
    const uint32_t buttons = (HM_LAB_LEFT | HM_LAB_RIGHT | HM_LAB_JUMP |
        HM_LAB_ATTACK | HM_LAB_WALL_UPGRADE | HM_LAB_RESET |
        HM_LAB_SAVE | HM_LAB_LOAD);
    hm_input input;
    hm_level11_lab_save next_save;
    if (!session || !save || !hm_level11_session_valid(session) ||
        save->valid > 1u || ((held | down) & ~buttons) != 0u ||
        (down & ~held) != 0u)
        return HM_LORE_INVALID;
    if (down & HM_LAB_RESET) {
        /* Explicit local tutorial restart; no original iOS save semantics. */
        hm_level11_native_session next = *session;
        if (hm_level11_session_init(&next, session->world,
                                   &session->sealed_bindings) != HM_LORE_APPLIED)
            return HM_LORE_INVALID;
        *session = next;
        return HM_LORE_APPLIED;
    }
    if (down & HM_LAB_LOAD) {
        if (!save->valid) return HM_LORE_BLOCKED;
        return hm_level11_snapshot_restore(session, save->data,
                          sizeof(save->data)) ? HM_LORE_APPLIED : HM_LORE_INVALID;
    }
    if (down & HM_LAB_SAVE) {
        next_save = *save;
        if (!hm_level11_snapshot_encode(session, next_save.data,
                                       sizeof(next_save.data)))
            return HM_LORE_INVALID;
        next_save.valid = 1u;
        *save = next_save;
        return HM_LORE_APPLIED;
    }
    if (down & HM_LAB_WALL_UPGRADE)
        return hm_level11_session_grant_wall_crusher(session, 1u);
    input.axis = (float)((((held & HM_LAB_RIGHT) != 0u) ? 1 : 0) -
                         (((held & HM_LAB_LEFT) != 0u) ? 1 : 0));
    input.jump = (uint8_t)((down & HM_LAB_JUMP) != 0u);
    input.reset = 0u;
    return hm_level11_session_step(session, input, 1.0f / 60.0f,
                          (uint8_t)((held & HM_LAB_ATTACK) != 0u));
}
