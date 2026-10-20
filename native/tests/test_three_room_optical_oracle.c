/* Stage 091 schedule preflight: real C99 state at the exact HID guest frames.
 * This executes source gameplay from real spawns, with no forced CLEAR,
 * patched map, teleport, privileged guest RAM, or simulated screenshots.
 * Host fixed-step agreement is necessary, never sufficient, for NeXium.
 */
#include "heman_three_room_chain.h"
#include "heman_synthetic_room2.h"
#include "heman_synthetic_room3.h"
#include "heman_air_smash.h"
#include "raster_scene.h"
#include "third_room_marker.h"
#include "dash_hud.h"
#include "finale_overlay.h"
#include "air_smash_hud.h"
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
/* Source C99 raster/HUD oracle for the same 18 NeXium capture frames.
 * These pixels are rendered on the HOST, not screenshots from NeXium.
 * CI may claim source-to-verifier pixel-contract compatibility only.
 */
#define RW 640u
#define RH 360u
#define PIXEL(x,y) raster[(unsigned)(y)*RW+(unsigned)(x)]
static uint32_t raster[RW*RH];
static uint32_t frozen_raster[RW*RH];
static int have_frozen=0;
static const unsigned sample_frames[]={
    75u,105u,330u,365u,465u,505u,535u,650u,820u,
    850u,930u,945u,970u,1045u,1080u,1120u,1170u,1190u
};
static int contains(const unsigned *v,unsigned n,unsigned f) {
    unsigned i;
    for(i=0u;i<n;++i)if(v[i]==f)return 1;
    return 0;
}
static int oracle(unsigned f,const hm_world *w,
                  const hm_combat_config *c, const hm_session *g,
                  unsigned stage,const hm_dash_state *dash,
                  const hm_air_smash_state *smash) {
    static const char *const digits[]={
       "010110010010111",
       "111001111100111",
       "111001111001111"
    };
    static const unsigned clear_f[]={
        75u,465u,505u,1045u,1080u,1120u
    };
    static const unsigned finish_f[]={1045u,1080u,1120u};
    hm_raster_view view;
    unsigned i,magenta=0u,cyan=0u;
    int expected_clear,expected_finish,expected_respawn;
    if(!contains(sample_frames,sizeof(sample_frames)/sizeof(sample_frames[0]),f))
        return 1;
    memset(&view,0,sizeof(view));
    view.world=w;view.combat=c;view.game=g;
    if(!hm_raster_render(raster,RW,RH,RW,&view) ||
       !hm_three_room_marker(raster,RW,RH,RW,(uint8_t)stage) ||
       (stage>=1u && !hm_dash_hud(raster,RW,RH,RW,dash)) ||
       (stage==2u &&
           !hm_finale_overlay(raster,RW,RH,RW,1u,
                               (uint8_t)(g->player.completed!=0u),0u)) ||
       (stage==2u && !hm_air_smash_hud(raster,RW,RH,RW,smash))) {
        fprintf(stderr,"Stage093 raster call failed at frame=%u\n",f);
        return 0;
    }
    if(PIXEL(393u,4u)!=UINT32_C(0xffe1c86d) ||
       PIXEL(398u,8u)!=UINT32_C(0xff354967)) {
        fprintf(stderr,"Stage093 missing stage border at %u\n",f);
        return 0;
    }
    for(i=0u;i<15u;++i) {
        unsigned x=405u+(i%3u)*4u,y=10u+(i/3u)*4u;
        const uint32_t want=digits[stage][i]=='1' ?
               UINT32_C(0xfff1e6bf):UINT32_C(0xff354967);
        if(PIXEL(x,y)!=want) {
            fprintf(stderr,"Stage093 stage digit wrong frame=%u bit=%u\n",f,i);
            return 0;
        }
    }
    expected_clear=contains(clear_f,sizeof(clear_f)/sizeof(clear_f[0]),f);
    if((PIXEL(547u,47u)==UINT32_C(0xff216950))!=expected_clear ||
       (PIXEL(553u,53u)==UINT32_C(0xfff0d486))!=expected_clear) {
        fprintf(stderr,"Stage093 CLEAR color mismatch at %u\n",f);
        return 0;
    }
    expected_finish=contains(finish_f,sizeof(finish_f)/sizeof(finish_f[0]),f);
    if((PIXEL(208u,120u)==UINT32_C(0xffe1c86d))!=expected_finish ||
       (PIXEL(258u,155u)==UINT32_C(0xfff1e6bf))!=expected_finish ||
       (PIXEL(254u,201u)==UINT32_C(0xff42d58a))!=expected_finish ||
       (PIXEL(311u,210u)==UINT32_C(0xff42d58a))!=expected_finish ||
       (PIXEL(315u,213u)==UINT32_C(0xfff1e6bf))!=expected_finish ||
       (PIXEL(322u,218u)==UINT32_C(0xfff1e6bf))!=expected_finish) {
        fprintf(stderr,"Stage093 FINISH or B-prompt wrong at %u\n",f);
        return 0;
    }
    expected_respawn=f>=850u&&f<=1120u;
    if((PIXEL(522u,62u)==UINT32_C(0xff42d58a))!=expected_respawn) {
        fprintf(stderr,"Stage093 respawn HUD wrong at %u\n",f);
        return 0;
    }
    for(i=10u;i<467u;++i) {
        unsigned y;
        for(y=44u;y<68u;++y)
            if(PIXEL(i,y)==UINT32_C(0xffff00ff))++magenta;
    }
    if(magenta!=192u) {
        fprintf(stderr,"Stage093 world-X magenta marker=%u at %u\n",magenta,f);
        return 0;
    }
    for(i=80u;i<340u;++i)
        if(PIXEL(476u,i)==UINT32_C(0xffffff00))++cyan;
    if(cyan!=9u) {
        fprintf(stderr,"Stage093 world-Y cyan marker=%u at %u\n",cyan,f);
        return 0;
    }
    if(f==1080u) {
        memcpy(frozen_raster,raster,sizeof(raster));
        have_frozen=1;
    }
    if(f==1120u &&
       (!have_frozen||memcmp(raster,frozen_raster,sizeof(raster))!=0)) {
        fprintf(stderr,"Stage093 native FINISH raster was not frozen\n");
        return 0;
    }
    printf("Stage093 optical oracle: frame=%u stage=%u CLEAR=%d FINISH=%d "
           "respawn=%d x=%.2f foot=%.2f (host C99, not guest)\n",
           f,stage,expected_clear,expected_finish,expected_respawn,
           g->player.x,g->player.feet_y);
    return 1;
}

static unsigned buttons_at(unsigned f, unsigned old) {
    switch(f) {
        case 45u:case 110u:case 530u: return R;
        case 78u:case 95u:case 470u:case 515u:
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
        const unsigned now=buttons_at(frame,before);
        unsigned down;
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
        if(!oracle(frame,&world,&combat,&game,stage,&dash,&smash))return 15;
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
