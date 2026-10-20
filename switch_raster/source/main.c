/* Asset-free graphical Nintendo Switch proof-of-concept.
   This is NOT the original iOS He-Man game or its character art. */
#include <switch.h>
#include <stdint.h>
#include <string.h>
#include "heman_core.h"
#include "heman_combat.h"
#include "heman_session.h"
#include "heman_pause.h"
#ifdef HM_LEVEL_CHAIN_PROBE
#include "heman_stage_chain.h"
#include "heman_synthetic_room2.h"
#include "heman_dash.h"
#include "heman_finale.h"
#ifdef HM_AIR_SMASH_PROBE
#include "heman_air_smash.h"
#include "air_smash_hud.h"
#endif
#include "dash_hud.h"
#include "stage_marker.h"
#include "finale_overlay.h"
#ifdef HM_THREE_ROOM_PROBE
#include "heman_three_room_chain.h"
#include "heman_synthetic_room3.h"
#include "third_room_marker.h"
#endif
#endif
#include "pause_overlay.h"
#include "probe_selfcheck.h"
#include "session_selftest.h"
#include "runtime_replay.h"
#include "raster_scene.h"

#define W 48u
#define H 24u
static uint8_t cells[W*H];
/* Opt-in test-only checkpoint near initial spawn for real NeXium HID
   travel and native B-button respawn. All gameplay rules are unchanged. */
#if defined(HM_EXIT_PROBE) || defined(HM_LEVEL_CHAIN_PROBE)
/* Test-only native exit within D-pad travel from spawn x=50.
   Unmodified world event processing drives player.completed. */
static const hm_event events[] = {
    {HM_EXIT,90.0f,272.0f,8.0f}
};
#elif defined(HM_CHECKPOINT_PROBE)
static const hm_event events[] = {
    {HM_CHECKPOINT,90.0f,272.0f,8.0f},
    {HM_HAZARD,210.0f,262.0f,8.0f}
};
#else
static const hm_event events[] = {
    {HM_PICKUP,170.0f,251.0f,8.0f},
    {HM_CHECKPOINT,340.0f,257.0f,8.0f},
    {HM_HAZARD,585.0f,257.0f,8.0f},
    {HM_EXIT,728.0f,257.0f,8.0f}
};
#endif

static hm_world make_world(void) {
    hm_world w;
    uint32_t x;
    memset(&w,0,sizeof(w));
    memset(cells,0,sizeof(cells));
    for(x=0u;x<W;++x)cells[17u*W+x]=1u;
    for(x=15u;x<18u;++x)cells[15u*W+x]=1u;
    w.solid=cells;
    w.columns=W;w.rows=H;w.tile_size=16u;
    w.spawn_x=50.0f;w.spawn_feet_y=272.0f;
    w.actor_half_width=5.0f;w.actor_height=22.0f;
    w.speed=120.0f;w.gravity=1200.0f;w.jump_speed=420.0f;
    w.terminal_speed=1400.0f;
    w.viewport_width=320.0f;w.viewport_height=240.0f;
    w.death_margin=96.0f;
    w.events=events;
    w.event_count=(uint32_t)(sizeof(events)/sizeof(events[0]));
    return w;
}

#ifdef HM_LEVEL_CHAIN_PROBE
/* The exact room-2 tiles/events/combat now come from the shared C99
   fixture, which is exercised directly by host CI before NeXium. */
static uint8_t second_cells[HM_ROOM2_CELLS];
#ifdef HM_THREE_ROOM_PROBE
static uint8_t third_cells[HM_ROOM3_CELLS];
#endif
#endif

