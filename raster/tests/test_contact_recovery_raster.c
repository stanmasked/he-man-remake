/* Stage 040: real session combat contact, invulnerability and defeat recovery.
 * Purely original source-only synthetic encounter; no external game assets.
 * Compiled with GCC and Clang against exactly the core used by Switch NRO.
 */
#include "heman_session.h"
#include "raster_scene.h"
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#define COLS 48u
#define ROWS 24u
#define WIDTH HM_RASTER_WIDTH
#define HEIGHT HM_RASTER_HEIGHT
static uint8_t floor_cells[COLS * ROWS];
static uint32_t pixels[WIDTH * HEIGHT];

static void assert_hp_pixels(const hm_raster_view *view, unsigned health) {
    const uint32_t full = UINT32_C(0xffe77965);
    const uint32_t empty = UINT32_C(0xff493b51);
    unsigned tick;
    assert(hm_raster_render(pixels, WIDTH, HEIGHT, WIDTH, view) == 1);
    for (tick = 0u; tick < 3u; ++tick)
        assert(pixels[18u * WIDTH + (18u + tick * 18u)] ==
               (tick < health ? full : empty));
    assert(pixels[53u * WIDTH + 125u] == UINT32_C(0xffff00ff));
    assert(pixels[302u * WIDTH + 475u] == UINT32_C(0xffffff00));
}

int main(void) {
    hm_world world;
    hm_combat_config cfg;
    hm_session game;
    hm_raster_view view;
    hm_input neutral = {0.0f, 0u, 0u};
    unsigned step;

    memset(&world, 0, sizeof(world));
    memset(&cfg, 0, sizeof(cfg));
    memset(floor_cells, 0, sizeof(floor_cells));
    for (step = 0u; step < COLS; ++step)
        floor_cells[17u * COLS + step] = 1u;
    world.solid = floor_cells;
    world.columns = COLS; world.rows = ROWS; world.tile_size = 16u;
    world.spawn_x = 50.0f; world.spawn_feet_y = 272.0f;
    world.actor_half_width = 5.0f; world.actor_height = 22.0f;
    world.speed = 120.0f; world.gravity = 1200.0f;
    world.jump_speed = 420.0f; world.terminal_speed = 1400.0f;
    world.viewport_width = 320.0f; world.viewport_height = 240.0f;
    world.death_margin = 96.0f;

    cfg.patrol_left = 46.0f; cfg.patrol_right = 54.0f;
    cfg.enemy_start_x = 50.0f; cfg.enemy_feet_y = 272.0f;
    cfg.enemy_speed = 8.0f; cfg.sword_reach = 30.0f;
    cfg.contact_range = 9.0f;
    cfg.enemy_initial_hp = 2u; cfg.player_initial_hp = 3u;
    cfg.sword_cooldown_frames = 15u; cfg.hurt_cooldown_frames = 45u;

    assert(hm_session_init(&world, &cfg, &game) == HM_SESSION_OK);
    view.world = &world; view.game = &game; view.combat = &cfg;
    view.qa_state = 0u; view.qa_fingerprint = 0u;
    assert_hp_pixels(&view, 3u);

    for (step = 1u; step <= 94u; ++step) {
        assert(hm_session_step(&world, &cfg, &game, neutral, 0u,
                               1.0f / 60.0f) == HM_SESSION_OK);
        assert(game.player.x == 50.0f);
        assert(game.player.feet_y == 272.0f);
        if (step == 1u) {
            assert(game.combat.player_hp == 2u);
            assert(game.combat.player_hits == 1u);
            assert(game.combat.hurt_cooldown == 45u);
            assert_hp_pixels(&view, 2u);
        }
        if (step == 45u) {
            assert(game.combat.player_hp == 2u);
            assert(game.combat.player_hits == 1u);
            assert(game.combat.hurt_cooldown == 1u);
            assert_hp_pixels(&view, 2u);
        }
        if (step == 46u) {
            assert(game.combat.player_hp == 1u);
            assert(game.combat.player_hits == 2u);
            assert(game.combat.hurt_cooldown == 45u);
            assert_hp_pixels(&view, 1u);
        }
        if (step == 90u) {
            assert(game.combat.player_hp == 1u);
            assert(game.combat.player_hits == 2u);
            assert_hp_pixels(&view, 1u);
        }
        if (step == 91u) {
            assert(game.combat.player_hp == 0u);
            assert(game.combat.player_hits == 3u);
            assert_hp_pixels(&view, 0u);
        }
        if (step == 92u) {
            /* Defeat is recovered only on the NEXT game step. */
            assert(game.combat.player_hp == 3u);
            assert(game.combat.player_hits == 0u);
            assert(game.player.respawns == 1u);
            assert(game.combat.enemy_hp == 2u);
            assert_hp_pixels(&view, 3u);
        }
        if (step == 93u) {
            /* The contact enemy may damage again after an ordinary reset. */
            assert(game.combat.player_hp == 2u);
            assert(game.combat.player_hits == 1u);
            assert(game.player.respawns == 1u);
            assert_hp_pixels(&view, 2u);
        }
    }
    puts("Contact damage / 45-frame invulnerability / defeat and respawn: PASS");
    return 0;
}
