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

    /* An automatic hazard respawn must reset combat in the same frame:
       neither a half-dead enemy nor partial player HP may survive. */
    {
        hm_world hazard_world = world_fixture();
        const hm_event hazard = { HM_HAZARD, 32.0f, 210.0f, 10.0f };
        hm_session hazard_session, hazard_saved;
        hm_input idle = {0.0f, 0u, 0u};
        hazard_world.events = &hazard;
        hazard_world.event_count = 1u;
        assert(hm_session_init(&hazard_world, &combat, &hazard_session)
               == HM_SESSION_OK);
        hazard_session.combat.enemy_hp = 1u;
        hazard_session.combat.player_hp = 1u;
        assert(hm_session_step(&hazard_world, &combat, &hazard_session,
                               idle, 0u, 1.0f / 60.0f) == HM_SESSION_OK);
        assert(hazard_session.player.respawns == 1u);
        assert(hazard_session.player.hazards == 1u);
        assert(hazard_session.combat.enemy_hp == combat.enemy_initial_hp);
        assert(hazard_session.combat.player_hp == combat.player_initial_hp);
        assert(hazard_session.combat.frame == 0u);

        /* A malformed combat config after the world-level respawn fails
           transactionally, leaving the entire caller state unchanged. */
        hazard_saved = hazard_session;
        combat.enemy_speed = NAN;
        assert(hm_session_step(&hazard_world, &combat, &hazard_session,
                               idle, 0u, 1.0f / 60.0f)
               == HM_SESSION_COMBAT_ERROR);
        assert(memcmp(&hazard_session, &hazard_saved,
                      sizeof(hazard_session)) == 0);
        combat = combat_fixture();
    }

    /* A synthetic combat defeat is visible for one completed frame.
       The next call then restores player and encounter atomically through
       the native respawn operation, ignoring incoming motion and attack. */
    {
        hm_session defeated, saved;
        hm_input right = {1.0f, 0u, 0u};
        assert(hm_session_init(&world, &combat, &defeated) == HM_SESSION_OK);
        defeated.combat.player_hp = 0u;
        defeated.combat.enemy_hp = 1u;
        defeated.combat.sword_cooldown = 8u;
        saved = defeated;
        assert(hm_session_step(&world, &combat, &defeated,
                               right, 1u, 1.0f / 60.0f) == HM_SESSION_OK);
        assert(defeated.player.x == world.spawn_x);
        assert(defeated.player.respawns == saved.player.respawns + 1u);
        assert(defeated.player.frame == saved.player.frame + 1u);
        assert(defeated.combat.player_hp == combat.player_initial_hp);
        assert(defeated.combat.enemy_hp == combat.enemy_initial_hp);
        assert(defeated.combat.sword_cooldown == 0u);
        assert(defeated.combat.frame == 0u);

        /* Even a defeat recovery must roll back on invalid physics
           input (bad dt), preserving both states and all counters. */
        defeated.combat.player_hp = 0u;
        saved = defeated;
        assert(hm_session_step(&world, &combat, &defeated,
                               right, 1u, NAN) == HM_SESSION_PHYSICS_ERROR);
        assert(memcmp(&defeated, &saved, sizeof(defeated)) == 0);

        /* Invalid caller input is not masked by the forced reset. */
        right.axis = NAN;
        assert(hm_session_step(&world, &combat, &defeated,
                               right, 1u, 1.0f / 60.0f)
               == HM_SESSION_PHYSICS_ERROR);
        assert(memcmp(&defeated, &saved, sizeof(defeated)) == 0);
        right.axis = 1.0f;

        /* Reinitialization of combat may also fail. The player must not
           be respawned unless the whole transaction can commit. */
        combat.enemy_speed = NAN;
        assert(hm_session_step(&world, &combat, &defeated,
                               right, 1u, 1.0f / 60.0f)
               == HM_SESSION_COMBAT_ERROR);
        assert(memcmp(&defeated, &saved, sizeof(defeated)) == 0);
        combat = combat_fixture();
    }

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
