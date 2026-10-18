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
    *session = next;
    return HM_SESSION_OK;
}
