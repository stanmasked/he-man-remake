/* Asset-free graphical Nintendo Switch proof-of-concept.
   This is NOT the original iOS He-Man game or its character art. */
#include <switch.h>
#include <stdint.h>
#include <string.h>
#include "heman_core.h"
#include "heman_combat.h"
#include "heman_session.h"
#include "probe_selfcheck.h"
#include "session_selftest.h"
#include "runtime_replay.h"
#include "raster_scene.h"

#define W 48u
#define H 24u
static uint8_t cells[W*H];
static const hm_event events[] = {
    {HM_PICKUP,170.0f,251.0f,8.0f},
    {HM_CHECKPOINT,340.0f,257.0f,8.0f},
    {HM_HAZARD,585.0f,257.0f,8.0f},
    {HM_EXIT,728.0f,257.0f,8.0f}
};

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
    w.events=events;w.event_count=4u;
    return w;
}

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
    return c;
}

int main(int argc, char **argv) {
    hm_world world=make_world();
    hm_combat_config combat=make_combat();
    hm_session game;
    hm_raster_view view;
    hm_replay_report replay={0};
    hm_session_result status;
    hm_replay_status qa_status=HM_REPLAY_OK;
    Framebuffer fb;
    PadState pad;
    Result rc;
    uint8_t qa_state=0u;
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
        status=hm_session_step(&world,&combat,&game,input,
             (uint8_t)((down&HidNpadButton_X)!=0u),1.0f/60.0f);
        if(status!=HM_SESSION_OK)break;
        view.qa_state=qa_state;
        view.qa_fingerprint=qa_state==1u?replay.fingerprint:0u;
        pixels=(uint32_t*)framebufferBegin(&fb,&stride);
        if(!pixels || stride%sizeof(uint32_t)!=0u ||
           !hm_raster_render(pixels,HM_RASTER_WIDTH,HM_RASTER_HEIGHT,
                             stride/sizeof(uint32_t),&view)) {
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
