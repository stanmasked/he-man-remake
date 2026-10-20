#include "heman_synthetic_room2.h"
#include <string.h>

/* Source-authored private-free room: one pickup, checkpoint, hazard, exit. */
static const hm_event room2_events[] = {
    {HM_PICKUP, 170.0f, 267.0f, 8.0f},
    {HM_CHECKPOINT, 330.0f, 273.0f, 8.0f},
    {HM_HAZARD, 570.0f, 273.0f, 8.0f},
    {HM_EXIT, 735.0f, 273.0f, 8.0f}
};

int hm_synthetic_room2_init(hm_world *world, hm_combat_config *combat,
                            uint8_t *tiles, uint32_t tile_count) {
    uint8_t initial_tiles[HM_ROOM2_CELLS];
    hm_world proposed_world;
    hm_combat_config proposed_combat;
    hm_state provisional_player;
    hm_combat_state provisional_enemy;
    uint32_t x;
    if (!world || !combat || !tiles || tile_count != HM_ROOM2_CELLS)
        return 0;

    memset(initial_tiles, 0, sizeof(initial_tiles));
    for (x = 0; x < HM_ROOM2_COLUMNS; ++x)
        initial_tiles[18u * HM_ROOM2_COLUMNS + x] = 1u;
    for (x = 9u; x < 13u; ++x)
        initial_tiles[13u * HM_ROOM2_COLUMNS + x] = 1u;
    for (x = 23u; x < 28u; ++x)
        initial_tiles[15u * HM_ROOM2_COLUMNS + x] = 1u;

    memset(&proposed_world, 0, sizeof(proposed_world));
    proposed_world.solid = initial_tiles;
    proposed_world.columns = HM_ROOM2_COLUMNS;
    proposed_world.rows = HM_ROOM2_ROWS;
    proposed_world.tile_size = 16u;
    proposed_world.spawn_x = 48.0f;
    proposed_world.spawn_feet_y = 288.0f;
    proposed_world.actor_half_width = 5.0f;
    proposed_world.actor_height = 22.0f;
    proposed_world.speed = 120.0f;
    proposed_world.gravity = 1200.0f;
    proposed_world.jump_speed = 420.0f;
    proposed_world.terminal_speed = 1400.0f;
    proposed_world.viewport_width = 320.0f;
    proposed_world.viewport_height = 240.0f;
    proposed_world.death_margin = 96.0f;
    proposed_world.events = room2_events;
    proposed_world.event_count =
        (uint32_t)(sizeof(room2_events) / sizeof(room2_events[0]));

    memset(&proposed_combat, 0, sizeof(proposed_combat));
    proposed_combat.patrol_left = 230.0f;
    proposed_combat.patrol_right = 320.0f;
    proposed_combat.enemy_start_x = 275.0f;
    proposed_combat.enemy_feet_y = 288.0f;
    proposed_combat.enemy_speed = 38.0f;
    proposed_combat.sword_reach = 30.0f;
    proposed_combat.contact_range = 9.0f;
    proposed_combat.enemy_initial_hp = 2u;
    proposed_combat.player_initial_hp = 3u;
    proposed_combat.sword_cooldown_frames = 15u;
    proposed_combat.hurt_cooldown_frames = 45u;

    if (hm_init(&proposed_world, &provisional_player) != HM_OK ||
        hm_combat_init(&proposed_combat, &provisional_enemy) != HM_COMBAT_OK)
        return 0;

    memcpy(tiles, initial_tiles, sizeof(initial_tiles));
    proposed_world.solid = tiles;
    *world = proposed_world;
    *combat = proposed_combat;
    return 1;
}