static hm_combat_config make_combat(void) {
    hm_combat_config c;
    memset(&c,0,sizeof(c));
    c.patrol_left=220.0f;c.patrol_right=355.0f;
    c.enemy_start_x=290.0f;c.enemy_feet_y=272.0f;
    c.enemy_speed=38.0f;c.sword_reach=30.0f;
    c.contact_range=9.0f;c.enemy_initial_hp=2u;
    c.player_initial_hp=3u;c.sword_cooldown_frames=15u;
    c.hurt_cooldown_frames=45u;
#ifdef HM_ATTACK_PROBE
    /* A dedicated combat-distance scenario for real input / HUD testing.
       Only the opt-in attack NRO uses it. The actual combat rules, core
       gameplay transition and rendering are completely unmodified. */
    c.patrol_left=66.0f;
    c.patrol_right=74.0f;
    c.enemy_start_x=68.0f;
    c.enemy_speed=8.0f;
#endif
#ifdef HM_DAMAGE_PROBE
    /* Dedicated no-input contact-damage/respawn encounter.
       Keep the actual combat and respawn engines unchanged. At 60 Hz,
       contact damage occurs at frames 1, 31 and 61, then native
       defeat recovery restores both subsystems on frame 62. */
    c.patrol_left=46.0f;
    c.patrol_right=54.0f;
    c.enemy_start_x=50.0f;
    c.enemy_speed=8.0f;
    c.hurt_cooldown_frames=30u;
#endif
#ifdef HM_CHECKPOINT_DEFEAT_PROBE
    /* Optional checkpoint-and-contact encounter. Movement is injected
       through the real NeXium D-pad after boot: the hero first activates
       the ordinary x=90 checkpoint, then the native combat loop causes
       three real contact hits with 30-frame immunity. Respawn logic,
       input handling and the renderer are completely unmodified. */
    c.patrol_left=86.0f;
    c.patrol_right=94.0f;
    c.enemy_start_x=90.0f;
    c.enemy_speed=8.0f;
    c.hurt_cooldown_frames=30u;
#endif
    return c;
}



