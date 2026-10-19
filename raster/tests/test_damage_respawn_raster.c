/* Actual shared C99 session/combat/raster host rehearsal. Neither damage
   nor defeat is fabricated: one contact enemy automatically causes three
   spaced hits followed by the standard next-frame recovery. */
#include "heman_session.h"
#include "raster_scene.h"
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#define W HM_RASTER_WIDTH
#define H HM_RASTER_HEIGHT
#define NC 48u
#define NR 24u
static uint8_t solid[NC*NR];
static uint32_t framebuffer[W*H];

static void inspect(const hm_raster_view *view, unsigned frame,
                    uint8_t hp, uint32_t respawns) {
    uint32_t i;
    const uint32_t lit=UINT32_C(0xffe77965);
    const uint32_t empty=UINT32_C(0xff493b51);
    uint32_t recovered=respawns>0u?
        UINT32_C(0xff42d58a):UINT32_C(0xff283d51);
    assert(view->game->combat.player_hp==hp);
    assert(view->game->player.respawns==respawns);
    assert(view->game->player.x==50.0f);
    assert(view->game->combat.enemy_hp==2u);
    assert(hm_raster_render(framebuffer,W,H,W,view)==1);
    for(i=0u;i<3u;++i)
        assert(framebuffer[18u*W+18u+i*18u]==(i<hp?lit:empty));
    assert(framebuffer[18u*W+226u]==UINT32_C(0xffe1c86d));
    assert(framebuffer[18u*W+244u]==UINT32_C(0xffe1c86d));
    assert(framebuffer[53u*W+125u]==UINT32_C(0xffff00ff));
    assert(framebuffer[62u*W+522u]==recovered);
    assert(framebuffer[302u*W+475u]==UINT32_C(0xffffff00));
    printf("host frame=%u HP=%u respawns=%u hit=%u cooldown=%u\n",
           frame,(unsigned)hp,(unsigned)respawns,
           (unsigned)view->game->combat.player_hits,
           (unsigned)view->game->combat.hurt_cooldown);
}

int main(void) {
    hm_world world;
    hm_combat_config combat;
    hm_session session;
    hm_raster_view view;
    uint32_t frame;
    hm_input idle={0.0f,0u,0u};
    memset(&world,0,sizeof(world));
    memset(&combat,0,sizeof(combat));
    memset(solid,0,sizeof(solid));
    for(frame=0u;frame<NC;++frame)solid[17u*NC+frame]=1u;
    world.solid=solid;world.columns=NC;world.rows=NR;
    world.tile_size=16u;
    world.spawn_x=50.0f;world.spawn_feet_y=272.0f;
    world.actor_half_width=5.0f;world.actor_height=22.0f;
    world.speed=120.0f;world.gravity=1200.0f;
    world.jump_speed=420.0f;world.terminal_speed=1400.0f;
    world.viewport_width=320.0f;world.viewport_height=240.0f;
    world.death_margin=96.0f;
    combat.patrol_left=46.0f;combat.patrol_right=54.0f;
    combat.enemy_start_x=50.0f;combat.enemy_feet_y=272.0f;
    combat.enemy_speed=8.0f;
    combat.sword_reach=30.0f;combat.contact_range=9.0f;
    combat.enemy_initial_hp=2u;combat.player_initial_hp=3u;
    combat.sword_cooldown_frames=15u;
    combat.hurt_cooldown_frames=30u;
    assert(hm_session_init(&world,&combat,&session)==HM_SESSION_OK);
    view.world=&world;view.game=&session;view.combat=&combat;
    view.qa_state=0u;view.qa_fingerprint=0u;
    for(frame=1u;frame<=62u;++frame) {
        assert(hm_session_step(&world,&combat,&session,idle,0u,
                               1.0f/60.0f)==HM_SESSION_OK);
        if(frame==10u||frame==25u||frame==40u||
           frame==61u||frame==62u) {
            uint8_t hp=frame==10u||frame==25u?2u:
                       frame==40u?1u:frame==61u?0u:3u;
            inspect(&view,frame,hp,frame==62u?1u:0u);
            assert(session.combat.player_hits==
                   (frame==10u||frame==25u?1u:
                    frame==40u?2u:frame==61u?3u:0u));
            if(frame==25u)
                assert(session.combat.hurt_cooldown>0u);
            if(frame==62u) {
                assert(session.combat.frame==0u);
                assert(session.combat.hurt_cooldown==0u);
            }
        }
    }
    puts("Native invulnerability and real respawn/HP framebuffer: PASS");
    return 0;
}
