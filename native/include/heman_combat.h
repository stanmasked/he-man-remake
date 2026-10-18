#ifndef HEMAN_COMBAT_H
#define HEMAN_COMBAT_H

#include <stdint.h>
#include "heman_core.h"

/* Independent C99 *synthetic* one-enemy combat experiment. Does not
   reconstruct the original He-Man game or its combat rules. */
typedef struct {
    float patrol_left;
    float patrol_right;
    float enemy_start_x;
    float enemy_feet_y;
    float enemy_speed;
    float sword_reach;
    float contact_range;
    uint8_t enemy_initial_hp;
    uint8_t player_initial_hp;
    uint16_t sword_cooldown_frames;
    uint16_t hurt_cooldown_frames;
} hm_combat_config;

typedef struct {
    float enemy_x;
    int8_t direction;           /* +1 right, -1 left */
    uint8_t enemy_hp;
    uint8_t player_hp;
    uint16_t sword_cooldown;
    uint16_t hurt_cooldown;
    uint32_t frame;
    uint32_t sword_hits;
    uint32_t player_hits;
} hm_combat_state;

typedef enum {
    HM_COMBAT_OK = 0,
    HM_COMBAT_INVALID = 1,
    HM_COMBAT_LIMIT = 2
} hm_combat_result;

hm_combat_result hm_combat_init(const hm_combat_config *config,
                                hm_combat_state *state);
/* Trigger only on fresh press. Any rejected input leaves state untouched.
   dt must be positive and <= 1/30 second. */
hm_combat_result hm_combat_step(const hm_combat_config *config,
                                hm_combat_state *state,
                                const hm_state *player,
                                uint8_t attack_pressed,
                                uint8_t facing_right,
                                float dt);
#endif
