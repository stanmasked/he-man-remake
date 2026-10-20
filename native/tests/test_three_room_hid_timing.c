/* Stage 091 schedule preflight: real C99 state at the exact HID guest frames.
 * This executes source gameplay from real spawns, with no forced CLEAR,
 * patched map, teleport, privileged guest RAM, or simulated screenshots.
 * Host fixed-step agreement is necessary, never sufficient, for NeXium.
 */
#include "heman_three_room_chain.h"
#include "heman_synthetic_room2.h"
#include "heman_synthetic_room3.h"
#include "heman_air_smash.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

#define W 48u
#define H 24u
#define FPS_DT (1.0f / 60.0f)
#define R 1u
#define A 2u
#define B 4u
static uint8_t first_cells[W*H],second_cells[HM_ROOM2_CELLS];
static uint8_t third_cells[HM_ROOM3_CELLS];
static const hm_event first_exit[] = {{HM_EXIT,90.0f,272.0f,8.0f}};

static hm_world first_world(void) {
    hm_world w;
    unsigned x;
    memset(&w,0,sizeof(w));
    memset(first_cells,0,sizeof(first_cells));
    for(x=0u;x<W;++x)first_cells[17u*W+x]=1u;
    for(x=15u;x<18u;++x)first_cells[15u*W+x]=1u;
    w.solid=first_cells;w.columns=W;w.rows=H;w.tile_size=16u;
    w.spawn_x=50.0f;w.spawn_feet_y=272.0f;
    w.actor_half_width=5.0f;w.actor_height=22.0f;
    w.speed=120.0f;w.gravity=1200.0f;w.jump_speed=420.0f;
    w.terminal_speed=1400.0f;w.viewport_width=320.0f;
    w.viewport_height=240.0f;w.death_margin=96.0f;
    w.events=first_exit;w.event_count=1u;
    return w;
}
static hm_combat_config first_combat(void) {
    hm_combat_config c;
    memset(&c,0,sizeof(c));
    c.patrol_left=220.0f;c.patrol_right=355.0f;
    c.enemy_start_x=290.0f;c.enemy_feet_y=272.0f;
    c.enemy_speed=38.0f;c.sword_reach=30.0f;
    c.contact_range=9.0f;c.enemy_initial_hp=2u;
    c.player_initial_hp=3u;c.sword_cooldown_frames=15u;
    c.hurt_cooldown_frames=45u;
    return c;
}

/* Preserve every press/release from the real experimental NeXium schedule.
   Frames are receiver ordinal numbers, not wall-clock millisecond guesses.
   Subsequent guest-versus-host comparisons may reveal one-frame offset. */
