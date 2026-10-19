#include "raster_scene.h"
#include <assert.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#define W HM_RASTER_WIDTH
#define H HM_RASTER_HEIGHT
#define STRIDE (W + 3u)
static struct {
    uint32_t prefix;
    uint32_t image[STRIDE * H];
    uint32_t suffix;
} guarded;
static uint8_t tiles[48u*24u];

static uint32_t checksum(const uint32_t *p) {
    uint32_t h=UINT32_C(2166136261), x, y;
    for (y=0u;y<H;++y)
        for (x=0u;x<W;++x)
            h=(h ^ p[y*STRIDE+x]) * UINT32_C(16777619);
    return h;
}

int main(void) {
    hm_world world;
    hm_combat_config combat;
    hm_session game;
    hm_raster_view view;
    uint32_t first, moved, qa, row;
    hm_input input={1.0f,0u,0u};
    const hm_event events[] = {
        {HM_PICKUP,80.0f,251.0f,8.0f},
        {HM_CHECKPOINT,128.0f,251.0f,8.0f}
    };
    memset(&world,0,sizeof(world));
    memset(&combat,0,sizeof(combat));
    memset(tiles,0,sizeof(tiles));
    for(row=0u;row<48u;++row)tiles[17u*48u+row]=1u;
    world.solid=tiles;
    world.columns=48u;world.rows=24u;world.tile_size=16u;
    world.spawn_x=50.0f;world.spawn_feet_y=272.0f;
    world.actor_half_width=5.0f;world.actor_height=22.0f;
    world.speed=120.0f;world.gravity=1200.0f;
    world.jump_speed=420.0f;world.terminal_speed=1400.0f;
    world.viewport_width=320.0f;world.viewport_height=240.0f;
    world.death_margin=96.0f;
    world.events=events;world.event_count=2u;

    combat.patrol_left=220.0f;combat.patrol_right=355.0f;
    combat.enemy_start_x=290.0f;combat.enemy_feet_y=272.0f;
    combat.enemy_speed=30.0f;combat.sword_reach=30.0f;
    combat.contact_range=8.0f;
    combat.enemy_initial_hp=2u;combat.player_initial_hp=3u;
    combat.sword_cooldown_frames=15u;combat.hurt_cooldown_frames=45u;
    assert(hm_session_init(&world,&combat,&game)==HM_SESSION_OK);

    view.world=&world;view.game=&game;view.combat=&combat;
    view.qa_state=0u;view.qa_fingerprint=0u;
    guarded.prefix=UINT32_C(0x01234567);
    guarded.suffix=UINT32_C(0x89abcdef);
    for(row=0u;row<STRIDE*H;++row)
        guarded.image[row]=UINT32_C(0x5a5a5a5a);
    assert(hm_raster_render(guarded.image,W,H,STRIDE,&view)==1);
    first=checksum(guarded.image);
    assert(first!=0u);
    /* A dedicated magenta tracker is fixed to the player's world x,
       not the independently patrolling enemy or camera. */
    assert(guarded.image[53u*STRIDE+120u]==UINT32_C(0xffff00ff));
    /* The independent cyan world-Y HUD marker starts at feet_y=272. */
    assert(guarded.image[302u*STRIDE+475u]==UINT32_C(0xffffff00));
    game.player.feet_y=220.0f;
    assert(hm_raster_render(guarded.image,W,H,STRIDE,&view)==1);
    assert(guarded.image[250u*STRIDE+475u]==UINT32_C(0xffffff00));
    assert(guarded.image[302u*STRIDE+475u]!=UINT32_C(0xffffff00));
    game.player.feet_y=272.0f;
    assert(hm_raster_render(guarded.image,W,H,STRIDE,&view)==1);
    assert(checksum(guarded.image)==first);
    assert(guarded.image[53u*STRIDE+445u]!=UINT32_C(0xffff00ff));
    assert(guarded.image[0]==UINT32_C(0xff1b2c46));
    assert(guarded.image[(H-1u)*STRIDE+W/2u]!=UINT32_C(0x5a5a5a5a));
    for(row=0u;row<H;++row)
        assert(guarded.image[row*STRIDE+W]==UINT32_C(0x5a5a5a5a));
    assert(guarded.prefix==UINT32_C(0x01234567));
    assert(guarded.suffix==UINT32_C(0x89abcdef));

    assert(hm_raster_render(guarded.image,W,H,STRIDE,&view)==1);
    assert(checksum(guarded.image)==first);

    for(row=0u;row<80u;++row)
        assert(hm_session_step(&world,&combat,&game,input,0u,
                               1.0f/60.0f)==HM_SESSION_OK);
    assert(hm_raster_render(guarded.image,W,H,STRIDE,&view)==1);
    moved=checksum(guarded.image);
    assert(moved!=first);
    assert(guarded.image[53u*STRIDE+120u]!=UINT32_C(0xffff00ff));
    assert(guarded.image[53u*STRIDE+445u]==UINT32_C(0xffff00ff));
    view.qa_state=1u;view.qa_fingerprint=UINT32_C(0x1234abcd);
    assert(hm_raster_render(guarded.image,W,H,STRIDE,&view)==1);
    qa=checksum(guarded.image);
    assert(qa!=moved);

    /* Stage 055: the actual HM_EXIT completion state must reveal a
       source-authored CLEAR indicator without changing game state. */
    assert(guarded.image[47u*STRIDE+547u]!=UINT32_C(0xff216950));
    assert(guarded.image[53u*STRIDE+553u]!=UINT32_C(0xfff0d486));
    game.player.completed=1u;
    assert(hm_raster_render(guarded.image,W,H,STRIDE,&view)==1);
    assert(guarded.image[47u*STRIDE+547u]==UINT32_C(0xff216950));
    assert(guarded.image[53u*STRIDE+553u]==UINT32_C(0xfff0d486));
    assert(checksum(guarded.image)!=qa);
    assert(guarded.prefix==UINT32_C(0x01234567));
    assert(guarded.suffix==UINT32_C(0x89abcdef));
    for(row=0u;row<H;++row)
        assert(guarded.image[row*STRIDE+W]==UINT32_C(0x5a5a5a5a));
    game.player.completed=0u;
    assert(hm_raster_render(guarded.image,W,H,STRIDE,&view)==1);
    assert(checksum(guarded.image)==qa);

    /* Any invalid request leaves the entire pre-existing image unchanged. */
    view.qa_state=3u;
    assert(hm_raster_render(guarded.image,W,H,STRIDE,&view)==0);
    assert(checksum(guarded.image)==qa);
    view.qa_state=1u;
    assert(hm_raster_render(guarded.image,W,H,W-1u,&view)==0);
    assert(checksum(guarded.image)==qa);
    assert(hm_raster_render(guarded.image,W-1u,H,STRIDE,&view)==0);
    assert(checksum(guarded.image)==qa);
    assert(hm_raster_render(NULL,W,H,STRIDE,&view)==0);
    game.player.camera_x = -1.0f;
    assert(hm_raster_render(guarded.image,W,H,STRIDE,&view)==0);
    assert(checksum(guarded.image)==qa);
    game.player.camera_x = 0.0f;
    /* Malformed borrowed events must reject without touching pixels. */
    {
        hm_event invalid[] = {{ HM_PICKUP, NAN, 251.0f, 8.0f }};
        world.events = invalid;
        world.event_count = 1u;
        assert(hm_raster_render(guarded.image,W,H,STRIDE,&view)==0);
        assert(checksum(guarded.image)==qa);
        world.events = events;
        world.event_count = 2u;
    }
    assert(guarded.prefix==UINT32_C(0x01234567));
    assert(guarded.suffix==UINT32_C(0x89abcdef));
    printf("Asset-free raster PASS: initial=%08lx moved=%08lx qa=%08lx\n",
           (unsigned long)first,(unsigned long)moved,(unsigned long)qa);
    return 0;
}
