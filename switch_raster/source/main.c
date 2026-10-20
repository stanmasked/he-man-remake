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
#include "stage_marker.h"
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
/* Independent second exercise room, with a different ground elevation,
   short platforms and its own checkpoints/enemy. No iOS geometry. */
static uint8_t second_cells[W*H];
static const hm_event second_events[]={
    {HM_PICKUP,170.0f,267.0f,8.0f},
    {HM_CHECKPOINT,330.0f,273.0f,8.0f},
    {HM_HAZARD,570.0f,273.0f,8.0f},
    {HM_EXIT,735.0f,273.0f,8.0f}
};
static hm_world make_second_world(void) {
    hm_world result=make_world();
    uint32_t x;
    memset(second_cells,0,sizeof(second_cells));
    for(x=0u;x<W;++x)second_cells[18u*W+x]=1u;
    for(x=9u;x<13u;++x)second_cells[13u*W+x]=1u;
    for(x=23u;x<28u;++x)second_cells[15u*W+x]=1u;
    result.solid=second_cells;
    result.spawn_x=48.0f;
    result.spawn_feet_y=288.0f;
    result.events=second_events;
    result.event_count=(uint32_t)(sizeof(second_events)/sizeof(second_events[0]));
    return result;
}
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

#ifdef HM_LEVEL_CHAIN_PROBE
static hm_combat_config make_second_combat(void) {
    hm_combat_config c=make_combat();
    c.enemy_feet_y=288.0f;
    c.patrol_left=230.0f;
    c.patrol_right=320.0f;
    c.enemy_start_x=275.0f;
    return c;
}
#endif

int main(int argc, char **argv) {
    hm_world world=make_world();
    hm_combat_config combat=make_combat();
    hm_session game;
#ifdef HM_LEVEL_CHAIN_PROBE
    hm_world second_world=make_second_world();
    hm_combat_config second_combat=make_second_combat();
    uint8_t stage=0u;
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
        if(hm_chain_continue_edge_allowed(
                &game,stage,paused,
                (uint8_t)((down&HidNpadButton_Minus)!=0u),
                (uint8_t)((down&HidNpadButton_A)!=0u))) {
            /* The CLEAR → A edge changes rooms without advancing a
               gameplay frame, so no hidden jump/attack leaks through. */
            if(hm_chain_try_advance(&second_world,&second_combat,
                                    &game,&stage,1u)!=HM_CHAIN_ADVANCED) {
                status=HM_SESSION_INVALID;
                break;
            }
            world=second_world;
            combat=second_combat;
            status=HM_SESSION_OK;
        } else
#endif
        {
            status=hm_paused_session_step(&world,&combat,&game,&paused,input,
                 (uint8_t)((down&HidNpadButton_X)!=0u),
                 (uint8_t)((down&HidNpadButton_Minus)!=0u),1.0f/60.0f);
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
           || !hm_stage_marker(pixels,HM_RASTER_WIDTH,HM_RASTER_HEIGHT,
                               stride/sizeof(uint32_t),stage)
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
