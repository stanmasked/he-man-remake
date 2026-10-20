/* Pure C99 Stage 088 third synthetic training room, no iOS content. */
#include "heman_synthetic_room3.h"
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#define CANARY UINT32_C(0xbadbed77)
static struct {
    uint32_t before;
    uint8_t cells[HM_ROOM3_CELLS];
    uint32_t after;
} guarded;

static void assert_exact_map(const uint8_t *cells) {
    unsigned x,y;unsigned count=0u;
    for(y=0u;y<HM_ROOM3_ROWS;++y)
        for(x=0u;x<HM_ROOM3_COLUMNS;++x) {
            unsigned solid=(y==18u) ||
                (y==14u&&x>=8u&&x<13u) ||
                (y==12u&&x>=20u&&x<26u) ||
                (y==15u&&x>=35u&&x<41u);
            assert(cells[y*HM_ROOM3_COLUMNS+x]==(uint8_t)solid);
            count+=solid;
        }
    assert(count==HM_ROOM3_COLUMNS+5u+6u+6u);
}
int main(void) {
    hm_world w,before_w,second_world;
    hm_combat_config c,before_c,second_combat;
    hm_state player;
    hm_session game;
    hm_input right={1.0f,0u,0u},idle={0.0f,0u,0u};
    uint8_t before[HM_ROOM3_CELLS],other[HM_ROOM3_CELLS];
    uint32_t tick;
    unsigned pickup=0u,checkpoint=0u,hazard=0u;
    memset(&w,0x3c,sizeof(w));
    memset(&c,0x78,sizeof(c));
    guarded.before=CANARY;guarded.after=CANARY;
    memset(guarded.cells,0xa5,sizeof(guarded.cells));
    before_w=w;before_c=c;
    memcpy(before,guarded.cells,sizeof(before));
    assert(hm_synthetic_room3_init(NULL,&c,guarded.cells,HM_ROOM3_CELLS)==0);
    assert(hm_synthetic_room3_init(&w,NULL,guarded.cells,HM_ROOM3_CELLS)==0);
    assert(hm_synthetic_room3_init(&w,&c,NULL,HM_ROOM3_CELLS)==0);
    assert(hm_synthetic_room3_init(&w,&c,guarded.cells,0u)==0);
    assert(hm_synthetic_room3_init(&w,&c,guarded.cells,HM_ROOM3_CELLS+1u)==0);
    assert(memcmp(&w,&before_w,sizeof(w))==0);
    assert(memcmp(&c,&before_c,sizeof(c))==0);
    assert(memcmp(before,guarded.cells,sizeof(before))==0);
    assert(guarded.before==CANARY && guarded.after==CANARY);
    assert(hm_synthetic_room3_init(&w,&c,guarded.cells,HM_ROOM3_CELLS)==1);
    assert(w.solid==guarded.cells && w.columns==HM_ROOM3_COLUMNS &&
           w.rows==HM_ROOM3_ROWS && w.tile_size==16u);
    assert(w.spawn_x==48.0f && w.spawn_feet_y==288.0f);
    assert(w.event_count==4u);
    assert(w.events[0].kind==HM_PICKUP && w.events[0].x==158.0f);
    assert(w.events[1].kind==HM_CHECKPOINT && w.events[1].x==434.0f);
    assert(w.events[2].kind==HM_HAZARD && w.events[2].x==678.0f);
    assert(w.events[3].kind==HM_EXIT && w.events[3].x==842.0f);
    assert(c.enemy_start_x==316.0f && c.enemy_feet_y==288.0f);
    assert(c.enemy_initial_hp==3u && c.player_initial_hp==3u);
    assert_exact_map(guarded.cells);
    assert(hm_init(&w,&player)==HM_OK);
    assert(hm_session_init(&w,&c,&game)==HM_SESSION_OK);
    assert(game.player.x==w.spawn_x && game.combat.enemy_hp==3u);

    /* Actual physics from spawn must trigger the new room's authored
       pickup, checkpoint, and hazard. This deliberately does not say
       that a human/neXium controller has beaten the entire third room. */
    for(tick=0u;tick<420u;++tick) {
        assert(hm_step(&w,&player,right,1.0f/60.0f)==HM_OK);
        if(player.picked&1u)pickup=1u;
        if(player.checkpoint)checkpoint=1u;
        if(player.hazards){hazard=1u;break;}
    }
    assert(pickup && checkpoint && hazard);
    assert(player.respawns>0u);
    assert(player.checkpoint==1);
    assert(player.x>=410.0f && player.x<=451.0f);

    /* An independent goal-event reachability unit test; starts near
       exit and does NOT count as a full-route completion proof. */
    assert(hm_init(&w,&player)==HM_OK);
    player.x=830.0f;
    player.feet_y=288.0f;
    player.grounded=1u;
    for(tick=0u;tick<15u&&!player.completed;++tick)
        assert(hm_step(&w,&player,right,1.0f/60.0f)==HM_OK);
    assert(player.completed==1u);
    assert(hm_step(&w,&player,idle,1.0f/60.0f)==HM_OK);

    /* No pointer retained to the temporary stack buffer, and repeated
       construction is exact and independent of session progress. */
    memset(other,0xf3,sizeof(other));
    assert(hm_synthetic_room3_init(&second_world,&second_combat,
                                  other,HM_ROOM3_CELLS)==1);
    assert(memcmp(other,guarded.cells,sizeof(other))==0);
    assert(second_world.solid==other);
    assert(second_combat.enemy_start_x==c.enemy_start_x);
    assert(guarded.before==CANARY && guarded.after==CANARY);
    puts("PASS: isolated third-room map, exact native pickup/checkpoint/hazard/goal");
    return 0;
}
