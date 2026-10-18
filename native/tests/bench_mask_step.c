/* Non-gating synthetic 300x19 performance probe (never game assets). */
#include "heman_core.h"
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <time.h>
#define W 300u
#define H 19u
#define T 32u
#define N 900u
static uint16_t cells[W*H];
static uint64_t shapes[2u*T];
int main(void) {
    hm_mask_grid grid={cells,shapes,W,H,T,2};
    hm_world world;
    hm_state actor;
    unsigned x,y,frame;
    clock_t begin,end;
    memset(cells,0xff,sizeof(cells));
    memset(shapes,0,sizeof(shapes));
    for(y=0;y<T;++y)shapes[T+y]=UINT64_C(0xffffffff);
    for(x=0;x<W;++x)cells[12u*W+x]=1;
    memset(&world,0,sizeof(world));
    world.columns=W;world.rows=H;world.tile_size=T;world.mask_grid=&grid;
    world.spawn_x=100;world.spawn_feet_y=12*T;
    world.actor_half_width=5;world.actor_height=22;
    world.speed=120;world.gravity=1200;world.jump_speed=400;
    world.terminal_speed=1400;world.viewport_width=800;
    world.viewport_height=480;world.death_margin=90;
    world.max_rise=6;world.max_drop=6;
    if(hm_init(&world,&actor)!=HM_OK)return 2;
    begin=clock();
    for(frame=0;frame<N;++frame) {
        const hm_input input={(frame%240u)<120u?1.0f:-1.0f,
                              (uint8_t)(frame%120u==30u),0};
        if(hm_step(&world,&actor,input,1.0f/60.0f)!=HM_OK)return 3;
    }
    end=clock();
    printf("synthetic_frames=%u cpu_seconds=%.6f final_x=%.5f "
           "final_feet=%.5f camera_x=%.5f respawns=%u\n",N,
           (double)(end-begin)/(double)CLOCKS_PER_SEC,actor.x,
           actor.feet_y,actor.camera_x,actor.respawns);
    return 0;
}
