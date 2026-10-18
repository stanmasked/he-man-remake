#include "heman_core.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <string.h>

#define COLS 64u
#define ROWS 24u
#define TILE 16u
static uint8_t terrain[COLS * ROWS];
static hm_event events[] = {
    {HM_PICKUP, 80.0f, 272.0f, 7.0f},
    {HM_CHECKPOINT, 130.0f, 288.0f, 8.0f},
    {HM_TRIGGER, 165.0f, 272.0f, 7.0f},
    {HM_HAZARD, 220.0f, 272.0f, 8.0f},
    {HM_EXIT, 450.0f, 272.0f, 10.0f}
};

static hm_world sample(void) {
    hm_world w;
    unsigned col;
    memset(terrain, 0, sizeof terrain);
    for (col = 0; col < COLS; ++col) terrain[18u * COLS + col] = 1;
    memset(&w, 0, sizeof w);
    w.solid = terrain; w.columns = COLS; w.rows = ROWS; w.tile_size = TILE;
    w.spawn_x = 50; w.spawn_feet_y = 288;
    w.actor_half_width = 5; w.actor_height = 22;
    w.speed = 120; w.gravity = 1200; w.jump_speed = 420; w.terminal_speed = 1400;
    w.viewport_width = 320; w.viewport_height = 240; w.death_margin = 96;
    w.events = events; w.event_count = (uint32_t)(sizeof events / sizeof events[0]);
    return w;
}
static void tick(const hm_world *w, hm_state *s, float axis, int jump, int reset) {
    const hm_input input = {axis, (uint8_t)jump, (uint8_t)reset};
    assert(hm_step(w, s, input, 1.0f/60.0f) == HM_OK);
}
static int near(float a, float b) {return fabsf(a-b) <= .02f;}

static void test_spawn_and_ground(void) {
    hm_world w = sample(); hm_state s; unsigned i;
    assert(hm_init(&w, &s) == HM_OK);
    assert(s.checkpoint == -1 && s.frame == 0);
    assert(!hm_overlaps(&w, s.x, s.feet_y));
    for (i=0; i<20; ++i) tick(&w,&s,0,0,0);
    assert(s.grounded && near(s.feet_y, 288));
    assert(s.frame == 20 && s.landings == 1);
}
static void test_jump_and_ceiling(void) {
    hm_world w = sample(); hm_state s; unsigned i; int hit=0;
    for (i=3; i<14; ++i) terrain[14u*COLS+i] = 1;
    assert(hm_init(&w,&s)==HM_OK);
    tick(&w,&s,0,0,0);
    for (i=0;i<30;++i) {
        tick(&w,&s,0,i==0,0);
        if (s.ceiling_hit) {hit=1; break;}
    }
    assert(hit && s.vy==0 && !s.grounded);
    for (i=0;i<100;++i) tick(&w,&s,0,0,0);
    assert(s.grounded && near(s.feet_y,288));
}
static void test_wall_and_no_tunnel(void) {
    hm_world w=sample();hm_state s;unsigned row,i;
    for (row=14;row<18;++row) terrain[row*COLS+15]=1;
    w.event_count=0; /* Keep synthetic hazard from interfering with wall test. */
    assert(hm_init(&w,&s)==HM_OK);
    tick(&w,&s,0,0,0);
    for (i=0;i<200;++i) tick(&w,&s,1,0,0);
    assert(s.wall_hit && s.x + w.actor_half_width <= 240.01f);
    assert(!hm_overlaps(&w,s.x,s.feet_y));
}
static void test_pickup_checkpoint_hazard(void) {
    hm_world w=sample();hm_state s;unsigned i;
    assert(hm_init(&w,&s)==HM_OK);
    tick(&w,&s,0,0,0);
    for (i=0;i<95;++i) tick(&w,&s,1,0,0);
    assert((s.picked & 1u) !=0);
    assert(s.checkpoint == 1);
    assert((s.triggered & (1u<<2)) !=0);
    assert(s.hazards>=1 && s.respawns>=1);
    assert(s.x < 220);
    tick(&w,&s,0,0,1);
    assert(near(s.x,130) && near(s.feet_y,288));
    assert((s.picked & 1u)!=0);
}
static void test_camera_and_exit(void) {
    hm_world w=sample();hm_state s;unsigned i;
    w.event_count=0;
    assert(hm_init(&w,&s)==HM_OK);
    for(i=0;i<240;++i) tick(&w,&s,1,0,0);
    assert(s.x>400 && s.camera_x>0 && s.camera_x<=704);
    assert(s.camera_y>=0 && s.camera_y<=144);
    w.event_count=5;
    assert(hm_init(&w,&s)==HM_OK);
    s.x=450;s.feet_y=288;s.grounded=1;
    tick(&w,&s,0,0,0);
    assert(s.completed);
}
static void test_replay_determinism(void) {
    hm_world w=sample();hm_state a,b;unsigned i;
    assert(hm_init(&w,&a)==HM_OK);
    assert(hm_init(&w,&b)==HM_OK);
    for(i=0;i<180;++i) {
        const float axis=i<80?1.0f:0.0f;
        tick(&w,&a,axis,i==100,0);
        tick(&w,&b,axis,i==100,0);
    }
    assert(memcmp(&a,&b,sizeof a)==0);
}
static void test_invalid_inputs_rollback(void) {
    hm_world w=sample();hm_state s,backup;hm_input bad={2.0f,0,0};
    assert(hm_init(&w,&s)==HM_OK);
    backup=s;
    assert(hm_step(&w,&s,bad,1.0f/60.0f)==HM_INVALID);
    assert(memcmp(&s,&backup,sizeof s)==0);
    bad.axis=0;
    assert(hm_step(&w,&s,bad,0)==HM_INVALID);
    assert(memcmp(&s,&backup,sizeof s)==0);
    w.spawn_feet_y=294;
    assert(hm_init(&w,&s)==HM_INVALID);
    w=sample();w.event_count=33;
    assert(hm_init(&w,&s)==HM_INVALID);
}
static void test_ledge_and_respawn(void) {
    hm_world w=sample();hm_state s;unsigned col,i;
    for(col=8;col<64;++col) terrain[18u*COLS+col]=0;
    w.event_count=0;
    assert(hm_init(&w,&s)==HM_OK);
    tick(&w,&s,0,0,0);
    for(i=0;i<240;++i) tick(&w,&s,1,0,0);
    assert(s.respawns>=1);
}
int main(void) {
    test_spawn_and_ground();test_jump_and_ceiling();test_wall_and_no_tunnel();
    test_pickup_checkpoint_hazard();test_camera_and_exit();
    test_replay_determinism();test_invalid_inputs_rollback();
    test_ledge_and_respawn();
    puts("PASS: 8 native C99 core scenarios (synthetic cells only)");
    return 0;
}
