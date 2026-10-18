/* Synthetic tests: complete validation at frame entry, fast overlap inside. */
#include "heman_core.h"
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

static uint16_t tiles[9];
static uint64_t mask_rows[2 * 16];
static hm_mask_grid geometry = {tiles,mask_rows,3,3,16,2};

static hm_world make_world(void) {
    hm_world w;
    unsigned row;
    memset(&w,0,sizeof(w));
    memset(tiles,0xff,sizeof(tiles));
    memset(mask_rows,0,sizeof(mask_rows));
    for(row=0;row<16;++row)mask_rows[16+row]=UINT64_C(65535);
    tiles[3]=1;tiles[4]=1;tiles[5]=1;
    w.columns=3;w.rows=3;w.tile_size=16;w.mask_grid=&geometry;
    w.spawn_x=18;w.spawn_feet_y=16;w.actor_half_width=4;w.actor_height=10;
    w.speed=120;w.gravity=1200;w.jump_speed=400;w.terminal_speed=1400;
    w.viewport_width=320;w.viewport_height=240;w.death_margin=60;
    w.max_rise=3;w.max_drop=3;
    return w;
}
int main(void) {
    hm_world w=make_world();
    hm_state s, saved;
    hm_input in={1,0,0};
    unsigned n;
    assert(hm_init(&w,&s)==HM_OK);
    assert(hm_mask_valid(&geometry));
    for(n=0;n<30;++n)assert(hm_step(&w,&s,in,1.0f/60.0f)==HM_OK);
    assert(!hm_overlaps(&w,s.x,s.feet_y));
    /* Public call never bypasses full geometry validation. */
    saved=s;
    tiles[0]=600;
    assert(hm_mask_body_overlap(&geometry,18,16,4,10)==-1);
    assert(hm_step(&w,&s,in,1.0f/60.0f)==HM_INVALID);
    assert(memcmp(&saved,&s,sizeof(s))==0);
    tiles[0]=UINT16_MAX;
    /* Mask row mutation is caught on the very next step. */
    mask_rows[16]=UINT64_C(1) << 20;
    assert(hm_step(&w,&s,in,1.0f/60.0f)==HM_INVALID);
    assert(memcmp(&saved,&s,sizeof(s))==0);
    mask_rows[16]=UINT64_C(65535);
    assert(hm_mask_valid(&geometry));
    assert(hm_mask_body_overlap_prevalidated(&geometry,18,16,4,10)==0);
    assert(hm_step(&w,&s,in,1.0f/60.0f)==HM_OK);
    puts("PASS: checked API, validated fast collision, mutation rollback");
    return 0;
}
