/* Stage 068: test the precise stage-2 tile/event/combat data used by Switch.
   Every asset is created in source code, never extracted from iOS. */
#include "heman_synthetic_room2.h"
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#define CANARY UINT32_C(0xdac1cade)
static struct {
    uint32_t before;
    uint8_t tiles[HM_ROOM2_CELLS];
    uint32_t after;
} guarded;

static void init_with_canaries(hm_world *world, hm_combat_config *combat) {
    guarded.before=CANARY;
    guarded.after=CANARY;
    memset(guarded.tiles,0x5a,sizeof(guarded.tiles));
    assert(hm_synthetic_room2_init(world,combat,guarded.tiles,
                                  HM_ROOM2_CELLS)==1);
    assert(guarded.before==CANARY && guarded.after==CANARY);
}
static void assert_cells_exact(const hm_world *world) {
    uint32_t row,col,n=0u;
    for(row=0u;row<HM_ROOM2_ROWS;++row)
        for(col=0u;col<HM_ROOM2_COLUMNS;++col) {
            uint8_t expected=(uint8_t)(
                row==18u || (row==13u && col>=9u && col<13u) ||
                (row==15u && col>=23u && col<28u));
            assert(world->solid[row*HM_ROOM2_COLUMNS+col]==expected);
            n+=(uint32_t)expected;
        }
    assert(n==HM_ROOM2_COLUMNS+4u+5u);
}
int main(void) {
    hm_world world,before_world,second;
    hm_combat_config combat,before_combat,second_combat;
    hm_state player;
    hm_session game;
    hm_input right={1.0f,0u,0u},idle={0.0f,0u,0u};
    uint8_t snapshot[HM_ROOM2_CELLS],other[HM_ROOM2_CELLS];
    unsigned frame;
    int pickup=0,checkpoint=0,hazard=0;

    memset(&world,0x37,sizeof(world));
    memset(&combat,0x42,sizeof(combat));
    guarded.before=CANARY;
    guarded.after=CANARY;
    memset(guarded.tiles,0x5a,sizeof(guarded.tiles));
    before_world=world;before_combat=combat;
    memcpy(snapshot,guarded.tiles,sizeof(snapshot));
    assert(!hm_synthetic_room2_init(NULL,&combat,guarded.tiles,
                                    HM_ROOM2_CELLS));
    assert(!hm_synthetic_room2_init(&world,NULL,guarded.tiles,
                                    HM_ROOM2_CELLS));
    assert(!hm_synthetic_room2_init(&world,&combat,NULL,HM_ROOM2_CELLS));
    assert(!hm_synthetic_room2_init(&world,&combat,guarded.tiles,0u));
    assert(!hm_synthetic_room2_init(&world,&combat,guarded.tiles,
                                    HM_ROOM2_CELLS+1u));
    assert(memcmp(&world,&before_world,sizeof(world))==0);
    assert(memcmp(&combat,&before_combat,sizeof(combat))==0);
    assert(memcmp(guarded.tiles,snapshot,sizeof(snapshot))==0);
    assert(guarded.before==CANARY && guarded.after==CANARY);

    init_with_canaries(&world,&combat);
    assert(world.solid==guarded.tiles);
    assert(world.columns==48u && world.rows==24u && world.tile_size==16u);
    assert(world.spawn_x==48.0f && world.spawn_feet_y==288.0f);
    assert(world.speed==120.0f && world.jump_speed==420.0f);
    assert(world.event_count==4u);
    assert(world.events[0].kind==HM_PICKUP && world.events[0].x==170.0f);
    assert(world.events[1].kind==HM_CHECKPOINT && world.events[1].x==330.0f);
    assert(world.events[2].kind==HM_HAZARD && world.events[2].x==570.0f);
    assert(world.events[3].kind==HM_EXIT && world.events[3].x==735.0f);
    assert(combat.enemy_start_x==275.0f && combat.enemy_feet_y==288.0f);
    assert(combat.patrol_left==230.0f && combat.patrol_right==320.0f);
    assert(combat.enemy_initial_hp==2u && combat.player_initial_hp==3u);
    assert(combat.enemy_speed==38.0f && combat.sword_reach==30.0f);
    assert(combat.sword_cooldown_frames==15u);
    assert(combat.hurt_cooldown_frames==45u);
    assert_cells_exact(&world);

    assert(hm_init(&world,&player)==HM_OK);
    assert(hm_session_init(&world,&combat,&game)==HM_SESSION_OK);
    assert(game.player.x==world.spawn_x && game.combat.enemy_hp==2u);
    /* The actual native physics must physically reach the same fixture's
       pickup/checkpoint/hazard; these are not inferred from event names. */
    for(frame=0u;frame<400u;++frame) {
        assert(hm_step(&world,&player,right,1.0f/60.0f)==HM_OK);
        if(player.picked & 1u)pickup=1;
        if(player.checkpoint==1)checkpoint=1;
        if(player.hazards>0u){hazard=1;break;}
    }
    assert(pickup && checkpoint && hazard);
    assert(player.respawns>0u);
    assert(player.hazards==1u);
    assert(player.checkpoint==1);
    assert(player.x>=300.0f && player.x<=345.0f);
    /* The real final CLEAR event is also reachable with native movement.
       Position the player near that goal to avoid requiring an artificial
       controller solution for the intermediate hazard in a host unit. */
    assert(hm_init(&world,&player)==HM_OK);
    player.x=725.0f;
    player.feet_y=288.0f;
    player.grounded=1u;
    for(frame=0u;frame<12u && !player.completed;++frame)
        assert(hm_step(&world,&player,right,1.0f/60.0f)==HM_OK);
    assert(player.completed==1u);
    assert(hm_step(&world,&player,idle,1.0f/60.0f)==HM_OK);

    /* Re-running the builder is deterministic and unrelated to current
       gameplay progress or the visible stage-1 world pointer. */
    memset(other,0xff,sizeof(other));
    assert(hm_synthetic_room2_init(&second,&second_combat,
                                   other,HM_ROOM2_CELLS)==1);
    assert(memcmp(other,guarded.tiles,sizeof(other))==0);
    assert(second.solid==other && second_combat.enemy_start_x==combat.enemy_start_x);
    assert(guarded.before==CANARY && guarded.after==CANARY);
    puts("PASS: exact Switch room-2 geometry, native pickup/checkpoint/hazard/exit");
    return 0;
}
