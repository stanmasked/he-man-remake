#include "dash_hud.h"

#define HUD_WIDTH 640u
#define HUD_HEIGHT 360u
#define BORDER UINT32_C(0xffe1c86d)
#define READY UINT32_C(0xff6ee0d8)
#define ACTIVE UINT32_C(0xffffaa55)
#define COOLING UINT32_C(0xff566578)
#define PANEL UINT32_C(0xff1b2c46)

static void fill(uint32_t *p,uint32_t stride,unsigned x,unsigned y,
                 unsigned w,unsigned h,uint32_t color) {
    unsigned i,j;
    for(i=y;i<y+h;++i)
        for(j=x;j<x+w;++j)
            p[i*stride+j]=color;
}

int hm_dash_hud(uint32_t *pixels, uint32_t width, uint32_t height,
                uint32_t stride, const hm_dash_state *dash) {
    unsigned completed;
    uint32_t color;
    if(!pixels || width!=HUD_WIDTH || height!=HUD_HEIGHT ||
       stride<HUD_WIDTH || stride>4096u || !dash ||
       dash->remaining>HM_DASH_DURATION_FRAMES ||
       dash->recovery>HM_DASH_RECOVERY_FRAMES) return 0;
    fill(pixels,stride,432u,9u,40u,23u,BORDER);
    fill(pixels,stride,435u,12u,34u,17u,PANEL);
    if(dash->remaining) {
        color=ACTIVE;
        completed=(unsigned)dash->remaining*30u/HM_DASH_DURATION_FRAMES;
    } else if(dash->recovery) {
        color=COOLING;
        completed=(unsigned)(HM_DASH_RECOVERY_FRAMES-dash->recovery)*30u/
                   HM_DASH_RECOVERY_FRAMES;
    } else {
        color=READY;
        completed=30u;
    }
    if(completed)
        fill(pixels,stride,437u,16u,completed,9u,color);
    return 1;
}