static unsigned buttons_at(unsigned f, unsigned old) {
    switch(f) {
        case 45u:case 110u:case 530u:case 960u: return R;
        case 78u:case 95u:case 500u:case 515u:
        case 1080u:case 1143u: return 0u;
        case 90u:case 510u:case 1140u: return
            f==1140u?B:A;
        case 350u:case 952u:return R|A;
        case 353u:case 955u:return R;
        default:return old;
    }
}
static void failure(unsigned f,const hm_session *s,unsigned stage,
                    const char *why) {
    fprintf(stderr,"Stage091 HID contract FAIL frame=%u stage=%u "
        "x=%.2f feet=%.2f cleared=%u hazards=%u respawns=%u hp=%u: %s\n",
        f,stage,s->player.x,s->player.feet_y,s->player.completed,
        s->player.hazards,s->player.respawns,s->combat.player_hp,why);
}
int main(void) {
    hm_world world=first_world(),w2,w3;
    hm_combat_config combat=first_combat(),c2,c3;
    hm_session game,final_copy;
    hm_dash_state dash={0u,0u},dash_copy;
    hm_air_smash_state smash={0},smash_copy;
    unsigned held=0u, stage=0u,frame;
    uint8_t paused=0u;
    unsigned transitions=0u, max_stage3_hazards=0u;
    unsigned jumped=0u, completed_frame=0u;
    float y945=0.0f;
    assert(hm_synthetic_room2_init(&w2,&c2,second_cells,
               HM_ROOM2_CELLS)==1);
    assert(hm_synthetic_room3_init(&w3,&c3,third_cells,
               HM_ROOM3_CELLS)==1);
    assert(hm_session_init(&world,&combat,&game)==HM_SESSION_OK);
    for(frame=1u;frame<=1190u;++frame) {
        const unsigned before=held;
        const unsigned now=buttons_at(frame,before);\n        unsigned down;
        hm_session_result result;
        hm_input input;
        held=now;
        down=now & ~before;
        input.axis=(held&R)?1.0f:0.0f;
        input.jump=(uint8_t)((down&A)!=0u);
        input.reset=(uint8_t)((down&B)!=0u);
        if(hm_three_room_continue_allowed(
              &game,(uint8_t)stage,paused,0u,input.jump)) {
            const hm_world *next=stage==0u?&w2:&w3;
            const hm_combat_config *next_c=stage==0u?&c2:&c3;
            uint8_t next_stage=(uint8_t)stage;
            if(hm_three_room_try_advance(next,next_c,&game,&next_stage,1u)
                  !=HM_CHAIN_ADVANCED) {
                failure(frame,&game,stage,"native A transition rejected");
                return 1;
            }
            stage=next_stage;
            world=*next; combat=*next_c;
            dash=(hm_dash_state){0};
            smash=(hm_air_smash_state){0};
            ++transitions;
            continue;
        }
        if(stage==0u)
            result=hm_paused_session_step(&world,&combat,&game,&paused,
                        input,0u,0u,FPS_DT);
        else if(stage==1u)
            result=hm_dash_session_step(&world,&combat,&game,&paused,&dash,
                        input,0u,0u,0u,FPS_DT);
        else
            result=hm_air_smash_step(&world,&combat,&game,&paused,&dash,
                        &smash,1u,input,0u,0u,0u,0u,FPS_DT);
        if(result!=HM_SESSION_OK) {
            failure(frame,&game,stage,"C99 frame rejected");
            return 2;
        }
        if(stage==2u && game.player.hazards>max_stage3_hazards)
            max_stage3_hazards=game.player.hazards;
        if(stage==2u && game.player.completed && !completed_frame)
            completed_frame=frame;
        if(frame==75u && (stage!=0u || !game.player.completed)) {
            failure(frame,&game,stage,"stage1 real CLEAR not reached");
            return 3;
        }
        if(frame==105u && (stage!=1u || game.player.completed)) {
            failure(frame,&game,stage,"stage1 A transition failed");
            return 4;
        }
        if(frame==465u && (stage!=1u || !game.player.completed)) {
            failure(frame,&game,stage,"stage2 real CLEAR not reached");
            return 5;
        }
        if(frame==535u && (stage!=2u || game.player.completed)) {
            failure(frame,&game,stage,"stage2 A transition to stage3 failed");
            return 6;
        }
        if(frame==820u && (stage!=2u || game.player.hazards!=0u)) {
            failure(frame,&game,stage,"third hazard occurred too early");
            return 7;
        }
        if(frame==850u && (stage!=2u || game.player.hazards!=1u)) {
            failure(frame,&game,stage,"third room first hazard/respawn missing");
            return 8;
        }
        if(frame==945u)y945=game.player.feet_y;
        if(frame==970u) {
            if(!(game.player.feet_y<y945-25.0f &&
                 game.player.hazards==1u))
            {
                failure(frame,&game,stage,"third-room A jump did not clear hazard");
                return 9;
            }
            jumped=1u;
        }
        if(frame==1045u && (stage!=2u || !game.player.completed)) {
            failure(frame,&game,stage,"final native HM_EXIT not yet reached");
            return 10;
        }
        if(frame==1080u) {
            final_copy=game;dash_copy=dash;smash_copy=smash;
        }
        if(frame==1120u &&
           (memcmp(&game,&final_copy,sizeof(game))!=0 ||
            memcmp(&dash,&dash_copy,sizeof(dash))!=0 ||
            memcmp(&smash,&smash_copy,sizeof(smash))!=0)) {
            failure(frame,&game,stage,"third FINISH gameplay did not freeze");
            return 11;
        }
        if(frame==1140u && (stage!=2u || game.player.completed ||
            game.player.x!=w3.spawn_x || game.player.hazards!=0u ||
            game.combat.player_hp!=c3.player_initial_hp)) {
            failure(frame,&game,stage,"native B did not restart third room");
            return 12;
        }
        if(frame==1190u && (stage!=2u || game.player.completed ||
            game.player.x!=w3.spawn_x || game.player.hazards!=0u)) {
            failure(frame,&game,stage,"stage3 moved after B with input released");
            return 13;
        }
    }
    if(transitions!=2u || !jumped || max_stage3_hazards!=1u ||
       !completed_frame) {
        failure(frame,&game,stage,"missing two transitions or earned finale");
        return 14;
    }
    printf("PASS: stage091 actual C99 guest HID schedule 1->2->3, "
           "single hazard, A jump, earned CLEAR frame=%u, "
           "frozen FINISH and native B replay\n",completed_frame);
    return 0;
}
