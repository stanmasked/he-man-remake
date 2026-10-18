/* Synthetic fixed-step CSV reference, never reads commercial assets. */
#include "heman_core.h"
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#define W 40u
#define H 20u
#define T 16u
#define FRAMES 180
static uint8_t tiles[W*H];

static int scenario_setup(const char *name, hm_world *world) {
    uint32_t col, row;
    memset(tiles, 0, sizeof tiles);
    for (col=0; col<W; ++col) tiles[10u*W+col] = 1;
    memset(world, 0, sizeof(*world));
    world->solid=tiles; world->columns=W;world->rows=H;world->tile_size=T;
    world->spawn_x=40.0f;world->spawn_feet_y=160.0f;
    world->actor_half_width=5.0f;world->actor_height=22.0f;
    world->speed=120.0f;world->gravity=1200.0f;world->jump_speed=420.0f;
    world->terminal_speed=1400.0f;world->viewport_width=320.0f;
    world->viewport_height=240.0f;world->death_margin=80.0f;
    if (!strcmp(name,"flat")) return 1;
    if (!strcmp(name,"wall")) {
        world->spawn_x=180.0f;
        for(row=6;row<10;++row) tiles[row*W+15u]=1;
        return 1;
    }
    if (!strcmp(name,"ceiling")) {
        for(col=1;col<18;++col) tiles[6u*W+col]=1;
        return 1;
    }
    if (!strcmp(name,"ledge")) {
        for(col=13;col<W;++col) tiles[10u*W+col]=0;
        world->spawn_x=160.0f;
        return 1;
    }
    return 0;
}
static hm_input input_for(const char *name, int frame) {
    hm_input in={0,0,0};
    if (!strcmp(name,"flat")) {
        in.axis=(frame>=25&&frame<120)?1.0f:0.0f;
        in.jump=(uint8_t)(frame==54);
    } else if (!strcmp(name,"wall")) {
        in.axis=(frame>=15)?1.0f:0.0f;
        in.jump=(uint8_t)(frame==95);
    } else if (!strcmp(name,"ceiling")) {
        in.jump=(uint8_t)(frame==30);
    } else if (!strcmp(name,"ledge")) {
        in.axis=(frame>=20)?1.0f:0.0f;
    }
    return in;
}
int main(int argc, char **argv) {
    hm_world world;
    hm_state state;
    int i;
    if (argc!=2 || !scenario_setup(argv[1],&world) || hm_init(&world,&state)!=HM_OK) {
        fprintf(stderr,"scenario error\n");return 2;
    }
    puts("frame,x,feet_y,vy,grounded,wall_hit,ceiling_hit,camera_x,camera_y,respawns");
    for(i=0;i<FRAMES;++i) {
        hm_input input=input_for(argv[1],i);
        if(hm_step(&world,&state,input,1.0f/60.0f)!=HM_OK) {
            fprintf(stderr,"step error at %d\n",i);return 3;
        }
        printf("%u,%.8f,%.8f,%.8f,%u,%u,%u,%.8f,%.8f,%u\n",
               state.frame,state.x,state.feet_y,state.vy,state.grounded,
               state.wall_hit,state.ceiling_hit,state.camera_x,state.camera_y,state.respawns);
    }
    return 0;
}
