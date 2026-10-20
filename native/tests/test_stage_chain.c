/* Portable two-level synthetic course regression, not original iOS levels. */
#include "heman_stage_chain.h"
#include "heman_synthetic_room2.h"
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#define COLS 32u
#define ROWS 20u
static uint8_t solid_first[COLS*ROWS], solid_second[COLS*ROWS];
static const hm_event exit_first[]={{HM_EXIT, 50.0f, 224.0f, 9.0f}};
static const hm_event exit_second[]={{HM_EXIT, 190.0f, 240.0f, 8.0f}};

static hm_world world_fixture(unsigned which) {
    hm_world w;
    uint8_t *solid = which ? solid_second : solid_first;
    unsigned x, floor_row=which?15u:14u;
    memset(&w,0,sizeof(w));
    memset(solid,0,COLS*ROWS);
    for(x=0u;x<COLS;++x)solid[floor_row*COLS+x]=1u;
    w.solid=solid;w.columns=COLS;w.rows=ROWS;w.tile_size=16u;
    w.spawn_x=which?64.0f:32.0f;
    w.spawn_feet_y=which?240.0f:224.0f;
    w.actor_half_width=5.0f;w.actor_height=22.0f;
    w.speed=120.0f;w.gravity=1200.0f;w.jump_speed=420.0f;
    w.terminal_speed=1400.0f;
    w.viewport_width=320.0f;w.viewport_height=240.0f;
    w.death_margin=96.0f;
    w.events=which?exit_second:exit_first;
    w.event_count=1u;
    return w;
}
static hm_combat_config combat_fixture(unsigned which) {
    hm_combat_config c;
    memset(&c,0,sizeof(c));
    c.patrol_left=which?140.0f:100.0f;
    c.patrol_right=which?200.0f:180.0f;
    c.enemy_start_x=which?170.0f:140.0f;
    c.enemy_feet_y=which?240.0f:224.0f;
    c.enemy_speed=30.0f;c.sword_reach=30.0f;
    c.contact_range=8.0f;c.enemy_initial_hp=2u;
    c.player_initial_hp=3u;c.sword_cooldown_frames=12u;
    c.hurt_cooldown_frames=30u;
    return c;
}
int main(void) {
    hm_world first=world_fixture(0), second, bad;
    hm_combat_config combat_first=combat_fixture(0), combat_second;
    hm_session game,snapshot;
    uint8_t room2_tiles[HM_ROOM2_CELLS];
    hm_input right={1.0f,0u,0u};
    uint8_t stage=0u;
    unsigned i;
    assert(hm_synthetic_room2_init(&second,&combat_second,
                                   room2_tiles,HM_ROOM2_CELLS)==1);
    assert(hm_session_init(&first,&combat_first,&game)==HM_SESSION_OK);
    snapshot=game;
    /* Explicit C99 input policy: Minus wins over simultaneous A, and a
       paused or non-CLEAR room must not transition on A alone. */
    assert(!hm_chain_continue_edge_allowed(&game,stage,0u,0u,1u));
    assert(!hm_chain_continue_edge_allowed(&game,stage,0u,1u,1u));
    assert(!hm_chain_continue_edge_allowed(&game,stage,1u,0u,1u));
    assert(!hm_chain_continue_edge_allowed(NULL,stage,0u,0u,1u));
    /* A before clearing cannot skip the first room. */
    assert(hm_chain_try_advance(&second,&combat_second,&game,&stage,1u)
           ==HM_CHAIN_NOT_READY);
    assert(stage==0u && memcmp(&game,&snapshot,sizeof(game))==0);
    /* Earn the first original C99 HM_EXIT event through real movement. */
    for (i=0u;i<30u && !game.player.completed;++i)
        assert(hm_session_step(&first,&combat_first,&game,right,0u,
                               1.0f/60.0f)==HM_SESSION_OK);
    assert(game.player.completed==1u);
    assert(game.player.frame>0u);
    assert(hm_chain_continue_edge_allowed(&game,stage,0u,0u,1u));
    assert(!hm_chain_continue_edge_allowed(&game,stage,0u,1u,1u));
    assert(!hm_chain_continue_edge_allowed(&game,stage,1u,0u,1u));
    assert(!hm_chain_continue_edge_allowed(&game,stage,0u,0u,0u));
    assert(!hm_chain_continue_edge_allowed(&game,1u,0u,0u,1u));
    assert(!hm_chain_continue_edge_allowed(&game,2u,0u,0u,1u));
    assert(!hm_chain_continue_edge_allowed(&game,stage,2u,0u,1u));
    snapshot=game;
    assert(hm_chain_try_advance(&second,&combat_second,&game,&stage,0u)
           ==HM_CHAIN_NOT_READY);
    assert(stage==0u && memcmp(&game,&snapshot,sizeof(game))==0);
    /* Invalid target cannot consume completed progress, frame or HP. */
    bad=second;bad.columns=0u;
    assert(hm_chain_try_advance(&bad,&combat_second,&game,&stage,1u)
           ==HM_CHAIN_SETUP_ERROR);
    assert(stage==0u && memcmp(&game,&snapshot,sizeof(game))==0);
    assert(hm_chain_try_advance(&second,&combat_second,&game,&stage,2u)
           ==HM_CHAIN_INVALID);
    assert(stage==0u && memcmp(&game,&snapshot,sizeof(game))==0);
    /* Reset all session, enemy and camera state atomically at room 2. */
    game.combat.player_hp=1u;
    game.combat.enemy_hp=1u;
    assert(hm_chain_try_advance(&second,&combat_second,&game,&stage,1u)
           ==HM_CHAIN_ADVANCED);
    assert(stage==1u && game.player.x==second.spawn_x);
    assert(game.player.feet_y==second.spawn_feet_y);
    assert(game.player.frame==0u && game.player.completed==0u);
    assert(game.player.respawns==0u && game.player.checkpoint==-1);
    assert(game.combat.player_hp==combat_second.player_initial_hp);
    assert(game.combat.enemy_hp==combat_second.enemy_initial_hp);
    snapshot=game;
    /* Stage 2 is terminal. A never loops back or silently restarts. */
    assert(hm_chain_try_advance(&second,&combat_second,&game,&stage,1u)
           ==HM_CHAIN_NOT_READY);
    assert(memcmp(&game,&snapshot,sizeof(game))==0 && stage==1u);
    assert(hm_chain_try_advance(NULL,&combat_second,&game,&stage,1u)
           ==HM_CHAIN_INVALID);
    assert(memcmp(&game,&snapshot,sizeof(game))==0);
    stage=3u;
    assert(hm_chain_try_advance(&second,&combat_second,&game,&stage,1u)
           ==HM_CHAIN_INVALID);
    assert(stage==3u && memcmp(&game,&snapshot,sizeof(game))==0);
    puts("PASS: two-room synthetic CLEAR + A transition and atomic rollback");
    return 0;
}
