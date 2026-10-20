#include "heman_finale.h"
#include <math.h>

hm_session_result hm_finale_session_step(
    const hm_world *world, const hm_combat_config *combat,
    hm_session *session, uint8_t *paused, hm_dash_state *dash,
    uint8_t stage, hm_input movement, uint8_t attack_pressed,
    uint8_t toggle_pause, uint8_t start_dash, float dt) {
    if (!world || !combat || !session || !paused || !dash ||
        stage > 1u || *paused > 1u ||
        attack_pressed > 1u || toggle_pause > 1u || start_dash > 1u ||
        dash->remaining > HM_DASH_DURATION_FRAMES ||
        dash->recovery > HM_DASH_RECOVERY_FRAMES)
        return HM_SESSION_INVALID;

    /* Validate commands even on paused or finished frames. Otherwise a
       malformed command could escape detection behind a freeze. */
    if (!isfinite(movement.axis) || movement.axis < -1.0f ||
        movement.axis > 1.0f || movement.jump > 1u ||
        movement.reset > 1u || !isfinite(dt) ||
        !(dt > 0.0f && dt <= 1.0f/30.0f))
        return HM_SESSION_PHYSICS_ERROR;

    if (stage == 0u)
        return hm_paused_session_step(world, combat, session, paused,
                                      movement, attack_pressed,
                                      toggle_pause, dt);

    /* The ordinary second-room dash path remains source-identical until
       the *actual* native exit event sets completed. A deliberate B reset
       also returns to the ordinary adapter, including while paused. */
    if (!session->player.completed ||
        (!toggle_pause && movement.reset && !*paused))
        return hm_dash_session_step(world, combat, session, paused, dash,
                                    movement, attack_pressed, toggle_pause,
                                    start_dash, dt);

    /* At FINAL CLEAR, Minus toggles pause but does not consume a game frame.
       While paused, B cannot restart; resuming takes one button-edge frame. */
    if (toggle_pause)
        return hm_paused_session_step(world, combat, session, paused,
                                      movement, attack_pressed, 1u, dt);

    /* All other actions are ignored at final completion. This intentionally
       freezes combat, cooldowns, camera, dash counters and frame number. */
    return HM_SESSION_OK;
}
