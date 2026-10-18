#include "session_selftest.h"
#include "heman_session.h"
#include <math.h>
#include <stdint.h>
#include <string.h>

#define COLS 32u
#define ROWS 20u

hm_session_selftest_code hm_session_selftest(void) {
    uint8_t solid[COLS * ROWS];
    hm_world world;
    hm_combat_config combat;
    hm_session game, original;
    hm_input input = {1.0f, 0u, 0u};
    const hm_event hazard = { HM_HAZARD, 32.0f, 210.0f, 10.0f };
    uint32_t col, frame;
    memset(solid, 0, sizeof(solid));
    for (col = 0; col < COLS; ++col)
        solid[14u * COLS + col] = 1u;
    memset(&world, 0, sizeof(world));
    world.solid = solid;
    world.columns = COLS;
    world.rows = ROWS;
    world.tile_size = 16u;
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

    memset(&combat, 0, sizeof(combat));
    combat.patrol_left = 100.0f;
    combat.patrol_right = 180.0f;
    combat.enemy_start_x = 140.0f;
    combat.enemy_feet_y = 224.0f;
    combat.enemy_speed = 30.0f;
    combat.sword_reach = 30.0f;
    combat.contact_range = 8.0f;
    combat.enemy_initial_hp = 2u;
    combat.player_initial_hp = 3u;
    combat.sword_cooldown_frames = 12u;
    combat.hurt_cooldown_frames = 30u;

    if (hm_session_init(&world, &combat, &game) != HM_SESSION_OK)
        return HM_SESSION_SELFTEST_INIT;
    for (frame = 0; frame < 30u; ++frame) {
        if (hm_session_step(&world, &combat, &game, input,
                            0u, 1.0f / 60.0f) != HM_SESSION_OK)
            return HM_SESSION_SELFTEST_MOVEMENT;
    }
    if (game.player.frame != 30u || game.combat.frame != 30u ||
        game.player.x < 85.0f || game.combat.enemy_hp != 2u)
        return HM_SESSION_SELFTEST_MOVEMENT;

    world.events = &hazard;
    world.event_count = 1u;
    if (hm_session_init(&world, &combat, &game) != HM_SESSION_OK)
        return HM_SESSION_SELFTEST_HAZARD;
    game.combat.player_hp = 1u;
    game.combat.enemy_hp = 1u;
    input.axis = 0.0f;
    if (hm_session_step(&world, &combat, &game, input,
                        0u, 1.0f / 60.0f) != HM_SESSION_OK ||
        game.player.respawns != 1u || game.player.hazards != 1u ||
        game.combat.player_hp != 3u || game.combat.enemy_hp != 2u ||
        game.combat.frame != 0u)
        return HM_SESSION_SELFTEST_HAZARD;

    world.events = NULL;
    world.event_count = 0u;
    if (hm_session_init(&world, &combat, &game) != HM_SESSION_OK)
        return HM_SESSION_SELFTEST_DEFEAT;
    game.combat.player_hp = 0u;
    game.combat.enemy_hp = 1u;
    input.axis = 1.0f;
    if (hm_session_step(&world, &combat, &game, input,
                        1u, 1.0f / 60.0f) != HM_SESSION_OK ||
        game.player.respawns != 1u || game.player.x != world.spawn_x ||
        game.combat.enemy_hp != 2u || game.combat.player_hp != 3u ||
        game.combat.frame != 0u)
        return HM_SESSION_SELFTEST_DEFEAT;

    original = game;
    combat.enemy_speed = NAN;
    if (hm_session_step(&world, &combat, &game, input,
                        0u, 1.0f / 60.0f) != HM_SESSION_COMBAT_ERROR ||
        memcmp(&game, &original, sizeof(game)) != 0)
        return HM_SESSION_SELFTEST_ROLLBACK;
    return HM_SESSION_SELFTEST_OK;
}
