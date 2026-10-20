/* All three stages are original-content-free. No source iOS traces. */
#include "heman_three_room_chain.h"
#include "heman_synthetic_room3.h"
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#define COLS 30u
#define ROWS 20u
static uint8_t simple_cells[COLS*ROWS];
static uint8_t third_cells[HM_ROOM3_CELLS];
static const hm_event simple_exits[]={{HM_EXIT,44.0f,224.0f,7.0f}};

static void make_simple(hm_world *w,hm_combat_config *c) {
    unsigned x;
    memset(w,0,sizeof(*w));memset(c,0,sizeof(*c));
    memset(simple_cells,0,sizeof(simple_cells));
    for(x=0u;x<COLS;++x)simple_cells[14u*COLS+x]=1u;
    w->solid=simple_cells;w->columns=COLS;w->rows=ROWS;
    w->tile_size=16u;w->spawn_x=32.0f;w->spawn_feet_y=224.0f;
    w->actor_half_width=5.0f;w->actor_height=22.0f;
    w->speed=120.0f;w->gravity=1200.0f;w->jump_speed=420.0f;
    w->terminal_speed=1400.0f;w->viewport_width=320.0f;
    w->viewport_height=240.0f;w->death_margin=96.0f;
    w->events=simple_exits;w->event_count=1u;
    c->patrol_left=110.0f;c->patrol_right=150.0f;
    c->enemy_start_x=120.0f;c->enemy_feet_y=224.0f;
    c->enemy_speed=20.0f;c->sword_reach=25.0f;
    c->contact_range=5.0f;c->enemy_initial_hp=2u;
    c->player_initial_hp=3u;c->sword_cooldown_frames=12u;
    c->hurt_cooldown_frames=25u;
}
static void native_clear(hm_world *w,hm_combat_config *c,hm_session *s) {
    hm_input right={1.0f,0u,0u};
    unsigned i;
    for(i=0u;i<30u&&!s->player.completed;++i)
        assert(hm_session_step(w,c,s,right,0u,1.0f/60.0f)==HM_SESSION_OK);
    assert(s->player.completed==1u);
}
int main(void) {
    hm_world tiny,third,bad;
    hm_combat_config c,third_c;
    hm_session game,old;
    uint8_t stage=0u;
    make_simple(&tiny,&c);
    assert(hm_synthetic_room3_init(&third,&third_c,
                                  third_cells,HM_ROOM3_CELLS)==1);
    assert(hm_session_init(&tiny,&c,&game)==HM_SESSION_OK);
    assert(!hm_three_room_continue_allowed(&game,stage,0u,0u,1u));
    old=game;
    assert(hm_three_room_try_advance(&tiny,&c,&game,&stage,1u)
           ==HM_CHAIN_NOT_READY);
    assert(stage==0u&&memcmp(&game,&old,sizeof(game))==0);
    native_clear(&tiny,&c,&game);
    assert(hm_three_room_continue_allowed(&game,stage,0u,0u,1u));
    assert(!hm_three_room_continue_allowed(&game,stage,0u,1u,1u));
    assert(!hm_three_room_continue_allowed(&game,stage,1u,0u,1u));
    assert(!hm_three_room_continue_allowed(&game,stage,0u,0u,0u));
    old=game;bad=tiny;bad.columns=0u;
    assert(hm_three_room_try_advance(&bad,&c,&game,&stage,1u)
           ==HM_CHAIN_SETUP_ERROR);
    assert(stage==0u&&memcmp(&game,&old,sizeof(game))==0);
    assert(hm_three_room_try_advance(&tiny,&c,&game,&stage,2u)
           ==HM_CHAIN_INVALID);
    assert(stage==0u&&memcmp(&game,&old,sizeof(game))==0);
    assert(hm_three_room_try_advance(&tiny,&c,&game,&stage,1u)
           ==HM_CHAIN_ADVANCED);
    assert(stage==1u&&game.player.frame==0u&&!game.player.completed);
    assert(!hm_three_room_continue_allowed(&game,stage,0u,0u,1u));
    native_clear(&tiny,&c,&game);
    assert(hm_three_room_continue_allowed(&game,stage,0u,0u,1u));
    old=game;bad=third;bad.rows=0u;
    assert(hm_three_room_try_advance(&bad,&third_c,&game,&stage,1u)
           ==HM_CHAIN_SETUP_ERROR);
    assert(stage==1u&&memcmp(&game,&old,sizeof(game))==0);
    assert(hm_three_room_try_advance(&third,&third_c,&game,&stage,1u)
           ==HM_CHAIN_ADVANCED);
    assert(stage==2u && game.player.frame==0u);
    assert(game.player.x==third.spawn_x);
    assert(game.combat.enemy_hp==third_c.enemy_initial_hp);
    assert(!hm_three_room_continue_allowed(&game,stage,0u,0u,1u));
    old=game;
    assert(hm_three_room_try_advance(&third,&third_c,&game,&stage,1u)
           ==HM_CHAIN_NOT_READY);
    assert(stage==2u&&memcmp(&game,&old,sizeof(game))==0);
    stage=3u;
    assert(hm_three_room_try_advance(&third,&third_c,&game,&stage,1u)
           ==HM_CHAIN_INVALID);
    assert(stage==3u&&memcmp(&game,&old,sizeof(game))==0);
    puts("PASS: 0->1->2 three-room real C99 CLEAR/A transitions, rollback");
    return 0;
}
