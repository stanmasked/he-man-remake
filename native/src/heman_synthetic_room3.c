#include "heman_synthetic_room3.h"
#include <string.h>

/* Source-authored training course, no commercial game tile coordinates. */
static const hm_event room3_events[] = {
    {HM_PICKUP, 158.0f, 282.0f, 8.0f},
    {HM_CHECKPOINT, 434.0f, 288.0f, 8.0f},
    {HM_HAZARD, 678.0f, 288.0f, 9.0f},
    {HM_EXIT, 842.0f, 288.0f, 10.0f}
};

int hm_synthetic_room3_init(hm_world *world, hm_combat_config *combat,
                            uint8_t *tiles, uint32_t tile_count) {
    uint8_t proposed_tiles[HM_ROOM3_CELLS];
    hm_world next_world;
    hm_combat_config next_combat;
    hm_state checked_player;
    hm_combat_state checked_enemy;
    uint32_t x;
    if (!world || !combat || !tiles || tile_count != HM_ROOM3_CELLS)
        return 0;
    memset(proposed_tiles, 0, sizeof(proposed_tiles));
    for (x = 0u; x < HM_ROOM3_COLUMNS; ++x)
        proposed_tiles[18u * HM_ROOM3_COLUMNS + x] = 1u;
    for (x = 8u; x < 13u; ++x)
        proposed_tiles[14u * HM_ROOM3_COLUMNS + x] = 1u;
    for (x = 20u; x < 26u; ++x)
        proposed_tiles[12u * HM_ROOM3_COLUMNS + x] = 1u;
    for (x = 35u; x < 41u; ++x)
        proposed_tiles[15u * HM_ROOM3_COLUMNS + x] = 1u;

    memset(&next_world, 0, sizeof(next_world));
    next_world.solid = proposed_tiles;
    next_world.columns = HM_ROOM3_COLUMNS;
    next_world.rows = HM_ROOM3_ROWS;
    next_world.tile_size = 16u;
    next_world.spawn_x = 48.0f;
    next_world.spawn_feet_y = 288.0f;
    next_world.actor_half_width = 5.0f;
    next_world.actor_height = 22.0f;
    next_world.speed = 120.0f;
    next_world.gravity = 1200.0f;
    next_world.jump_speed = 420.0f;
    next_world.terminal_speed = 1400.0f;
    next_world.viewport_width = 320.0f;
    next_world.viewport_height = 240.0f;
    next_world.death_margin = 96.0f;
    next_world.events = room3_events;
    next_world.event_count =
        (uint32_t)(sizeof(room3_events) / sizeof(room3_events[0]));

    memset(&next_combat, 0, sizeof(next_combat));
    next_combat.patrol_left = 292.0f;
    next_combat.patrol_right = 370.0f;
    next_combat.enemy_start_x = 316.0f;
    next_combat.enemy_feet_y = 288.0f;
    next_combat.enemy_speed = 34.0f;
    next_combat.sword_reach = 32.0f;
    next_combat.contact_range = 9.0f;
    next_combat.enemy_initial_hp = 3u;
    next_combat.player_initial_hp = 3u;
    next_combat.sword_cooldown_frames = 15u;
    next_combat.hurt_cooldown_frames = 45u;

    if (hm_init(&next_world, &checked_player) != HM_OK ||
        hm_combat_init(&next_combat, &checked_enemy) != HM_COMBAT_OK)
        return 0;
    memcpy(tiles, proposed_tiles, sizeof(proposed_tiles));
    next_world.solid = tiles;
    *world = next_world;
    *combat = next_combat;
    return 1;
}
