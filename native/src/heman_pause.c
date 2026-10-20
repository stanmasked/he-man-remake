#include "heman_pause.h"
#include <math.h>

hm_session_result hm_paused_session_step(
    const hm_world *world, const hm_combat_config *combat_cfg,
    hm_session *session, uint8_t *paused, hm_input movement,
    uint8_t attack_pressed, uint8_t toggle_pause, float dt) {
    if (!world || !combat_cfg || !session || !paused ||
        *paused > 1u || attack_pressed > 1u || toggle_pause > 1u)
        return HM_SESSION_INVALID;
    /* Validate all controller inputs BEFORE a pause can hide a bad command.
       The session is untouched on any invalid input, even when frozen. */
    if (!(movement.axis >= -1.0f && movement.axis <= 1.0f) ||
        movement.jump > 1u || movement.reset > 1u ||
        !isfinite(dt) || !(dt > 0.0f && dt <= 1.0f/30.0f))
        return HM_SESSION_PHYSICS_ERROR;
    if (toggle_pause) {
        *paused = (uint8_t)(1u - *paused);
        return HM_SESSION_OK;
    }
    if (*paused)
        return HM_SESSION_OK;
    /* The original native C99 session handles all gameplay and rollback. */
    return hm_session_step(world, combat_cfg, session, movement,
                           attack_pressed, dt);
}
