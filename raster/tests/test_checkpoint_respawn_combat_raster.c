/* Stage 048: checkpoint persistence across real combat death and world hazard.
 * Source-only same C99 physics/combat/raster linked into the Switch NRO.
 * No original iOS game data, proprietary sprites, or emulator state edits.
 */
#include "heman_session.h"
#include "raster_scene.h"
#include <assert.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#define COLS 48u
#define ROWS 24u
#define WIDTH HM_RASTER_WIDTH
#define HEIGHT HM_RASTER_HEIGHT

static uint8_t floor_cells[COLS * ROWS];
static uint32_t pixels[WIDTH * HEIGHT];
static const hm_event events[] = {
    { HM_CHECKPOINT, 90.0f, 272.0f, 8.0f },
    { HM_HAZARD, 150.0f, 262.0f, 8.0f }
};

static void render_assert(const hm_raster_view *view,
                          uint8_t hp, uint8_t enemy_hp,
                          uint32_t respawns, uint32_t player_x) {
    uint32_t i;
    uint32_t marker_x = 20u + 2u * player_x + 5u;
    const hm_session *s = view->game;
    assert(s->combat.player_hp == hp);
    assert(s->combat.enemy_hp == enemy_hp);
    assert(s->player.respawns == respawns);
    assert(s->player.x == (float)player_x);
    assert(s->player.checkpoint == 0);
    assert(marker_x < WIDTH);
    assert(hm_raster_render(pixels, WIDTH, HEIGHT, WIDTH, view) == 1);
    for (i = 0u; i < 3u; ++i) {
        const uint32_t expected = i < hp
            ? UINT32_C(0xffe77965) : UINT32_C(0xff493b51);
        assert(pixels[18u * WIDTH + 18u + 18u * i] == expected);
    }
    for (i = 0u; i < 2u; ++i) {
        const uint32_t expected = i < enemy_hp
            ? UINT32_C(0xffe1c86d) : UINT32_C(0xff493b51);
        assert(pixels[18u * WIDTH + 226u + 18u * i] == expected);
    }
    assert(pixels[53u * WIDTH + marker_x] == UINT32_C(0xffff00ff));
    assert(pixels[62u * WIDTH + 522u] ==
           (respawns ? UINT32_C(0xff42d58a) : UINT32_C(0xff283d51)));
    /* World checkpoint flag changes yellow to green only on activation.
       Sample the flag between the hero's head/body and sword at x=190. */
    assert(pixels[250u * WIDTH + 190u] == UINT32_C(0xff77e4a6));
}

static void step_ok(const hm_world *w, const hm_combat_config *c,
                    hm_session *s, float axis, uint8_t jump,
                    uint8_t sword) {
    hm_input input = {axis, jump, 0u};
    assert(hm_session_step(w, c, s, input, sword, 1.0f/60.0f)
           == HM_SESSION_OK);
}

