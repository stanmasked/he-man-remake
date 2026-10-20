#include "air_smash_hud.h"

#define OUTER UINT32_C(0xff203449)
#define INNER UINT32_C(0xff1b2c46)
#define READY UINT32_C(0xff6ee0d8)
#define ACTIVE UINT32_C(0xffffaa55)
#define COOLDOWN UINT32_C(0xff566578)
#define IMPACT UINT32_C(0xff42d58a)
#define LETTER UINT32_C(0xfff1e6bf)

static void block(uint32_t *pixels, uint32_t stride,
                  unsigned x, unsigned y, unsigned width,
                  unsigned height, uint32_t color) {
    unsigned row,col;
    for(row=y;row<y+height;++row)
        for(col=x;col<x+width;++col)
            pixels[row*stride+col]=color;
}
int hm_air_smash_hud(uint32_t *pixels, uint32_t width, uint32_t height,
                     uint32_t stride, const hm_air_smash_state *ability) {
    uint32_t fill;
    if(!pixels || !ability || width!=640u || height!=360u ||
       stride<640u || stride>4096u || ability->armed>1u ||
       ability->impact_frames>HM_SMASH_FEEDBACK_FRAMES ||
       ability->cooldown>HM_SMASH_COOLDOWN_FRAMES ||
       ability->enemy_hits>ability->impacts) return 0;
    fill=ability->impact_frames?IMPACT:
         ability->armed?ACTIVE:
         ability->cooldown?COOLDOWN:READY;
    /* 48x28 HUD cue, anchored independently of moving camera. */
    block(pixels,stride,575u,79u,52u,32u,OUTER);
    block(pixels,stride,578u,82u,46u,26u,INNER);
    block(pixels,stride,588u,88u,23u,14u,fill);
    /* Two small ZL hint strokes visible while the ability is ready. */
    block(pixels,stride,580u,88u,5u,2u,LETTER);
    block(pixels,stride,580u,98u,5u,2u,LETTER);
    block(pixels,stride,615u,88u,2u,12u,LETTER);
    return 1;
}
