/* Synthetic pickup healing through the real combined C99 physics session.
   No iOS game content or Switch SDK required. */
#include "heman_session.h"

#include <assert.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#define COLS 32u
#define ROWS 20u
static uint8_t cells[COLS * ROWS];

static hm_world make_world(const hm_event *events, uint32_t count) {
    hm_world w;
    uint32_t x;
    memset(&w, 0, sizeof(w));
    memset(cells, 0, sizeof(cells));
    for (x = 0u; x < COLS; ++x) cells[14u * COLS + x] = 1u;
    w.solid = cells;
    w.columns = COLS;
    w.rows = ROWS;
    w.tile_size = 16u;
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
    w.events = events;
    w.event_count = count;
    return w;
}

static hm_combat_config make_combat(void) {
    hm_combat_config c;
    memset(&c, 0, sizeof(c));
    c.patrol_left = 100.0f;
    c.patrol_right = 160.0f;
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
    const hm_event pickup[] = {
        { HM_PICKUP, 32.0f, 210.0f, 10.0f },
        { HM_PICKUP, 33.0f, 210.0f, 10.0f }
    };
    hm_world world = make_world(pickup, 1u);
    hm_combat_config combat = make_combat();
    hm_session session, saved;
    hm_input idle = {0.0f, 0u, 0u};
    uint32_t frame;

    assert(hm_session_init(&world, &combat, &session) == HM_SESSION_OK);
    session.combat.player_hp = 1u;

    /* One new pickup heals one HP, even while the player stands on it. */
    assert(hm_session_step(&world, &combat, &session,
                           idle, 0u, 1.0f/60.0f) == HM_SESSION_OK);
    assert(session.player.picked == 1u);
    assert(session.combat.player_hp == 2u);

    /* A recorded pickup cannot heal again on subsequent frames. */
    session.combat.player_hp = 1u;
    for (frame = 0u; frame < 5u; ++frame)
        assert(hm_session_step(&world, &combat, &session,
                               idle, 0u, 1.0f/60.0f) == HM_SESSION_OK);
    assert(session.combat.player_hp == 1u);
    assert(session.player.picked == 1u);

    /* Multiple *new* pickup bits can heal, but never exceed max HP. */
    world = make_world(pickup, 2u);
    assert(hm_session_init(&world, &combat, &session) == HM_SESSION_OK);
    session.combat.player_hp = 2u;
    assert(hm_session_step(&world, &combat, &session,
                           idle, 0u, 1.0f/60.0f) == HM_SESSION_OK);
    assert(session.player.picked == 3u);
    assert(session.combat.player_hp == 3u);

    /* The normal B reset does not un-collect the pickup or apply healing.
       Combat starts at full HP and old collected bits stay recorded. */
    idle.reset = 1u;
    assert(hm_session_step(&world, &combat, &session,
                           idle, 0u, 1.0f/60.0f) == HM_SESSION_OK);
    assert(session.combat.player_hp == combat.player_initial_hp);
    assert(session.player.picked == 3u);

    /* A failed combat transition cannot consume a new pickup. */
    world = make_world(pickup, 1u);
    assert(hm_session_init(&world, &combat, &session) == HM_SESSION_OK);
    session.combat.player_hp = 1u;
    saved = session;
    idle.reset = 0u;
    combat.enemy_speed = NAN;
    assert(hm_session_step(&world, &combat, &session,
                           idle, 0u, 1.0f/60.0f) == HM_SESSION_COMBAT_ERROR);
    assert(memcmp(&session, &saved, sizeof(session)) == 0);
    combat = make_combat();
    idle.reset = 0u;
    assert(hm_session_step(&world, &combat, &session,
                           idle, 0u, 1.0f/60.0f) == HM_SESSION_OK);
    assert(session.player.picked == 1u);
    assert(session.combat.player_hp == 2u);

    /* A naturally full-health character never exceeds its max. */
    assert(hm_session_init(&world, &combat, &session) == HM_SESSION_OK);
    assert(hm_session_step(&world, &combat, &session,
                           idle, 0u, 1.0f/60.0f) == HM_SESSION_OK);
    assert(session.combat.player_hp == combat.player_initial_hp);

    puts("Synthetic one-time pickup healing and rollback tests passed");
    return 0;
}
