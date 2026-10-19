/* Stage 052: original C99 checkpoint + contact-death + sword victory.
 * Host counterpart of actual guest NeXium D-pad/X evidence (separate).
 * Game logic and RGBA8888 renderer are identical to the devkitPro NRO.
 */
#include "heman_session.h"
#include "raster_scene.h"
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#define COLUMNS 48u
#define ROWS 24u
#define W HM_RASTER_WIDTH
#define H HM_RASTER_HEIGHT

static uint8_t tiles[COLUMNS * ROWS];
static uint32_t screen[W * H];
static const hm_event checkpoint[] = {
    { HM_CHECKPOINT, 90.0f, 272.0f, 8.0f },
    { HM_HAZARD, 210.0f, 262.0f, 8.0f }
};

static void rendered_health(const hm_raster_view *v,
                            uint8_t hero, uint8_t enemy,
                            uint32_t respawns) {
    uint32_t i;
    assert(v->game->combat.player_hp == hero);
    assert(v->game->combat.enemy_hp == enemy);
    assert(v->game->player.respawns == respawns);
    assert(v->game->player.checkpoint == 0);
    assert(v->game->player.x == 90.0f);
    assert(hm_raster_render(screen, W, H, W, v) == 1);
    for (i = 0; i < 3u; ++i)
        assert(screen[18u * W + 18u + 18u * i] ==
               (i < hero ? UINT32_C(0xffe77965) :
                           UINT32_C(0xff493b51)));
    for (i = 0; i < 2u; ++i)
        assert(screen[18u * W + 226u + 18u * i] ==
               (i < enemy ? UINT32_C(0xffe1c86d) :
                            UINT32_C(0xff493b51)));
    assert(screen[62u * W + 522u] ==
           (respawns ? UINT32_C(0xff42d58a) : UINT32_C(0xff283d51)));
    assert(screen[53u * W + 205u] == UINT32_C(0xffff00ff));
    assert(screen[250u * W + 207u] == UINT32_C(0xff77e4a6));
}

int main(void) {
    hm_world world;
    hm_combat_config combat;
    hm_session game;
    hm_raster_view view;
    hm_input input = {0.0f, 0u, 0u};
    uint32_t t, defeated = 0u, recovered = 0u, first = 0u, second = 0u;
    memset(&world, 0, sizeof(world));
    memset(&combat, 0, sizeof(combat));
    memset(tiles, 0, sizeof(tiles));
    for (t = 0u; t < COLUMNS; ++t) tiles[17u * COLUMNS + t] = 1u;
    world.solid = tiles; world.columns = COLUMNS; world.rows = ROWS;
    world.tile_size = 16u; world.spawn_x = 50.0f; world.spawn_feet_y = 272.0f;
    world.actor_half_width = 5.0f; world.actor_height = 22.0f;
    world.speed = 120.0f; world.gravity = 1200.0f;
    world.jump_speed = 420.0f; world.terminal_speed = 1400.0f;
    world.viewport_width = 320.0f; world.viewport_height = 240.0f;
    world.death_margin = 96.0f;
    world.events = checkpoint; world.event_count = 2u;

    combat.patrol_left = 86.0f; combat.patrol_right = 94.0f;
    combat.enemy_start_x = 90.0f; combat.enemy_feet_y = 272.0f;
    combat.enemy_speed = 8.0f; combat.sword_reach = 30.0f;
    combat.contact_range = 9.0f;
    combat.enemy_initial_hp = 2u; combat.player_initial_hp = 3u;
    combat.sword_cooldown_frames = 15u;
    combat.hurt_cooldown_frames = 30u;

    assert(hm_session_init(&world, &combat, &game) == HM_SESSION_OK);
    view.world = &world; view.combat = &combat; view.game = &game;
    view.qa_state = 0u; view.qa_fingerprint = 0u;
    assert(hm_raster_render(screen, W, H, W, &view) == 1);
    assert(screen[250u * W + 207u] == UINT32_C(0xffffcd77));

    for (t = 1u; t <= 160u; ++t) {
        uint8_t attack = (uint8_t)(
            recovered && (t == recovered + 6u || t == recovered + 25u)
        );
        input.axis = (t <= 20u) ? 1.0f : 0.0f;
        assert(hm_session_step(&world, &combat, &game, input, attack,
                               1.0f/60.0f) == HM_SESSION_OK);
        if (t == 20u) {
            assert(game.player.x == 90.0f);
            assert(game.player.checkpoint == 0);
        }
        if (game.combat.player_hp == 0u) {
            assert(defeated == 0u);
            defeated = t;
            assert(game.player.respawns == 0u);
            rendered_health(&view, 0u, 2u, 0u);
        }
        if (defeated && t == defeated + 1u) {
            assert(recovered == 0u);
            recovered = t;
            rendered_health(&view, 3u, 2u, 1u);
        }
        if (attack && t == recovered + 6u) {
            first = t;
            assert(game.combat.sword_hits == 1u);
            rendered_health(&view, 2u, 1u, 1u);
        }
        if (attack && t == recovered + 25u) {
            second = t;
            assert(game.combat.sword_hits == 2u);
            rendered_health(&view, 2u, 0u, 1u);
        }
    }
    assert(defeated > 20u && recovered == defeated + 1u);
    assert(first == recovered + 6u && second == recovered + 25u);
    assert(game.combat.player_hits == 1u);
    assert(game.combat.sword_hits == 2u);
    rendered_health(&view, 2u, 0u, 1u);
    puts("Checkpoint natural combat defeat -> auto-recover -> two sword hits: PASS");
    return 0;
}