int main(int argc, char **argv) {
    hm_world world=make_world();
    hm_combat_config combat=make_combat();
    hm_session game;
#ifdef HM_LEVEL_CHAIN_PROBE
    hm_world second_world;
    hm_combat_config second_combat;
#ifdef HM_THREE_ROOM_PROBE
    hm_world third_world;
    hm_combat_config third_combat;
#endif
    uint8_t stage=0u;
    hm_dash_state dash={0u,0u};
#ifdef HM_AIR_SMASH_PROBE
    hm_air_smash_state air_smash={0};
#endif
#endif
    hm_raster_view view;
    hm_replay_report replay={0};
    hm_session_result status;
    hm_replay_status qa_status=HM_REPLAY_OK;
    Framebuffer fb;
    PadState pad;
    Result rc;
    uint8_t qa_state=0u;
    uint8_t paused=0u;
    (void)argc;(void)argv;
#ifdef HM_LEVEL_CHAIN_PROBE
    if(!hm_synthetic_room2_init(&second_world,&second_combat,
                                second_cells,HM_ROOM2_CELLS))return 2;
#ifdef HM_THREE_ROOM_PROBE
    if(!hm_synthetic_room3_init(&third_world,&third_combat,
                                third_cells,HM_ROOM3_CELLS))return 2;
#endif
#endif
    status=hm_session_init(&world,&combat,&game);
    if(status!=HM_SESSION_OK ||
       hm_probe_boot_selfcheck()!=HM_PROBE_CHECK_OK ||
       hm_session_selftest()!=HM_SESSION_SELFTEST_OK)
        return 2;
    memset(&fb,0,sizeof(fb));
    padConfigureInput(1,HidNpadStyleSet_NpadStandard);
    padInitializeDefault(&pad);
    rc=framebufferCreate(&fb,nwindowGetDefault(),
                         HM_RASTER_WIDTH,HM_RASTER_HEIGHT,
                         PIXEL_FORMAT_RGBA_8888,2);
    if(R_FAILED(rc))return 3;
    rc=framebufferMakeLinear(&fb);
    if(R_FAILED(rc)){framebufferClose(&fb);return 4;}
    view.world=&world;
    view.game=&game;
    view.combat=&combat;
    view.qa_state=0u;
    view.qa_fingerprint=0u;
    while(appletMainLoop()) {
        hm_input input={0.0f,0u,0u};
        uint64_t held,down;
        uint32_t stride=0u;
        uint32_t *pixels;
        padUpdate(&pad);
        held=padGetButtons(&pad);
        down=padGetButtonsDown(&pad);
        if(down&HidNpadButton_Plus)break;
        if(held&HidNpadButton_Left)input.axis-=1.0f;
        if(held&HidNpadButton_Right)input.axis+=1.0f;
        input.jump=(uint8_t)((down&HidNpadButton_A)!=0u);
        input.reset=(uint8_t)((down&HidNpadButton_B)!=0u);
        if(down&HidNpadButton_Y) {
            qa_status=hm_replay_verify(&replay);
            qa_state=qa_status==HM_REPLAY_OK?1u:2u;
        }
        /* Minus toggles an atomic pause adapter. No native physics, enemy
           patrol, damage or checkpoint timer advances while paused.
           Plus remains the standard NRO exit button. */
#ifdef HM_LEVEL_CHAIN_PROBE
#ifdef HM_THREE_ROOM_PROBE
        if(hm_three_room_continue_allowed(
                &game,stage,paused,
                (uint8_t)((down&HidNpadButton_Minus)!=0u),
                (uint8_t)((down&HidNpadButton_A)!=0u))) {
            const hm_world *next_world =
                stage==0u?&second_world:&third_world;
            const hm_combat_config *next_combat =
                stage==0u?&second_combat:&third_combat;
            if(hm_three_room_try_advance(next_world,next_combat,
                                     &game,&stage,1u)!=HM_CHAIN_ADVANCED) {
                status=HM_SESSION_INVALID;
                break;
            }
            world=*next_world;
            combat=*next_combat;
            dash.remaining=0u;
            dash.recovery=0u;
#ifdef HM_AIR_SMASH_PROBE
            air_smash=(hm_air_smash_state){0};
#endif
            status=HM_SESSION_OK;
        } else
#else
        if(hm_chain_continue_edge_allowed(
                &game,stage,paused,
                (uint8_t)((down&HidNpadButton_Minus)!=0u),
                (uint8_t)((down&HidNpadButton_A)!=0u))) {
            if(hm_chain_try_advance(&second_world,&second_combat,
                                    &game,&stage,1u)!=HM_CHAIN_ADVANCED) {
                status=HM_SESSION_INVALID;
                break;
            }
            world=second_world;
            combat=second_combat;
            dash.remaining=0u;
            dash.recovery=0u;
#ifdef HM_AIR_SMASH_PROBE
            air_smash=(hm_air_smash_state){0};
#endif
            status=HM_SESSION_OK;
        } else
#endif
#endif
        {
#ifdef HM_LEVEL_CHAIN_PROBE
#ifdef HM_THREE_ROOM_PROBE
            if(stage==1u) {
                /* Room 2 is no longer terminal; A at its real CLEAR
                   advances to room 3, so no second-room FINISH here. */
                status=hm_dash_session_step(&world,&combat,&game,&paused,
                     &dash,input,
                     (uint8_t)((down&HidNpadButton_X)!=0u),
                     (uint8_t)((down&HidNpadButton_Minus)!=0u),
                     (uint8_t)((down&HidNpadButton_ZR)!=0u),
                     1.0f/60.0f);
            } else if(stage==2u) {
#ifdef HM_AIR_SMASH_PROBE
                status=hm_air_smash_step(&world,&combat,&game,&paused,
                     &dash,&air_smash,1u,input,
                     (uint8_t)((down&HidNpadButton_X)!=0u),
                     (uint8_t)((down&HidNpadButton_Minus)!=0u),
                     (uint8_t)((down&HidNpadButton_ZR)!=0u),
                     (uint8_t)((down&HidNpadButton_ZL)!=0u),
                     1.0f/60.0f);
#else
                status=hm_finale_session_step(&world,&combat,&game,&paused,
                     &dash,1u,input,
                     (uint8_t)((down&HidNpadButton_X)!=0u),
                     (uint8_t)((down&HidNpadButton_Minus)!=0u),
                     (uint8_t)((down&HidNpadButton_ZR)!=0u),
                     1.0f/60.0f);
#endif
            } else
#else
            if(stage==1u) {
#ifdef HM_AIR_SMASH_PROBE
                status=hm_air_smash_step(&world,&combat,&game,&paused,
                     &dash,&air_smash,stage,input,
                     (uint8_t)((down&HidNpadButton_X)!=0u),
                     (uint8_t)((down&HidNpadButton_Minus)!=0u),
                     (uint8_t)((down&HidNpadButton_ZR)!=0u),
                     (uint8_t)((down&HidNpadButton_ZL)!=0u),
                     1.0f/60.0f);
#else
                status=hm_finale_session_step(&world,&combat,&game,&paused,
                     &dash,stage,input,
                     (uint8_t)((down&HidNpadButton_X)!=0u),
                     (uint8_t)((down&HidNpadButton_Minus)!=0u),
                     (uint8_t)((down&HidNpadButton_ZR)!=0u),
                     1.0f/60.0f);
#endif
            } else
#endif
#endif
            {
                status=hm_paused_session_step(&world,&combat,&game,&paused,input,
                     (uint8_t)((down&HidNpadButton_X)!=0u),
                     (uint8_t)((down&HidNpadButton_Minus)!=0u),1.0f/60.0f);
            }
        }
        if(status!=HM_SESSION_OK)break;
        view.qa_state=qa_state;
        view.qa_fingerprint=qa_state==1u?replay.fingerprint:0u;
        pixels=(uint32_t*)framebufferBegin(&fb,&stride);
        if(!pixels || stride%sizeof(uint32_t)!=0u ||
           !hm_raster_render(pixels,HM_RASTER_WIDTH,HM_RASTER_HEIGHT,
                             stride/sizeof(uint32_t),&view) ||
           (paused && !hm_pause_overlay(pixels,HM_RASTER_WIDTH,
                     HM_RASTER_HEIGHT,stride/sizeof(uint32_t)))
#ifdef HM_LEVEL_CHAIN_PROBE
#ifdef HM_THREE_ROOM_PROBE
           || !hm_three_room_marker(pixels,HM_RASTER_WIDTH,HM_RASTER_HEIGHT,
                                    stride/sizeof(uint32_t),stage)
#else
           || !hm_stage_marker(pixels,HM_RASTER_WIDTH,HM_RASTER_HEIGHT,
                               stride/sizeof(uint32_t),stage)
#endif
           || (stage>=1u &&
               !hm_dash_hud(pixels,HM_RASTER_WIDTH,HM_RASTER_HEIGHT,
                            stride/sizeof(uint32_t),&dash))
#ifdef HM_THREE_ROOM_PROBE
           || (stage==2u &&
               !hm_finale_overlay(pixels,HM_RASTER_WIDTH,HM_RASTER_HEIGHT,
                        stride/sizeof(uint32_t),1u,
                        (uint8_t)(game.player.completed!=0u),paused))
#else
           || (stage==1u &&
               !hm_finale_overlay(pixels,HM_RASTER_WIDTH,HM_RASTER_HEIGHT,
                        stride/sizeof(uint32_t),stage,
                        (uint8_t)(game.player.completed!=0u),paused))
#endif
#ifdef HM_AIR_SMASH_PROBE
           || (
#ifdef HM_THREE_ROOM_PROBE
               stage==2u
#else
               stage==1u
#endif
               &&
               !hm_air_smash_hud(pixels,HM_RASTER_WIDTH,HM_RASTER_HEIGHT,
                        stride/sizeof(uint32_t),&air_smash))
#endif
#endif
           ) {
            if(pixels)framebufferEnd(&fb);
            status=HM_SESSION_INVALID;
            break;
        }
        framebufferEnd(&fb);
        /* Approximate frame pacing, not emulator/hardware timing proof. */
        svcSleepThread(16666667LL);
    }
    framebufferClose(&fb);
    return status==HM_SESSION_OK?0:5;
}
