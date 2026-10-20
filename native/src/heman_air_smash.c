#include "heman_air_smash.h"

#include <math.h>
#include <stdint.h>

/* A new C99 attack adapter, deliberately isolated from default gameplay.
   Operates only on local copies until every actual gameplay step succeeds.
   No input modifies the map, original game assets, guest RAM or collision. */
hm_session_result hm_air_smash_step(
    const hm_world *world, const hm_combat_config *combat,
    hm_session *session, uint8_t *paused, hm_dash_state *dash,
    hm_air_smash_state *ability, uint8_t stage, hm_input movement,
    uint8_t attack_pressed, uint8_t toggle_pause, uint8_t start_dash,
    uint8_t start_smash, float dt) {
    hm_session candidate;
    hm_dash_state dash_candidate;
    hm_air_smash_state next;
    hm_session_result result;
    uint8_t pause_candidate, was_airborne, was_completed, activate;
    uint32_t before_frame, before_respawn;

    if (!world || !combat || !session || !paused || !dash || !ability ||
        stage > 1u || *paused > 1u || ability->armed > 1u ||
        ability->cooldown > HM_SMASH_COOLDOWN_FRAMES ||
        ability->impact_frames > HM_SMASH_FEEDBACK_FRAMES ||
        ability->enemy_hits > ability->impacts ||
        start_smash > 1u || attack_pressed > 1u ||
        toggle_pause > 1u || start_dash > 1u)
        return HM_SESSION_INVALID;
    if (!isfinite(movement.axis) || movement.axis < -1.0f ||
        movement.axis > 1.0f || movement.jump > 1u ||
        movement.reset > 1u || !isfinite(dt) ||
        !(dt > 0.0f && dt <= 1.0f / 30.0f))
        return HM_SESSION_PHYSICS_ERROR;

    candidate = *session;
    dash_candidate = *dash;
    pause_candidate = *paused;
    next = *ability;
    before_frame = session->player.frame;
    before_respawn = session->player.respawns;
    was_completed = session->player.completed;
    was_airborne = (uint8_t)!session->player.grounded;

    /* Minus always owns the frame. No strike, cooldown or combat changes
       while paused or toggling. The native pause/finale code still runs. */
    activate = (uint8_t)(stage == 1u && start_smash &&
               !*paused && !toggle_pause && !movement.reset &&
               !was_completed && was_airborne && !ability->armed &&
               ability->cooldown == 0u && session->combat.player_hp > 0u);
    if (activate) {
        next.armed = 1u;
        next.cooldown = HM_SMASH_COOLDOWN_FRAMES;
    }
    if (stage == 1u && next.armed &&
        !*paused && !toggle_pause && !was_completed &&
        !movement.reset && candidate.player.vy < HM_SMASH_DROP_SPEED)
        candidate.player.vy = HM_SMASH_DROP_SPEED;

    result = hm_finale_session_step(
        world, combat, &candidate, &pause_candidate, &dash_candidate,
        stage, movement, attack_pressed, toggle_pause, start_dash, dt);
    if (result != HM_SESSION_OK) return result;

    /* The room-2 terminal B restart allocates a fresh native session.
       The ability is reset in the same accepted transaction. */
    if (stage == 1u && was_completed && movement.reset &&
        !*paused && !toggle_pause) {
        next = (hm_air_smash_state){0};
    } else if (candidate.player.frame != before_frame) {
        if (candidate.player.respawns != before_respawn ||
            candidate.combat.player_hp == 0u || candidate.player.completed) {
            next.armed = 0u;
            next.impact_frames = 0u;
            next.cooldown = 0u;
        } else {
            if (!activate && next.cooldown) --next.cooldown;
            if (next.impact_frames) --next.impact_frames;
            if (next.armed && candidate.player.grounded &&
                (was_airborne || activate)) {
                /* Native swept physics supplied this landing, not a fake
                   overlap computed in the drawing layer. */
                if (next.impacts == UINT32_MAX) return HM_SESSION_INVALID;
                ++next.impacts;
                next.armed = 0u;
                next.impact_frames = HM_SMASH_FEEDBACK_FRAMES;
                if (candidate.combat.enemy_hp &&
                    fabsf(candidate.player.x -
                          candidate.combat.enemy_x) <= HM_SMASH_HIT_DISTANCE &&
                    fabsf(candidate.player.feet_y -
                          combat->enemy_feet_y) <= 28.0f) {
                    if (next.enemy_hits == UINT32_MAX)
                        return HM_SESSION_INVALID;
                    --candidate.combat.enemy_hp;
                    ++next.enemy_hits;
                }
            }
        }
    }
    *session = candidate;
    *paused = pause_candidate;
    *dash = dash_candidate;
    *ability = next;
    return HM_SESSION_OK;
}
