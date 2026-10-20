#include "heman_dash.h"
#include <math.h>

hm_session_result hm_dash_session_step(
    const hm_world *world, const hm_combat_config *combat,
    hm_session *session, uint8_t *paused, hm_dash_state *dash,
    hm_input movement, uint8_t attack_pressed,
    uint8_t toggle_pause, uint8_t start_dash, float dt) {
    hm_dash_state next;
    hm_world adjusted;
    hm_session_result result;
    uint32_t before_frame,before_respawn;
    uint8_t candidate;
    if (!world || !combat || !session || !paused || !dash ||
        *paused > 1u || start_dash > 1u || toggle_pause > 1u ||
        attack_pressed > 1u ||
        dash->remaining > HM_DASH_DURATION_FRAMES ||
        dash->recovery > HM_DASH_RECOVERY_FRAMES)
        return HM_SESSION_INVALID;
    if (!isfinite(movement.axis) || movement.axis < -1.0f ||
        movement.axis > 1.0f || movement.jump > 1u ||
        movement.reset > 1u || !isfinite(dt) ||
        !(dt > 0.0f && dt <= 1.0f / 30.0f))
        return HM_SESSION_PHYSICS_ERROR;

    /* The existing pause adapter owns all pause semantics. In particular
       simultaneous Minus+ZR must only toggle pause, never begin dashing. */
    if (toggle_pause || *paused)
        return hm_paused_session_step(world,combat,session,paused,movement,
                                      attack_pressed,toggle_pause,dt);

    next=*dash;
    candidate=(uint8_t)(start_dash && !movement.reset &&
              movement.axis != 0.0f && session->player.grounded &&
              session->combat.player_hp > 0u &&
              !session->player.completed && next.recovery == 0u &&
              next.remaining == 0u);
    if (candidate) {
        next.remaining=HM_DASH_DURATION_FRAMES;
        next.recovery=HM_DASH_RECOVERY_FRAMES;
    }
    if (movement.reset || session->combat.player_hp == 0u ||
        session->player.completed)
        next.remaining=0u;

    adjusted=*world;
    if (next.remaining && movement.axis != 0.0f) {
        if (!isfinite(world->speed) || world->speed <= 0.0f ||
            world->speed > 240.0f) return HM_SESSION_PHYSICS_ERROR;
        adjusted.speed=world->speed*2.0f;
    }
    before_frame=session->player.frame;
    before_respawn=session->player.respawns;
    result=hm_paused_session_step(&adjusted,combat,session,paused,movement,
                                  attack_pressed,0u,dt);
    if (result != HM_SESSION_OK) return result;
    /* No timer movement on an adapter OK that didn't step a game frame. */
    if (session->player.frame == before_frame) return HM_SESSION_OK;
    if (next.remaining) --next.remaining;
    if (next.recovery && !candidate) --next.recovery;
    if (session->player.respawns != before_respawn ||
        session->combat.player_hp == 0u)
        next.remaining=0u;
    *dash=next;
    return HM_SESSION_OK;
}
