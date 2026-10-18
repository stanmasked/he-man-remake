#include "heman_combat.h"
#include <math.h>
#include <limits.h>
#include <string.h>

static int valid_scalar(float x) {
    return isfinite(x) && x > -1000000.0f && x < 1000000.0f;
}

static int valid_config(const hm_combat_config *c) {
    if (!c || !valid_scalar(c->patrol_left) ||
        !valid_scalar(c->patrol_right) ||
        !valid_scalar(c->enemy_start_x) ||
        !valid_scalar(c->enemy_feet_y) ||
        !valid_scalar(c->enemy_speed) ||
        !valid_scalar(c->sword_reach) ||
        !valid_scalar(c->contact_range)) return 0;
    return c->patrol_left >= 0.0f &&
           c->patrol_right > c->patrol_left &&
           c->patrol_right - c->patrol_left >= 8.0f &&
           c->enemy_start_x >= c->patrol_left &&
           c->enemy_start_x <= c->patrol_right &&
           c->enemy_speed > 0.0f && c->enemy_speed <= 240.0f &&
           c->sword_reach >= 1.0f && c->sword_reach <= 80.0f &&
           c->contact_range >= 1.0f && c->contact_range <= 40.0f &&
           c->enemy_initial_hp >= 1u && c->enemy_initial_hp <= 20u &&
           c->player_initial_hp >= 1u && c->player_initial_hp <= 20u &&
           c->sword_cooldown_frames > 0u &&
           c->hurt_cooldown_frames > 0u;
}

hm_combat_result hm_combat_init(const hm_combat_config *config,
                                hm_combat_state *state) {
    if (!state || !valid_config(config)) return HM_COMBAT_INVALID;
    memset(state, 0, sizeof(*state));
    state->enemy_x = config->enemy_start_x;
    state->direction = 1;
    state->enemy_hp = config->enemy_initial_hp;
    state->player_hp = config->player_initial_hp;
    return HM_COMBAT_OK;
}

hm_combat_result hm_combat_step(const hm_combat_config *config,
                                hm_combat_state *state,
                                const hm_state *player,
                                uint8_t attack_pressed,
                                uint8_t facing_right,
                                float dt) {
    hm_combat_state next;
    float delta, gap, vertical;
    int in_front;
    if (!valid_config(config) || !state || !player ||
        !valid_scalar(state->enemy_x) ||
        state->enemy_x < config->patrol_left ||
        state->enemy_x > config->patrol_right ||
        (state->direction != 1 && state->direction != -1) ||
        state->enemy_hp > config->enemy_initial_hp ||
        state->player_hp > config->player_initial_hp ||
        !valid_scalar(player->x) || !valid_scalar(player->feet_y) ||
        !valid_scalar(dt) || dt <= 0.0f || dt > 1.0f / 30.0f ||
        attack_pressed > 1u || facing_right > 1u) return HM_COMBAT_INVALID;
    if (state->frame == UINT32_MAX ||
        state->sword_hits == UINT32_MAX ||
        state->player_hits == UINT32_MAX) return HM_COMBAT_LIMIT;

    next = *state;
    ++next.frame;
    if (next.sword_cooldown) --next.sword_cooldown;
    if (next.hurt_cooldown) --next.hurt_cooldown;
    vertical = fabsf(player->feet_y - config->enemy_feet_y);
    delta = next.enemy_x - player->x;
    gap = fabsf(delta);
    in_front = facing_right ? delta >= 0.0f : delta <= 0.0f;

    /* Hit test precedes patrol movement, independent of rendering speed.
       A new button press consumes cooldown even when the hit misses. */
    if (attack_pressed && next.sword_cooldown == 0u &&
        next.player_hp > 0u) {
        next.sword_cooldown = config->sword_cooldown_frames;
        if (next.enemy_hp > 0u && in_front &&
            gap <= config->sword_reach && vertical <= 28.0f) {
            --next.enemy_hp;
            ++next.sword_hits;
        }
    }
    if (next.enemy_hp > 0u) {
        next.enemy_x += (float)next.direction * config->enemy_speed * dt;
        if (next.enemy_x > config->patrol_right) {
            next.enemy_x = config->patrol_right;
            next.direction = -1;
        } else if (next.enemy_x < config->patrol_left) {
            next.enemy_x = config->patrol_left;
            next.direction = 1;
        }
        if (next.player_hp > 0u && next.hurt_cooldown == 0u &&
            fabsf(player->x - next.enemy_x) <= config->contact_range &&
            vertical <= 28.0f) {
            --next.player_hp;
            ++next.player_hits;
            next.hurt_cooldown = config->hurt_cooldown_frames;
        }
    }
    *state = next;
    return HM_COMBAT_OK;
}
