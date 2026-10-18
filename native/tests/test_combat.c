#include "heman_combat.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <string.h>

static hm_combat_config config(void) {
    hm_combat_config c;
    memset(&c, 0, sizeof(c));
    c.patrol_left = 100.0f;
    c.patrol_right = 140.0f;
    c.enemy_start_x = 120.0f;
    c.enemy_feet_y = 224.0f;
    c.enemy_speed = 60.0f;
    c.sword_reach = 24.0f;
    c.contact_range = 8.0f;
    c.enemy_initial_hp = 2u;
    c.player_initial_hp = 3u;
    c.sword_cooldown_frames = 12u;
    c.hurt_cooldown_frames = 30u;
    return c;
}

int main(void) {
    hm_combat_config cfg = config();
    hm_combat_state state, saved;
    hm_state player;
    unsigned i;
    memset(&player, 0, sizeof(player));
    player.x = 102.0f;
    player.feet_y = 224.0f;

    assert(hm_combat_init(&cfg, &state) == HM_COMBAT_OK);
    assert(state.enemy_hp == 2u && state.player_hp == 3u);
    assert(hm_combat_step(&cfg, &state, &player, 1u, 1u, 1.0f/60.0f)
           == HM_COMBAT_OK);
    assert(state.enemy_hp == 1u && state.sword_hits == 1u);
    assert(state.frame == 1u);

    /* Cooldown prevents extra hits despite repeated button presses. */
    for (i = 0; i < 11u; ++i)
        assert(hm_combat_step(&cfg, &state, &player, 1u, 1u, 1.0f/60.0f)
               == HM_COMBAT_OK);
    assert(state.enemy_hp == 1u && state.sword_hits == 1u);
    /* Move into range again and deliver second hit once cooldown expires. */
    player.x = state.enemy_x - 10.0f;
    assert(hm_combat_step(&cfg, &state, &player, 1u, 1u, 1.0f/60.0f)
           == HM_COMBAT_OK);
    assert(state.enemy_hp == 0u && state.sword_hits == 2u);
    assert(state.player_hp > 0u);

    /* Dead enemies neither patrol nor damage the player. */
    saved = state;
    player.x = state.enemy_x;
    for (i = 0; i < 90u; ++i)
        assert(hm_combat_step(&cfg, &state, &player, 0u, 1u, 1.0f/60.0f)
               == HM_COMBAT_OK);
    assert(state.enemy_x == saved.enemy_x);
    assert(state.player_hp == saved.player_hp);
    assert(state.enemy_hp == 0u);

    /* A backward attack misses; contact is subject to invulnerability. */
    assert(hm_combat_init(&cfg, &state) == HM_COMBAT_OK);
    player.x = 118.0f;
    assert(hm_combat_step(&cfg, &state, &player, 1u, 0u, 1.0f/60.0f)
           == HM_COMBAT_OK);
    assert(state.enemy_hp == 2u);
    assert(state.player_hp == 2u && state.player_hits == 1u);
    for (i = 0; i < 8u; ++i)
        assert(hm_combat_step(&cfg, &state, &player, 0u, 0u, 1.0f/60.0f)
               == HM_COMBAT_OK);
    assert(state.player_hits == 1u);
    for (i = 0; i < 90u; ++i) {
        assert(hm_combat_step(&cfg, &state, &player, 0u, 0u, 1.0f/60.0f)
               == HM_COMBAT_OK);
        assert(state.enemy_x >= cfg.patrol_left);
        assert(state.enemy_x <= cfg.patrol_right);
    }
    assert(state.player_hits >= 2u);

    /* All invalid inputs leave state byte-for-byte unchanged. */
    saved = state;
    assert(hm_combat_step(&cfg, &state, &player, 2u, 1u, 1.0f/60.0f)
           == HM_COMBAT_INVALID);
    assert(memcmp(&state, &saved, sizeof(state)) == 0);
    assert(hm_combat_step(&cfg, &state, &player, 0u, 1u, NAN)
           == HM_COMBAT_INVALID);
    assert(memcmp(&state, &saved, sizeof(state)) == 0);
    cfg.enemy_speed = NAN;
    assert(hm_combat_step(&cfg, &state, &player, 0u, 1u, 1.0f/60.0f)
           == HM_COMBAT_INVALID);
    assert(memcmp(&state, &saved, sizeof(state)) == 0);
    assert(hm_combat_init(&cfg, &state) == HM_COMBAT_INVALID);
    assert(memcmp(&state, &saved, sizeof(state)) == 0);
    puts("Synthetic C99 melee combat tests passed");
    return 0;
}
