#include "heman_session.h"
#include <string.h>

hm_session_result hm_session_init(const hm_world *world,
                                  const hm_combat_config *combat_cfg,
                                  hm_session *session) {
    hm_session fresh;
    if (!world || !combat_cfg || !session) return HM_SESSION_INVALID;
    memset(&fresh, 0, sizeof(fresh));
    if (hm_init(world, &fresh.player) != HM_OK)
        return HM_SESSION_PHYSICS_ERROR;
    if (hm_combat_init(combat_cfg, &fresh.combat) != HM_COMBAT_OK)
        return HM_SESSION_COMBAT_ERROR;
    fresh.facing_right = 1u;
    *session = fresh;
    return HM_SESSION_OK;
}

hm_session_result hm_session_step(const hm_world *world,
                                  const hm_combat_config *combat_cfg,
                                  hm_session *session,
                                  hm_input movement,
                                  uint8_t attack_pressed,
                                  float dt) {
    hm_session next;
    hm_result physics_result;
    hm_combat_result combat_result;
    if (!session || !world || !combat_cfg || attack_pressed > 1u ||
        session->facing_right > 1u) return HM_SESSION_INVALID;
    /* Check the caller's axis before replacing movement during defeat
       recovery. Otherwise a NaN/out-of-range command would be hidden. */
    if (!(movement.axis >= -1.0f && movement.axis <= 1.0f))
        return HM_SESSION_PHYSICS_ERROR;
    next = *session;
    /* The test combat module considers zero HP a defeat. Restore the
       encounter on the NEXT simulation frame, using the ordinary native
       player respawn path so checkpoint/camera rules stay consistent.
       Suppress directional input and attacks on that recovery frame. */
    if (session->combat.player_hp == 0u) {
        movement.axis = 0.0f;
        movement.jump = 0u;
        movement.reset = 1u;
        attack_pressed = 0u;
    }
    if (movement.axis < 0.0f) next.facing_right = 0u;
    if (movement.axis > 0.0f) next.facing_right = 1u;
    physics_result = hm_step(world, &next.player, movement, dt);
    if (physics_result != HM_OK) return HM_SESSION_PHYSICS_ERROR;
    /* An automatic world respawn (e.g. a hazard or falling outside the
       synthetic map) must restore combat along with the player. Checking
       the counter instead of inspecting events keeps both subsystems
       synchronized without guessing the original game's hazard rules. */
    if (movement.reset || next.player.respawns != session->player.respawns) {
        combat_result = hm_combat_init(combat_cfg, &next.combat);
    } else {
        combat_result = hm_combat_step(combat_cfg, &next.combat, &next.player,
                                       attack_pressed, next.facing_right, dt);
    }
    if (combat_result != HM_COMBAT_OK) return HM_SESSION_COMBAT_ERROR;

    /* Independently authored synthetic pickup rule: each newly collected
       world pickup restores one combat HP, up to initial maximum. The
       engine sets the pickup bit once; old bits can never heal again.
       Apply only after both substeps succeeded, on the temporary copy,
       so a rejected frame cannot consume a pickup. */
    if (!movement.reset && next.player.respawns == session->player.respawns) {
        uint32_t newly_picked = next.player.picked & ~session->player.picked;
        while (newly_picked && next.combat.player_hp <
                               combat_cfg->player_initial_hp) {
            next.combat.player_hp++;
            newly_picked &= newly_picked - 1u;
        }
    }

    *session = next;
    return HM_SESSION_OK;
}
