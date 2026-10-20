/* Synthetic native pause regressions, not original iOS game rules. */
#include "heman_pause.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <string.h>

#define COLS 32u
#define ROWS 20u
static uint8_t tiles[COLS*ROWS];

static hm_world world_fixture(void) {
    hm_world w;
    unsigned i;
    memset(&w,0,sizeof(w)); memset(tiles,0,sizeof(tiles));
    for (i=0u;i<COLS;++i) tiles[14u*COLS+i]=1u;
    w.solid=tiles;w.columns=COLS;w.rows=ROWS;w.tile_size=16u;
    w.spawn_x=32.0f;w.spawn_feet_y=224.0f;
    w.actor_half_width=5.0f;w.actor_height=22.0f;
    w.speed=120.0f;w.gravity=1200.0f;w.jump_speed=420.0f;
    w.terminal_speed=1400.0f;w.viewport_width=320.0f;
    w.viewport_height=240.0f;w.death_margin=96.0f;
    return w;
}
static hm_combat_config combat_fixture(void) {
    hm_combat_config c;
    memset(&c,0,sizeof(c));
    c.patrol_left=100.0f;c.patrol_right=180.0f;
    c.enemy_start_x=140.0f;c.enemy_feet_y=224.0f;
    c.enemy_speed=30.0f;c.sword_reach=30.0f;c.contact_range=8.0f;
    c.enemy_initial_hp=2u;c.player_initial_hp=3u;
    c.sword_cooldown_frames=12u;c.hurt_cooldown_frames=30u;
    return c;
}
int main(void) {
    hm_world w=world_fixture();
    hm_combat_config c=combat_fixture();
    hm_session game,saved,reference;
    hm_input move={1.0f,0u,0u};
    uint8_t paused=0u;
    unsigned i;
    assert(hm_session_init(&w,&c,&game)==HM_SESSION_OK);
    reference=game;
    /* The unpaused adapter is byte-identical to native session stepping. */
    for (i=0u;i<25u;++i) {
        assert(hm_paused_session_step(&w,&c,&game,&paused,move,0u,0u,
                                      1.0f/60.0f)==HM_SESSION_OK);
        assert(hm_session_step(&w,&c,&reference,move,0u,1.0f/60.0f)
               ==HM_SESSION_OK);
    }
    assert(memcmp(&game,&reference,sizeof(game))==0);
    assert(paused==0u && game.player.frame==25u);
    /* Minus toggles freeze without consuming a simulated game frame. */
    saved=game;
    assert(hm_paused_session_step(&w,&c,&game,&paused,move,1u,1u,
                                  1.0f/60.0f)==HM_SESSION_OK);
    assert(paused==1u && memcmp(&game,&saved,sizeof(game))==0);
    for (i=0u;i<90u;++i) {
        hm_input attack_and_reset={1.0f,1u,1u};
        assert(hm_paused_session_step(&w,&c,&game,&paused,attack_and_reset,
                                      1u,0u,1.0f/60.0f)==HM_SESSION_OK);
        assert(memcmp(&game,&saved,sizeof(game))==0);
    }
    /* Invalid commands never mutate either paused flag or session. */
    move.axis=NAN;
    assert(hm_paused_session_step(&w,&c,&game,&paused,move,0u,0u,
                                  1.0f/60.0f)==HM_SESSION_PHYSICS_ERROR);
    assert(paused==1u && memcmp(&game,&saved,sizeof(game))==0);
    move.axis=0.0f;
    assert(hm_paused_session_step(&w,&c,&game,&paused,move,0u,0u,
                                  NAN)==HM_SESSION_PHYSICS_ERROR);
    assert(hm_paused_session_step(&w,&c,&game,&paused,move,2u,0u,
                                  1.0f/60.0f)==HM_SESSION_INVALID);
    assert(hm_paused_session_step(&w,&c,&game,&paused,move,0u,2u,
                                  1.0f/60.0f)==HM_SESSION_INVALID);
    assert(paused==1u && memcmp(&game,&saved,sizeof(game))==0);
    /* A resume edge consumes no input, avoids phantom attack/jump/reset. */
    move.axis=1.0f;
    assert(hm_paused_session_step(&w,&c,&game,&paused,move,1u,1u,
                                  1.0f/60.0f)==HM_SESSION_OK);
    assert(paused==0u && memcmp(&game,&saved,sizeof(game))==0);
    assert(hm_paused_session_step(&w,&c,&game,&paused,move,0u,0u,
                                  1.0f/60.0f)==HM_SESSION_OK);
    assert(game.player.frame==26u && game.player.x>saved.player.x);
    /* A corrupt pause flag must be rejected atomically. */
    saved=game;paused=3u;
    assert(hm_paused_session_step(&w,&c,&game,&paused,move,0u,1u,
                                  1.0f/60.0f)==HM_SESSION_INVALID);
    assert(paused==3u && memcmp(&game,&saved,sizeof(game))==0);
    puts("PASS: synthetic pause freezes movement, combat, frames and inputs");
    return 0;
}
