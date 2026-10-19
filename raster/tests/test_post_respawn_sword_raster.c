/* Stage 046 host rehearsal: normal contact defeat + post-respawn X swords.
 * Uses exactly the portable C99 gameplay/renderer sources in devkitPro NRO.
 * Guest NeXium/HID proof is separate; this is NOT original iOS gameplay.
 */
#include "heman_session.h"
#include "raster_scene.h"
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#define COLUMNS 48u
#define ROWS 24u
#define WIDTH HM_RASTER_WIDTH
#define HEIGHT HM_RASTER_HEIGHT

static uint8_t solid[COLUMNS * ROWS];
static uint32_t pixels[WIDTH * HEIGHT];

static void inspect(const hm_raster_view *view,
                    uint8_t player_hp, uint8_t enemy_hp,
                    uint32_t respawns) {
    uint32_t i;
    assert(view->game->combat.player_hp == player_hp);
    assert(view->game->combat.enemy_hp == enemy_hp);
    assert(view->game->player.respawns == respawns);
    assert(view->game->player.x == 50.0f);
    assert(hm_raster_render(pixels, WIDTH, HEIGHT, WIDTH, view) == 1);
    for (i = 0u; i < 3u; ++i) {
        assert(pixels[18u * WIDTH + 18u + i * 18u] ==
               (i < player_hp ? UINT32_C(0xffe77965) :
                                UINT32_C(0xff493b51)));
    }
    for (i = 0u; i < 2u; ++i) {
        assert(pixels[18u * WIDTH + 226u + i * 18u] ==
               (i < enemy_hp ? UINT32_C(0xffe1c86d) :
                               UINT32_C(0xff493b51)));
    }
    assert(pixels[62u * WIDTH + 522u] ==
           (respawns ? UINT32_C(0xff42d58a) : UINT32_C(0xff283d51)));
    assert(pixels[53u * WIDTH + 125u] == UINT32_C(0xffff00ff));
}

int main(void) {
    hm_world w;
    hm_combat_config c;
    hm_session game;
    hm_raster_view view;
    hm_input no_move = {0.0f, 0u, 0u};
    uint32_t t;
    memset(&w, 0, sizeof(w));
    memset(&c, 0, sizeof(c));
    memset(solid, 0, sizeof(solid));
    for (t=0u; t<COLUMNS; ++t) solid[17u * COLUMNS + t] = 1u;

    w.solid = solid; w.columns = COLUMNS; w.rows = ROWS;
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

    assert(hm_session_init(&w, &c, &game) == HM_SESSION_OK);
    view.world = &w; view.combat = &c; view.game = &game;
    view.qa_state = 0u; view.qa_fingerprint = 0u;

    for (t=1u; t<=170u; ++t) {
        /* A single native press is a one-frame edge. Real guest actions
           are injected after receiver frames 65 / 84 with small HID delay. */
        uint8_t x_down = (uint8_t)(t == 66u || t == 85u);
        assert(hm_session_step(&w, &c, &game, no_move, x_down,
                               1.0f/60.0f) == HM_SESSION_OK);
        assert(game.player.x == 50.0f);
        assert(game.player.feet_y == 272.0f);
        if (t == 61u) {
            assert(game.combat.player_hits == 3u);
            inspect(&view, 0u, 2u, 0u);
        }
        if (t == 62u) {
            assert(game.combat.sword_hits == 0u);
            inspect(&view, 3u, 2u, 1u);
        }
        if (t == 66u) {
            assert(game.combat.sword_hits == 1u);
            inspect(&view, 2u, 1u, 1u);
        }
        if (t == 79u) inspect(&view, 2u, 1u, 1u);
        if (t == 85u) {
            assert(game.combat.sword_hits == 2u);
            inspect(&view, 2u, 0u, 1u);
        }
        if (t == 115u || t == 170u) {
            assert(game.combat.sword_hits == 2u);
            assert(game.combat.player_hits == 1u);
            inspect(&view, 2u, 0u, 1u);
        }
    }
    puts("Post-respawn X: native HP 2->1->0, player HP stable and guest HUD pixels: PASS");
    return 0;
}
