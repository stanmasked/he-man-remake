/* Synthetic C99 cross-module tests, no private IPA or Nintendo SDK. */
#include "heman_session.h"

#include <assert.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#define COLS 32u
#define ROWS 20u
#define TILE 16u
static uint8_t tiles[COLS * ROWS];

static hm_world world_fixture(void) {
    hm_world w;
    uint32_t col;
    memset(&w, 0, sizeof(w));
    memset(tiles, 0, sizeof(tiles));
    for (col = 0; col < COLS; ++col)
        tiles[14u * COLS + col] = 1u;
    w.solid = tiles;
    w.columns = COLS;
    w.rows = ROWS;
    w.tile_size = TILE;
    w.spawn_x = 32.0f;
    w.spawn_feet_y = 224.0f;
    w.actor_half_width = 5.0f;
    w.actor_height = 22.0f;
    w.speed = 120.0f;
    w.gravity = 1200.0f;
    w.jump_speed = 420.0f;
    w.terminal_speed = 1400.0f;
    w.viewport_width = 320.0f;
    w.viewport_height = 240.0f;
    w.death_margin = 96.0f;
    return w;
}

static hm_combat_config combat_fixture(void) {
    hm_combat_config c;
    memset(&c, 0, sizeof(c));
    c.patrol_left = 100.0f;
    c.patrol_right = 180.0f;
    c.enemy_start_x = 140.0f;
    c.enemy_feet_y = 224.0f;
    c.enemy_speed = 30.0f;
    c.sword_reach = 30.0f;
    c.contact_range = 8.0f;
    c.enemy_initial_hp = 2u;
    c.player_initial_hp = 3u;
    c.sword_cooldown_frames = 12u;
    c.hurt_cooldown_frames = 30u;
    return c;
}

int main(void) {
    hm_world world = world_fixture();
    hm_combat_config combat = combat_fixture();
    hm_session session, snapshot, repeat;
    hm_input input = {1.0f, 0u, 0u};
    unsigned i;

    memset(&session, 0xA5, sizeof(session));
    assert(hm_session_init(&world, &combat, &session) == HM_SESSION_OK);
    assert(session.facing_right == 1u);
    assert(session.player.x == 32.0f);
    assert(session.combat.enemy_hp == 2u);
    assert(session.combat.player_hp == 3u);

    /* Move through actual hm_step physics and combat in the same update. */
    for (i = 0; i < 30u; ++i)
        assert(hm_session_step(&world, &combat, &session,
                               input, 0u, 1.0f / 60.0f) == HM_SESSION_OK);
    assert(session.player.frame == 30u);
    assert(session.combat.frame == 30u);
    assert(session.player.x > 85.0f);
    assert(session.combat.enemy_x >= combat.patrol_left);
    assert(session.combat.enemy_x <= combat.patrol_right);

    /* All failing updates must roll back BOTH the actor and combat state. */
    snapshot = session;
    combat.enemy_speed = NAN;
    assert(hm_session_step(&world, &combat, &session, input,
                            0u, 1.0f / 60.0f) == HM_SESSION_COMBAT_ERROR);
    assert(memcmp(&session, &snapshot, sizeof(session)) == 0);
    combat = combat_fixture();
    assert(hm_session_step(&world, &combat, &session, input,
                            0u, NAN) == HM_SESSION_PHYSICS_ERROR);
    assert(memcmp(&session, &snapshot, sizeof(session)) == 0);
    assert(hm_session_step(&world, &combat, &session, input,
                            2u, 1.0f / 60.0f) == HM_SESSION_INVALID);
    assert(memcmp(&session, &snapshot, sizeof(session)) == 0);

    /* Reset should atomically restore the enemy but retain the standard
       native hm_step reset semantics (frame and respawn counter advance). */
    session.combat.enemy_hp = 0u;
    session.combat.player_hp = 1u;
    input.axis = 0.0f; input.reset = 1u;
    assert(hm_session_step(&world, &combat, &session,
                           input, 0u, 1.0f / 60.0f) == HM_SESSION_OK);
    assert(session.player.x == world.spawn_x);
    assert(session.player.respawns == snapshot.player.respawns + 1u);
    assert(session.combat.enemy_hp == combat.enemy_initial_hp);
    assert(session.combat.player_hp == combat.player_initial_hp);
    assert(session.combat.frame == 0u);

    /* Init failure must also leave the destination unchanged. */
    snapshot = session;
    combat.enemy_speed = NAN;
    assert(hm_session_init(&world, &combat, &session)
           == HM_SESSION_COMBAT_ERROR);
    assert(memcmp(&session, &snapshot, sizeof(session)) == 0);
    combat = combat_fixture();

    /* Identical scripted inputs produce the same complete session. */
    assert(hm_session_init(&world, &combat, &repeat) == HM_SESSION_OK);
    assert(hm_session_init(&world, &combat, &session) == HM_SESSION_OK);
    input.reset = 0u; input.axis = 1.0f;
    for (i = 0u; i < 120u; ++i) {
        uint8_t strike = (uint8_t)((i == 50u || i == 65u) ? 1u : 0u);
        if (i >= 60u) input.axis = -1.0f;
        assert(hm_session_step(&world, &combat, &repeat,
                               input, strike, 1.0f/60.0f) == HM_SESSION_OK);
    }
    input.axis = 1.0f;
    for (i = 0u; i < 120u; ++i) {
        uint8_t strike = (uint8_t)((i == 50u || i == 65u) ? 1u : 0u);
        if (i >= 60u) input.axis = -1.0f;
        assert(hm_session_step(&world, &combat, &session,
                               input, strike, 1.0f/60.0f) == HM_SESSION_OK);
    }
    assert(memcmp(&session, &repeat, sizeof(session)) == 0);

    puts("Synthetic atomic gameplay session tests passed");
    return 0;
}
