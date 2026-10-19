/* Stage 043: full post-defeat recovery to player-controlled combat.
 * Exercises the unchanged, source-only C99 session and RGBA renderer.
 * Host-only regression: NeXium guest input is a separate integration task.
 */
#include "heman_session.h"
#include "raster_scene.h"
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#define NC 48u
#define NR 24u
#define RW HM_RASTER_WIDTH
#define RH HM_RASTER_HEIGHT
static uint8_t ground[NC * NR];
static uint32_t rgba[RW * RH];

static void expect_pixels(const hm_raster_view *view,
                          unsigned hp, unsigned enemy_hp) {
    const uint32_t live_player = UINT32_C(0xffe77965);
    const uint32_t live_enemy = UINT32_C(0xffe1c86d);
    const uint32_t empty = UINT32_C(0xff493b51);
    unsigned tick;
    int mx;
    assert(view->game->combat.player_hp == hp);
    assert(view->game->combat.enemy_hp == enemy_hp);
    assert(hm_raster_render(rgba, RW, RH, RW, view) == 1);
    for (tick = 0u; tick < 3u; ++tick)
        assert(rgba[18u * RW + 18u + 18u * tick] ==
               (tick < hp ? live_player : empty));
    for (tick = 0u; tick < 2u; ++tick)
        assert(rgba[18u * RW + 226u + 18u * tick] ==
               (tick < enemy_hp ? live_enemy : empty));
    assert(rgba[62u * RW + 522u] ==
           (view->game->player.respawns ?
            UINT32_C(0xff42d58a) : UINT32_C(0xff283d51)));
    mx = 20 + (int)(view->game->player.x * 2.0f + 0.5f) + 5;
    assert(mx >= 0 && mx < (int)RW);
    assert(rgba[53u * RW + (uint32_t)mx] == UINT32_C(0xffff00ff));
    assert(rgba[302u * RW + 475u] == UINT32_C(0xffffff00));
}

int main(void) {
    hm_world w;
    hm_combat_config c;
    hm_session s;
    hm_raster_view v;
    uint32_t t;
    memset(&w, 0, sizeof(w));
    memset(&c, 0, sizeof(c));
    memset(ground, 0, sizeof(ground));
    for (t = 0u; t < NC; ++t) ground[17u * NC + t] = 1u;
    w.solid = ground; w.columns = NC; w.rows = NR;
    w.tile_size = 16u; w.spawn_x = 50.0f; w.spawn_feet_y = 272.0f;
    w.actor_half_width = 5.0f; w.actor_height = 22.0f;
    w.speed = 120.0f; w.gravity = 1200.0f;
    w.jump_speed = 420.0f; w.terminal_speed = 1400.0f;
    w.viewport_width = 320.0f; w.viewport_height = 240.0f;
    w.death_margin = 96.0f;

    c.patrol_left = 46.0f; c.patrol_right = 54.0f;
    c.enemy_start_x = 50.0f; c.enemy_feet_y = 272.0f;
    c.enemy_speed = 8.0f; c.sword_reach = 30.0f;
    c.contact_range = 9.0f; c.enemy_initial_hp = 2u;
    c.player_initial_hp = 3u; c.sword_cooldown_frames = 15u;
    c.hurt_cooldown_frames = 30u;
    assert(hm_session_init(&w, &c, &s) == HM_SESSION_OK);
    v.world = &w; v.combat = &c; v.game = &s;
    v.qa_state = 0u; v.qa_fingerprint = 0u;

    for (t = 1u; t <= 110u; ++t) {
        hm_input input = {0.0f, 0u, 0u};
        uint8_t sword = (uint8_t)(t == 77u || t == 95u);
        if (t >= 63u && t <= 74u) input.axis = 1.0f;
        if (t >= 75u && t <= 76u) input.axis = -1.0f;
        assert(hm_session_step(&w, &c, &s, input, sword,
                               1.0f / 60.0f) == HM_SESSION_OK);
        assert(s.player.feet_y == 272.0f);
        assert(s.player.grounded);
        if (t == 61u) {
            assert(s.combat.player_hp == 0u);
            assert(s.combat.player_hits == 3u);
            assert(s.player.respawns == 0u);
            expect_pixels(&v, 0u, 2u);
        }
        if (t == 62u) {
            assert(s.combat.player_hp == 3u);
            assert(s.combat.player_hits == 0u);
            assert(s.combat.frame == 0u);
            assert(s.player.respawns == 1u);
            assert(s.player.x == 50.0f);
            expect_pixels(&v, 3u, 2u);
        }
        if (t == 63u) {
            /* Contact works after respawn even when the player moves. */
            assert(s.player.x == 52.0f);
            assert(s.combat.player_hp == 2u);
            assert(s.combat.player_hits == 1u);
            assert(s.player.respawns == 1u);
            expect_pixels(&v, 2u, 2u);
        }
        if (t == 74u) {
            assert(s.player.x == 74.0f);
            assert(s.facing_right == 1u);
            assert(s.combat.player_hp == 2u);
            expect_pixels(&v, 2u, 2u);
        }
        if (t == 76u) {
            assert(s.player.x == 70.0f);
            assert(s.facing_right == 0u);
            assert(s.combat.player_hp == 2u);
            expect_pixels(&v, 2u, 2u);
        }
        if (t == 77u) {
            assert(s.combat.enemy_hp == 1u);
            assert(s.combat.sword_hits == 1u);
            assert(s.combat.player_hits == 1u);
            expect_pixels(&v, 2u, 1u);
        }
        if (t == 95u) {
            assert(s.combat.enemy_hp == 0u);
            assert(s.combat.sword_hits == 2u);
            assert(s.combat.player_hp == 2u);
            expect_pixels(&v, 2u, 0u);
        }
        if (t == 110u) {
            assert(s.combat.enemy_hp == 0u);
            assert(s.combat.player_hits == 1u);
            assert(s.combat.sword_hits == 2u);
            assert(s.combat.player_hp == 2u);
            assert(s.player.respawns == 1u);
            assert(s.player.x == 70.0f);
            expect_pixels(&v, 2u, 0u);
        }
    }
    puts("Post-respawn movement, facing, sword hits and live HUD: PASS");
    return 0;
}
