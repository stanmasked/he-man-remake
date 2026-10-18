#include "heman_mask_motion.h"
#include <math.h>
#include <stddef.h>

#define MAX_TRAVEL 512.0f

static int clear_body(const hm_mask_grid *g, float x, float feet,
                      const hm_mask_motion_config *c) {
    return hm_mask_body_overlap(g, x, feet, c->half_width, c->height) == 0;
}
/* Return last safe position; initial position is always clear. */
static float axis_sweep(const hm_mask_grid *g, float x, float feet, float delta,
                        int horizontal, const hm_mask_motion_config *c, int *blocked) {
    const float start = horizontal ? x : feet;
    const int steps = (int)ceilf(fabsf(delta));
    float safe = start;
    int k;
    *blocked = 0;
    for(k=1;k<=steps;++k) {
        float next=start+delta*(float)k/(float)steps;
        if (!clear_body(g,horizontal?next:x,horizontal?feet:next,c)) {
            int b;
            float bad=next;
            for(b=0;b<14;++b) {
                float mid=(bad+safe)*0.5f;
                if(clear_body(g,horizontal?mid:x,horizontal?feet:mid,c))safe=mid;
                else bad=mid;
            }
            *blocked=1;
            return safe;
        }
        safe=next;
    }
    return start+delta;
}
int hm_mask_motion_step(const hm_mask_grid *g, hm_mask_actor *actor,
                        const hm_mask_motion_config *c,
                        float axis, int jump, float dt) {
    hm_mask_actor a;
    float dx, new_x, feet;
    int hit, supported;
    unsigned rise;
    if (!g || !actor || !c || !hm_mask_valid(g) ||
        !isfinite(actor->x) || !isfinite(actor->feet_y) ||
        !isfinite(actor->vertical_speed) || !isfinite(axis) ||
        !isfinite(dt) || !isfinite(c->half_width) || !isfinite(c->height) ||
        !isfinite(c->horizontal_speed) || !isfinite(c->gravity) ||
        !isfinite(c->jump_speed) || dt<=0 || dt>1.0f/30 ||
        fabsf(axis)>1.0f || c->half_width<=0 || c->height<=0 ||
        c->half_width>64 || c->height>128 ||
        c->horizontal_speed<=0 || c->gravity<=0 || c->jump_speed<=0 ||
        c->max_rise>32 || c->max_drop>32 ||
        !clear_body(g,actor->x,actor->feet_y,c)) return -1;
    dx=axis*c->horizontal_speed*dt;
    if(!isfinite(dx) || fabsf(dx)>MAX_TRAVEL) return -1;
    a=*actor;
    a.wall_hit=0;
    a.ceiling_hit=0;
    supported=!clear_body(g,a.x,a.feet_y+0.25f,c);
    if(a.grounded && supported && !jump) {
        new_x=axis_sweep(g,a.x,a.feet_y,dx,1,c,&hit);
        if(hit && dx!=0) {
            /* Only climb when the complete raised trajectory is clear. */
            for(rise=1;rise<=c->max_rise;++rise) {
                float raised, candidate, landing;
                int uphit, sidehit, downhit;
                raised=axis_sweep(g,a.x,a.feet_y,-(float)rise,0,c,&uphit);
                if(uphit)break;
                candidate=axis_sweep(g,a.x,raised,dx,1,c,&sidehit);
                if(sidehit)continue;
                landing=axis_sweep(g,candidate,raised,
                                  (float)(rise+c->max_drop)+0.5f,0,c,&downhit);
                if(downhit && landing<=a.feet_y+(float)c->max_drop+0.001f) {
                    a.x=candidate;a.feet_y=landing;a.grounded=1;
                    a.vertical_speed=0;*actor=a;return 0;
                }
            }
        }
        a.x=new_x;
        a.wall_hit=(unsigned)hit;
        feet=axis_sweep(g,a.x,a.feet_y,(float)c->max_drop+0.5f,0,c,&hit);
        if(hit) {
            a.feet_y=feet;a.grounded=1;a.vertical_speed=0;
            *actor=a;return 0;
        }
        a.grounded=0;a.vertical_speed=0;
    } else {
        a.x=axis_sweep(g,a.x,a.feet_y,dx,1,c,&hit);
        a.wall_hit=(unsigned)hit;
        if(a.grounded && supported && jump) {
            a.vertical_speed=-c->jump_speed;
            a.grounded=0;
        } else if(a.grounded) {
            a.grounded=0;a.vertical_speed=0;
        }
    }
    a.vertical_speed+=c->gravity*dt;
    if(!isfinite(a.vertical_speed))return -1;
    dx=a.vertical_speed*dt;
    if(!isfinite(dx)||fabsf(dx)>MAX_TRAVEL)return -1;
    a.feet_y=axis_sweep(g,a.x,a.feet_y,dx,0,c,&hit);
    if(hit) {
        a.ceiling_hit=(unsigned)(dx<0);
        a.grounded=(unsigned)(dx>=0);
        a.vertical_speed=0;
    }
    *actor=a;
    return 0;
}
