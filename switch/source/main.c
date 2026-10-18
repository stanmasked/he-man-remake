/* Asset-free Nintendo Switch *core probe*, not a remade He-Man game.
   Requires devkitA64 + libnx. No game assets or original scripts. */
#include <switch.h>
#include <stdio.h>
#include <string.h>
#include "heman_core.h"

#define W 48u
#define H 24u
#define T 16u
static uint8_t level[W * H];

static hm_world make_world(void) {
    hm_world w;
    unsigned x;
    memset(&w,0,sizeof(w));
    memset(level,0,sizeof(level));
    for(x=0;x<W;++x)level[17u*W+x]=1;
    for(x=15;x<18;++x)level[15u*W+x]=1;
    w.solid=level;
    w.columns=W;w.rows=H;w.tile_size=T;
    w.spawn_x=50;w.spawn_feet_y=17*T;
    w.actor_half_width=5;w.actor_height=22;
    w.speed=120;w.gravity=1200;w.jump_speed=420;
    w.terminal_speed=1400;
    w.viewport_width=320;w.viewport_height=240;w.death_margin=96;
    return w;
}

int main(void) {
    hm_world world=make_world();
    hm_state state;
    PadState pad;
    hm_result result=hm_init(&world,&state);
    consoleInit(NULL);
    padConfigureInput(1,HidNpadStyleSet_NpadStandard);
    padInitializeDefault(&pad);
    if(result != HM_OK) {
        printf("Core setup error: %d\n", (int)result);
        consoleUpdate(NULL);
        consoleExit(NULL);
        return 1;
    }
    while(appletMainLoop()) {
        hm_input input={0.0f,0,0};
        uint64_t down, held;
        padUpdate(&pad);
        down=padGetButtonsDown(&pad);
        held=padGetButtons(&pad);
        if(down & HidNpadButton_Plus)break;
        if(held & HidNpadButton_Left)input.axis-=1.0f;
        if(held & HidNpadButton_Right)input.axis+=1.0f;
        input.jump=(uint8_t)((down & HidNpadButton_A)!=0);
        input.reset=(uint8_t)((down & HidNpadButton_B)!=0);
        result=hm_step(&world,&state,input,1.0f/60.0f);
        if(result != HM_OK)break;
        /* Text console diagnostics only. No sprites, assets, or rendering. */
        if(state.frame % 15u == 0u) {
            printf("\x1b[2J\x1b[H");
            printf("He-Man C99 core probe (synthetic course)\n");
            printf("Left/Right: move | A: jump | B: reset | +: quit\n\n");
            printf("frame %u\n",state.frame);
            printf("x %.2f / feet %.2f / velocity %.2f\n",
                   state.x,state.feet_y,state.vy);
            printf("ground %u / wall %u / ceiling %u\n",
                   state.grounded,state.wall_hit,state.ceiling_hit);
            printf("Camera x %.1f / respawns %u\n",
                   state.camera_x,state.respawns);
            printf("\nThis is NOT the original iOS game.\n");
        }
        consoleUpdate(NULL);
    }
    consoleExit(NULL);
    return result==HM_OK?0:2;
}
