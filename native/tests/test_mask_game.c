/* Entirely synthetic C99 masked-gameplay scenarios. */
#include "heman_core.h"
#include <assert.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#define MS 16u
#define MW 3u
#define MH 3u
static uint16_t ids[MW*MH];
static uint64_t rows[3*MS];
static hm_mask_grid grid={ids,rows,MW,MH,MS,3};
static hm_world world(void) {
    hm_world w;
    unsigned y;
    memset(ids,0xff,sizeof(ids));
    memset(rows,0,sizeof(rows));
    for(y=0;y<MS;++y) {
        rows[MS+y]=(UINT64_C(65535)<<(15u-y)) & UINT64_C(65535);
        rows[2u*MS+y]=UINT64_C(65535);
    }
    ids[0]=1;ids[1]=2;
    memset(&w,0,sizeof(w));
    w.columns=MW;w.rows=MH;w.tile_size=MS;
    w.mask_grid=&grid;w.actor_half_width=.4f;w.actor_height=5;
    w.spawn_x=2;w.spawn_feet_y=13;w.speed=60;
    w.gravity=1200;w.jump_speed=100;w.terminal_speed=700;
    w.viewport_width=320;w.viewport_height=240;w.death_margin=60;
    w.max_rise=3;w.max_drop=3;
    return w;
}
static void tick(const hm_world *w,hm_state *s,float axis,int jump) {
    hm_input in={axis,(uint8_t)jump,0};
    assert(hm_step(w,s,in,1.0f/60.0f)==HM_OK);
}
static void uphill_and_downhill(void) {
    hm_world w=world();hm_state s;int i;
    assert(hm_init(&w,&s)==HM_OK);
    tick(&w,&s,0,0);
    assert(s.grounded);
    for(i=0;i<10;++i) {
        const float old=s.feet_y;
        tick(&w,&s,1,0);
        assert(s.grounded && s.feet_y <= old + .01f);
        assert(!hm_overlaps(&w,s.x,s.feet_y));
    }
    assert(s.x>10 && s.feet_y<6);
    for(i=0;i<8;++i) tick(&w,&s,-1,0);
    assert(s.grounded && s.x<6 && s.feet_y>9);
}
static void wall_and_ceiling(void) {
    hm_world w=world();hm_state s;int i;
    ids[0]=UINT16_MAX;ids[1]=2;ids[3]=2;ids[4]=2;
    w.spawn_x=10;w.spawn_feet_y=16;
    assert(hm_init(&w,&s)==HM_OK);
    tick(&w,&s,0,0);
    for(i=0;i<20;++i)tick(&w,&s,1,0);
    assert(s.wall_hit && s.x+w.actor_half_width<=16.01f);
    assert(!hm_overlaps(&w,s.x,s.feet_y));
    /* A low ceiling must block lifting the entire body. */
    w=world();
    rows[MS+5]=UINT64_C(65535);
    assert(hm_init(&w,&s)==HM_OK);
    tick(&w,&s,0,0);
    for(i=0;i<5;++i)tick(&w,&s,1,0);
    assert(s.x<5.01f && s.feet_y>=11.0f && s.wall_hit);
    assert(!hm_overlaps(&w,s.x,s.feet_y));
}
static void jump_and_input_rollback(void) {
    hm_world w=world();hm_state s,old;hm_input input={1,0,0};
    assert(hm_init(&w,&s)==HM_OK);
    tick(&w,&s,0,0);
    tick(&w,&s,0,1);
    assert(!s.grounded && s.feet_y<13);
    old=s;
    ids[0]=999;
    assert(hm_step(&w,&s,input,1.0f/60.0f)==HM_INVALID);
    assert(memcmp(&old,&s,sizeof s)==0);
    ids[0]=1;
    w.max_rise=33;
    assert(hm_init(&w,&s)==HM_INVALID);
}
int main(void) {
    uphill_and_downhill();
    wall_and_ceiling();
    jump_and_input_rollback();
    puts("PASS: native C99 masked gameplay slope, wall, headroom, rollback");
    return 0;
}