int main(void) {
    hm_world w;
    hm_combat_config c, broken;
    hm_session game, snapshot;
    hm_raster_view view;
    hm_input held = {-1.0f, 1u, 0u};
    uint32_t t;
    memset(&w, 0, sizeof(w));
    memset(&c, 0, sizeof(c));
    memset(floor_cells, 0, sizeof(floor_cells));
    for (t = 0u; t < COLS; ++t)
        floor_cells[17u * COLS + t] = 1u;
    w.solid = floor_cells; w.columns = COLS; w.rows = ROWS;
    w.tile_size = 16u; w.spawn_x = 50.0f; w.spawn_feet_y = 272.0f;
    w.actor_half_width = 5.0f; w.actor_height = 22.0f;
    w.speed = 120.0f; w.gravity = 1200.0f;
    w.jump_speed = 420.0f; w.terminal_speed = 1400.0f;
    w.viewport_width = 320.0f; w.viewport_height = 240.0f;
    w.death_margin = 96.0f;
    w.events = events; w.event_count = 2u;

    c.patrol_left = 106.0f; c.patrol_right = 114.0f;
    c.enemy_start_x = 110.0f; c.enemy_feet_y = 272.0f;
    c.enemy_speed = 8.0f; c.sword_reach = 30.0f;
    c.contact_range = 9.0f;
    c.enemy_initial_hp = 2u; c.player_initial_hp = 3u;
    c.sword_cooldown_frames = 15u; c.hurt_cooldown_frames = 30u;

    assert(hm_session_init(&w, &c, &game) == HM_SESSION_OK);
    assert(game.player.checkpoint == -1);
    view.world = &w; view.game = &game; view.combat = &c;
    view.qa_state = 0u; view.qa_fingerprint = 0u;

    /* A yellow checkpoint before contact cannot already count as active. */
    assert(hm_raster_render(pixels, WIDTH, HEIGHT, WIDTH, &view) == 1);
    assert(pixels[250u * WIDTH + 190u] == UINT32_C(0xffffcd77));

    for (t = 0u; t < 20u; ++t) step_ok(&w, &c, &game, 1.0f, 0u, 0u);
    assert(game.player.x == 90.0f);
    assert(game.player.checkpoint == 0);
    assert(game.combat.player_hits == 0u);
    render_assert(&view, 3u, 2u, 0u, 90u);

    /* Walk into a DIFFERENT location and lose the entire native health bar.
       Death time is bounded but not hard-coded to avoid coupling to patrol
       phase; no direct writes to combat HP are permitted. */
    for (t = 0u; t < 10u; ++t) step_ok(&w, &c, &game, 1.0f, 0u, 0u);
    assert(game.player.x == 110.0f);
    for (t = 0u; t < 120u && game.combat.player_hp > 0u; ++t)
        step_ok(&w, &c, &game, 0.0f, 0u, 0u);
    assert(t < 120u);
    assert(game.combat.player_hp == 0u);
    assert(game.combat.player_hits == 3u);
    assert(game.player.respawns == 0u);
    assert(game.player.checkpoint == 0);
    render_assert(&view, 0u, 2u, 0u, 110u);

    /* Failed recovery cannot move the hero or consume checkpoint state. */
    snapshot = game;
    broken = c;
    broken.enemy_speed = NAN;
    assert(hm_session_step(&w, &broken, &game, held, 1u, 1.0f/60.0f)
           == HM_SESSION_COMBAT_ERROR);
    assert(memcmp(&game, &snapshot, sizeof(game)) == 0);

    /* Native next-frame recovery uses activated checkpoint, not world
       spawn: held Left + Jump + X are all suppressed on this one step. */
    assert(hm_session_step(&w, &c, &game, held, 1u, 1.0f/60.0f)
           == HM_SESSION_OK);
    assert(game.player.x == 90.0f && game.player.feet_y == 272.0f);
    assert(game.player.checkpoint == 0);
    assert(game.player.respawns == 1u);
    assert(game.combat.frame == 0u);
    assert(game.combat.sword_hits == 0u);
    assert(game.facing_right == 1u);
    render_assert(&view, 3u, 2u, 1u, 90u);

    /* Walk towards enemy again and prove real player control has resumed. */
    for (t = 0u; t < 7u; ++t) step_ok(&w, &c, &game, 1.0f, 0u, 0u);
    assert(game.player.x == 104.0f);
    assert(game.player.checkpoint == 0);
    assert(game.player.grounded == 1u);
    assert(game.combat.player_hp >= 2u);
    render_assert(&view, game.combat.player_hp, 2u, 1u, 104u);

    step_ok(&w, &c, &game, 0.0f, 0u, 1u);
    assert(game.combat.sword_hits == 1u);
    assert(game.combat.enemy_hp == 1u);
    for (t = 0u; t < 15u; ++t) step_ok(&w, &c, &game, 0.0f, 0u, 0u);
    step_ok(&w, &c, &game, 0.0f, 0u, 1u);
    assert(game.combat.sword_hits == 2u);
    assert(game.combat.enemy_hp == 0u);
    assert(game.combat.player_hp >= 1u);
    render_assert(&view, game.combat.player_hp, 0u, 1u, 104u);

    /* The world hazard performs a SECOND respawn and restores combat,
       while retaining the already activated checkpoint and not returning
       to the original x=50 spawn point. */
    for (t = 0u; t < 40u && game.player.respawns == 1u; ++t)
        step_ok(&w, &c, &game, 1.0f, 0u, 0u);
    assert(t < 40u);
    assert(game.player.hazards == 1u);
    assert(game.player.respawns == 2u);
    assert(game.player.checkpoint == 0);
    assert(game.combat.frame == 0u);
    render_assert(&view, 3u, 2u, 2u, 90u);

    puts("Checkpoint -> distant combat death -> checkpoint respawn -> sword victory -> hazard checkpoint respawn: PASS");
    return 0;
}
