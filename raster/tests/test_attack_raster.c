/* Source-only host rehearsal for the actual NeXium X-button test.
   Exactly the same C99 gameplay/raster engines execute in the NRO.
   No original IPA, game art or proprietary assets are used. */
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
static uint8_t ground[COLS*ROWS];
static uint32_t pixels[WIDTH*HEIGHT];

static void check_hp(const hm_raster_view *view, uint8_t current_hp) {
    const uint32_t live = UINT32_C(0xffe1c86d);
    const uint32_t depleted = UINT32_C(0xff493b51);
    assert(hm_raster_render(pixels,WIDTH,HEIGHT,WIDTH,view)==1);
    assert(pixels[18u*WIDTH+226u] == (current_hp >= 1u ? live : depleted));
    assert(pixels[18u*WIDTH+244u] == (current_hp >= 2u ? live : depleted));
    /* Enemy damage cannot erase or relocate the static player-x HUD marker. */
    assert(pixels[53u*WIDTH+125u] == UINT32_C(0xffff00ff));
    /* Player remains grounded throughout this no-direction test. */
    assert(pixels[302u*WIDTH+475u] == UINT32_C(0xffffff00));
}

int main(void) {
    hm_world world;
    hm_combat_config combat;
    hm_session session;
    hm_raster_view view;
    uint32_t frame;
    hm_input input={0.0f,0u,0u};

    memset(&world,0,sizeof(world));
    memset(&combat,0,sizeof(combat));
    memset(ground,0,sizeof(ground));
    for(frame=0u;frame<COLS;++frame) ground[17u*COLS+frame]=1u;
    world.solid=ground;world.columns=COLS;world.rows=ROWS;
    world.tile_size=16u;world.spawn_x=50.0f;world.spawn_feet_y=272.0f;
    world.actor_half_width=5.0f;world.actor_height=22.0f;
    world.speed=120.0f;world.gravity=1200.0f;
    world.jump_speed=420.0f;world.terminal_speed=1400.0f;
    world.viewport_width=320.0f;world.viewport_height=240.0f;
    world.death_margin=96.0f;

    combat.patrol_left=66.0f;combat.patrol_right=74.0f;
    combat.enemy_start_x=68.0f;combat.enemy_feet_y=272.0f;
    combat.enemy_speed=8.0f;combat.sword_reach=30.0f;
    combat.contact_range=9.0f;
    combat.enemy_initial_hp=2u;combat.player_initial_hp=3u;
    combat.sword_cooldown_frames=15u;combat.hurt_cooldown_frames=45u;

    assert(hm_session_init(&world,&combat,&session)==HM_SESSION_OK);
    view.world=&world;view.combat=&combat;view.game=&session;
    view.qa_state=0u;view.qa_fingerprint=0u;

    for(frame=1u;frame<=120u;++frame) {
        uint8_t attack=(uint8_t)((frame==45u || frame==85u) ? 1u : 0u);
        assert(hm_session_step(&world,&combat,&session,input,attack,
                               1.0f/60.0f)==HM_SESSION_OK);
        if(frame==30u || frame==65u || frame==120u) {
            const uint8_t expected=(uint8_t)(frame==30u?2u:frame==65u?1u:0u);
            assert(session.combat.enemy_hp==expected);
            assert(session.combat.player_hp==3u);
            assert(session.combat.sword_hits==(uint32_t)(2u-expected));
            assert(session.player.x==50.0f);
            check_hp(&view,expected);
        }
    }
    assert(session.combat.enemy_hp==0u);
    assert(session.combat.sword_hits==2u);
    assert(session.combat.player_hits==0u);
    puts("Synthetic sword attack + real raster HP 2->1->0: PASS");
    return 0;
}
