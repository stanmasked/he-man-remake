#include "heman_mask_motion.h"
#include <assert.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
static uint16_t cells[4]={1,2,UINT16_MAX,UINT16_MAX};
static uint64_t packed[3*16];
static hm_mask_grid ramp_grid(void) {
    hm_mask_grid grid={cells,packed,2,2,16,3};
    unsigned y;
    for(y=0;y<16;++y) {
        packed[y]=0;
        /* A full-height wedge, rising from the left toward the right. */
        packed[16+y]=UINT64_C(65535) ^ ((UINT64_C(1) << (15-y))-1);
        packed[32+y]=UINT64_C(65535);
    }
    return grid;
}
int main(void) {
    hm_mask_grid g=ramp_grid();
    const hm_mask_motion_config cfg={0.4f,5.0f,60.0f,1200.0f,400.0f,3,3};
    hm_mask_actor actor={2,13,0,1,0,0};
    float before=actor.feet_y;
    int i, rise=0, fall=0;
    assert(hm_mask_valid(&g));
    assert(!hm_mask_body_overlap(&g,actor.x,actor.feet_y,cfg.half_width,cfg.height));
    for(i=0;i<9;++i) {
        assert(hm_mask_motion_step(&g,&actor,&cfg,1,0,1.0f/60)==0);
        assert(!hm_mask_body_overlap(&g,actor.x,actor.feet_y,cfg.half_width,cfg.height));
        rise |= actor.feet_y < before - .01f;
        before=actor.feet_y;
    }
    assert(rise && actor.x>2 && actor.grounded);
    for(i=0;i<6;++i) {
        assert(hm_mask_motion_step(&g,&actor,&cfg,-1,0,1.0f/60)==0);
        assert(!hm_mask_body_overlap(&g,actor.x,actor.feet_y,cfg.half_width,cfg.height));
        fall |= actor.feet_y > before + .01f;
        before=actor.feet_y;
    }
    assert(fall);
    assert(hm_mask_motion_step(&g,&actor,&cfg,0,1,1.0f/60)==0);
    assert(!actor.grounded);
    assert(actor.vertical_speed<0);
    assert(hm_mask_motion_step(&g,&actor,&cfg,0,0,1.0f)==-1);
    puts("PASS: synthetic native packed-mask slope walking, jump and safety limits");
    return 0;
}
