/* Synthetic wedge traversal: C99 integrated hm_step mask trace. */
#include "heman_core.h"
#include <stdint.h>
#include <stdio.h>
#include <string.h>
static uint16_t ids[9];
static uint64_t rows[3*16];
static hm_mask_grid grid={ids,rows,3,3,16,3};
int main(void) {
    hm_world w;hm_state s;int tick;unsigned y;
    memset(ids,0xff,sizeof ids);memset(rows,0,sizeof rows);
    for(y=0;y<16;++y) {
        rows[16+y]=(UINT64_C(65535)<<(15u-y)) & UINT64_C(65535);
        rows[32+y]=UINT64_C(65535);
    }
    ids[0]=1;ids[1]=2;
    memset(&w,0,sizeof w);
    w.columns=3;w.rows=3;w.tile_size=16;w.mask_grid=&grid;
    w.actor_half_width=.4f;w.actor_height=5.0f;
    w.spawn_x=2;w.spawn_feet_y=13;
    w.speed=60;w.gravity=1200;w.jump_speed=100;w.terminal_speed=700;
    w.viewport_width=320;w.viewport_height=240;w.death_margin=60;
    w.max_rise=3;w.max_drop=3;
    if(hm_init(&w,&s)!=HM_OK)return 2;
    puts("frame,x,feet_y,vy,grounded,wall_hit,ceiling_hit");
    for(tick=0;tick<26;++tick) {
        const hm_input in={tick<1?0.0f:tick<12?1.0f:tick<22?-1.0f:0.0f,0,0};
        if(hm_step(&w,&s,in,1.0f/60.0f)!=HM_OK)return 3;
        printf("%u,%.7f,%.7f,%.7f,%u,%u,%u\n",
               s.frame,s.x,s.feet_y,s.vy,s.grounded,s.wall_hit,s.ceiling_hit);
    }
    return 0;
}
