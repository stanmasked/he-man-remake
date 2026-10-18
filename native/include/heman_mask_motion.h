#ifndef HEMAN_MASK_MOTION_H
#define HEMAN_MASK_MOTION_H
#include "heman_mask.h"
#ifdef __cplusplus
extern "C" {
#endif
/* Independent masked-body experiment, not a replacement for hm_step yet. */
typedef struct {
    float x, feet_y, vertical_speed;
    unsigned grounded, wall_hit, ceiling_hit;
} hm_mask_actor;
typedef struct {
    float half_width, height, horizontal_speed, gravity, jump_speed;
    unsigned max_rise, max_drop;
} hm_mask_motion_config;
/* 0 success; negative means invalid/blocked start. Fixed dt (0,1/30]. */
int hm_mask_motion_step(const hm_mask_grid *grid, hm_mask_actor *actor,
                        const hm_mask_motion_config *config,
                        float axis, int jump, float dt);
#ifdef __cplusplus
}
#endif
#endif
